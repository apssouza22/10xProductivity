---
name: slack-setup
description: Set up Slack connection. Auth is SSO browser session — no API token page exists. Only input needed from the user is any Slack message URL from their workspace.
---

# Slack — Setup

## Auth method: SSO browser session

Slack uses a short-lived client token (`xoxc`) + cookie (`d`) captured from your browser session after SSO. No API token page exists. No admin approval needed.

**What to ask the user:** "Send me any Slack message link from your workspace (right-click any message → Copy link)."

That is the only input needed. Everything else is automated.

> **Note:** Slack AI (natural-language Q&A) requires Business+ or Enterprise+ plan. On Free/Pro plans, `search.messages` still works for keyword search.

---

## Steps

1. Extract the workspace URL from the message link the user provides:
   - e.g. `https://acme.slack.com/archives/C.../p...` → `https://acme.slack.com/`
2. Update `SLACK_WORKSPACE_URL` in `.env`
3. Run the SSO script:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --slack-only
```

The script opens a Chromium window. On managed machines with enterprise SSO it completes automatically (~20s). On personal machines, the user logs in once through the browser. The session is saved to `~/.browser_automation/profile/` — nothing auth-related goes to `.env`.

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

Token TTL: ~8h. Re-run when `auth.test` via `session_request` returns `ok=False`.

## Verified multi-workspace setup

The default and account-scoped flows were both tested with real Slack sessions
and scrubbed output:

```text
$ python3 shared_utils/playwright_sso.py --slack-only
# → slack: ok
# → auth.test: ok=True, team=primary-workspace, user=alice
# → conversations.open: ok=True, channel=D0123456789
# → chat.postMessage: ok=True

$ python3 shared_utils/playwright_sso.py --slack-only --account sideproject
# → slack:sideproject: ok
# → auth.test: ok=True, team=sideproject-workspace, user=alice
# → conversations.open: ok=True, channel=D9876543210
# → chat.postMessage: ok=True
```

Failure case: private workspaces that use Google sign-in may show `This browser
or app may not be secure` in Playwright-controlled Chromium. If the scoped
`SLACK_<ACCOUNT>_XOXC` and `SLACK_<ACCOUNT>_D_COOKIE` values are still valid,
the refresher validates them and skips browser login. If they are expired, log
in through the opened browser manually or refresh from an already trusted
browser session.
