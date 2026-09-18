# Agents, Conversations & Insights

`client.agents` manages agents ("co-workers"); `client.conversations` chats with
them; `client.insights` reads their analytics dashboards.

## Agents

```python
from noxus_sdk.resources.assistants import AgentSettings

settings = AgentSettings(
    model=["gpt-4o-mini"],
    temperature=0.7,
    max_tokens=4000,
    tools=[],                       # required (empty list = no tools)
    extra_instructions="Be concise and friendly.",
    persona=None, tone=None,        # optional
)
agent = client.agents.create(name="Support Bot", settings=settings)
```

`AgentSettings` fields: `model: list[str]`, `temperature: float`, `max_tokens`
(default 64000), `tools: list[...]` (required — the discriminated tool union:
web_research, kb_qa, workflow, code_execution, sandbox, …), `persona`, `tone`,
`extra_instructions`, `agent_flow_id`.

### CRUD & lifecycle

```python
client.agents.list()                         # -> list[Agent]
client.agents.get(agent_id)                  # -> Agent
client.agents.update(agent_id, name=None, settings=None, preview=False)
client.agents.delete(agent_id)
client.agents.duplicate(agent_id)            # -> new Agent
client.agents.publish(agent_id)              # publish the current draft as a version
client.agents.restore(agent_id)              # restore last published
client.agents.list_versions(agent_id, page=1, page_size=10)
client.agents.get_tool_schemas()             # -> dict of available tool configs
```

`update(..., preview=True)` returns what the change *would* look like without
saving. From an `Agent` object you can call `.update(name, settings)`,
`.delete()`, and `.triggers()` / `.add_trigger(trigger_data)` directly.

### Export / import

```python
blob = client.agents.export(agent_id, version="auto", version_id=None,
                            set_active_on_import=False)          # -> bytes
client.agents.export_preview(agent_id)                          # -> dict
client.agents.import_(blob, version="auto", mode="clone",
                      activate=False, dry_run=False)            # -> list[dict]
```

`mode` is `"clone" | "version" | "replace"`; `dry_run=True` validates only.

## Conversations

A conversation is a chat session, optionally bound to an agent (`agent_id`) or
configured inline with `ConversationSettings` (same shape as `AgentSettings`).

```python
from noxus_sdk.resources.conversations import ConversationSettings, MessageRequest

# bound to an existing agent
convo = client.conversations.create(name="Chat", agent_id=agent_id)

# or configured inline
convo = client.conversations.create(
    name="Chat",
    settings=ConversationSettings(model=["gpt-4o-mini"], temperature=0.7, tools=[]),
)
```

### Sending messages

`MessageRequest` fields: `content: str` (required), `tool` (`"web_research" |
"kb_qa" | "workflow" | <custom>`), `kb_id`, `workflow_id`, `files`,
`model_selection`.

```python
# blocking — returns the assistant's ChatMessage
reply = convo.chat(MessageRequest(content="Summarize our refund policy"))

# fire-and-store without waiting for the full reply object
convo.add_message(MessageRequest(content="hello"))

# read history
messages = convo.get_messages()              # -> list[Message]
```

### Streaming

```python
for event in convo.stream(MessageRequest(content="Tell me a long story"),
                          format="json"):     # or "vercel"
    print(event)

async for event in convo.astream(MessageRequest(content="...")):
    print(event)
```

`stream` / `astream` yield `StreamEvent`s (tokens, tool calls, completion).
`iter_messages` / `aiter_messages` replay a conversation's events.

### Managing conversations

```python
client.conversations.list(page=1, page_size=10)
client.conversations.get(conversation_id)
client.conversations.update(conversation_id, name=None, settings=None)
client.conversations.delete(conversation_id)
convo.refresh()                              # re-fetch latest state
```

## Insights (agent dashboards)

Read-only analytics computed over an agent's conversations. Every metric takes an
`agent_id` and optional `days` (window), `deployment_id` (scope to one channel),
and `message_length` (`"short" | "medium" | "long"`). All return `dict`s.

```python
client.insights.bootstrap_status(agent_id)           # is analytics ready yet?
client.insights.top_topics(agent_id, days=30, limit=10)
client.insights.sub_topics(agent_id, parent="billing", days=30)
client.insights.csat_score(agent_id, days=7)
client.insights.sentiment_over_time(agent_id, days=30)
client.insights.rating_drivers(agent_id, days=30, limit=8)
client.insights.conversation_funnel(agent_id, days=30)
client.insights.custom_insights(agent_id, days=30, limit=20)
client.insights.noticed(agent_id, limit=12)          # auto-surfaced highlights

# drill from a chart into the underlying conversations
client.insights.conversations(
    agent_id, kind="topic", key="billing", days=30, limit=20,
)   # kind: "topic" | "subtopic" | "driver" | "custom" | "cx"
```

Each has an `a`-prefixed async twin (`atop_topics`, `acsat_score`, …).
