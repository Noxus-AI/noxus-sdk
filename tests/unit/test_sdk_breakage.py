"""Try to break every SDK deserialization path.

Focuses on:
- setattr + validate_assignment patterns (refresh / update)
- hasattr guard letting through unexpected keys
- Discriminated union edge cases
- Missing / extra / wrong-type fields from API responses
"""

from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.assistants import Agent
from noxus_sdk.resources.conversations import (
    Conversation,
    ConversationSettings,
    ConversationTool,
    Message,
    MessageEvent,
)
from noxus_sdk.resources.knowledge_bases import KnowledgeBase, KBConfigV3
from noxus_sdk.resources.runs import Run


def _client():
    return create_autospec(Client, instance=True)


def _minimal_settings(**overrides) -> dict:
    base = {"model": ["gpt-4o"], "temperature": 0.7, "tools": [], **overrides}
    return base


def _minimal_agent(**overrides) -> dict:
    return {
        "id": str(uuid4()),
        "group_id": str(uuid4()),
        "name": "Agent",
        "definition": _minimal_settings(),
        **overrides,
    }


def _minimal_conversation(**overrides) -> dict:
    return {
        "id": str(uuid4()),
        "name": "Conv",
        "created_at": "2024-01-01T00:00:00",
        "last_updated_at": "2024-01-01T00:00:00",
        "status": "idle",
        "settings": _minimal_settings(),
        **overrides,
    }


def _minimal_run(**overrides) -> dict:
    return {
        "id": str(uuid4()),
        "group_id": str(uuid4()),
        "workflow_id": str(uuid4()),
        "input": {},
        "status": "completed",
        "progress": 100,
        "created_at": "2024-01-01T00:00:00",
        **overrides,
    }


def _minimal_kb(**overrides) -> dict:
    return {
        "id": str(uuid4()),
        "group_id": str(uuid4()),
        "name": "KB",
        "status": "ready",
        "description": "test",
        "document_types": ["text"],
        "kb_type": "v3",
        "size": 0,
        "num_docs": 0,
        "total_documents": 0,
        "training_documents": 0,
        "trained_documents": 0,
        "error_documents": 0,
        "uploaded_documents": 0,
        "source_types": {},
        "training_source_types": [],
        "settings_": KBConfigV3().model_dump(),
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
        **overrides,
    }


# ════════════════════════════════════════════════════════════════════
#  1. Conversation._update_w_response — the setattr minefield
# ════════════════════════════════════════════════════════════════════


class TestConversationSetattr:
    """_update_w_response does setattr for each API response key."""

    def test_settings_as_raw_dict(self):
        """refresh() returns settings as a raw dict — must coerce to ConversationSettings."""
        conv = Conversation(client=_client(), **_minimal_conversation())
        conv._update_w_response(
            {
                "settings": _minimal_settings(persona="Updated"),
            }
        )
        assert conv.settings.persona == "Updated"

    def test_settings_with_tools_as_raw_dicts(self):
        """settings.tools come as raw dicts — discriminator must resolve them."""
        conv = Conversation(client=_client(), **_minimal_conversation())
        conv._update_w_response(
            {
                "settings": _minimal_settings(
                    tools=[
                        {"type": "web_research", "enabled": True},
                        {"type": "kb_qa", "kb_id": "kb-1", "enabled": True},
                    ]
                ),
            }
        )
        assert len(conv.settings.tools) == 2
        assert conv.settings.tools[1].type == "kb_qa"

    def test_settings_with_unknown_tool_in_update(self):
        """Unknown tool type during refresh must not crash."""
        conv = Conversation(client=_client(), **_minimal_conversation())
        conv._update_w_response(
            {
                "settings": _minimal_settings(
                    tools=[
                        {"type": "web_research", "enabled": True},
                        {
                            "type": "future_mcp_tool",
                            "enabled": True,
                            "server": "http://x",
                        },
                    ]
                ),
            }
        )
        assert len(conv.settings.tools) == 2
        unknown = next(t for t in conv.settings.tools if t.type == "future_mcp_tool")
        assert isinstance(unknown, ConversationTool)

    def test_update_ignores_unknown_top_level_keys(self):
        """API may return keys that don't exist on Conversation — must not crash."""
        conv = Conversation(client=_client(), **_minimal_conversation())
        # "new_backend_field" doesn't exist on Conversation model
        conv._update_w_response(
            {
                "name": "Updated",
                "new_backend_field": "something",
            }
        )
        assert conv.name == "Updated"

    def test_update_with_none_settings(self):
        """What if settings is None in the response?"""
        conv = Conversation(client=_client(), **_minimal_conversation())
        # settings is required (no default), so setting it to None should fail
        with pytest.raises(Exception):
            conv._update_w_response({"settings": None})

    def test_update_messages_as_raw_dicts(self):
        """messages come as raw dicts with UUID and datetime."""
        conv = Conversation(client=_client(), **_minimal_conversation())
        conv._update_w_response(
            {
                "messages": [
                    {
                        "id": str(uuid4()),
                        "created_at": "2024-01-01T00:00:00",
                        "message_parts": [{"role": "assistant", "content": "hi"}],
                    }
                ],
            }
        )
        assert len(conv.messages) == 1


# ════════════════════════════════════════════════════════════════════
#  2. Agent — definition coercion and update patterns
# ════════════════════════════════════════════════════════════════════


class TestAgentSetattr:
    def test_definition_as_raw_dict(self):
        """Agent.update does setattr — definition must coerce from dict."""
        agent = Agent(client=_client(), **_minimal_agent())
        # Simulate the setattr loop from Agent.update()
        for key, value in {"definition": _minimal_settings(persona="New")}.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        assert agent.definition.persona == "New"

    def test_definition_with_all_extra_backend_fields(self):
        """Backend definition has 50+ fields — extra must not crash."""
        defn = _minimal_settings()
        defn.update(
            {
                "top_p": 0.9,
                "top_k": 40,
                "enable_reasoning": False,
                "parallel_tool_calls": True,
                "is_coworker": True,
                "workflows": [],
                "knowledge_bases": [],
                "coworkers": [],
                "base_tools": [],
                "actions": [],
                "mcp_servers": [],
            }
        )
        agent = Agent(client=_client(), **_minimal_agent(definition=defn))
        assert agent.definition.temperature == 0.7

    def test_draft_definition_as_none(self):
        agent = Agent(client=_client(), **_minimal_agent(draft_definition=None))
        assert agent.draft_definition is None

    def test_draft_definition_as_raw_dict(self):
        agent = Agent(
            client=_client(),
            **_minimal_agent(draft_definition=_minimal_settings(persona="Draft")),
        )
        assert agent.draft_definition is not None
        assert agent.draft_definition.persona == "Draft"

    def test_agent_with_extra_top_level_fields(self):
        """API returns fields Agent doesn't model — extra='allow' keeps them."""
        payload = _minimal_agent()
        payload["image_url"] = "https://example.com/img.png"
        payload["allow_public_access"] = True
        payload["completely_new_field"] = {"nested": True}
        agent = Agent(client=_client(), **payload)
        assert agent.name == "Agent"


# ════════════════════════════════════════════════════════════════════
#  3. Tool discriminator stress tests
# ════════════════════════════════════════════════════════════════════


class TestToolDiscriminator:
    def test_tool_with_missing_type_field(self):
        """Tool dict without a 'type' key — type is required, must fail."""
        with pytest.raises(Exception):
            ConversationSettings(
                **_minimal_settings(
                    tools=[
                        {"enabled": True, "extra_instructions": "no type here"},
                    ]
                )
            )

    def test_tool_with_empty_type(self):
        """Tool with type="" — falls back to ConversationTool."""
        s = ConversationSettings(
            **_minimal_settings(
                tools=[
                    {"type": "", "enabled": True},
                ]
            )
        )
        assert s.tools[0].type == ""
        assert isinstance(s.tools[0], ConversationTool)

    def test_tool_with_none_type(self):
        """Tool with type=None."""
        with pytest.raises(Exception):
            ConversationSettings(
                **_minimal_settings(
                    tools=[
                        {"type": None, "enabled": True},
                    ]
                )
            )

    def test_many_unknown_tools(self):
        """10 unknown tool types in one settings — all must parse."""
        tools = [
            {"type": f"future_tool_{i}", "enabled": True, "custom": i}
            for i in range(10)
        ]
        s = ConversationSettings(**_minimal_settings(tools=tools))
        assert len(s.tools) == 10
        for i, t in enumerate(s.tools):
            assert t.type == f"future_tool_{i}"
            assert isinstance(t, ConversationTool)

    def test_mixed_known_and_unknown_tools(self):
        """Mix of known and unknown tool types."""
        s = ConversationSettings(
            **_minimal_settings(
                tools=[
                    {"type": "web_research", "enabled": True},
                    {"type": "alien_tool", "enabled": True, "planet": "mars"},
                    {"type": "kb_qa", "kb_id": "kb-1", "enabled": True},
                    {"type": "another_future", "enabled": False},
                ]
            )
        )
        types = [t.type for t in s.tools]
        assert types == ["web_research", "alien_tool", "kb_qa", "another_future"]

    def test_tool_enabled_as_string(self):
        """Backend might send enabled as string "true" — Pydantic coerces bools."""
        s = ConversationSettings(
            **_minimal_settings(
                tools=[
                    {"type": "web_research", "enabled": "true"},
                ]
            )
        )
        assert s.tools[0].enabled is True

    def test_tool_enabled_missing(self):
        """enabled has default=True, so missing is fine."""
        s = ConversationSettings(
            **_minimal_settings(
                tools=[
                    {"type": "web_research"},
                ]
            )
        )
        assert s.tools[0].enabled is True


# ════════════════════════════════════════════════════════════════════
#  4. Run resource edge cases
# ════════════════════════════════════════════════════════════════════


class TestRunEdgeCases:
    def test_run_with_extra_fields(self):
        """Backend Run schema has many fields the SDK doesn't model."""
        payload = _minimal_run()
        payload["workflow_definition"] = {"nodes": [], "edges": []}
        payload["definitions"] = {"some": "defs"}
        payload["started_at"] = "2024-01-01T00:00:01"
        run = Run(client=_client(), **payload)
        assert run.status == "completed"

    def test_run_refresh_with_output(self):
        run = Run(client=_client(), **_minimal_run())
        run._setattr_safe = lambda k, v: setattr(run, k, v) if hasattr(run, k) else None
        # Simulate refresh response
        for key, value in {
            "status": "completed",
            "output": {"result": "ok"},
            "progress": 100,
        }.items():
            if hasattr(run, key):
                setattr(run, key, value)
        assert run.output == {"result": "ok"}

    def test_run_with_null_output(self):
        run = Run(client=_client(), **_minimal_run(output=None))
        assert run.output is None

    def test_run_with_null_node_ids(self):
        run = Run(client=_client(), **_minimal_run(node_ids=None))
        assert run.node_ids is None

    def test_run_with_list_node_ids(self):
        run = Run(client=_client(), **_minimal_run(node_ids=["n1", "n2"]))
        assert run.node_ids == ["n1", "n2"]


# ════════════════════════════════════════════════════════════════════
#  5. KnowledgeBase edge cases
# ════════════════════════════════════════════════════════════════════


class TestKBEdgeCases:
    def test_kb_with_extra_fields(self):
        payload = _minimal_kb()
        payload["ingestion_status"] = "idle"
        payload["last_ingestion_at"] = None
        kb = KnowledgeBase(client=_client(), **payload)
        assert kb.name == "KB"

    def test_kb_refresh_setattr(self):
        """KB.refresh uses same setattr pattern."""
        kb = KnowledgeBase(client=_client(), **_minimal_kb())
        for key, value in {"name": "Updated KB", "status": "training"}.items():
            if hasattr(kb, key):
                setattr(kb, key, value)
        assert kb.name == "Updated KB"
        assert kb.status == "training"

    def test_kb_settings_as_v3(self):
        kb = KnowledgeBase(client=_client(), **_minimal_kb())
        assert kb.version == "v3"

    def test_kb_with_documents(self):
        payload = _minimal_kb()
        payload["documents"] = [
            {
                "id": str(uuid4()),
                "name": "doc.pdf",
                "prefix": "/",
                "status": "trained",
                "source_type": "Document",
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01",
            }
        ]
        kb = KnowledgeBase(client=_client(), **payload)
        assert len(kb.documents) == 1
        assert kb.documents[0].name == "doc.pdf"


# ════════════════════════════════════════════════════════════════════
#  6. MessageEvent (SSE) parsing
# ════════════════════════════════════════════════════════════════════


class TestMessageEventParsing:
    def test_normal_event(self):
        e = MessageEvent(role="assistant", type="text", content="hello")
        assert e.content == "hello"

    def test_event_without_content(self):
        e = MessageEvent(role="assistant", type="conversation_end")
        assert e.content is None

    def test_event_from_json(self):
        e = MessageEvent.model_validate_json(
            '{"role": "assistant", "type": "text", "content": "hi"}'
        )
        assert e.content == "hi"

    def test_event_with_extra_fields(self):
        """SSE events may include extra fields in the future."""
        e = MessageEvent.model_validate_json(
            '{"role": "assistant", "type": "text", "content": "hi", "metadata": {"token_count": 5}}'
        )
        assert e.content == "hi"

    def test_event_missing_role(self):
        """role is required — must fail."""
        with pytest.raises(Exception):
            MessageEvent.model_validate_json('{"type": "text", "content": "hi"}')

    def test_event_missing_type(self):
        """type is required — must fail."""
        with pytest.raises(Exception):
            MessageEvent.model_validate_json('{"role": "assistant", "content": "hi"}')


# ════════════════════════════════════════════════════════════════════
#  7. ConversationSettings — model field alias edge cases
# ════════════════════════════════════════════════════════════════════


class TestModelFieldAlias:
    def test_only_model_selection_in_api_response(self):
        """Backend sends model_selection, not model."""
        s = ConversationSettings(
            **{
                "model_selection": ["gpt-4o"],
                "temperature": 0.7,
                "tools": [],
            }
        )
        assert s.model == ["gpt-4o"]

    def test_model_field_directly(self):
        s = ConversationSettings(
            **{
                "model": ["claude-3"],
                "temperature": 0.7,
                "tools": [],
            }
        )
        assert s.model == ["claude-3"]

    def test_model_dump_uses_model_not_alias(self):
        """model_dump() should use the field name 'model', not the alias."""
        s = ConversationSettings(
            **{
                "model": ["gpt-4o"],
                "temperature": 0.7,
                "tools": [],
            }
        )
        dumped = s.model_dump()
        assert "model" in dumped
        assert dumped["model"] == ["gpt-4o"]

    def test_round_trip(self):
        """Create settings, dump, re-parse — must not lose data."""
        original = ConversationSettings(
            **{
                "model": ["gpt-4o", "claude-3"],
                "temperature": 0.5,
                "tools": [
                    {
                        "type": "web_research",
                        "enabled": True,
                        "extra_instructions": "be fast",
                    },
                    {"type": "kb_qa", "kb_id": "kb-1"},
                ],
                "persona": "Helpful",
                "tone": "Casual",
                "extra_instructions": "Be concise",
            }
        )
        dumped = original.model_dump()
        restored = ConversationSettings(**dumped)

        assert restored.model == ["gpt-4o", "claude-3"]
        assert restored.temperature == 0.5
        assert restored.persona == "Helpful"
        assert restored.tone == "Casual"
        assert restored.extra_instructions == "Be concise"
        assert len(restored.tools) == 2
        assert restored.tools[0].extra_instructions == "be fast"
        assert restored.tools[1].type == "kb_qa"


# ════════════════════════════════════════════════════════════════════
#  8. Edge: Conversation constructed with assistant_id alias
# ════════════════════════════════════════════════════════════════════


class TestAssistantIdAlias:
    def test_assistant_id_maps_to_agent_id(self):
        aid = str(uuid4())
        conv = Conversation(client=_client(), **_minimal_conversation(assistant_id=aid))
        assert conv.agent_id == aid

    def test_agent_id_directly(self):
        aid = str(uuid4())
        conv = Conversation(client=_client(), **_minimal_conversation(agent_id=aid))
        assert conv.agent_id == aid

    def test_neither_assistant_id_nor_agent_id(self):
        conv = Conversation(client=_client(), **_minimal_conversation())
        assert conv.agent_id is None

    def test_update_response_with_assistant_id(self):
        """_update_w_response remaps assistant_id → agent_id."""
        conv = Conversation(client=_client(), **_minimal_conversation())
        aid = str(uuid4())
        conv._update_w_response({"assistant_id": aid})
        assert conv.agent_id == aid
