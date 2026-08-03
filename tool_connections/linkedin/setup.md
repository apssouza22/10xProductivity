---
name: linkedin-setup
description: Set up LinkedIn connection using li_at session cookie. No developer app needed. Opens a browser once for login, then reuses the persistent profile.
---

# LinkedIn — Setup

## Auth method: session-cookie (li_at)

LinkedIn has no public API for personal use without app approval. This connection uses your browser session cookie (`li_at`) extracted via Playwright. Sessions are saved to the shared profile at `~/.browser_automation/agent_profile/` so LinkedIn recognizes the device — no 2FA after the first login.

**What to ask the user:** Nothing. Just run `sso.py` — it opens a browser window for login.

---

## Steps

1. Run the session capture script:

```bash
source .venv/bin/activate
python3 personal/linkedin/sso.py   # run from personal/ copy (see setup.md Step 1)
```

2. A Chromium window opens. Log in to LinkedIn (complete 2FA if prompted — this is the only time).
3. Once the feed loads, the session is saved in `~/.browser_automation/agent_profile/`.
4. The browser window closes.

**Second run and beyond:** the script reuses `~/.browser_automation/agent_profile/` and skips straight to feed — no login, no 2FA.

---

## Refresh

Re-run `sso.py` when the session expires (~24h for CSRF, weeks for `li_at`). No `.env` changes needed.

```bash
# Check if session is still valid:
python3 tool_connections/linkedin/sso.py
# → LinkedIn session ok — nothing to do.

# Force refresh:
python3 tool_connections/linkedin/sso.py --force
```

---

## Verify

```python
from shared_utils.session_request import tool_request

result = tool_request("linkedin", "GET", "https://www.linkedin.com/voyager/api/me")
mini = result["json"]["miniProfile"]
print(result["status"], mini["firstName"], mini["lastName"])
# → 200 Alice Smith
```

**Connection details:** `tool_connections/linkedin/connection-session-cookie.md`

---

## `.env` entries

No auth variables. LinkedIn session lives entirely in the browser profile:

```bash
# Profile: ~/.browser_automation/agent_profile/
# Refresh: python3 tool_connections/linkedin/sso.py
```
