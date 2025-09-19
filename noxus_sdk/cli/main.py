import typer

from noxus_sdk import __version__
from noxus_sdk.cli.commands.plugin import app as plugin_app

app = typer.Typer(
    help="Noxus CLI - Software development kit to extend the Noxus platform",
)

app.add_typer(plugin_app, name="plugin")


@app.command()
def version() -> None:
    """Show version information"""
    typer.echo(f"noxus version {__version__}")


def main() -> None:
    """Main entry point for the CLI"""
    app()


if __name__ == "__main__":
    main()
