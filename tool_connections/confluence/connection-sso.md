---
name: confluence
auth: sso-session
description: Confluence wiki — search pages, fetch content, browse spaces via browser session. Use when looking up internal documentation, runbooks, architecture pages, or procedures. No API token — auth lives in the browser profile.
env_vars:
  - CONFLUENCE_BASE_URL
sniffer:
  profile: ~/.browser_automation/confluence_profile
  url: ${CONFLUENCE_BASE_URL}
  filter: /rest/api
---

# Confluence — browser session

Confluence via a persistent browser profile (`~/.browser_automation/confluence_profile/`).

Env: `CONFLUENCE_BASE_URL` only (instance URL — not a secret).

```bash
# Confluence Cloud:
# CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki
# Confluence Server / Data Center:
# CONFLUENCE_BASE_URL=https://confluence.yourcompany.com
```

**API calls:** use `shared_utils/session_request.py` — not `curl` with API tokens.

For API-token auth instead, see `connection-api-token.md`.

---

## Verify connection

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["CONFLUENCE_BASE_URL"].rstrip("/")

result = tool_request("confluence", "GET", f"{base}/rest/api/user/current")
user = result.get("json") or {}
print(user.get("displayName"), user.get("username"))
# → Alice Smith alice@example.com
```

---

## Auth setup

**Minimum user input:** any Confluence page URL (to infer `CONFLUENCE_BASE_URL`).

1. Set `CONFLUENCE_BASE_URL` in `.env` (include `/wiki` for Cloud).
2. Run session capture:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --confluence-only
```

Sign in through the browser if prompted — the session is saved in `~/.browser_automation/confluence_profile/`.

If another tool using the same profile is already logged in, Confluence may skip the login prompt.

---

## Refresh session

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --confluence-only
```

Re-run when `user/current` returns 401.

---

## Search pages

```python
from urllib.parse import quote
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["CONFLUENCE_BASE_URL"].rstrip("/")
keyword = "<KEYWORD>"

cql = quote(f'text~"{keyword}" AND type=page')
result = tool_request(
    "confluence", "GET",
    f"{base}/rest/api/content/search?cql={cql}&limit=5&expand=space",
)
for page in (result.get("json") or {}).get("results", []):
    print(page.get("title"), page.get("space", {}).get("key"), page.get("id"))
```

---

## Fetch page content

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["CONFLUENCE_BASE_URL"].rstrip("/")
page_id = "<PAGE_ID>"

result = tool_request(
    "confluence", "GET",
    f"{base}/rest/api/content/{page_id}?expand=body.view",
)
body = (result.get("json") or {}).get("body", {}).get("view", {}).get("value", "")
print(body[:3000])
```

---

## List spaces

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["CONFLUENCE_BASE_URL"].rstrip("/")

result = tool_request("confluence", "GET", f"{base}/rest/api/space?limit=25")
for space in (result.get("json") or {}).get("results", []):
    print(space.get("key"), space.get("name"))
```

---

## Notes

- **Cloud base URL** must include `/wiki` (e.g. `https://acme.atlassian.net/wiki`).
- **Profile:** `~/.browser_automation/confluence_profile/`
- **CQL syntax:** same as the REST API — `text~`, `title~`, `space=`, `type=page`.
- **API token alternative:** `connection-api-token.md` if browser session REST calls return 401.
