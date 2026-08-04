---
name: langfuse-setup
description: Set up Langfuse (LLM observability) via browser sign-in. Minimum input is a Langfuse project URL.
---

# Langfuse — Setup

## Auth method: browser session

Langfuse Cloud uses browser sign-in (Google/GitHub/email). Auth stays in `~/.browser_automation/agent_profile/` — not in `.env`.

**What to ask the user:** a Langfuse project URL (e.g. `https://cloud.langfuse.com/project/your-project-id/traces`).

From the URL we infer:
- `LANGFUSE_BASE_URL` — host (`https://cloud.langfuse.com`, `https://us.cloud.langfuse.com`, etc.)
- `LANGFUSE_PROJECT_ID` — segment after `/project/`

---

## Steps

1. Set `LANGFUSE_BASE_URL` and `LANGFUSE_PROJECT_ID` in `.env` from the URL
2. Capture the browser session:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --langfuse-only
```

Sign in through the browser when prompted. Session is saved to `~/.browser_automation/agent_profile/`.

---

## Verify

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["LANGFUSE_BASE_URL"].rstrip("/")
project = env["LANGFUSE_PROJECT_ID"]
traces_url = f"{base}/project/{project}/traces"

result = tool_request("langfuse", "GET", traces_url, warmup_url=traces_url, via_page_fetch=True)
print("ok:", result.get("ok"))
print("url:", traces_url)
text = (result.get("body") or "")[:200]
print("snippet:", text)
# → ok: True
# If ok is False or snippet mentions sign-in: run playwright_sso.py --langfuse-only again
```

**Connection details:** `tool_connections/langfuse/connection-sso.md`

**API key alternative:** `tool_connections/langfuse/connection-api-key.md` — for programmatic trace/observation queries.

---

## `.env` entries

```bash
# --- Langfuse ---
# Instance URL and project ID — auth stays in ~/.browser_automation/agent_profile/
# Refresh session: python3 shared_utils/playwright_sso.py --langfuse-only
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_PROJECT_ID=your-project-id
```

---

## Refresh

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --langfuse-only
```

Session TTL: typically days/weeks (depends on Langfuse/IdP). Re-run when traces page redirects to sign-in.
