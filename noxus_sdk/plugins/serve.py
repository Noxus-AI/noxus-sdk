from __future__ import annotations
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
    RemoteExecutionContext,  # noqa: TCH001 - For some reason ruff is not detecting the type hinting on responses, this cant be in the type check block
)
from noxus_sdk.plugins.dispatch import ComponentNotFoundError, PluginDispatcher
from noxus_sdk.plugins.exceptions import PluginValidationError
from noxus_sdk.plugins.manifest import (
    PluginManifest,  # noqa: TCH001 - For some reason ruff is not detecting the type hinting on responses, this cant be in the type check block
)
from noxus_sdk.plugins.validate import discover_and_load_plugin
from noxus_sdk.schemas import ValidationResult

if TYPE_CHECKING:
    from pathlib import Path

    from noxus_sdk.plugins import BasePlugin
    from noxus_sdk.files import File, SourceType, SourceMetadata


class UnavailableFileHelper(FileHelper):
    """File operations aren't available under ``noxus plugin serve``.

    Serving a plugin over HTTP is a local authoring aid. Platform file access
    used to be proxied by the plugin-server, which no longer exists — on the
    platform, plugins run as sandboxed workers and their file callbacks are
    serviced over the worker channel (see ``noxus_sdk.plugins.worker``).
    """

    _MESSAGE = (
        "File operations are not available when serving a plugin locally. "
        "Nodes that read or write platform files must be run by the platform, "
        "which hosts the plugin as a sandboxed worker."
    )

    async def get_content(self, file: File) -> bytes:
        raise RuntimeError(self._MESSAGE)

    async def upload_file(
        self,
        file_name: str,
        content: bytes,
        content_type: str = "text/plain",
        source_type: SourceType | str = "Document",
        source_metadata: SourceMetadata | dict | None = None,
        group_id: str | None = None,
    ) -> dict:
        raise RuntimeError(self._MESSAGE)


# Exception handler configuration: (status_code, error_message, detail_extractor)
EXCEPTION_HANDLERS: dict[
    type[Exception], tuple[int, str, Callable[[Exception], str | list]]
] = {
    ValueError: (400, "Bad Request", str),
    ValidationError: (
        422,
        "Validation Error",
        lambda e: cast(ValidationError, e).errors(),
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

    # Load the plugin once; all handlers below delegate to this dispatcher so
    # the HTTP and stdio (sandbox worker) transports share identical logic.
    dispatcher = PluginDispatcher(plugin_class, plugin_name)

    logger.debug(
        f"Loaded nodes from plugin class: {plugin_class.__name__}. Available nodes: {dispatcher.available_nodes}",
    )
    logger.debug(
        f"Loaded integrations from plugin class: {plugin_class.__name__}. Available integrations: {dispatcher.available_integrations}",
    )

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
        """Health check endpoint for the locally served plugin"""
        return {
            "status": "healthy",
            "plugin": plugin_name,
            "service": "noxus-plugin",
        }

    # =============================================================================
    # PLUGIN ENDPOINTS
    # =============================================================================

    @app.post("/validate-config")
    async def validate_config(config: dict) -> ValidationResult:
        """Validate plugin configuration"""
        logger.debug("Validating plugin configuration")
        result = dispatcher.validate_config(config)
        logger.debug(f"Configuration validation result: {result.valid}")
        return result

    @app.get("/manifest")
    def get_manifest() -> PluginManifest:
        """Get plugin manifest"""
        logger.debug("Getting plugin manifest")
        return dispatcher.manifest()

    # =============================================================================
    # NODE ENDPOINTS
    # =============================================================================

    @app.get("/nodes")
    def list_nodes() -> dict:
        """List available nodes in this plugin"""
        logger.debug("Listing available nodes")
        return dispatcher.list_nodes()

    @app.post("/nodes/{node_name}/execute")
    async def execute_node(
        node_name: str,
        ctx: RemoteExecutionContext,
        inputs: dict,
        config: dict,
    ) -> ExecutionResponse:
        """Execute a specific node from the plugin with provided input data and context"""
        logger.debug(f"Preparing to execute node: {node_name}")

        ctx.set_file_helper(UnavailableFileHelper())

        try:
            return await dispatcher.execute_node(node_name, ctx, inputs, config)
        except ComponentNotFoundError as e:
            logger.error(str(e))
            raise HTTPException(status_code=404, detail=str(e)) from e

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
        try:
            result = await dispatcher.node_config(
                node_name, ctx, config, skip_cache=skip_cache
            )
        except ComponentNotFoundError as e:
            logger.error(str(e))
            raise HTTPException(status_code=404, detail=str(e)) from e
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
        try:
            result = await dispatcher.integration_config(integration_name)
        except ComponentNotFoundError as e:
            logger.error(str(e))
            raise HTTPException(status_code=404, detail=str(e)) from e
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
        try:
            result = await dispatcher.integration_ready(integration_name, creds)
        except ComponentNotFoundError as e:
            logger.error(str(e))
            raise HTTPException(status_code=404, detail=str(e)) from e
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
        # Historically the plugin-server's UVProcessEngine parsed this line to
        # discover the port of a plugin it had spawned. That service is gone and
        # nothing in the codebase parses it any more; it survives only as a hint
        # for local tooling that wants the bound port (e.g. when port=0).
        print(f"PLUGIN_PORT:{actual_port}", flush=True)  # noqa: T201 - deliberate stdout contract for local tooling

    config = Config(
        fastapi_app,
        log_level="info",
        host=host,
        use_colors=True,
    )
    server = Server(config)
    server.run(sockets=[server_socket])

    return fastapi_app
