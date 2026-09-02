"""Cross-workspace safety gates of the coding-agents plugin.

The plugin lives outside the workspace (plugins/coding-agents), so it is put
on sys.path directly; its only dependency is the SDK under test.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parents[3] / "plugins" / "coding-agents")
)

from coding_agents.plugin_config import CodingAgentsPluginConfig  # noqa: E402
from coding_agents import nodes as nodes_mod  # noqa: E402
from noxus_sdk.errors import IntegrationFailedError  # noqa: E402
from noxus_sdk.plugins.context import RemoteExecutionContext  # noqa: E402


def test_plugin_config_invalid_until_shared_sandbox_acknowledged():
    result = CodingAgentsPluginConfig().validate_config()
    assert not result.valid
    assert any("share one sandbox" in e for e in result.errors)

    result = CodingAgentsPluginConfig(acknowledge_shared_sandbox=True).validate_config()
    assert result.valid


@pytest.mark.asyncio
async def test_nodes_refuse_to_run_without_shared_sandbox_ack():
    config = nodes_mod.AgentTaskConfiguration(task="say hi")
    ctx = RemoteExecutionContext(group_id="g1", plugin_config={})
    with pytest.raises(IntegrationFailedError, match="shared sandbox"):
        await nodes_mod._run_agent(config, ctx, nodes_mod.CLAUDE_CODE_SPEC)


@pytest.mark.asyncio
async def test_shell_login_seeding_is_opt_in(tmp_path, monkeypatch):
    shell_home = tmp_path / "shell"
    shell_home.mkdir()
    (shell_home / ".claude.json").write_text("{}")
    monkeypatch.setattr(nodes_mod, "AGENT_HOMES_ROOT", str(tmp_path / "homes"))
    monkeypatch.setattr(nodes_mod, "SHELL_HOME", str(shell_home))

    async def fake_exec(
        command: str, env: dict, cwd: str, timeout: int, label: str = ""
    ) -> tuple[str, str, int, bool]:
        return ("ok", "", 0, False)

    monkeypatch.setattr(nodes_mod, "_exec_shell", fake_exec)
    config = nodes_mod.AgentTaskConfiguration(task="say hi")

    ctx = RemoteExecutionContext(
        group_id="g1", plugin_config={"acknowledge_shared_sandbox": True}
    )
    await nodes_mod._run_agent(config, ctx, nodes_mod.CLAUDE_CODE_SPEC)
    assert not os.path.exists(tmp_path / "homes" / "g1" / ".claude.json")

    ctx = RemoteExecutionContext(
        group_id="g2",
        plugin_config={
            "acknowledge_shared_sandbox": True,
            "share_shell_login": True,
        },
    )
    await nodes_mod._run_agent(config, ctx, nodes_mod.CODEX_SPEC)
    assert os.path.exists(tmp_path / "homes" / "g2" / ".claude.json")


@pytest.mark.asyncio
async def test_workspace_home_is_private(tmp_path, monkeypatch):
    monkeypatch.setattr(nodes_mod, "AGENT_HOMES_ROOT", str(tmp_path / "homes"))
    monkeypatch.setattr(nodes_mod, "SHELL_HOME", str(tmp_path / "shell"))

    async def fake_exec(
        command: str, env: dict, cwd: str, timeout: int, label: str = ""
    ) -> tuple[str, str, int, bool]:
        return ("ok", "", 0, False)

    monkeypatch.setattr(nodes_mod, "_exec_shell", fake_exec)
    config = nodes_mod.AgentTaskConfiguration(task="say hi")
    ctx = RemoteExecutionContext(
        group_id="g1", plugin_config={"acknowledge_shared_sandbox": True}
    )
    await nodes_mod._run_agent(config, ctx, nodes_mod.CLAUDE_CODE_SPEC)
    mode = os.stat(tmp_path / "homes" / "g1").st_mode & 0o777
    assert mode == 0o700
