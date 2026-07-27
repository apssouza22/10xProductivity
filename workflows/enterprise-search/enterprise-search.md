---
name: enterprise-search
description: Search institutional knowledge across all connected tools. Uses Slackbot/Slack AI as the default first search; validates with Confluence or other official sources when useful; adds Jira, Linear, Notion, or GitHub as needed. Reads verified_connections.md to determine what is available and adapts accordingly.
---

# Enterprise Search — Institutional Knowledge

> **What this file is for:** You have a question or need to find something. This workflow searches your connected tools, synthesizes the results, and tells you where the knowledge lives — without you having to open each tool manually.

Point your agent here:

> *"Read workflows/enterprise-search/enterprise-search.md and search for [your question or topic]."*

---

## Step 1: Load your connected tools

Read `verified_connections.md`. Note which tools are available. Only search tools listed there — skip anything not connected.

| Tool | What it finds |
|------|--------------|
| Slack | Decisions, incident threads, informal knowledge, "why did we do X" |
| Confluence | Documented knowledge, runbooks, architecture docs, procedures |
| Jira | Tickets, bug reports, epics, sprint work |
| Linear | Project issues, bugs, feature requests |
| Notion | Pages and databases shared with your integration |
| GitHub | Code, PRs, issues, commit history |
| Google AI Mode | Open-web / external knowledge — synthesized answer across Google's index (news, public docs, market data, company info) |

---

## Step 2: Search

**Auth routing:** **Try browser session first** when the tool's `setup.md` documents it (`auth: sso-session` or `auth: session-cookie`) — use `shared_utils/session_request.py`. If `verified_connections.md` lists `connection-api-token.md` for a tool, or browser session returns 401, use that connection file's token-based snippets instead.

**Start with Slackbot / Slack AI by default** (when Slack is connected). It is the first search for most enterprise knowledge questions because it can synthesize the current conversational record across Slack and often surfaces the practical answer fastest, especially for time-sensitive employee/process questions.

**Also run Confluence in the same batch when it can validate or explain the answer.** Slack is the default source for current state and informal institutional knowledge; Confluence is the deliberate documentation source. For policy, process, HR, compliance, runbook, or "what is the official rule?" questions, use Confluence to confirm the Slack answer when available.

**Also scan `verified_connections.md` for AI-synthesized search** — connections whose descriptions say they answer natural-language questions across *multiple* backends (internal AI assistants, enterprise knowledge search, “institutional memory,” etc.). They are not the same as a single-source tool like Jira. If you find any, open the linked `connection-*.md` and run the query flow it documents **in the same parallel batch** as Slackbot and any validation sources. Those tools often return one answer that already spans several systems.

Add the named tools below based on what you see or what was asked:

| Add this tool | When |
|---------------|------|
| Jira / Linear | Query mentions a ticket, feature, bug, sprint, or "is X done?" |
| GitHub | Query mentions code, a function, file, PR, error, or implementation detail |
| Notion | Connected and Confluence didn't return enough |
| Google AI Mode | Query needs **external / open-web** knowledge — public docs, news, market or company data, "what is X" about the outside world. Prefer it over raw web search/fetch: ask the question and let it synthesize across Google's index. |

Run all selected searches simultaneously after selecting the batch. Do not wait for one to finish before starting the next.

---

## Per-tool search instructions

### Slack

Two modes — try Slack AI first if available, fall back to `search.messages`.

**Mode 1: Slack AI** *(requires Business+ or Enterprise+ plan)*

Best for natural-language questions. Posts to your Slackbot DM and synthesizes a cited answer from all channels you have access to. Response arrives in ~0.2s — poll immediately with 1s sleep, not longer.

**Key gotcha:** Slack AI puts its answer in `blocks` (rich text), not the `text` field. Use `extract_ai_answer()` below — reading `.get("text", "")` will return "_Thinking..._" instead of the real answer.

```python
import json, time
from urllib.parse import urlencode
from shared_utils.session_request import tool_request

def slack_api(method, endpoint, data=None, params=None):
    url = f"https://slack.com/api/{endpoint}"
    if params:
        url += "?" + urlencode(params)
    result = tool_request("slack", method, url, body=data)
    return result.get("json") or json.loads(result.get("body") or "{}")

def extract_element(item):
    t = item.get("type", "")
    if t == "text":    return item.get("text", "")
    if t == "link":    return item.get("text") or item.get("url", "")
    if t == "channel": return f"#{item.get('channel_id', '?')}"
    if t == "user":    return f"@{item.get('user_id', '?')}"
    if t == "emoji":   return f":{item.get('name', '')}:"
    return ""

def extract_ai_answer(msg):
    """Read Slack AI answer from blocks, not text field."""
    parts = []
    for block in msg.get("blocks", []):
        if block.get("type") == "timeline":
            continue  # skip Slack AI's internal search traces
        if block.get("type") == "rich_text":
            for el in block.get("elements", []):
                el_type = el.get("type", "")
                items = el.get("elements", [])
                if el_type == "rich_text_list":
                    for li in items:
                        parts.append("  • " + "".join(extract_element(i) for i in li.get("elements", [])))
                elif el_type == "rich_text_preformatted":
                    parts.append("```" + "".join(extract_element(i) for i in items) + "```")
                else:
                    parts.append("".join(extract_element(i) for i in items))
        elif block.get("type") == "section" and block.get("text"):
            parts.append(block["text"].get("text", ""))
    return "\n".join(p for p in parts if p.strip())

# Get your Slackbot DM channel
dm = slack_api("POST", "conversations.open", {"users": "USLACKBOT"})["channel"]["id"]

# Post question and poll for AI response
r = slack_api("POST", "chat.postMessage", {"channel": dm, "text": "<YOUR QUERY>"})
msg_ts = r["ts"]
for _ in range(60):
    time.sleep(1)
    replies = slack_api("GET", "conversations.replies", params={"channel": dm, "ts": msg_ts, "limit": "20"})
    ai = [m for m in replies.get("messages", [])
          if float(m.get("ts","0")) > float(msg_ts)
          and m.get("subtype") in {"ai", "ai_complete"}]
    if ai:
        answer = extract_ai_answer(ai[-1])
        if answer and "Thinking" not in answer:
            print(answer)
            break
```

If Slack AI returns an error or is unavailable (plan restriction), fall back to Mode 2.

**Mode 2: `search.messages`** *(always available)*

Full-text search with Slack syntax.

```python
def search_slack(query, count=10):
    r = slack_api("GET", "search.messages",
                  params={"query": query, "count": str(count), "sort": "score"})
    return [{"channel": m.get("channel", {}).get("name","?"),
             "user": m.get("username","?"),
             "text": m.get("text","")[:200],
             "permalink": m.get("permalink","")}
            for m in r.get("messages", {}).get("matches", [])]

results = search_slack("<YOUR QUERY>")
for r in results:
    print(f"#{r['channel']} @{r['user']}: {r['text']}\n{r['permalink']}\n")
```

Slack search syntax: `in:#channel`, `from:username`, `after:2026-01-01`, `before:2026-03-01`

---

### Confluence

Full-text CQL search across all pages. **Try browser session first** (`connection-sso.md`); use API token (`connection-api-token.md`) only if browser session is not set up or returns 401.

**Browser session** (`auth: sso-session`)

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
    print(page.get("title"), page.get("space", {}).get("key"), page.get("id"),
          f"{base}/pages/{page.get('id')}")

# Full page body:
# tool_request("confluence", "GET", f"{base}/rest/api/content/<PAGE_ID>?expand=body.view")
```

**API token** (`auth: api-token`)

```bash
source .env

# Cloud: Basic auth (-u email:token). Server/DC: Bearer token
curl -s -u "$CONFLUENCE_EMAIL:$CONFLUENCE_TOKEN" \
  "$CONFLUENCE_BASE_URL/rest/api/content/search?cql=text~%22<KEYWORD>%22+AND+type=page&limit=5&expand=space" \
  | jq '.results[] | {title, space: .space.key, id}'
```

---

### Jira

JQL full-text search across issues.

```python
from pathlib import Path
import urllib.request, json, ssl, base64, urllib.parse

env = {k.strip(): v.strip() for line in Path(".env").read_text().splitlines()
       if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
# ⚠ Cloud: Basic auth (email:token). Server/DC: Bearer token (no email needed)
if "JIRA_EMAIL" in env:
    creds = base64.b64encode(f"{env['JIRA_EMAIL']}:{env['JIRA_API_TOKEN']}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
else:
    headers = {"Authorization": f"Bearer {env['JIRA_API_TOKEN']}", "Accept": "application/json"}

jql = 'text ~ "<KEYWORD>" ORDER BY updated DESC'
params = urllib.parse.urlencode({"jql": jql, "maxResults": 5,
                                  "fields": "summary,status,assignee,updated"})
req = urllib.request.Request(f"{env['JIRA_BASE_URL']}/rest/api/2/search?{params}", headers=headers)
results = json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())

for i in results["issues"]:
    f = i["fields"]
    print(f"{i['key']}: {f['summary']} [{f['status']['name']}]")
    print(f"  {env['JIRA_BASE_URL']}/browse/{i['key']}\n")
```

---

### GitHub *(code-related queries only)*

Search code, issues, and PRs. Only include in the search if the query is about code, a specific file, a function name, an error message, or an implementation detail.

```bash
source .env

# Search code
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/search/code?q=<KEYWORD>&per_page=5" \
  | jq '.items[] | {path, repository: .repository.full_name,
      url: .html_url}'

# Search issues and PRs
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/search/issues?q=<KEYWORD>+is:issue&per_page=5" \
  | jq '.items[] | {number, title, state, url: .html_url}'

curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "$GITHUB_BASE_URL/search/issues?q=<KEYWORD>+is:pr&per_page=5" \
  | jq '.items[] | {number, title, state, url: .html_url}'
```

To scope to a specific repo: append `+repo:{owner}/{repo}` to the query.

---


## Step 3: Synthesize and present results

After all searches complete, give the user **one direct answer** — not a tool-by-tool breakdown.

- **Lead with the answer**, not with which tool found it. The user doesn't care that "Slack AI said X" or "Notion found Y" — they asked a question, give them the answer.
- **Merge all results** into a single coherent response. If multiple sources agree, state the conclusion once. If they conflict, surface the conflict briefly.
- **Include original source links whenever available and useful.** Prefer links to the Slack thread/message, Confluence page, Jira ticket, doc, PR, or other source that directly supports the answer. If the only evidence is a raw Slack message or intermediate search result, include that link rather than dropping provenance, unless the link would expose irrelevant or sensitive context.
- **If a source found nothing useful, do not mention it.** Omit empty-handed tools entirely — "Notion didn't find anything" adds no value.
- **If a result looks like a full doc worth reading**, offer to fetch it: *"There's a Confluence page 'Cursor Install Guide' — want me to read the full content?"*

---

## Notes

- **AI-synthesized tools in `verified_connections.md`:** Use only what each connection file documents — no vendor-specific names are required in this workflow. Skip if the description is clearly a single-purpose API (e.g. only metrics or only tickets).
- **Slack AI vs. search.messages:** Slack AI gives synthesized answers but requires Business+ plan. `search.messages` always works but returns raw messages. Try AI first; fall back automatically if it fails.
- **Notion searches titles only.** Body text is not indexed by the API. A "no results" from Notion doesn't mean the knowledge isn't there — it may just not be in the page title.
- **GitHub is expensive for non-code queries.** Skip it unless the query is clearly code-related; it adds noise and burns API rate limits.
- **Confluence vs. Jira overlap:** Confluence has the narrative ("how it works"), Jira has the status ("is it done"). Both are worth searching for most topics.
- **Credentials:** API-token tools load secrets from `.env`. Browser-session tools keep auth in `~/.browser_automation/profile/` — use `session_request.py` for API calls; only instance URLs belong in `.env`.
