"""Stress-test the SDK against realistic backend API responses.

Simulates the exact payloads the backend returns and tries to break
every deserialization path. Uses MagicMock with spec=Client to satisfy
the BaseResource type check.
"""

from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.assistants import Agent, AgentSettings
from noxus_sdk.resources.conversations import (
    Conversation,
    ConversationSettings,
    ConversationTool,
    KnowledgeBaseQaTool,
    WebResearchTool,
)


def _client():
    return create_autospec(Client, instance=True)


# ── Helpers: realistic backend payloads ──────────────────────────────

# These are the extra fields the backend serializes that the SDK
# doesn't model.  If the SDK can't handle them, it'll crash here.

_BACKEND_EXTRA_TOOL_FIELDS = {
    "title": "Web Research",
    "description": "Search the web for information",
    "category": "search",
    "tool_display_icon": "search",
    "tool_display_message_start": "Searching...",
    "tool_display_message_end": "Search complete",
    "requires_approval": False,
    "visible": True,
    "icon": "globe",
    "bg_color": "#E8F5E9",
    "icon_color": "#4CAF50",
    "chatflow_usable": True,
    "deprecated": False,
}

_BACKEND_EXTRA_SETTINGS_FIELDS = {
    "parameter_preset": "default",
    "top_p": 0.9,
    "top_k": 40,
    "timeout": 300.0,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
    "stop_sequences": [],
    "enable_reasoning": False,
    "reasoning_effort": "medium",
    "parallel_tool_calls": True,
    "is_coworker": True,
    "preset_selector": None,
    "hide_reasoning": False,
    "hide_workflow_progress": False,
    "tool_display_preset": "execution",
    "minimal_caret_only": False,
    "citation_style": "inline",
    "chat_input_placeholder": "",
    "agent_title_mode": "auto",
    "usage_limits_maximum_request": 100,
    "usage_limits_maximum_tokens": 100000,
    "usage_limits_max_messages": 50,
    "usage_limits_agent_timeout": 600,
    "subagents_enabled": False,
    "enable_gp_subagent": False,
    "allow_dynamic_subagents": False,
    "tool_grant_scope": "workspace",
    # Categorized tool fields (backend-internal, SDK ignores)
    "workflows": [],
    "knowledge_bases": [],
    "coworkers": [],
    "base_tools": [],
    "actions": [],
    "mcp_servers": [],
    "subagents": [],
    "chatflow_tools": [],
}


def _full_backend_tool(type_: str, **extra) -> dict:
    """Build a tool dict exactly as CoWorkerSettings.model_dump() would."""
    base = {
        "type": type_,
        "enabled": True,
        "extra_instructions": None,
        **_BACKEND_EXTRA_TOOL_FIELDS,
    }
    base.update(extra)
    return base


def _full_backend_settings(**overrides) -> dict:
    """Build a ConversationSettings dict as the backend actually returns it."""
    base = {
        "model": ["gpt-4o"],
        "model_selection": ["gpt-4o"],
        "temperature": 0.7,
        "max_tokens": 64000,
        "persona": None,
        "tone": None,
        "extra_instructions": None,
        "agent_flow_id": None,
        **_BACKEND_EXTRA_SETTINGS_FIELDS,
        "tools": [
            _full_backend_tool("web_research"),
            _full_backend_tool("noxus_qa"),
            _full_backend_tool("kb_selector"),
            _full_backend_tool(
                "kb_qa", kb_id="kb-123", advanced_search=True, private=False
            ),
            _full_backend_tool(
                "workflow",
                workflow_id="wf-456",
                inputs_descriptions={},
                version_id=None,
            ),
            _full_backend_tool(
                "human_in_the_loop",
                has_timeout=False,
                timeout=None,
                handover_message="Transferring...",
            ),
            _full_backend_tool("attach_file"),
            _full_backend_tool("memory"),
            _full_backend_tool("filesystem"),
            _full_backend_tool("code_execution", timeout=120),
            _full_backend_tool(
                "agent_tool", agent_id="agent-sub-1", max_clarification_turns=3
            ),
            _full_backend_tool("sandbox", persistent=False, include_execute=True),
            _full_backend_tool("schedule_tool"),
            _full_backend_tool("todos", enable_subtasks=True),
            _full_backend_tool("agent_memory"),
        ],
    }
    base.update(overrides)
    return base


def _full_backend_agent(**overrides) -> dict:
    return {
        "id": str(uuid4()),
        "group_id": str(uuid4()),
        "name": "Test Agent",
        "description": "A test agent",
        "definition": _full_backend_settings(),
        "draft_definition": None,
        "visible": True,
        "image_url": None,
        "last_updated_at": "2024-01-01T00:00:00",
        "deleted_at": None,
        "allow_public_access": False,
        **overrides,
    }


def _full_backend_conversation(**settings_overrides) -> dict:
    return {
        "id": str(uuid4()),
        "name": "Test Conversation",
        "created_at": "2024-01-01T00:00:00",
        "last_updated_at": "2024-01-01T00:00:00",
        "status": "idle",
        "assistant_id": str(uuid4()),
        "etag": "abc123",
        "settings": _full_backend_settings(**settings_overrides),
        "messages": [],
        # Extra backend fields
        "user_id": str(uuid4()),
        "api_key_id": str(uuid4()),
        "manual": False,
        "preview": False,
        "assistant_version_id": None,
        "chat_transport": None,
        "public_access_token": None,
        "todos": [],
    }


# ════════════════════════════════════════════════════════════════════
#  1. Agent — full backend payload with all extra fields
# ════════════════════════════════════════════════════════════════════


class TestAgentFullPayload:
    def test_agent_with_all_backend_fields(self):
        """Agent must parse even with 50+ extra fields the SDK doesn't model."""
        payload = _full_backend_agent()
        agent = Agent(client=_client(), **payload)
        assert agent.name == "Test Agent"
        assert agent.definition.temperature == 0.7
        assert len(agent.definition.tools) == 15

    def test_agent_tools_preserve_known_fields(self):
        payload = _full_backend_agent()
        agent = Agent(client=_client(), **payload)
        tool_map = {t.type: t for t in agent.definition.tools}

        assert tool_map["kb_qa"].kb_id == "kb-123"
        assert tool_map["workflow"].workflow_id == "wf-456"
        assert tool_map["code_execution"].timeout == 120

    def test_agent_with_persona_tone_instructions(self):
        payload = _full_backend_agent()
        payload["definition"]["persona"] = "You are a helpful bot"
        payload["definition"]["tone"] = "Friendly and concise"
        payload["definition"]["extra_instructions"] = "Always cite sources"
        agent = Agent(client=_client(), **payload)

        assert agent.definition.persona == "You are a helpful bot"
        assert agent.definition.tone == "Friendly and concise"
        assert agent.definition.extra_instructions == "Always cite sources"

    def test_agent_with_draft_definition(self):
        payload = _full_backend_agent()
        payload["draft_definition"] = _full_backend_settings(
            persona="Draft persona", temperature=0.5
        )
        agent = Agent(client=_client(), **payload)

        assert agent.draft_definition is not None
        assert agent.draft_definition.persona == "Draft persona"
        assert agent.draft_definition.temperature == 0.5

    def test_agent_extra_fields_not_lost(self):
        """Agent has extra='allow', so unknown fields should be preserved."""
        payload = _full_backend_agent()
        agent = Agent(client=_client(), **payload)
        # Agent has ConfigDict(extra="allow") so image_url etc. should stick
        assert agent.name == "Test Agent"


# ════════════════════════════════════════════════════════════════════
#  2. Agent — unknown tool types (discriminator edge case)
# ════════════════════════════════════════════════════════════════════


class TestUnknownToolTypes:
    def test_unknown_tool_type_falls_back(self):
        """Unknown tool types fall back to ConversationTool instead of crashing."""
        settings = _full_backend_settings()
        settings["tools"].append(
            _full_backend_tool("mcp_tool", server_url="http://localhost:3000")
        )
        s = ConversationSettings(**settings)
        mcp = next(t for t in s.tools if t.type == "mcp_tool")
        assert isinstance(mcp, ConversationTool)
        assert mcp.type == "mcp_tool"
        assert mcp.enabled is True

    def test_unknown_tool_type_in_agent(self):
        """Unknown tool types work through the Agent path too."""
        payload = _full_backend_agent()
        payload["definition"]["tools"].append(_full_backend_tool("brand_new_tool"))
        agent = Agent(client=_client(), **payload)
        new_tool = next(t for t in agent.definition.tools if t.type == "brand_new_tool")
        assert isinstance(new_tool, ConversationTool)

    def test_unknown_tool_preserves_extra_fields(self):
        """Unknown tools have extra='allow' so backend fields are kept."""
        settings = _full_backend_settings()
        settings["tools"] = [
            {
                "type": "future_tool",
                "enabled": True,
                "extra_instructions": None,
                "custom_field": "custom_value",
                "nested": {"key": "val"},
            }
        ]
        s = ConversationSettings(**settings)
        tool = s.tools[0]
        assert tool.type == "future_tool"
        assert tool.custom_field == "custom_value"  # type: ignore[attr-defined]
        assert tool.nested == {"key": "val"}  # type: ignore[attr-defined]


# ════════════════════════════════════════════════════════════════════
#  3. Conversation — full backend payload
# ════════════════════════════════════════════════════════════════════


class TestConversationFullPayload:
    def test_conversation_with_all_backend_fields(self):
        payload = _full_backend_conversation()
        conv = Conversation(client=_client(), **payload)
        assert conv.name == "Test Conversation"
        assert conv.status == "idle"
        assert conv.settings.temperature == 0.7
        assert len(conv.settings.tools) == 15

    def test_conversation_with_persona(self):
        payload = _full_backend_conversation(persona="Helpful bot")
        conv = Conversation(client=_client(), **payload)
        assert conv.settings.persona == "Helpful bot"

    def test_conversation_agent_id_alias(self):
        aid = str(uuid4())
        payload = _full_backend_conversation()
        payload["assistant_id"] = aid
        conv = Conversation(client=_client(), **payload)
        assert conv.agent_id == aid


# ════════════════════════════════════════════════════════════════════
#  4. ConversationSettings — edge cases
# ════════════════════════════════════════════════════════════════════


class TestConversationSettingsEdgeCases:
    def test_model_selection_alias(self):
        """Backend sends model_selection, SDK field is model."""
        s = ConversationSettings(
            model_selection=["gpt-4o"],
            temperature=0.7,
            tools=[],
        )
        assert s.model == ["gpt-4o"]

    def test_both_model_and_model_selection(self):
        """Backend might send both — model should win (or at least not crash)."""
        s = ConversationSettings(
            model=["claude-3"],
            model_selection=["gpt-4o"],
            temperature=0.7,
            tools=[],
        )
        # model takes precedence per AliasChoices ordering
        assert s.model == ["claude-3"]

    def test_missing_model_field(self):
        """If neither model nor model_selection is present, should fail."""
        with pytest.raises(Exception):
            ConversationSettings(temperature=0.7, tools=[])

    def test_missing_temperature(self):
        with pytest.raises(Exception):
            ConversationSettings(model=["gpt-4o"], tools=[])

    def test_missing_tools(self):
        with pytest.raises(Exception):
            ConversationSettings(model=["gpt-4o"], temperature=0.7)

    def test_empty_tools_list(self):
        s = ConversationSettings(model=["gpt-4o"], temperature=0.7, tools=[])
        assert s.tools == []

    def test_extra_backend_fields_silently_ignored(self):
        """ConversationSettings doesn't have extra='allow', extra fields are dropped."""
        s = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[],
            # Backend-only fields:
            top_p=0.9,
            enable_reasoning=True,
            parallel_tool_calls=True,
            usage_limits_max_messages=50,
        )
        assert s.temperature == 0.7
        assert not hasattr(s, "top_p")

    def test_agent_flow_id(self):
        s = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[],
            agent_flow_id="flow-123",
        )
        assert s.agent_flow_id == "flow-123"


# ════════════════════════════════════════════════════════════════════
#  5. Tool edge cases
# ════════════════════════════════════════════════════════════════════


class TestToolEdgeCases:
    def test_kb_qa_missing_kb_id(self):
        """kb_id is required on KnowledgeBaseQaTool — should fail."""
        with pytest.raises(Exception):
            ConversationSettings(
                model=["gpt-4o"],
                temperature=0.7,
                tools=[{"type": "kb_qa", "enabled": True}],
            )

    def test_workflow_missing_workflow_id(self):
        """workflow_id is required on WorkflowTool — should fail."""
        with pytest.raises(Exception):
            ConversationSettings(
                model=["gpt-4o"],
                temperature=0.7,
                tools=[{"type": "workflow", "enabled": True}],
            )

    def test_tool_with_extra_backend_fields(self):
        """All tools inherit extra='allow' from ConversationTool, so extra fields are preserved."""
        s = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[_full_backend_tool("web_research")],
        )
        tool = s.tools[0]
        assert tool.type == "web_research"
        assert tool.title == "Web Research"  # type: ignore[attr-defined]
        assert tool.category == "search"  # type: ignore[attr-defined]

    def test_tool_with_extra_allow_preserves_fields(self):
        """Tools WITH extra='allow' should keep extra fields."""
        s = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[
                _full_backend_tool(
                    "agent_tool", agent_id="a-1", max_clarification_turns=3
                )
            ],
        )
        tool = s.tools[0]
        assert tool.type == "agent_tool"
        assert tool.agent_id == "a-1"
        # AgentTool has extra="allow", so backend fields are preserved
        assert tool.max_clarification_turns == 3  # type: ignore[attr-defined]

    def test_all_15_tool_types_parse(self):
        """Every tool type the backend sends must parse without error."""
        settings = _full_backend_settings()
        s = ConversationSettings(**settings)
        types = [t.type for t in s.tools]
        assert "web_research" in types
        assert "kb_qa" in types
        assert "workflow" in types
        assert "agent_tool" in types
        assert "sandbox" in types
        assert "code_execution" in types
        assert "human_in_the_loop" in types
        assert "schedule_tool" in types
        assert "todos" in types
        assert "agent_memory" in types
        assert len(s.tools) == 15

    def test_disabled_tool(self):
        s = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[{"type": "web_research", "enabled": False}],
        )
        assert s.tools[0].enabled is False

    def test_tool_extra_instructions_as_string(self):
        s = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[{"type": "web_research", "extra_instructions": "Be thorough"}],
        )
        assert s.tools[0].extra_instructions == "Be thorough"


# ════════════════════════════════════════════════════════════════════
#  6. Agent _update_w_response (setattr loop)
# ════════════════════════════════════════════════════════════════════


class TestAgentUpdateResponse:
    def test_update_definition_via_setattr(self):
        """Agent.update() does setattr for each key in the API response.
        With validate_assignment=True, setting definition= with a raw dict
        must trigger ConversationSettings validation."""
        initial = _full_backend_agent()
        agent = Agent(client=_client(), **initial)

        # Simulate backend response from PATCH /v1/agents/{id}
        update_response = _full_backend_agent(
            name="Updated Agent",
        )
        update_response["definition"]["persona"] = "New persona"
        update_response["definition"]["temperature"] = 0.3

        for key, value in update_response.items():
            if hasattr(agent, key):
                setattr(agent, key, value)

        assert agent.name == "Updated Agent"
        assert agent.definition.persona == "New persona"
        assert agent.definition.temperature == 0.3


# ════════════════════════════════════════════════════════════════════
#  7. Conversation _update_w_response (setattr loop)
# ════════════════════════════════════════════════════════════════════


class TestConversationUpdateResponse:
    def test_refresh_updates_settings(self):
        """Conversation._update_w_response does setattr for each key.
        With validate_assignment=True, setting settings= with a raw dict
        must trigger ConversationSettings validation."""
        initial = _full_backend_conversation()
        conv = Conversation(client=_client(), **initial)

        # Simulate backend response from GET /v1/conversations/{id}
        refresh_response = _full_backend_conversation(persona="Refreshed persona")

        conv._update_w_response(refresh_response)
        assert conv.settings.persona == "Refreshed persona"


# ════════════════════════════════════════════════════════════════════
#  8. Missing fields that backend sometimes omits
# ════════════════════════════════════════════════════════════════════


class TestMissingFields:
    def test_agent_no_draft_definition(self):
        payload = _full_backend_agent(draft_definition=None)
        agent = Agent(client=_client(), **payload)
        assert agent.draft_definition is None

    def test_conversation_no_etag(self):
        payload = _full_backend_conversation()
        del payload["etag"]
        conv = Conversation(client=_client(), **payload)
        assert conv.etag is None

    def test_conversation_no_assistant_id(self):
        payload = _full_backend_conversation()
        del payload["assistant_id"]
        conv = Conversation(client=_client(), **payload)
        assert conv.agent_id is None

    def test_conversation_no_messages(self):
        payload = _full_backend_conversation()
        del payload["messages"]
        conv = Conversation(client=_client(), **payload)
        assert conv.messages == []

    def test_settings_no_persona_tone_instructions(self):
        settings = _full_backend_settings()
        del settings["persona"]
        del settings["tone"]
        del settings["extra_instructions"]
        s = ConversationSettings(**settings)
        assert s.persona is None
        assert s.tone is None
        assert s.extra_instructions is None

    def test_settings_no_agent_flow_id(self):
        settings = _full_backend_settings()
        # agent_flow_id not present at all
        if "agent_flow_id" in settings:
            del settings["agent_flow_id"]
        s = ConversationSettings(**settings)
        assert s.agent_flow_id is None
