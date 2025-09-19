# {{ cookiecutter.__package_name }}

{{ cookiecutter.description }}

## Installation

Install dependencies:

```bash
pip install -e .
```

## Development

### Local Testing

```bash
# Validate the plugin
noxus plugin validate

# Package the plugin
noxus plugin package
```

### Project Structure

```
{{ cookiecutter.__package_name }}/
├── {{ cookiecutter.__package_name }}/
│   ├── __init__.py      # Plugin definition
│   └── nodes/           # Node implementations
├── pyproject.toml       # Dependencies and metadata
├── tests/               # Test files
└── README.md           # This file
```

### Adding Dependencies

Edit the `dependencies` section in `pyproject.toml`:

```toml
[project]
dependencies = [
    "your-dependency>=1.0.0",
]
```

### System Dependencies

For system packages, add them to `pyproject.toml`:

```toml
[tool.plugin]
system_dependencies = ["git", "curl"]
```

### Testing

Run tests:

```bash
python -m pytest tests/
```
