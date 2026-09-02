"""Transport-agnostic plugin dispatch.

The same plugin operations (manifest, node execute/config, integration
config/ready, trigger poll, config validation) are exposed over two
transports:

- a line-delimited JSON-RPC loop over stdio, via
  :mod:`noxus_sdk.plugins.worker` — the warm dispatcher the platform hosts
  inside a per-plugin sandbox. This is how plugins actually run.
- HTTP, via :func:`noxus_sdk.plugins.serve.generate_fastapi_app` — the local
  authoring aid behind ``noxus plugin serve``. Nothing on the platform calls
  it.

Keeping the logic here means both transports stay byte-for-byte consistent
and there is exactly one place that knows how to turn a request into a node
call. The transports are thin: they only (de)serialize and route.
"""

from __future__ import annotations

import inspect
from datetime import datetime
from types import UnionType
from typing import TYPE_CHECKING, Union, get_args, get_origin

from loguru import logger
from pydantic import ValidationError

from noxus_sdk.integrations.schemas import DeviceAuthPoll, DeviceAuthStart
from noxus_sdk.nodes.connector import DataType
from noxus_sdk.nodes.schemas import ConfigResponse, ExecutionResponse
from noxus_sdk.schemas import ValidationResult

if TYPE_CHECKING:
    from noxus_sdk.plugins import BasePlugin
    from noxus_sdk.plugins.context import RemoteExecutionContext
    from noxus_sdk.plugins.manifest import PluginManifest


class ComponentNotFoundError(LookupError):
    """A node or integration name was not provided by the plugin.

    Carries a human-readable message that lists the available names so both
    the HTTP transport (404 body) and the JSON-RPC transport (error message)
    surface the same diagnostic.
    """


class PluginDispatcher:
    """Loads a plugin once and runs its operations.

    Instantiated a single time per served plugin (the plugin module graph is
    imported once, here), then reused across every request — this is what
    makes the sandbox worker "warm".
    """

    def __init__(self, plugin_class: type[BasePlugin], plugin_name: str) -> None:
        self.plugin_class = plugin_class
        self.plugin_name = plugin_name
        self.plugin_instance = plugin_class()
        self.available_nodes = self.plugin_instance.nodes()
        self.available_integrations = self.plugin_instance.integrations()
        self.available_triggers = self.plugin_instance.triggers()
        self.available_datasources = self.plugin_instance.datasources()
        self.node_map = {node.node_name: node for node in self.available_nodes}
        self.integration_map = {
            integration.type: integration for integration in self.available_integrations
        }
        self.trigger_map = {
            trigger.trigger_name: trigger for trigger in self.available_triggers
        }
        self.datasource_map = {
            datasource.datasource_name: datasource
            for datasource in self.available_datasources
        }

    # -- nodes ---------------------------------------------------------------

    def _node(self, node_name: str):  # noqa: ANN202 - returns a BaseNode subclass
        node_class = self.node_map.get(node_name)
        if node_class is None:
            raise ComponentNotFoundError(
                f"Node '{node_name}' not found. "
                f"Available nodes: {list(self.node_map.keys())}"
            )
        return node_class

    def list_nodes(self) -> dict:
        """List available nodes (name / class_name / description)."""
        return {
            "plugin": self.plugin_name,
            "nodes": [
                {
                    "name": node.node_name,
                    "class_name": node.__name__,
                    "description": node.description,
                }
                for node in self.available_nodes
            ],
        }

    async def execute_node(
        self,
        node_name: str,
        ctx: RemoteExecutionContext,
        inputs: dict,
        config: dict,
    ) -> ExecutionResponse:
        """Instantiate and run a node, coercing ``File`` inputs to models."""
        logger.info(f"[plugin] node.execute '{node_name}'")
        node_class = self._node(node_name)
        logger.debug(f"Creating node instance for {node_class.__name__}")

        config_class = node_class.get_config_class()
        node_config = config_class(**_coerce_config_values(config_class, config))
        node_instance = node_class(node_config)

        typed_inputs = _coerce_inputs(node_instance, inputs)

        logger.debug(f"Executing node {node_name}")
        if inspect.iscoroutinefunction(node_instance.call):
            outputs = await node_instance.call(ctx, **typed_inputs)
        else:
            outputs = node_instance.call(ctx, **typed_inputs)

        logger.debug(f"Node {node_name} executed successfully")
        return ExecutionResponse(
            success=True,
            outputs=outputs if isinstance(outputs, dict) else {"output": outputs},
        )

    async def node_config(
        self,
        node_name: str,
        ctx: RemoteExecutionContext,
        config: ConfigResponse,
        *,
        skip_cache: bool = False,
    ) -> ConfigResponse:
        """Resolve a node's dynamic configuration."""
        node_class = self._node(node_name)
        return await node_class.get_config(ctx, config, skip_cache=skip_cache)

    # -- integrations --------------------------------------------------------

    def _integration(self, integration_name: str):  # noqa: ANN202 - BaseIntegration subclass
        integration_class = self.integration_map.get(integration_name)
        if integration_class is None:
            raise ComponentNotFoundError(
                f"Integration '{integration_name}' not found. "
                f"Available integrations: {list(self.integration_map.keys())}"
            )
        return integration_class

    async def integration_config(self, integration_name: str) -> dict:
        """Return an integration's configuration schema."""
        return self._integration(integration_name).get_config()

    async def integration_ready(
        self, integration_name: str, creds: dict | None
    ) -> bool:
        """Check whether an integration is ready for the given credentials."""
        return await self._integration(integration_name).is_ready(creds)

    async def integration_device_auth_start(
        self, integration_name: str, ctx: RemoteExecutionContext
    ) -> DeviceAuthStart:
        integration = self._integration(integration_name)
        if not integration.supports_device_auth:
            raise ComponentNotFoundError(
                f"Integration '{integration_name}' does not support device auth"
            )
        return await integration.device_auth_start(ctx)

    async def integration_device_auth_poll(
        self, integration_name: str, ctx: RemoteExecutionContext, session_id: str
    ) -> DeviceAuthPoll:
        integration = self._integration(integration_name)
        if not integration.supports_device_auth:
            raise ComponentNotFoundError(
                f"Integration '{integration_name}' does not support device auth"
            )
        return await integration.device_auth_poll(ctx, session_id)

    # -- triggers --------------------------------------------------------------

    async def trigger_poll(
        self,
        trigger_name: str,
        ctx: RemoteExecutionContext,
        config: dict,
        state: dict,
    ) -> tuple[list[dict], dict]:
        """Run one poll of a plugin trigger: (events, new_state)."""
        logger.info(f"[plugin] trigger.poll '{trigger_name}'")
        trigger_class = self.trigger_map.get(trigger_name)
        if trigger_class is None:
            raise ComponentNotFoundError(
                f"Trigger '{trigger_name}' not found. "
                f"Available triggers: {list(self.trigger_map.keys())}"
            )
        trigger = trigger_class(trigger_class.get_config_class()(**config))
        return await trigger.poll(ctx, state)

    # -- datasources -----------------------------------------------------------

    async def datasource_fetch(
        self,
        datasource_name: str,
        ctx: RemoteExecutionContext,
        config: dict,
    ) -> list[dict]:
        """One-shot ingestion: return the files the datasource produces as JSON
        descriptors (their bytes are uploaded over the host callback)."""
        logger.info(f"[plugin] datasource.fetch '{datasource_name}'")
        datasource_class = self.datasource_map.get(datasource_name)
        if datasource_class is None:
            raise ComponentNotFoundError(
                f"Datasource '{datasource_name}' not found. "
                f"Available datasources: {list(self.datasource_map.keys())}"
            )
        datasource = datasource_class(datasource_class.get_config_class()(**config))
        files = await datasource.fetch(ctx)
        # `fetch` is typed `list[File]`, but the common idiom returns the result
        # of `helper.upload_file(...)` directly — which is a plain descriptor
        # dict, not a File model (same shape the File node emits). Accept both so
        # a datasource written the natural way doesn't crash on `.model_dump`.
        return [f if isinstance(f, dict) else f.model_dump(mode="json") for f in files]

    # -- plugin metadata -----------------------------------------------------

    def manifest(self) -> PluginManifest:
        """Return the plugin manifest."""
        return self.plugin_class.get_manifest()

    def validate_config(self, config: dict) -> ValidationResult:
        """Validate plugin-level configuration.

        Never raises: plugin-authored validation code is untrusted, so any
        failure is reported as an invalid result rather than propagated.
        """
        plugin_config_class = self.plugin_instance.get_config_class()
        try:
            plugin_config = plugin_config_class(**config)
            return plugin_config.validate_config()
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            return ValidationResult(valid=False, errors=[f"Validation error: {e!s}"])
        except Exception as e:  # noqa: BLE001 - untrusted plugin validation code; report, don't crash
            logger.error(f"Unexpected error during configuration validation: {e}")
            return ValidationResult(valid=False, errors=[f"Unexpected error: {e!s}"])


def _is_list_annotation(ann) -> bool:  # noqa: ANN001 - typing annotation object
    if ann is list or get_origin(ann) is list:
        return True
    if get_origin(ann) in (Union, UnionType):
        return any(_is_list_annotation(a) for a in get_args(ann))
    return False


def _coerce_config_values(config_class, config: dict) -> dict:  # noqa: ANN001
    """Split comma-separated text into list-typed config fields.

    The generic host editor renders every scalar setting row as a text input,
    so a list-typed setting (APT packages) arrives as ``"jq, ripgrep"``; split
    it rather than failing pydantic validation on the whole execution.
    """
    coerced = dict(config)
    for name, field in config_class.model_fields.items():
        val = coerced.get(name)
        if isinstance(val, str) and _is_list_annotation(field.annotation):
            coerced[name] = [p for p in (s.strip() for s in val.split(",")) if p]
    return coerced


def _coerce_inputs(node_instance, inputs: dict) -> dict:  # noqa: ANN001 - BaseNode instance
    """Rebuild rich connector inputs from their JSON wire form.

    Inputs cross the transport as plain JSON, so a ``File`` arrives as a dict
    and a ``datetime`` as an ISO string. Connectors declaring those types get
    the real object back, so node authors work with models rather than raw
    payloads. Lists are coerced element-wise. Everything else passes through,
    including inputs with no matching connector.
    """
    from noxus_sdk.files import File

    def _to_datetime(v):  # noqa: ANN001, ANN202 - JSON value in, datetime out
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                # Not a parseable timestamp — hand it over untouched rather
                # than failing the whole execution on one bad field.
                return v
        return v

    def _to_file(v):  # noqa: ANN001, ANN202
        return File(**v) if isinstance(v, dict) else v

    coercers = {
        DataType.File: _to_file,
        DataType.datetime: _to_datetime,
    }

    typed_inputs: dict = {}
    for connector in getattr(node_instance, "inputs", []):  # noqa: lint-ignore - external SDK, not under backend lint
        conn_name = getattr(connector, "name", None)
        if not conn_name or conn_name not in inputs:
            continue

        val = inputs[conn_name]
        conn_def = getattr(connector, "definition", None)
        data_type = getattr(conn_def, "data_type", None) if conn_def else None
        data_type_str = str(data_type).split(".")[-1] if data_type else ""

        coerce = next(
            (
                fn
                for dt, fn in coercers.items()
                if data_type == dt or data_type_str == dt.value
            ),
            None,
        )
        if coerce is None:
            typed_inputs[conn_name] = val
        elif isinstance(val, list):
            typed_inputs[conn_name] = [coerce(v) for v in val]
        else:
            typed_inputs[conn_name] = coerce(val)

    for key, value in inputs.items():
        if key not in typed_inputs:
            typed_inputs[key] = value

    return typed_inputs
