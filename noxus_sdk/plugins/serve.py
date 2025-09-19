from __future__ import annotations

import inspect
import socket
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import ValidationError
from uvicorn import Config, Server

from noxus_sdk.nodes.schemas import ConfigResponse, ExecutionResponse
from noxus_sdk.plugins.context import (
    RemoteExecutionContext,  # noqa: TCH001 - For some reason ruff is not detecting the type hinting on responses, this cant be in the type check block
)
from noxus_sdk.plugins.exceptions import PluginValidationError
from noxus_sdk.plugins.manifest import (
    PluginManifest,  # noqa: TCH001 - For some reason ruff is not detecting the type hinting on responses, this cant be in the type check block
)
from noxus_sdk.plugins.validate import discover_and_load_plugin
from noxus_sdk.schemas import ValidationResult

if TYPE_CHECKING:
    from pathlib import Path

    from noxus_sdk.plugins import BasePlugin


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
    integration_map = {integration.name: integration for integration in available_integrations}

    # Generate FastAPI app
    app = FastAPI(
        title=plugin_name,
        description=f"API server for {plugin_name} plugin",
    )

    # Error handling
    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        logger.error(f"ValueError: {exc}")
        return JSONResponse(
            status_code=400,
            content={"error": "Bad Request", "detail": str(exc)},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        _: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        logger.error(f"ValidationError: {exc}")
        return JSONResponse(
            status_code=422,
            content={"error": "Validation Error", "detail": exc.errors()},
        )

    @app.exception_handler(PluginValidationError)
    async def plugin_validation_error_handler(
        _: Request,
        exc: PluginValidationError,
    ) -> JSONResponse:
        logger.error(f"PluginValidationError: {exc}")
        return JSONResponse(
            status_code=400,
            content={"error": "Plugin Validation Error", "detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.error(f"Unexpected error: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": "An unexpected error occurred",
            },
        )

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
            error_msg = f"Node '{node_name}' not found. Available nodes: {available_node_names}"
            logger.error(error_msg)
            raise HTTPException(status_code=404, detail=error_msg)

        node_class = node_map[node_name]
        logger.debug(f"Creating node instance for {node_class.__name__}")

        # Create node config and instance
        node_config = node_class.get_config_class()(**config)
        node_instance = node_class(node_config)

        # Execute node
        logger.debug(f"Executing node {node_name}")
        is_coroutine = inspect.iscoroutinefunction(node_instance.call)

        if is_coroutine:
            outputs = await node_instance.call(ctx, **inputs)
        else:
            outputs = node_instance.call(ctx, **inputs)

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
            error_msg = f"Node '{node_name}' not found. Available nodes: {available_node_names}"
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
        result = await integration_class.get_config(ctx)
        logger.info(
            f"Successfully retrieved configuration for integration: {integration_name}",
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
