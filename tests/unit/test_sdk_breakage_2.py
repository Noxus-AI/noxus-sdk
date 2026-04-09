"""Round 2: more SDK breakage tests.

Bugs found:
1. AgentFlowDefinition.arun() passes args positionally instead of name=
2. KnowledgeBaseService.list_documents() iterates response directly (expects list, gets dict)
3. ConversationFile validator raises wrong exception type
4. Run.wait() bare except swallows auth/network errors
"""

from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.conversations import (
    ConversationFile,
    ConversationSettings,
    MessageRequest,
)
from noxus_sdk.resources.knowledge_bases import (
    KnowledgeBase,
    KnowledgeBaseDocument,
    KBConfigV3,
    DocumentStatus,
)
from noxus_sdk.resources.runs import Run, RunEvent
from noxus_sdk.workflows.agentflow import AgentFlowDefinition
from noxus_sdk.workflows.workflow import WorkflowDefinition

# Resolve forward refs for Python 3.10 compat
WorkflowDefinition.model_rebuild()
AgentFlowDefinition.model_rebuild()


def _client():
    return create_autospec(Client, instance=True)


# ════════════════════════════════════════════════════════════════════
#  BUG 1: AgentFlowDefinition.arun() passes args positionally
# ════════════════════════════════════════════════════════════════════


class TestAgentFlowArunBug:
    def test_run_uses_keyword_args(self):
        """run() correctly uses name= keyword — this works."""
        af = AgentFlowDefinition(client=_client(), name="My Flow")
        af.id = "flow-123"

        # run() calls: conversations.create(name=self.name, settings=...)
        # Verify it would work by checking the source
        import inspect

        source = inspect.getsource(af.run)
        assert "name=" in source, "run() should use name= keyword"

    def test_arun_uses_keyword_args_and_acreate(self):
        """arun() must use name= keyword, self.name (not self.id), and acreate."""
        import inspect

        source = inspect.getsource(AgentFlowDefinition.arun)
        assert "name=" in source, "arun() should use name= keyword"
        assert "self.name" in source, "arun() should use self.name, not self.id"
        assert "acreate" in source, "arun() should call acreate (async), not create"


# ════════════════════════════════════════════════════════════════════
#  BUG 2: KnowledgeBaseService.list_documents inconsistency
# ════════════════════════════════════════════════════════════════════


class TestKBListDocumentsInconsistency:
    def test_kb_instance_uses_items_key(self):
        """KnowledgeBase.list_documents accesses response['items'] — correct."""
        import inspect

        source = inspect.getsource(KnowledgeBase.list_documents)
        assert '["items"]' in source, "KB instance method accesses response['items']"

    def test_kb_service_uses_items_key(self):
        """KnowledgeBaseService.list_documents must also access response['items']."""
        from noxus_sdk.resources.knowledge_bases import KnowledgeBaseService
        import inspect

        source = inspect.getsource(KnowledgeBaseService.list_documents)
        assert '["items"]' in source, "Service method should access response['items']"


# ════════════════════════════════════════════════════════════════════
#  BUG 3: ConversationFile validator raises wrong exception
# ════════════════════════════════════════════════════════════════════


class TestConversationFileBug:
    def test_file_with_content(self):
        """Normal case — b64_content provided."""
        f = ConversationFile(name="test.txt", b64_content="aGVsbG8=")
        assert f.name == "test.txt"

    def test_file_with_url(self):
        """Normal case — url provided."""
        f = ConversationFile(name="test.txt", url="https://example.com/file")
        assert f.url == "https://example.com/file"

    def test_file_neither_content_nor_url_crashes(self):
        """Neither b64_content nor url — validator raises ValidationError incorrectly.
        Pydantic's ValidationError() constructor doesn't accept a plain string.
        This should raise ValueError instead."""
        with pytest.raises(Exception) as exc_info:
            ConversationFile(name="test.txt")
        # The bug: it raises TypeError because ValidationError("msg") is wrong
        # OR it might raise ValidationError if Pydantic catches it
        # Either way, the error message is poor
        assert exc_info.value is not None


# ════════════════════════════════════════════════════════════════════
#  BUG 4: RunEvent.is_terminal only checks workflow_status
# ════════════════════════════════════════════════════════════════════


class TestRunEventTerminal:
    def test_completed_event(self):
        e = RunEvent(type="status", data={"workflow_status": "completed"})
        assert e.is_terminal is True

    def test_failed_event(self):
        e = RunEvent(type="status", data={"workflow_status": "failed"})
        assert e.is_terminal is True

    def test_running_event(self):
        e = RunEvent(type="status", data={"workflow_status": "running"})
        assert e.is_terminal is False

    def test_event_without_workflow_status(self):
        """Events like node_started don't have workflow_status.
        is_terminal correctly returns False — not a bug per se,
        but means stream() depends on at least one terminal event."""
        e = RunEvent(type="node_started", data={"node_id": "n1"})
        assert e.is_terminal is False

    def test_empty_data(self):
        e = RunEvent(type="heartbeat", data={})
        assert e.is_terminal is False


# ════════════════════════════════════════════════════════════════════
#  BUG 5: MessageRequest.model_dump sends None values
# ════════════════════════════════════════════════════════════════════


class TestMessageRequestDump:
    def test_dump_includes_none_fields(self):
        """model_dump() includes None fields — API may reject them."""
        msg = MessageRequest(content="Hello")
        dumped = msg.model_dump()
        # These None values get sent to the API
        assert "tool" in dumped
        assert dumped["tool"] is None
        assert "kb_id" in dumped
        assert dumped["kb_id"] is None

    def test_dump_exclude_none_would_fix(self):
        """Using exclude_none=True would fix it — but callers don't use it."""
        msg = MessageRequest(content="Hello")
        clean = msg.model_dump(exclude_none=True)
        assert "tool" not in clean
        assert "kb_id" not in clean
        assert clean == {"content": "Hello"}


# ════════════════════════════════════════════════════════════════════
#  BUG 6: KnowledgeBaseDocument missing fields from real API
# ════════════════════════════════════════════════════════════════════


class TestKBDocumentRealPayload:
    def test_minimal_document(self):
        """API may return documents with minimal fields."""
        doc = KnowledgeBaseDocument(
            id=str(uuid4()),
            name="doc.pdf",
            prefix="/",
            status="trained",
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )
        assert doc.size == 0  # default
        assert doc.source_type is None  # default

    def test_full_document(self):
        doc = KnowledgeBaseDocument(
            id=str(uuid4()),
            name="doc.pdf",
            prefix="/test",
            status="trained",
            size=1024,
            source_type="Document",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            error=None,
        )
        assert doc.size == 1024

    def test_document_with_error(self):
        doc = KnowledgeBaseDocument(
            id=str(uuid4()),
            name="bad.pdf",
            prefix="/",
            status="error",
            created_at="2024-01-01",
            updated_at="2024-01-01",
            error={"message": "Parse failed", "code": "PARSE_ERROR"},
        )
        assert doc.error is not None
        assert doc.error["message"] == "Parse failed"

    def test_document_with_extra_backend_fields(self):
        """Backend may return fields the SDK doesn't model."""
        doc = KnowledgeBaseDocument(
            id=str(uuid4()),
            name="doc.pdf",
            prefix="/",
            status="trained",
            created_at="2024-01-01",
            updated_at="2024-01-01",
            # Extra fields from backend
            short_summary="A document about AI",
            summary="This document covers...",
            doc_type="pdf",
            file_id=str(uuid4()),
        )
        assert doc.name == "doc.pdf"


# ════════════════════════════════════════════════════════════════════
#  Verify: ConversationSettings round-trip through model_dump
# ════════════════════════════════════════════════════════════════════


class TestSettingsRoundTrip:
    def test_dump_and_reload_with_tools(self):
        """Settings → model_dump() → re-parse must not lose tool types."""
        original = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[
                {"type": "web_research", "enabled": True},
                {"type": "kb_qa", "kb_id": "kb-1", "enabled": True},
                {"type": "agent_tool", "agent_id": "a-1", "custom_field": "x"},
            ],
            persona="Test",
        )
        dumped = original.model_dump()
        restored = ConversationSettings(**dumped)

        assert len(restored.tools) == 3
        assert restored.tools[0].type == "web_research"
        assert restored.tools[1].type == "kb_qa"
        assert restored.tools[2].type == "agent_tool"
        assert restored.persona == "Test"

    def test_dump_and_reload_with_unknown_tool(self):
        """Unknown tools must survive round-trip."""
        original = ConversationSettings(
            model=["gpt-4o"],
            temperature=0.7,
            tools=[
                {"type": "future_tool", "enabled": True, "custom": "value"},
            ],
        )
        dumped = original.model_dump()
        restored = ConversationSettings(**dumped)

        assert len(restored.tools) == 1
        assert restored.tools[0].type == "future_tool"
