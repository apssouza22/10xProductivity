---
name: airflow-setup
description: Set up Apache Airflow via browser sign-in. Minimum input is the Airflow URL.
---

# Airflow — Setup

## Auth method: browser session

Airflow FAB login stores a `session` cookie in `~/.browser_automation/agent_profile/`. **API calls use that session only** — never username/password or Basic auth on REST endpoints.

**What to ask the user:** "Share your Airflow URL" (e.g. `http://localhost:8080` or `https://airflow.company.com`).

---

## Steps

1. Set `AIRFLOW_BASE_URL` in `.env` from the URL the user provided
2. Capture the browser session:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --airflow-only
```

Sign in at `/login` when prompted. Session is saved to `~/.browser_automation/agent_profile/`.

---

## Verify

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["AIRFLOW_BASE_URL"].rstrip("/")
headers = {"Accept": "application/json"}

result = tool_request("airflow", "GET", f"{base}/api/v1/dags?limit=3", headers=headers, via_page_fetch=True)
print(result.get("ok"), (result.get("json") or {}).get("total_entries"))
# → True 2
# If ok is False or redirect to /login: run playwright_sso.py --airflow-only again
```

**Connection details:** `tool_connections/airflow/connection-sso.md`

---

## `.env` entries

```bash
# --- Airflow ---
# Instance URL only — auth stays in ~/.browser_automation/agent_profile/
# Refresh session: python3 shared_utils/playwright_sso.py --airflow-only
AIRFLOW_BASE_URL=http://localhost:8080
```

---

## Refresh

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --airflow-only
```

Session TTL: varies by instance (local FAB often ~30 days).
