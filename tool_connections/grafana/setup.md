---
name: grafana-setup
description: Set up Grafana connection. Auth is browser session. Only input needed from the user is the Grafana URL.
---

# Grafana — Setup

## Auth method: browser session

Grafana is accessed through a browser session in `~/.browser_automation/grafana_profile/`. No API token page needed for instances that support web login.

**What to ask the user:** "Share your Grafana URL" (e.g. `https://grafana.acme.com`).

That is the only input needed. Set `GRAFANA_BASE_URL` in `.env`, then capture the session.

> **Alternative:** If your Grafana instance uses API keys instead of web login, use `connection-api-key.md` instead (ask for the API key directly — no browser automation needed).

---

## Steps

1. Set `GRAFANA_BASE_URL` in `.env` from the URL the user provided
2. Capture the browser session:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --grafana-only
```

Sign in through the browser if prompted. Session is saved to `~/.browser_automation/grafana_profile/`.

---

## Verify

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["GRAFANA_BASE_URL"].rstrip("/")
result = tool_request("grafana", "GET", f"{base}/api/user")
print(result.get("json"))
# → {"login": "alice", "email": "alice@example.com", "name": "Alice Smith"}
# If 401/redirect: session expired — run playwright_sso.py --grafana-only to refresh
```

**Connection details:** `tool_connections/grafana/connection-sso.md`

---

## `.env` entries

```bash
# --- Grafana ---
# Instance URL only — auth stays in ~/.browser_automation/grafana_profile/
# Refresh session: python3 shared_utils/playwright_sso.py --grafana-only
GRAFANA_BASE_URL=https://grafana.yourcompany.com
```

---

## Refresh

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --grafana-only
```

Session TTL: ~8h.
