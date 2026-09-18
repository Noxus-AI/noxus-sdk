# Deployments (Channels) & Triggers

`client.deployments` publishes an agent to a **channel** (embed widget, Slack,
form, …). `client.triggers` reads and manages **workflow** triggers and the
events they receive.

## Deployments

A deployment is "this agent, on this channel, with this config". It starts
inactive; **activate** builds its trigger and goes live.

### Discover channels

```python
for ch in client.deployments.list_channels():
    print(ch["channel_type"], ch["label"])   # channel_type is what you pass to create()
```

### Create → activate

```python
dep = client.deployments.create(
    agent_id,
    channel_type="embed_widget",             # from list_channels()
    name="Website widget",
    alias="acme-support",                    # optional stable public handle
    config={},                               # channel-specific, validated server-side
    assistant_version_id=None,               # pin a version (required before activate)
)
client.deployments.activate(agent_id, dep["id"])     # publish (needs a pinned version)
```

Deployments and their `config` are returned as plain dicts (secrets redacted).
Activation requires `assistant_version_id` to be set and the agent version to be
valid.

### Manage

```python
client.deployments.list(agent_id)                    # -> list[dict]
client.deployments.get(agent_id, deployment_id)
client.deployments.update(agent_id, deployment_id, {"name": "New name"})  # patch; alias:None clears it
client.deployments.deactivate(agent_id, deployment_id)
client.deployments.delete(agent_id, deployment_id)   # -> bool (deactivates first)
```

Mutating an **active** deployment's `config` or `assistant_version_id` rebuilds
its trigger automatically.

### Events

The events the deployment's trigger has received (deliveries, failures):

```python
client.deployments.list_events(agent_id, deployment_id, page=1, page_size=10)
for event in client.deployments.iter_events(agent_id, deployment_id):   # auto-paginate
    print(event)
```

Async twins throughout: `acreate`, `aactivate`, `adeactivate`, `aupdate`,
`adelete`, `alist`, `aget`, `alist_channels`, `alist_events`, `aiter_events`.

## Triggers (workflow)

Triggers fire a **workflow** on an external event (schedule, webhook, …).

```python
# read
client.triggers.list(workflow_id, page=1, page_size=10)          # -> list[dict]
client.triggers.list_events(workflow_id, trigger_id, search=None)
for ev in client.triggers.iter_events(workflow_id, trigger_id):  # auto-paginate
    print(ev)

# all events across the workspace, filtered
client.triggers.events(event_type="webhook", workflow_id=workflow_id, started_run=True)

# create / update / delete
client.triggers.create(workflow_id, definition={"type": "schedule", ...}, workflow_version_id="v-1")
client.triggers.update(workflow_id, trigger_id, definition={...}, workflow_version_id=None)
client.triggers.delete(trigger_id)                               # -> bool
```

`definition` is the trigger config dict (its shape depends on `type`). A trigger
is pinned to a `workflow_version_id`. Every method has an `a`-prefixed async twin.

> Agent triggers (as opposed to workflow triggers) are managed from an `Agent`
> object: `agent.add_trigger(trigger_data)` and `agent.triggers()`.
