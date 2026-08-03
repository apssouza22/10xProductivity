---
name: confluence-setup
description: Set up Confluence connection. Try browser session first (persistent profile). Fallback — Cloud API token or Server PAT.
---

# Confluence — Setup

## Step 1: Ask for a URL

Ask the user: **"Share any Confluence page URL."**

Infer `CONFLUENCE_BASE_URL` from the URL:
- `https://acme.atlassian.net/wiki/spaces/...` → `https://acme.atlassian.net/wiki` (**Cloud**)
- `https://confluence.acme.com/display/...` → `https://confluence.acme.com` (**Server / Data Center**)

---

## Browser session (try this first)

No API token. Auth stays in the shared browser profile at `~/.browser_automation/agent_profile/`.

**What to ask the user:** the page URL (step 1) only.

**Steps:**

1. Set `CONFLUENCE_BASE_URL` in `.env` (include `/wiki` for Cloud).
2. Capture the browser session:

```bash
source .venv/bin/activate
python3 shared_utils/playwright_sso.py --confluence-only
```

3. Sign in through the browser window if prompted.
4. Verify:

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["CONFLUENCE_BASE_URL"].rstrip("/")
result = tool_request("confluence", "GET", f"{base}/rest/api/user/current")
print(result.get("json", {}).get("displayName"))
# → Alice Smith
# If 401: session expired or blocked — try API token path below
```

**Connection details:** `tool_connections/confluence/connection-sso.md`

**Refresh** when the session expires:

```bash
python3 shared_utils/playwright_sso.py --confluence-only
```

---

## API token (fallback)

Use when browser session REST calls return 401 or the instance blocks session-based API access.

### Confluence Cloud

**What to ask:**
- "Paste your Confluence API token" → https://id.atlassian.com/manage-profile/security/api-tokens
- "Your Atlassian account email"

> Confluence Cloud and Jira Cloud share the same Atlassian account. If Jira is already set up, reuse the same token and email.

**Set `.env`:**
```bash
CONFLUENCE_EMAIL=you@yourcompany.com
CONFLUENCE_TOKEN=your-atlassian-api-token
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki
```

**Verify:**
```bash
export $(grep -v '^#' .env | grep 'CONFLUENCE_' | xargs)
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=type=page&limit=1" \
  | jq '{total: .size, first: .results[0].title}'
```

### Confluence Server / Data Center — Personal Access Token

**What to ask:** "Paste your Confluence Personal Access Token" → Profile → Personal Access Tokens

**Set `.env`:**
```bash
CONFLUENCE_TOKEN=your-personal-access-token
CONFLUENCE_BASE_URL=https://confluence.yourcompany.com
```

**Verify:**
```bash
curl -s -H "Authorization: Bearer $CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=type=page&limit=1" \
  | jq '{total: .size, first: .results[0].title}'
```

**Connection details:** `tool_connections/confluence/connection-api-token.md`

---

## `.env` entries

**Browser session:**
```bash
# --- Confluence ---
# Auth: ~/.browser_automation/agent_profile/
# Refresh: python3 shared_utils/playwright_sso.py --confluence-only
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki
```

**API token:**
```bash
# --- Confluence ---
CONFLUENCE_EMAIL=your-email@example.com
CONFLUENCE_TOKEN=your-atlassian-api-token
CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki
```
