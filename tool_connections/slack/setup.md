---
name: slack-setup
description: Set up Slack connection. Auth is browser session — no API token page exists. Only input needed from the user is any Slack message URL from their workspace.
---

# Slack — Setup

## Auth method: browser session

Slack is accessed through a browser session stored in the shared profile. No API token page exists. No admin approval needed.

**What to ask the user:** "Send me any Slack message link from your workspace (right-click any message → Copy link)."

That is the only input needed. Everything else is automated.

> **Note:** Slack AI (natural-language Q&A) requires Business+ or Enterprise+ plan. On Free/Pro plans, `search.messages` still works for keyword search.

---

## Steps

1. Extract the workspace URL from the message link the user provides:
   - e.g. `https://acme.slack.com/archives/C.../p...` → `https://acme.slack.com/`
2. Update `SLACK_WORKSPACE_URL` in `.env`
3. Capture the browser session:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --slack-only
```

The script opens a Chromium window. Sign in through the browser if prompted. The session is saved to `~/.browser_automation/profile/` — nothing auth-related goes to `.env`.

For multiple Slack workspaces, use account-scoped keys. The account name is
normalized to an uppercase `.env` prefix:

```bash
# .env
SLACK_ACME_WORKSPACE_URL=https://acme.slack.com/

source .venv/bin/activate
python3 shared_utils/playwright_sso.py --slack-only --account acme
```

That uses `SLACK_ACME_WORKSPACE_URL` in `.env` to target the acme workspace (same shared browser profile).

---

## Verify

```python
from shared_utils.session_request import tool_request

result = tool_request("slack", "GET", "https://slack.com/api/auth.test")
data = result.get("json") or {}
print(data.get("user"), data.get("team"))
# → alice  your-workspace
# If ok=False: session expired — run playwright_sso.py --slack-only to refresh
```

---

## `.env` entries

```bash
# --- Slack ---
# Instance URL only — auth stays in ~/.browser_automation/profile/
# Refresh session: python3 shared_utils/playwright_sso.py --slack-only
SLACK_WORKSPACE_URL=https://yourcompany.slack.com/

# Optional second workspace:
SLACK_ACME_WORKSPACE_URL=https://acme.slack.com/
```

---

## Refresh

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --slack-only

# Refresh a named workspace/account:
python3 shared_utils/playwright_sso.py --slack-only --account acme
```

Session TTL: ~8h. Re-run when `auth.test` via `session_request` returns `ok=False`.
