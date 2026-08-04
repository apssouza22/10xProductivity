---
name: airflow
auth: sso-session
description: Apache Airflow — list DAGs, inspect runs, read task logs, check scheduler health. Use for pipeline incidents, failed DAG runs, and task debugging.
env_vars:
  - AIRFLOW_BASE_URL
sniffer:
  profile: ~/.browser_automation/agent_profile
  url: ${AIRFLOW_BASE_URL}/home
  filter: /api/
---

# Airflow — browser session

Apache Airflow 2.x web UI and REST API. Auth is a FAB `session` cookie in `~/.browser_automation/agent_profile/` — not in `.env`.

**API calls:** use `shared_utils/session_request.py` with `tool_request("airflow", ...)`. GETs to `/api/v1/*` work with session cookies via `via_page_fetch=True`. POSTs to legacy UI endpoints need `X-CSRFToken` (see below).

⚠ **Never use Basic auth or username/password on REST calls.** On FAB-login instances, `/api/v1/*` returns 401 without the browser session cookie.

**Verified:** Airflow 2.10.3 (FAB login) — version, dags list, dag details, grid_data — 2026-08.

API docs: https://airflow.apache.org/docs/apache-airflow/2.10.3/stable-rest-api-ref.html

---

## Credentials

```bash
# Add to .env:
# AIRFLOW_BASE_URL=http://localhost:8080
# Auth: browser session in ~/.browser_automation/agent_profile/
# Refresh: python3 shared_utils/playwright_sso.py --airflow-only
```

---

## Auth

Browser session (`session` cookie). Refresh with:

```bash
python3 shared_utils/playwright_sso.py --airflow-only
```

All HTTP calls go through `shared_utils/session_request.py` with `via_page_fetch=True`.

---

## Verified snippets

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["AIRFLOW_BASE_URL"].rstrip("/")
headers = {"Accept": "application/json"}

result = tool_request("airflow", "GET", f"{base}/api/v1/version", headers=headers, via_page_fetch=True)
print(result.get("json"))
# → {"version": "2.10.3", "git_version": "..."}

result = tool_request(
    "airflow", "GET", f"{base}/api/v1/dags?limit=5",
    headers=headers, via_page_fetch=True,
)
dags = (result.get("json") or {}).get("dags") or []
print("dags:", [d.get("dag_id") for d in dags])
# → dags: ['your_dag_id', ...]
# ⚠ Fresh setup: run playwright_sso.py --airflow-only first.
# If redirect to /login: session expired — re-run sso.
```

---

## Key endpoints

### No auth

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Scheduler / metadatabase health |
| `GET /api/v1/version` | Airflow version |

### REST API (`/api/v1/*`) — session cookie

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/dags` | List DAGs (`limit`, `tags`, `only_active`) |
| `GET /api/v1/dags/{dag_id}` | DAG metadata |
| `GET /api/v1/dags/{dag_id}/details` | DAG + recent task instance states |
| `GET /api/v1/dags/{dag_id}/dagRuns` | List runs (`state`, `limit`, `order_by`) |
| `GET /api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances` | Task instances for a run |
| `GET /api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}` | Task logs (`full_content=true`) |
| `GET /api/v1/eventLogs` | Audit/event log (`dag_id`, `run_id`, `order_by=-when`) |
| `GET /api/v1/datasets` | Dataset list (`dag_ids`) |
| `GET /api/v1/datasets/events` | Dataset events for a run |
| `GET /api/v1/variables` | Airflow variables |
| `GET /api/v1/connections` | Connection IDs |
| `GET /api/v1/openapi.json` | Full OpenAPI spec |

### Legacy UI JSON (session + CSRF for POST)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/object/grid_data?dag_id={id}&num_runs=25` | GET | Grid view: runs + task states |
| `/object/graph_data?dag_id={id}` | GET | Graph view task graph |
| `/object/next_run_datasets/{dag_id}` | GET | Upstream datasets for next run |
| `/dag_stats` | POST | Run counts per DAG (`dag_ids=...`) |
| `/task_stats` | POST | Task state counts per DAG |
| `/last_dagruns` | POST | Last run state per DAG |
| `/next_run_datasets_summary` | POST | Dataset summary for home page |

⚠ POST endpoints require `X-CSRFToken` header (value from `csrf_token` cookie or page meta). GET `/api/v1/*` does not need CSRF on typical FAB instances.

---

## List DAGs

```python
from urllib.parse import urlencode
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["AIRFLOW_BASE_URL"].rstrip("/")
headers = {"Accept": "application/json"}

params = urlencode({"limit": 20, "only_active": False})
result = tool_request("airflow", "GET", f"{base}/api/v1/dags?{params}", headers=headers, via_page_fetch=True)
for dag in (result.get("json") or {}).get("dags", []):
    paused = "paused" if dag.get("is_paused") else "active"
    print(dag.get("dag_id"), paused, dag.get("tags"))
```

---

## Recent failed runs for a DAG

```python
from urllib.parse import urlencode
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["AIRFLOW_BASE_URL"].rstrip("/")
dag_id = "your_dag_id"
headers = {"Accept": "application/json"}

params = urlencode({"state": "failed", "limit": 5, "order_by": "-start_date"})
result = tool_request(
    "airflow", "GET",
    f"{base}/api/v1/dags/{dag_id}/dagRuns?{params}",
    headers=headers, via_page_fetch=True,
)
for run in (result.get("json") or {}).get("dag_runs", []):
    print(run.get("run_id"), run.get("state"), run.get("start_date"))
```

---

## Task logs for incident debugging

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["AIRFLOW_BASE_URL"].rstrip("/")
dag_id = "your_dag_id"
run_id = "scheduled__2026-08-03T06:00:00+00:00"
task_id = "your_task_id"
try_number = 1
headers = {"Accept": "application/json"}

result = tool_request(
    "airflow", "GET",
    f"{base}/api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/logs/{try_number}?full_content=true",
    headers=headers, via_page_fetch=True,
)
content = (result.get("json") or {}).get("content") or result.get("body") or ""
print(content[-2000:])  # tail of log
```

---

## Grid data (runs + per-task states in one call)

```python
from shared_utils.browser import load_env_file, DEFAULT_ENV_FILE
from shared_utils.session_request import tool_request

env = load_env_file(DEFAULT_ENV_FILE)
base = env["AIRFLOW_BASE_URL"].rstrip("/")
dag_id = "your_dag_id"
headers = {"Accept": "application/json"}

result = tool_request(
    "airflow", "GET",
    f"{base}/object/grid_data?dag_id={dag_id}&num_runs=10",
    headers=headers, via_page_fetch=True,
)
runs = (result.get("json") or {}).get("dag_runs") or []
print("runs:", len(runs), "latest:", runs[-1].get("state") if runs else None)
```

---

## Agent behavior

**Read actions — run freely:**
- List/get DAGs, runs, task instances, logs, variables, connections, datasets, event logs, health

**Write/interact actions — preview + explicit approval:**
- Trigger DAG (`POST /api/v1/dags/{dag_id}/dagRuns`)
- Pause/unpause DAG, clear runs, delete DAG
- Always give the UI URL (e.g. `{base}/dags/{dag_id}/grid`) so the user can verify manually

**Auth rule:** session cookie via `tool_request("airflow", ...)` only — never Basic auth or stored passwords on API calls.

---

## Typical actions to capture with the sniffer

```bash
python3 shared_utils/traffic_sniffer.py --tool airflow
```

Then in the browser: sign in → home (DAG list) → open a DAG grid → open graph → open task logs → browse Cluster Activity.

---

## Notes

- FAB username/password login at `/login` is common. Basic auth on REST API returns 401 — session cookie is required.
- `GET /api/v1/version` and `GET /health` work without login; everything else needs a session.
- No built-in search API for DAG content — filter with `GET /api/v1/dags?tags=...` or `dag_id_pattern` query param.
- No AI/chat API.
- Session cookie name: `session`. TTL varies by instance.
- For POST with CSRF: read `csrf_token` cookie after warmup and send as `X-CSRFToken`.
