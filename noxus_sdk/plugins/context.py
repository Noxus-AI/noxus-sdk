"""Remote execution context for plugins"""

from __future__ import annotations

from pydantic import BaseModel


class RemoteExecutionContext(BaseModel):
    plugin_config: dict = {}
    integration_credentials: dict[str, dict] = {}

    def get_integration_credentials(self, integration_name: str) -> dict:
        return self.integration_credentials[integration_name] if self.integration_credentials else {}
