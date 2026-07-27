---
name: slack
auth: sso-session
description: Slack — two complementary modes. (1) Slack AI: post a natural-language question to the Slackbot DM and get a synthesized AI answer in ~0.2s, drawn from all Slack content you have access to. (2) search.messages: raw full-text search with Slack syntax (in:#channel, from:user, date range). Also: read channel/thread history, post messages. No Slack app install needed — browser session auth.
env_vars:
  - SLACK_WORKSPACE_URL
sniffer:
  profile: ~/.browser_automation/slack_profile
  url: ${SLACK_WORKSPACE_URL}
  filter: /api/
---

# Slack

Access is via your own user session in a persistent browser profile (`~/.browser_automation/slack_profile/`). No Slack app installation or admin approval needed.

Env: `SLACK_WORKSPACE_URL` only (instance URL — not a secret). Auth tokens stay in the browser profile. Refresh via `python3 shared_utils/playwright_sso.py --slack-only` when the session stops working.

**API calls:** use `shared_utils/session_request.py` — it reuses the saved browser profile. Do not call `urllib`, `curl`, or read tokens from `.env`.

Multiple Slack workspaces are supported with account-scoped env keys:
`SLACK_ACME_WORKSPACE_URL`, `SLACK_ACME_XOXC`, `SLACK_ACME_D_COOKIE`
(refresh via `python3 shared_utils/playwright_sso.py --slack-only --account acme`).

---

## Verify connection

```python
from shared_utils.session_request import tool_request

result = tool_request("slack", "GET", "https://slack.com/api/auth.test")
data = result.get("json") or {}
print(data.get("ok"), data.get("user"), data.get("team"))
# → True alice your-workspace
```

## Auth setup

**Minimum user input:** ask for a Slack message link (right-click any message → Copy link, e.g. `https://acme.slack.com/archives/C.../p...`).

Extract workspace URL (`https://acme.slack.com/`), update `SLACK_WORKSPACE_URL` in `.env`, then run:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --slack-only
```

The script opens Chromium. Sign in through the browser if prompted — the session is saved in `~/.browser_automation/slack_profile/`. Nothing auth-related is written to `.env`.

For a second workspace, set a scoped URL and refresh with `--account`:

```bash
# .env
SLACK_ACME_WORKSPACE_URL=https://acme.slack.com/

source .venv/bin/activate
python3 shared_utils/playwright_sso.py --slack-only --account acme
```

The account name becomes an uppercase prefix in `.env` keys and a separate profile at `~/.browser_automation/slack_{account}_profile/`:

```bash
# .env
SLACK_ACME_WORKSPACE_URL=https://acme.slack.com/

source .venv/bin/activate
python3 shared_utils/playwright_sso.py --slack-only --account acme
```

That uses `SLACK_ACME_WORKSPACE_URL` in `.env` with the acme-scoped browser profile.

## Verified multi-workspace flow

The account-scoped flow was verified against two Slack workspaces:

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

Observed failure case: Google sign-in for a private personal workspace can show
`This browser or app may not be secure` in Playwright-controlled Chromium. If a
valid scoped token already exists, `check()` now validates `xoxc` together with
the `d` cookie and skips browser login. If no valid token exists, log in through
the opened browser manually or capture from an already trusted browser session.

---

## Choosing the right method

**Use `search.messages` for:**
- Time-specific queries: "my activity today", "messages this week", "what happened yesterday"
- Finding specific messages, people, or keywords with date filters
- When you need exact timestamps and message metadata

**Use Slack AI for:**
- Open-ended knowledge questions: "how do we handle X?", "what's our policy on Y?"
- Synthesized answers drawn from multiple channels
- When you want AI to summarize and cite sources

**⚠ Critical:** Slack AI cannot reliably filter by specific dates. For date-specific queries, always use `search.messages` with `after:` / `before:` filters.

---

## Slack AI — synthesized answers

**Requires:** Slack Business+ or Enterprise+ plan (not available on Free/Pro as of Jan 2026)

**Pattern:** Post question to Slackbot DM → poll `conversations.replies` for response with `subtype='ai'` or `subtype='ai_complete'`

**⚠ Key gotcha:** Response arrives in ~0.2s — poll immediately with 1s sleep, not with long delay

```python
import json, time
from shared_utils.session_request import tool_request

def slack_api(method, endpoint, data=None, params=None):
    url = f"https://slack.com/api/{endpoint}"
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    result = tool_request("slack", method, url, body=data)
    return result.get("json") or json.loads(result.get("body") or "{}")

# Get Slackbot DM ID (USLACKBOT is fixed across all workspaces)
r = slack_api("POST", "conversations.open", {"users": "USLACKBOT"})
slackbot_dm = r["channel"]["id"]

# Post question
r = slack_api("POST", "chat.postMessage", {"channel": slackbot_dm, "text": "how do we handle on-call escalations?"})
msg_ts = r["ts"]

# Poll for AI response (arrives in ~0.2s, poll with 1s sleep)
for _ in range(60):
    time.sleep(1)
    r = slack_api("GET", "conversations.replies", params={"channel": slackbot_dm, "ts": msg_ts, "limit": "20"})
    ai_replies = [m for m in r.get("messages", [])
                  if float(m.get("ts", "0")) > float(msg_ts)
                  and m.get("subtype") in {"ai", "ai_complete"}]
    if ai_replies:
        print(ai_replies[-1])
        break
```

**Multi-turn:** Pass `thread_ts` to `chat.postMessage` to continue conversation in same thread.

---

## search.messages — date-filtered search

**Best for:** Time-specific queries, keyword search with precise date filtering

**Syntax:** `from:@me after:2026-03-24`, `in:#channel keyword`, `from:alice before:2026-01-01`

```python
# Using api() helper from above
today = "2026-03-24"  # or: from datetime import datetime; datetime.now().strftime("%Y-%m-%d")

r = api("GET", "search.messages",
        params={"query": f"from:@me after:{today}", "count": "50", "sort": "timestamp"})

matches = r.get("messages", {}).get("matches", [])
for m in matches:
    print(f"{m.get('channel', {}).get('name')}: {m.get('text', '')[:100]}")
```

**Search operators:**
- `in:#channel-name` — specific channel
- `from:@username` — by author
- `after:YYYY-MM-DD` / `before:YYYY-MM-DD` — date filter
- `has:link` / `has:file` — filter by content type

---

## Resolve a user before DM/upload

`users.lookupByEmail` can return `not_allowed_token_type` for the xoxc session token. When that happens, recover the user ID from Slack search, then verify it with `users.info` before opening a DM.

```python
# First try lookupByEmail if available.
r = api("GET", "users.lookupByEmail", params={"email": "person@example.com"})
# → {"ok": false, "error": "not_allowed_token_type"}  # common for xoxc sessions
if r.get("ok"):
    user_id = r["user"]["id"]
else:
    # Fallback: search mentions and extract the <@ID|handle> value from results.
    sr = api("GET", "search.messages",
             params={"query": '"Person Name" OR "person.handle"', "count": "10"})
    # → {"ok": true, "messages": {"matches": [{"text": "...<@U0123456789|person.handle>..."}]}}
    user_id = "U0123456789"  # Example from a result like <@U0123456789|person.handle>

info = api("GET", "users.info", params={"user": user_id})
# → {"ok": true, "user": {"id": "U0123456789", ...}}
assert info.get("ok"), info
dm = api("POST", "conversations.open", {"users": user_id})
# → {"ok": true, "channel": {"id": "D0123456789", ...}}
```

---

## Read thread from URL

```python
import re

# URL: https://acme.slack.com/archives/C08E6GQMLP6/p1773406713930289
m = re.search(r"/archives/([A-Z0-9]+)/p(\d+)", slack_url)
channel_id = m.group(1)
ts = m.group(2)[:10] + "." + m.group(2)[10:]  # p1773406713930289 → 1773406713.930289

r = api("GET", "conversations.replies", params={"channel": channel_id, "ts": ts, "limit": "50"})
messages = r.get("messages", [])
```

---

## API reference

| Endpoint | What it does | Key params |
|----------|-------------|------------|
| `auth.test` | Verify token, get user/team | — |
| `chat.postMessage` | Post a message | `channel`, `text`, `thread_ts` (optional) |
| `conversations.open` | Open DM with user | `users` (e.g., `"USLACKBOT"`) |
| `conversations.replies` | Fetch thread / poll for Slack AI | `channel`, `ts` (thread root), `limit` |
| `conversations.history` | Read recent channel messages | `channel`, `limit` |
| `search.messages` | Full-text search with date filters | `query`, `count`, `sort` |
| `users.lookupByEmail` | Look up user by email when token permits | `email` |
| `users.info` | Look up user by ID | `user` |

---

## URL patterns

- Channel/DM URL: `.../archives/{CHANNEL_ID}/p{TS_NO_DOT}`
- `D...` = DM, `C...` = channel, `G...` = group DM
- Timestamp: `p1773406713930289` → `1773406713.930289`
