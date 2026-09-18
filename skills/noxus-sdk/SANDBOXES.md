# Sandboxes

`client.sandboxes` gives you ephemeral, network-jailed code-execution
environments (gVisor microVMs) with `noxus-sdk` pre-installed. Use them to run
untrusted or one-off code — data processing, generating a file, running an SDK
script against the platform.

## Lifecycle

```python
sb = client.sandboxes.create(label="my-job", persistent=False)   # -> Sandbox
client.sandboxes.list()                                          # -> list[Sandbox]
client.sandboxes.get(sandbox_id)
client.sandboxes.delete(sandbox_id)                              # -> bool
sb.kill()                                                        # same as delete, on the object
sb.refresh()                                                     # re-fetch status
```

`persistent=False` sandboxes are cheap and cleaned up when idle; pass
`persistent=True` only if you need it to survive between calls. `Sandbox` fields:
`id`, `status`, `created_at`, `last_activity`, `label`.

## Prefer the context manager — it always tears down

```python
with client.sandboxes.create(label="job") as sb:
    sb.files.write("/work/data.json", '{"n": 1}')
    result = sb.commands.run("cat /work/data.json")
    print(result.stdout)
# sandbox is killed on exit, even if the block raises

async with await client.sandboxes.acreate() as sb:   # async form
    ...
```

## Run commands

```python
result = sb.commands.run("python -c 'print(2+2)'", timeout=60)
# Execution fields:
result.stdout       # str
result.stderr       # str
result.exit_code    # int
result.timed_out    # bool
```

## Read & write files

```python
sb.files.write("/work/script.py", "print('hi')")     # str or bytes
sb.files.write("/work/blob.bin", b"\x00\x01")
content = sb.files.read("/work/script.py")            # -> str
raw = sb.files.read_bytes("/work/blob.bin")           # -> bytes
```

## Recipe: run an SDK script inside the sandbox

The sandbox can call the Noxus API itself (it has `noxus_sdk` baked in). Inject a
scoped key and backend URL as env vars, then run the script:

```python
script = """
import os
from noxus_sdk.client import Client
c = Client.from_env()
print([kb.name for kb in c.knowledge_bases.list()])
"""
with client.sandboxes.create(label="sdk-run") as sb:
    sb.files.write("/work/run.py", script)
    out = sb.commands.run(
        "export NOXUS_API_KEY=... NOXUS_BACKEND_URL=https://backend.noxus.ai; "
        "python /work/run.py"
    )
    print(out.stdout, "exit", out.exit_code)
```

> The sandbox network jails RFC1918 but NATs out, so the backend must be
> reachable at a **public** URL from inside the sandbox for the SDK-in-sandbox
> pattern to work.

Async twins exist throughout: `client.sandboxes.acreate` / `alist` / `aget` /
`adelete`; `sb.akill` / `sb.arefresh`; `sb.commands.arun`; and
`sb.files.awrite` / `aread` / `aread_bytes`.
