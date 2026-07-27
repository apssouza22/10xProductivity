---
name: grafana
auth: sso-session
description: Grafana dashboards — extract PromQL queries from panels, look up dashboard UIDs, query data. Use when you need the PromQL from a Grafana dashboard (e.g. for incident analysis), or want to find which dashboards exist for a service.
env_vars:
  - GRAFANA_BASE_URL
sniffer:
  profile: ~/.browser_automation/profile
  url: ${GRAFANA_BASE_URL}
  filter: /api/
---

# Grafana

Env: `GRAFANA_BASE_URL` only (instance URL). Session cookie lives in `~/.browser_automation/profile/`.

```bash
# Set in .env:
# GRAFANA_BASE_URL=https://grafana.yourcompany.com
```

Auth: session cookie in browser profile — refresh with `python3 shared_utils/playwright_sso.py --grafana-only`.

**API calls:** use `shared_utils/session_request.py` — it reuses the saved browser profile and attaches session cookies automatically.

**The primary use case is extracting PromQL:** Grafana dashboard JSON contains all panel queries with Grafana variable placeholders (e.g. `${env}`). Substitute variables to get runnable PromQL, then execute via your Prometheus-compatible endpoint.

## Verify connection

```python
from pathlib import Path
import os
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["GRAFANA_BASE_URL"].rstrip("/")
result = tool_request("grafana", "GET", f"{base}/api/user")
print(result.get("json"))
# → {"login": "alice", "email": "alice@example.com", "name": "Alice Smith"}
# ⚠ Fresh clone: run playwright_sso.py --grafana-only first to create the profile.
# If you see 401/redirect: session expired — run playwright_sso.py to refresh.
```

---

## Refresh session

```bash
# Refreshes the browser profile — opens browser for SSO, ~20–30 s
source .venv/bin/activate
python3 shared_utils/playwright_sso.py
```

---

## Get PromQL from a dashboard

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["GRAFANA_BASE_URL"].rstrip("/")
uid = "{uid}"

result = tool_request("grafana", "GET", f"{base}/api/dashboards/uid/{uid}")
dashboard = result["json"]
panels = [
    {"title": p.get("title"), "exprs": [t["expr"] for t in p.get("targets", []) if t.get("expr")]}
    for p in dashboard.get("dashboard", {}).get("panels", [])
    if p.get("targets")
]
print(panels[:10])
```

**Variable substitution:** Panel PromQL uses Grafana template variables like `${env}` or `$service`. Replace with actual values before running:

```python
import re

def substitute_vars(expr: str, vars: dict) -> str:
    """Replace Grafana ${var} and $var placeholders with actual values."""
    for k, v in vars.items():
        expr = re.sub(rf'\${{{re.escape(k)}}}', v, expr)
        expr = re.sub(rf'\${re.escape(k)}(?=[^a-zA-Z0-9_]|$)', v, expr)
    return expr

# Example
expr = 'rate(http_requests_total{env="${env}",service="${service}"}[5m])'
vars = {"env": "production", "service": "my-service"}
runnable = substitute_vars(expr, vars)
# → rate(http_requests_total{env="production",service="my-service"}[5m])
```

---

## Find dashboards

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["GRAFANA_BASE_URL"].rstrip("/")

# Search by keyword
result = tool_request("grafana", "GET", f"{base}/api/search?query=<keyword>&limit=10&type=dash-db")
for item in result.get("json") or []:
    print(item.get("title"), item.get("uid"), item.get("folderTitle"))

# Search by tag
result = tool_request("grafana", "GET", f"{base}/api/search?tag=<tag-name>&limit=20")
for item in result.get("json") or []:
    print(item.get("title"), item.get("uid"))
```

---

## Query live metric data

```python
import time
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["GRAFANA_BASE_URL"].rstrip("/")

# Execute a PromQL query (instant vector)
result = tool_request(
    "grafana", "GET",
    f"{base}/api/datasources/proxy/uid/{{datasource_uid}}/api/v1/query?query=up&time={int(time.time())}",
)
for row in (result.get("json") or {}).get("data", {}).get("result", []):
    print(row.get("metric"), row.get("value", [None, None])[1])

# Find datasource UIDs
result = tool_request("grafana", "GET", f"{base}/api/datasources")
for ds in result.get("json") or []:
    print(ds.get("uid"), ds.get("name"), ds.get("type"))
```

---

## Notes on auth

Grafana session cookies are set after SSO login (~8h TTL). On managed machines, `playwright_sso.py` completes this automatically in a headed Chromium window without user interaction. On personal machines, it opens the Grafana login page — complete login manually once, then the session is saved.

If your Grafana uses API keys instead of SSO:
```bash
# Alternative: API key auth (if your Grafana instance supports it)
# GRAFANA_API_KEY=your-grafana-api-key
curl -s "$GRAFANA_BASE_URL/api/dashboards/uid/{uid}" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  | jq '.dashboard.title'
```
