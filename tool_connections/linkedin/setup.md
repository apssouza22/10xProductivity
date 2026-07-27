---
name: linkedin-setup
description: Set up LinkedIn connection using li_at session cookie. No developer app needed. Opens a browser once for login, then reuses the persistent profile.
---

# LinkedIn — Setup

## Auth method: session-cookie (li_at)

LinkedIn has no public API for personal use without app approval. This connection uses your browser session cookie (`li_at`) extracted via Playwright. A persistent browser profile is saved to `~/.browser_automation/linkedin_profile/` so LinkedIn recognizes the device — no 2FA after the first login.

**What to ask the user:** Nothing. Just run `sso.py` — it opens a browser window for login.

---

## Steps

1. Run the SSO capture script:

```bash
source .venv/bin/activate
python3 personal/linkedin/sso.py   # run from personal/ copy (see setup.md Step 1)
```

2. A Chromium window opens. Log in to LinkedIn (complete 2FA if prompted — this is the only time).
3. Once the feed loads, the script captures `LINKEDIN_LI_AT` and `LINKEDIN_JSESSIONID` and writes them to `.env` automatically.
4. The browser window closes.

**Second run and beyond:** the script reuses `~/.browser_automation/linkedin_profile/` and skips straight to feed — no login, no 2FA.

---

## Refresh

- `LINKEDIN_JSESSIONID` expires in ~24h. Re-run `sso.py` to refresh (no 2FA, takes ~6s).
- `LINKEDIN_LI_AT` is long-lived (weeks to months). Re-run `sso.py --force` if it expires.

```bash
# Check if session is still valid:
python3 personal/linkedin/sso.py
# → LINKEDIN_LI_AT is valid — nothing to do.

# Force refresh:
python3 personal/linkedin/sso.py --force
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

```bash
# --- LinkedIn ---
# Short-lived JSESSIONID (~24h) — refresh with: python3 personal/linkedin/sso.py
# Long-lived li_at (weeks/months) — refresh with: python3 personal/linkedin/sso.py --force
# Persistent profile at: ~/.browser_automation/linkedin_profile/ (do not delete)
LINKEDIN_LI_AT=your-li_at-cookie-value
LINKEDIN_JSESSIONID=your-jsessionid-value
```
