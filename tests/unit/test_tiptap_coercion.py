"""Unit tests for TipTap rich-text to plain-string coercion on tool and settings models."""

import pytest
from noxus_sdk.resources.conversations import (
    ConversationSettings,
    ConversationTool,
    KnowledgeBaseQaTool,
    NoxusQaTool,
    WebResearchTool,
    WorkflowTool,
)


# ── ConversationTool-level extra_instructions ────────────────────────


class TestToolExtraInstructionsCoercion:
    """extra_instructions on individual tools should accept TipTap payloads."""

    def test_string_passthrough(self):
        tool = WebResearchTool(extra_instructions="Be concise")
        assert tool.extra_instructions == "Be concise"

    def test_none_passthrough(self):
        tool = WebResearchTool(extra_instructions=None)
        assert tool.extra_instructions is None

    def test_dict_tiptap_with_text(self):
        """A TipTap dict with non-empty text should extract the text."""
        tool = KnowledgeBaseQaTool(
            kb_id="some-kb-id",
            extra_instructions={
                "text": "Focus on recent sources",
                "definition": {"type": "doc", "content": [{"type": "paragraph"}]},
            },
        )
        assert tool.extra_instructions == "Focus on recent sources"

    def test_dict_tiptap_empty_text(self):
        """A TipTap dict with empty text (the user's reported case) should become None."""
        tool = KnowledgeBaseQaTool(
            kb_id="some-kb-id",
            extra_instructions={
                "text": "",
                "definition": {"type": "doc", "content": []},
            },
        )
        assert tool.extra_instructions is None

    def test_list_tiptap_parts(self):
        """A list of TipTap parts should concatenate the text fields."""
        tool = NoxusQaTool(
            extra_instructions=[
                {"text": "Part one. "},
                {"text": "Part two."},
            ],
        )
        assert tool.extra_instructions == "Part one. Part two."

    def test_list_tiptap_all_empty(self):
        """A list of TipTap parts that are all empty should become None."""
        tool = NoxusQaTool(
            extra_instructions=[
                {"text": ""},
                {"text": ""},
            ],
        )
        assert tool.extra_instructions is None

    def test_omitted_defaults_to_none(self):
        tool = WebResearchTool()
        assert tool.extra_instructions is None


# ── ConversationSettings-level extra_instructions ────────────────────


class TestSettingsExtraInstructionsCoercion:
    """Top-level extra_instructions on ConversationSettings should also coerce."""

    def test_dict_tiptap_on_settings(self):
        settings = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[],
            extra_instructions={
                "text": "Be helpful",
                "definition": {"type": "doc", "content": []},
            },
        )
        assert settings.extra_instructions == "Be helpful"

    def test_empty_dict_tiptap_on_settings(self):
        settings = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[],
            extra_instructions={
                "text": "",
                "definition": {"type": "doc", "content": []},
            },
        )
        assert settings.extra_instructions is None

    def test_list_tiptap_on_settings(self):
        settings = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[],
            extra_instructions=[
                {"text": "First. "},
                {"text": "Second."},
            ],
        )
        assert settings.extra_instructions == "First. Second."


# ── Full round-trip: settings with tools containing TipTap ───────────


class TestFullSettingsWithTiptapTools:
    """Simulate the exact payload shape that caused the user's ValidationError."""

    def test_agent_definition_with_tiptap_tool_instructions(self):
        """Reproduce the reported bug: kb_qa tool with TipTap extra_instructions."""
        raw_payload = {
            "model": ["gpt-4o"],
            "temperature": 0.7,
            "max_tokens": 64000,
            "tools": [
                {"type": "web_research", "enabled": True, "extra_instructions": None},
                {
                    "type": "kb_qa",
                    "enabled": True,
                    "kb_id": "some-kb-id",
                    "extra_instructions": {
                        "text": "",
                        "definition": {"type": "doc", "content": []},
                    },
                },
            ],
            "persona": {
                "text": "You are helpful.",
                "definition": {"type": "doc", "content": []},
            },
            "tone": None,
            "extra_instructions": {
                "text": "",
                "definition": {"type": "doc", "content": []},
            },
        }
        settings = ConversationSettings(**raw_payload)

        assert settings.persona == "You are helpful."
        assert settings.extra_instructions is None

        kb_tool = next(t for t in settings.tools if t.type == "kb_qa")
        assert kb_tool.extra_instructions is None

        web_tool = next(t for t in settings.tools if t.type == "web_research")
        assert web_tool.extra_instructions is None
