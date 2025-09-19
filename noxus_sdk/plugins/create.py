import subprocess
from pathlib import Path

from cookiecutter.main import cookiecutter


def create_plugin(output_dir: Path = Path()) -> Path:
    """Create a new plugin using cookiecutter template"""

    template_path = Path(__file__).parent.parent / "templates" / "cookiecutter-plugin"

    try:
        path = cookiecutter(
            str(template_path),
            no_input=False,
            output_dir=str(output_dir),
        )

        if not path:
            raise RuntimeError("No plugin directory was created")

        return Path(path)
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            # User cancelled, not an error
            raise KeyboardInterrupt("Plugin creation cancelled by user") from None
        raise RuntimeError(f"Cookiecutter failed: {e}") from e
