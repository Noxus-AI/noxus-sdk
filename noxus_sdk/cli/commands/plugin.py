from __future__ import annotations

import json
from pathlib import Path

import typer

from noxus_sdk.plugins import (
    PluginManifest,  # noqa: TCH001 - Typer is getting messed up type checking
)
from noxus_sdk.schemas import (
    ValidationResult,  # noqa: TCH001 - Typer is getting messed up type checking
)
from noxus_sdk.utils import setup_logging

setup_logging("INFO")

app = typer.Typer(help="Plugin management commands")


@app.command()
def create(
    output_dir: str = typer.Option(".", help="Directory to create plugin in"),
) -> None:
    """Create a new plugin from the template"""
    output_path = Path(output_dir)

    try:
        from noxus_sdk.plugins.create import create_plugin

        typer.echo("🎯 Creating new plugin from the template...")
        typer.echo("📝 Please answer the prompts to configure your plugin")

        plugin_dir = create_plugin(output_path)

        typer.echo(f"\n✅ Created plugin package at {plugin_dir}")
        typer.echo(f"📝 Edit {plugin_dir}/pyproject.toml to add dependencies")
        typer.echo(f"🔧 Edit {plugin_dir}/__init__.py to configure your plugin")
        typer.echo(f"🧪 Run 'noxus plugin validate --path {plugin_dir}' to validate")

    except KeyboardInterrupt:
        typer.echo("\n❌ Plugin creation cancelled", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def validate(
    path: str = typer.Option(".", help="Plugin directory path"),
    strict: bool = typer.Option(False, help="Enable strict validation"),  # noqa: FBT001, FBT003, Impossible to satisfy here
) -> tuple[PluginManifest | None, ValidationResult]:
    """Validate a plugin package"""

    from noxus_sdk.plugins.validate import validate_plugin

    manifest, result = validate_plugin(Path(path))

    if result.errors:
        typer.secho("❌ Validation failed with errors:", fg="red")
        for error in result.errors:
            typer.secho(f"   • {error}", fg="red")
        raise typer.Exit(code=1)

    if strict and result.warnings:
        typer.secho("❌ Validation failed with warnings (strict mode):", fg="red")
        for warning in result.warnings:
            typer.secho(f"   • {warning}", fg="red")
        raise typer.Exit(code=1)

    for warning in result.warnings:
        typer.secho(f"⚠️  {warning}", fg="yellow")

    if manifest:
        typer.secho(
            f"✅ Plugin '{manifest.name}' v{manifest.version} validated successfully",
            fg="green",
        )
    else:
        typer.secho("✅ Plugin structure validated successfully", fg="green")

    return manifest, result


@app.command()
def generate_manifest(
    path: str = typer.Option(".", help="Plugin directory path"),
) -> tuple[PluginManifest | None, ValidationResult]:
    """Generate manifest.json from plugin code"""

    output_path = Path(path) / "manifest.json"

    manifest, result = validate(path)

    if not manifest or result.errors:
        raise typer.Exit(code=1)

    typer.echo(f"📝 Generating manifest from {manifest.display_name}")

    # Convert to dict and write as JSON
    manifest_dict = manifest.model_dump()

    with open(output_path, "w") as f:
        json.dump(manifest_dict, f, indent=2)

    typer.secho(f"✅ Generated {output_path}", fg="green")

    return manifest, result


@app.command()
def package(
    path: str = typer.Option(".", help="Plugin directory path"),
    output: str | None = typer.Option(None, help="Output filename"),
) -> Path:
    """Package a plugin into a tar.gz file"""

    from noxus_sdk.plugins.package import package_plugin

    manifest, result = generate_manifest(path)
    plugin_path = Path(path)

    if not manifest or result.errors:
        raise typer.Exit(code=1)

    # Generate output filename if not provided
    if not output:
        output = f"{manifest.name}-{manifest.version}.tar.gz"

    output_path = Path(output)

    typer.echo(f"📦 Packaging {manifest.display_name} v{manifest.version}...")

    package_plugin(plugin_path, output_path)

    typer.secho(f"✅ Plugin packaged as {output_path}", fg="green")
    return output_path


@app.command()
def serve(
    path: str = typer.Option(".", help="Plugin directory path"),
    host: str = typer.Option("localhost", help="Host to serve the plugin on"),
    port: int = typer.Option(8505, help="Port to serve the plugin on"),
) -> None:
    """Serves a plugin"""

    from noxus_sdk.plugins.serve import serve_plugin

    serve_plugin(Path(path), host=host, port=port, print_port=True)
