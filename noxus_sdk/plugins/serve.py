from __future__ import annotations

import inspect
import os
import socket
from typing import TYPE_CHECKING, Callable, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import ValidationError
from uvicorn import Config, Server

from noxus_sdk.nodes.schemas import ConfigResponse, ExecutionResponse
from noxus_sdk.plugins.context import (
    FileHelper,
    RemoteExecutionContext,
)
from noxus_sdk.plugins.exceptions import PluginValidationError
from noxus_sdk.plugins.manifest import (
    PluginManifest,
)
from noxus_sdk.plugins.validate import discover_and_load_plugin
from noxus_sdk.schemas import ValidationResult

if TYPE_CHECKING:
    from pathlib import Path

    from noxus_sdk.files import File, SourceMetadata, SourceType
    from noxus_sdk.plugins import BasePlugin


class PluginFileHelper(FileHelper):
    def __init__(self, plugin_server_url: str):
        self.plugin_server_url = plugin_server_url.rstrip("/")

    async def get_content(self, file: File) -> bytes:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.plugin_server_url}/files/{file.id}",
                timeout=60.0,
            )
            response.raise_for_status()
            return response.content

    async def upload_file(
        self,
        file_name: str,
        content: bytes,
        content_type: str = "text/plain",
        source_type: SourceType | str = "Document",
        source_metadata: SourceMetadata | dict | None = None,
        group_id: str | None = None,
    ) -> dict:
        import base64

        import httpx

        async with httpx.AsyncClient() as client:
            # Ensure source_type is a string value, not the Enum member representation
            source_type_val = source_type
            if hasattr(source_type, "value"):
                source_type_val = source_type.value
            elif not isinstance(source_type, str):
                source_type_val = str(source_type)

            logger.info(f"Uploading file {file_name} for group {group_id or 'unknown'}")
            payload = {
                "filename": file_name,
                "content_type": content_type,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "group_id": group_id or "00000000-0000-0000-0000-000000000000",
                "source_type": source_type_val,
                "source_metadata": source_metadata,
            }
            response = await client.post(
                f"{self.plugin_server_url}/files/upload",
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()


# Exception handler configuration: (status_code, error_message, detail_extractor)
EXCEPTION_HANDLERS: dict[
    type[Exception],
    tuple[int, str, Callable[[Exception], str | list]],
] = {
    ValueError: (400, "Bad Request", str),
    ValidationError: (
        422,
        "Validation Error",
        lambda e: cast("ValidationError", e).errors(),
    ),
    PluginValidationError: (400, "Plugin Validation Error", str),
    Exception: (500, "Internal Server Error", lambda _: "An unexpected error occurred"),
}


def _register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers from EXCEPTION_HANDLERS configuration"""

    def create_handler(
        exc_type: type[Exception],
        status_code: int,
        error_message: str,
        detail_extractor: Callable[[Exception], str | list],
    ):
        async def handler(_: Request, exc: Exception) -> JSONResponse:
            logger.error(f"{exc_type.__name__}: {exc}")
            detail = detail_extractor(exc)
            return JSONResponse(
                status_code=status_code,
                content={"error": error_message, "detail": detail},
            )

        return handler

    for exc_type, (
        status_code,
        error_message,
        detail_extractor,
    ) in EXCEPTION_HANDLERS.items():
        handler = create_handler(exc_type, status_code, error_message, detail_extractor)
        app.add_exception_handler(exc_type, handler)


def generate_fastapi_app(plugin_class: type[BasePlugin], plugin_name: str) -> FastAPI:
    """Generates a FastAPI app for a plugin"""

    logger.debug(f"Generating FastAPI app for plugin {plugin_name}")

    # Get components from the plugin
    plugin_instance = plugin_class()
    available_nodes = plugin_instance.nodes()
    available_integrations = plugin_instance.integrations()

    logger.debug(
        f"Loaded nodes from plugin class: {plugin_class.__name__}. Available nodes: {available_nodes}",
    )
    logger.debug(
        f"Loaded integrations from plugin class: {plugin_class.__name__}. Available integrations: {available_integrations}",
    )

    node_map = {node.node_name: node for node in available_nodes}
    integration_map = {
        integration.type: integration for integration in available_integrations
    }

    # Generate FastAPI app
    app = FastAPI(
        title=plugin_name,
        description=f"API server for {plugin_name} plugin",
    )

    # Register exception handlers
    _register_exception_handlers(app)

    # =============================================================================
    # SYSTEM ENDPOINTS
    # =============================================================================

    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint for plugin server"""
        return {
            "status": "healthy",
            "plugin": plugin_name,
            "service": "noxus-plugin-server",
        }

    # =============================================================================
    # PLUGIN ENDPOINTS
    # =============================================================================

    @app.post("/validate-config")
    async def validate_config(config: dict) -> ValidationResult:
        """Validate plugin configuration"""
        logger.debug("Validating plugin configuration")

        plugin_config_class = plugin_instance.get_config_class()

        try:
            plugin_config = plugin_config_class(**config)
            result = plugin_config.validate_config()
            logger.debug(f"Configuration validation result: {result.valid}")
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            return ValidationResult(valid=False, errors=[f"Validation error: {e!s}"])
        except Exception as e:  # noqa: BLE001 - If the plugin validation code fails, we want to return a validation result with the error. We dont control the code so need to catch all exceptions.
            logger.error(f"Unexpected error during configuration validation: {e}")
            return ValidationResult(valid=False, errors=[f"Unexpected error: {e!s}"])

        return result

    @app.get("/manifest")
    def get_manifest() -> PluginManifest:
        """Get plugin manifest"""
        logger.debug("Getting plugin manifest")
        return plugin_class.get_manifest()

    # =============================================================================
    # NODE ENDPOINTS
    # =============================================================================

    @app.get("/nodes")
    def list_nodes() -> dict:
        """List available nodes in this plugin"""
        logger.debug("Listing available nodes")
        return {
            "plugin": plugin_name,
            "nodes": [
                {
                    "name": node.node_name,
                    "class_name": node.__name__,
                    "description": node.description,
                }
                for node in available_nodes
            ],
        }

    @app.post("/nodes/{node_name}/execute")
    async def execute_node(
        node_name: str,
        ctx: RemoteExecutionContext,
        inputs: dict,
        config: dict,
    ) -> ExecutionResponse:
        """Execute a specific node from the plugin with provided input data and context"""
        logger.debug(f"Preparing to execute node: {node_name}")

        # Validate node exists
        if node_name not in node_map:
            available_node_names = list(node_map.keys())
            error_msg = (
                f"Node '{node_name}' not found. Available nodes: {available_node_names}"
            )
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        node_class = node_map[node_name]
        logger.debug(f"Creating node instance for {node_class.__name__}")

        # Create node config and instance
        node_config = node_class.get_config_class()(**config)
        node_instance = node_class(node_config)

        # Initialize file helper
        # We assume the plugin server is running on the same host or we can get its URL
        # For now, let's use a default or environment variable
        plugin_server_url = os.environ.get("PLUGIN_SERVER_URL", "http://localhost:8500")
        ctx.set_file_helper(PluginFileHelper(plugin_server_url))

        # Convert inputs to their proper types if they are Pydantic models (like File)
        typed_inputs = {}
        from noxus_sdk.nodes.connector import DataType

        for connector in getattr(node_instance, "inputs", []):
            conn_name = getattr(connector, "name", None)
            if not conn_name:
                continue

            if conn_name in inputs:
                val = inputs[conn_name]

                # Get data type safely
                conn_def = getattr(connector, "definition", None)
                data_type = getattr(conn_def, "data_type", None) if conn_def else None
                data_type_str = str(data_type).split(".")[-1] if data_type else ""

                if data_type_str == "File" or data_type == DataType.File:
                    from noxus_sdk.files import File

                    if isinstance(val, dict):
                        typed_inputs[conn_name] = File(**val)
                    elif isinstance(val, list):
                        typed_inputs[conn_name] = [
                            File(**v) if isinstance(v, dict) else v for v in val
                        ]
                    else:
                        typed_inputs[conn_name] = val
                else:
                    typed_inputs[conn_name] = val

        # Add any inputs that weren't in the connector list
        for key, value in inputs.items():
            if key not in typed_inputs:
                typed_inputs[key] = value

        # Execute node
        logger.debug(f"Executing node {node_name}")
        is_coroutine = inspect.iscoroutinefunction(node_instance.call)

        if is_coroutine:
            outputs = await node_instance.call(ctx, **typed_inputs)
        else:
            outputs = node_instance.call(ctx, **typed_inputs)

        logger.debug(f"Node {node_name} executed successfully")

        return ExecutionResponse(
            success=True,
            outputs=outputs if isinstance(outputs, dict) else {"output": outputs},
        )

    @app.post("/nodes/{node_name}/config")
    async def get_node_config(
        node_name: str,
        config: ConfigResponse,
        ctx: RemoteExecutionContext,
        *,
        skip_cache: bool = False,
    ) -> ConfigResponse:
        """Get node configuration"""
        logger.debug(f"Getting configuration for node: {node_name}")

        if node_name not in node_map:
            available_node_names = list(node_map.keys())
            error_msg = (
                f"Node '{node_name}' not found. Available nodes: {available_node_names}"
            )
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        node_class = node_map[node_name]
        result = await node_class.get_config(ctx, config, skip_cache=skip_cache)
        logger.debug(f"Successfully retrieved configuration for node: {node_name}")
        return result

    # =============================================================================
    # INTEGRATION ENDPOINTS
    # =============================================================================

    @app.post("/integrations/{integration_name}/config")
    async def get_integration_config(
        integration_name: str,
        ctx: RemoteExecutionContext,
    ) -> dict:
        """Get integration configuration"""
        logger.info(f"Getting configuration for integration: {integration_name}")

        if integration_name not in integration_map:
            available_integrations = list(integration_map.keys())
            error_msg = f"Integration '{integration_name}' not found. Available integrations: {available_integrations}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        integration_class = integration_map[integration_name]
        result = integration_class.get_config()
        logger.info(
            f"Successfully retrieved configuration for integration: {integration_name}",
        )
        return result

    @app.post("/integrations/{integration_name}/ready")
    async def check_integration_ready(
        integration_name: str,
        creds: dict | None,
    ) -> bool:
        """Check if integration is ready"""
        logger.info(f"Checking readiness for integration: {integration_name}")

        if integration_name not in integration_map:
            available_integrations = list(integration_map.keys())
            error_msg = f"Integration '{integration_name}' not found. Available integrations: {available_integrations}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        integration_class = integration_map[integration_name]
        result = await integration_class.is_ready(creds)
        logger.info(
            f"Successfully checked readiness for integration: {integration_name} (Ready: {result})",
        )
        return result

    return app


def serve_plugin(
    plugin_folder: Path,
    host: str = "127.0.0.1",
    port: int = 8005,
    *,
    print_port: bool = False,  # If True, prints the port to stdout for parent process
) -> FastAPI:
    """Serves a plugin by importing it from the folder and starting a FastAPI server"""

    # Discover and load the plugin class from the folder
    plugin_class, validation_result = discover_and_load_plugin(plugin_folder)

    if validation_result.errors or plugin_class is None:
        logger.error(f"Failed to load plugin from {plugin_folder}")
        for error in validation_result.errors:
            logger.error(f"  - {error}")
        raise ValueError(
            f"Could not load plugin from {plugin_folder}: {validation_result.errors}",
        )

    if validation_result.warnings:
        for warning in validation_result.warnings:
            logger.warning(f"Plugin warning: {warning}")

    logger.debug(f"Imported plugin class: {plugin_class.__name__}")

    # Get plugin name from the class or folder
    plugin_name = getattr(plugin_class, "__name__", plugin_folder.name)

    # Generate FastAPI app with the plugin class
    fastapi_app = generate_fastapi_app(plugin_class, plugin_name)

    logger.debug(f"Serving plugin '{plugin_name}' from {plugin_folder}")

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )
    server_socket.bind((host, port))
    actual_port = server_socket.getsockname()[1]

    if print_port:
        # Print port information for parent process to read
        # The Plugin server will parse stdout and find the port, this has to be in this exact format
        print(f"PLUGIN_PORT:{actual_port}", flush=True)  # noqa: T201 - required for plugin server to read the port

    config = Config(
        fastapi_app,
        log_level="info",
        host=host,
        use_colors=True,
    )
    server = Server(config)
    server.run(sockets=[server_socket])

    return fastapi_app
