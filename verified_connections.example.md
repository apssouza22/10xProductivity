---
name: verified_connections
device: your-device-name
description: "[your-device-name] Your active tool connections — verified and ready on this device. Gitignored — device-specific, never committed. Covers: ... Load at session start."
---

# Tool Connections — Master Catalog

**This is the example file.** Do not load this as your capability index.

- **Your active connections:** load `TENX_PRIVATE_DIR/verified_connections.md` (device-specific, outside the public repo, never committed).
- **To set up connections:** *"Read setup.md and set up my tool connections."*
- **To refresh short-lived tokens (~8h):** run the tool's `sso.py` (e.g. `source .venv/bin/activate && python3 tool_connections/slack/sso.py`)

> **`device:`** Set this to your machine name (e.g. `my-macbook`, `work-laptop`). Because `TENX_PRIVATE_DIR/verified_connections.md` is device-specific and outside the public repo — each machine has its own set of verified tokens — the device field lets the agent know which machine it's running on and prevents confusion when context from multiple devices appears in the same session.

The sections below illustrate the format. After verifying a tool, append its section to `TENX_PRIVATE_DIR/verified_connections.md` using the same format — read the tool's `connection-*.md` frontmatter for name, description, and env_vars.

---

## Jira → `tool_connections/jira/connection-api-token.md`

All Jira operations — fetch issues, JQL search, update fields, write descriptions/comments, REST API quirks (components, editmeta, Agile/sprint API). Use when fetching a Jira issue, listing tickets, updating fields, writing Jira comments or descriptions, or using the Jira REST API.
Env: `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_BASE_URL`

---

## Slack → `tool_connections/slack/connection-sso.md`

Slack — two complementary modes. (1) Slack AI: post a natural-language question to the Slackbot DM and get a synthesized AI answer drawn from all Slack content. (2) search.messages: raw full-text search. Also: read channel/thread history, post messages.
Env: `SLACK_WORKSPACE_URL` (instance URL only). Auth: `~/.browser_automation/agent_profile/` (refresh with `python3 shared_utils/playwright_sso.py --slack-only`)

---

## Confluence → `tool_connections/confluence/connection-sso.md`

Confluence wiki — search pages, fetch content, browse spaces via browser session. No API token required when using the browser profile.
Env: `CONFLUENCE_BASE_URL` (include `/wiki` for Cloud). Auth: `~/.browser_automation/agent_profile/` (refresh with `python3 shared_utils/playwright_sso.py --confluence-only`)

API-token alternative: `tool_connections/confluence/connection-api-token.md`

---

## Langfuse → `tool_connections/langfuse/connection-sso.md`

Langfuse LLM observability — browse traces, investigate agent/LLM failures, find errors and slow runs. Use when investigating LLM incidents or correlating trace IDs from alerts.
Env: `LANGFUSE_BASE_URL`, `LANGFUSE_PROJECT_ID`. Auth: `~/.browser_automation/agent_profile/` (refresh with `python3 shared_utils/playwright_sso.py --langfuse-only`)

API-key alternative: `tool_connections/langfuse/connection-api-key.md`

---

## Airflow → `tool_connections/airflow/connection-sso.md`

Apache Airflow — list DAGs, inspect runs, read task logs, check scheduler health. Use for pipeline incidents, failed DAG runs, and task debugging.
Env: `AIRFLOW_BASE_URL`. Auth: `~/.browser_automation/agent_profile/` (refresh with `python3 shared_utils/playwright_sso.py --airflow-only`)

---

## Adding new connections

Add `tool_connections/{tool}/connection-*.md` with core frontmatter (`name`, `auth`, `description`, `env_vars`). After verifying, append a section to `TENX_PRIVATE_DIR/verified_connections.md` following the format above.
