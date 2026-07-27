# Tool Connector — Connect Any Work Tool to Your Agent

Connect any tool you use at work — internal company tools, custom-built systems, and commercial tools like Slack, Confluence, Jira, Linear, GitHub, Outlook, Datadog, and PagerDuty.

## Getting started

read `setup.md` — it is the full entry point for $ARGUMENTS.

## Routing

| Situation | Action |
|-----------|--------|
| Tool already in `verified_connections.md` | Reverify — run its verify snippet; if it passes, done |
| Tool has a recipe in `personal/{tool}/` | Load it and try; patch in `personal/` if it fails |
| Tool has a recipe in `tool_connections/{tool}/` | Read that tool's `setup.md` and follow it |
| Tool not found anywhere | Follow `add-new-tool.md` to build a recipe from scratch |

## Pre-built recipes available

Slack, Confluence, Jira, GitHub, Grafana and Kibana.

Internal and custom tools follow the same path — stay private in `personal/` (gitignored, never committed).
