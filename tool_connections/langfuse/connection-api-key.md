---
tool: langfuse
auth: api-key
description: Langfuse LLM observability — query traces, observations, errors, and costs. Use when investigating agent/LLM failures, finding slow or expensive runs, or correlating trace IDs with incidents.
env_vars:
  - LANGFUSE_BASE_URL
  - LANGFUSE_PROJECT_ID
  - LANGFUSE_PUBLIC_KEY
  - LANGFUSE_SECRET_KEY
---

# Langfuse — API keys

LLM tracing and observability. Query traces and observations for incident investigation.

API docs: https://langfuse.com/docs/api-and-data-platform/features/public-api

**Verified:** Langfuse Cloud EU (`https://cloud.langfuse.com`) — `/api/public/projects`, `/api/public/v2/observations` — 2026-08.

---

## Credentials

```bash
# Add to .env:
# LANGFUSE_BASE_URL=https://cloud.langfuse.com
# LANGFUSE_PROJECT_ID=your-project-id
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
# Generate at: project → Settings → API Keys
```

**Regions:** `https://cloud.langfuse.com` (EU), `https://us.cloud.langfuse.com` (US), `https://jp.cloud.langfuse.com` (JP).

---

## Auth

Basic Auth — public key as username, secret key as password.

```python
import base64
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE, urlopen

env = load_env_file(DEFAULT_ENV_FILE)
auth = base64.b64encode(
    f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}".encode()
).decode()
headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
```

---

## Verified snippets

```python
import base64
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE, urlopen

env = load_env_file(DEFAULT_ENV_FILE)
base = env["LANGFUSE_BASE_URL"].rstrip("/")
auth = base64.b64encode(
    f"{env['LANGFUSE_PUBLIC_KEY']}:{env['LANGFUSE_SECRET_KEY']}".encode()
).decode()
headers = {"Authorization": f"Basic {auth}", "Accept": "application/json"}
project_id = env["LANGFUSE_PROJECT_ID"]

# List projects (auth check)
req = urlopen(f"{base}/api/public/projects", headers=headers)
print(json.loads(req.read().decode()))
# → {"data": [{"id": "...", "name": "my-project", ...}]}

# Recent root observations (proxy for traces) — always bound the time window
to_time = datetime.now(timezone.utc)
from_time = to_time - timedelta(hours=24)
params = urlencode({
    "fromStartTime": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "toStartTime": to_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "isRootObservation": "true",
    "limit": 20,
    "fields": "core,basic,usage,trace_context",
})
req = urlopen(f"{base}/api/public/v2/observations?{params}", headers=headers)
obs = json.loads(req.read().decode())
print([{"traceId": o["traceId"], "name": o.get("name"), "level": o.get("level")} for o in obs["data"]])
# → [{"traceId": "abc-123", "name": "agent-run", "level": "ERROR"}, ...]

# Observations for a specific trace (include I/O for debugging)
trace_id = "your-trace-id"
params = urlencode({
    "traceId": trace_id,
    "fields": "core,basic,io,usage,model",
    "limit": 100,
})
req = urlopen(f"{base}/api/public/v2/observations?{params}", headers=headers)
print(json.loads(req.read().decode()))
# → {"data": [...], "meta": {"cursor": "..."}}

# Filter errors in the last 7 days
to_time = datetime.now(timezone.utc)
from_time = to_time - timedelta(days=7)
params = urlencode({
    "fromStartTime": from_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "toStartTime": to_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "filter": json.dumps([{"type": "string", "column": "level", "operator": "=", "value": "ERROR"}]),
    "limit": 50,
    "fields": "core,basic,trace_context",
})
req = urlopen(f"{base}/api/public/v2/observations?{params}", headers=headers)
print(json.loads(req.read().decode()))
```

**Trace UI link pattern:**

```
{LANGFUSE_BASE_URL}/project/{LANGFUSE_PROJECT_ID}/traces/{traceId}
```

---

## Agent behavior

**Read actions — run freely, no approval needed:**
- List projects (`GET /api/public/projects`)
- Query observations v2 (`GET /api/public/v2/observations`) with time bounds
- Query metrics v2 (`GET /api/public/v2/metrics`) for aggregates
- Fetch scores (`GET /api/public/v2/scores`)

**Write actions — show preview, get explicit user approval before executing:**
- Create/update prompts, datasets, scores, annotation queues
- Ingest traces (use OTEL endpoint only with approval)

---

## Notes

- Prefer **Observations API v2** over deprecated `/api/public/traces`. Group by `traceId` to reconstruct a trace.
- Always include `fromStartTime` and `toStartTime` on list queries to avoid huge responses.
- `input`/`output` are raw strings in v2 — `json.loads()` in your pipeline when needed.
- Request `fields=io` only when you need prompt/completion content (larger payloads).
- No native full-text search API — filter by `name`, `userId`, `traceId`, `level`, `environment`, or advanced `filter` JSON.
- Langfuse Cloud enforces API rate limits per organization.
