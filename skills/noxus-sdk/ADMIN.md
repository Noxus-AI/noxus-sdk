# Admin, Variables, Files & Analytics

Cross-cutting workspace and tenant management, plus variables/secrets, raw file
transfer, and usage analytics.

## Workspaces, users, teams, roles and system keys with `client.admin`

`get_me` tells you who the key is; `client.admin.enabled` is set from it when
`load_me=True`. **Tenant-level** operations (users, workspaces, roles, system
keys) require a **tenant-admin / system key**, not an ordinary workspace key.

```python
me = client.admin.get_me()          # -> ApiKey: id, name, tenant_admin, value, last_4_bytes, permissions
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

### Organization teams

A system key with `users:read` can list teams and read their members. Managing teams and direct memberships requires `org:admin`.

For an external SCIM bridge, keep the Noxus team ID alongside the directory group ID. Resolve directory users to Noxus user IDs before applying membership updates.

```python
team = client.admin.create_team("Support", user_ids=[ada_id])
client.admin.add_team_member(team.id, bo_id)
client.admin.remove_team_member(team.id, ada_id)
team = client.admin.replace_team_members(team.id, [bo_id, cam_id])
```

Use `replace_team_members` when the directory owns the complete list of direct members. It replaces all direct grants, including those entered by administrators. An empty list clears all direct grants. Independent SAML grants still apply. Use `add_team_member` and `remove_team_member` for individual changes.

`list_teams()`, `get_team(team_id)`, `create_team(name)`, and `rename_team(team_id, name)` return teams with their effective members. Each member has an `id`, `email`, `display_name`, and `saml_only`. A member with `saml_only=True` has access solely through SAML. Use `delete_team(team_id)` to remove the team and its access grants. Each method has an async counterpart, such as `await client.admin.areplace_team_members(team_id, user_ids)`.

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

`ApiKey` fields: `id`, `name`, `tenant_admin`, `last_4_bytes`, `permissions`, and
`value`, the key itself, which only the create calls and `get_me` return
(`list_system_keys` sends it empty for older SDKs, and this SDK reads that as `None`).

`tenant_admin` is deprecated: it is still sent and accepted, and is now derived from the key's roles.

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
