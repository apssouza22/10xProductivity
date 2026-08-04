---
tool: langfuse
auth: sso-session
description: Langfuse LLM observability — browse traces, investigate agent/LLM failures, find errors and slow runs. Use when investigating LLM incidents or correlating trace IDs from alerts.
env_vars:
  - LANGFUSE_BASE_URL
  - LANGFUSE_PROJECT_ID
sniffer:
  profile: ~/.browser_automation/agent_profile
  url: ${LANGFUSE_BASE_URL}
  filter: /api/trpc
---

# Langfuse — browser session

LLM tracing and observability on Langfuse Cloud. Session auth via NextAuth cookies in the shared browser profile.

**Verified:** Langfuse Cloud EU (`https://cloud.langfuse.com`) — traces UI + tRPC — 2026-08.

---

## Credentials

```bash
# Add to .env:
# LANGFUSE_BASE_URL=https://cloud.langfuse.com
# LANGFUSE_PROJECT_ID=your-project-id
# Auth: browser session in ~/.browser_automation/agent_profile/
# Refresh: python3 shared_utils/playwright_sso.py --langfuse-only
```

**Regions:** `https://cloud.langfuse.com` (EU), `https://us.cloud.langfuse.com` (US), `https://jp.cloud.langfuse.com` (JP).

---

## Auth

Browser session (NextAuth JWT cookies). Refresh with:

```bash
python3 shared_utils/playwright_sso.py --langfuse-only
```

All HTTP calls go through `shared_utils/session_request.py` with `via_page_fetch=True`.

---

## Verified snippets

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["LANGFUSE_BASE_URL"].rstrip("/")
project = env["LANGFUSE_PROJECT_ID"]
traces_url = f"{base}/project/{project}/traces"

# Open traces page (confirms session)
result = tool_request("langfuse", "GET", traces_url, warmup_url=traces_url, via_page_fetch=True)
print("session ok:", result.get("ok"))
# → session ok: True

# Trace detail page by ID
trace_id = "your-trace-id"
trace_url = f"{base}/project/{project}/traces/{trace_id}"
result = tool_request("langfuse", "GET", trace_url, warmup_url=traces_url, via_page_fetch=True)
print("trace page ok:", result.get("ok"))
# → trace page ok: True
```

**Trace UI links** (share with user):

```
{LANGFUSE_BASE_URL}/project/{LANGFUSE_PROJECT_ID}/traces/{traceId}
```

For structured JSON data (filters, pagination, bulk export), prefer **API keys** — see `connection-api-key.md`. Browser session is best for UI reads and quick incident lookups.

---

## Agent behavior

**Read actions — run freely, no approval needed:**
- Fetch traces list page (`/project/{id}/traces`)
- Fetch individual trace pages (`/project/{id}/traces/{traceId}`)
- Fetch sessions, observations, prompts pages in the same project

**Write actions — show preview + target URL, get explicit user approval before executing:**
- Create/edit prompts, datasets, scores, or project settings in the UI
- Delete traces or annotations

---

## Typical actions to capture with the sniffer

```bash
python3 shared_utils/traffic_sniffer.py --tool langfuse
```

Then in the browser: open traces list, filter by error level, open a trace, expand observations.

---

## Notes

- Langfuse web UI uses tRPC at `/api/trpc/*` — session cookies required; use `via_page_fetch=True`.
- Public REST API (`/api/public/*`) uses Basic Auth with project API keys — separate from browser session.
- No full-text search via browser session alone; use UI filters or switch to API keys for programmatic queries.
- Session shared with other tools in `agent_profile` — signing out of Google in that profile may invalidate Langfuse too.
