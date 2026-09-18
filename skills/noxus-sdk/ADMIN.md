# Admin, Variables, Files & Analytics

Cross-cutting workspace and tenant management, plus variables/secrets, raw file
transfer, and usage analytics.

## `client.admin` — workspaces, users, roles, system keys

`get_me` tells you who the key is; `client.admin.enabled` is set from it when
`load_me=True`. **Tenant-level** operations (users, workspaces, roles, system
keys) require a **tenant-admin / system key**, not an ordinary workspace key.

```python
me = client.admin.get_me()          # -> ApiKey: id, name, tenant_admin, value, permissions
```

### Workspaces

```python
client.admin.list_workspaces()                       # -> list[Workspace]
ws = client.admin.create_workspace("Marketing", description="…")   # -> Workspace
ws.delete()                                          # on the Workspace object
ws.add_api_key(...)                                  # mint a workspace key
```

`Workspace` fields: `id`, `name`, `description`.

### Users (tenant)

```python
client.admin.list_users()           # -> list[TenantUser]: id, email, display_name, tenant_admin, is_active
```

### Roles

```python
client.admin.list_roles()                            # -> list[dict]
client.admin.create_role("Editor", permissions={"resource:edit": True}, description="…")
client.admin.delete_role(role_id)
```

### System keys (tenant-scoped)

System keys live in the tenant's hidden **admin** workspace and may carry
tenant-wide permissions (`users:*`, `workspace:*`, `providers:manage`,
`org:*`, `billing:manage`) — ordinary workspace keys cannot. Mint them here:

```python
client.admin.list_system_keys()                      # -> list[ApiKey]
key = client.admin.create_system_key(
    "ci-bot", permissions=["users:read", "workspace:read"], tenant_admin=False
)
print(key.value)                                     # the secret — shown once
client.admin.delete_system_key(key.id)
```

`ApiKey` fields: `id`, `name`, `tenant_admin`, `value`, `permissions`.

## `client.variables` — variables & secrets

Workspace-scoped key/value config. `kind="secret"` values are write-only (never
returned on read).

```python
client.variables.list()                              # -> list[dict] (secret values stripped)
client.variables.create(
    "API_BASE",
    value="https://api.example.com",
    kind="variable",          # "variable" | "secret"
    value_type="string",      # string | number | boolean | object | datetime | file
    source="inline",          # inline | vault | environment
)
client.variables.update(variable_id, {"value": "…"})
client.variables.delete(variable_id)                 # -> bool
# escape hatch for the full payload shape:
client.variables.create_raw({"name": "X", "value": "…", "kind": "variable"})
```

## `client.files` — raw file transfer

```python
with open("report.pdf", "rb") as fd:
    f = client.files.save(fd)         # -> File (has an id/spot-uri)
data = client.files.get(f.id)         # -> bytes
```

Files are how you pass binary content to workflow/KB inputs that expect a file.

## `client.analytics` — usage metrics

```python
from datetime import datetime, timedelta

end = datetime.utcnow()
start = end - timedelta(days=30)
result = client.analytics.get("runs", start, end, page=1, page_size=50)
# -> AnalyticsResult
```

`metric` is the platform metric name; the window is `[time_start, time_end]`.
Agent-specific dashboards (CSAT, topics, sentiment) live under
`client.insights` instead — see [AGENTS.md](AGENTS.md).

All methods here have `a`-prefixed async twins.
