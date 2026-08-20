# Auto Pilot Agent

**A local-first stack for building a personal AI assistant to assist you in your daily work.**

Use the coding agents, browser sessions, desktop apps and tool access you already have.
No new company-wide automation platform, no admin-approved Slack app, no webhooks, and no IT project required.

If this saves you time, consider giving it a star. It helps others discover the project.

📖 **[Read the full article](ARTICLE.md)**: Building Personal AI Assistants for Work - a deep dive into leveraging AI coding assistants, Playwright-based browser sessions, and specialized agents to build sophisticated personal work assistants.

## The Idea

Most employees cannot install a new automation platform, register Slack or GitHub apps, add webhooks, or wait for 
IT approval every time they want an AI agent to help.

Auto Pilot Agent builds around the access you already have:

- your coding agent
- your browser and desktop apps
- your authenticated sessions
- your local machine
- your existing permissions
- your app notifications, messages, and calendar events

Coding agents are no longer just coding assistants. Cursor, Claude Code, Codex, Copilot, and similar tools can read files, 
run scripts, call APIs, use browsers, and work across your local environment. 
Auto Pilot Agent turns that agent into a personal work assistant that can operate within normal workplace constraints.

The shift is not "let an AI run autonomously." The shift is **human-AI interaction**:


### 1. Connect Your Tools

Your agent needs access to the same tools you already use: Slack, Jira, GitHub, Confluence, Google Drive, Outlook, Salesforce, internal portals, or anything else with an API, CLI, browser surface, or local files.

Auto Pilot Agent provides agent-readable setup guides in [`tool_connections/`](tool_connections/). The core principle is still zero new infrastructure: your local coding agent acts as you, using your existing access.

For the detailed connection philosophy, see [`tool_connections/README.md`](tool_connections/README.md).

### 2. Workflows

We include the `incident-investigator` workflow agent as an example. The incident investigator workflow is a set of subagents that work together to investigate an incident.
The incident investigator workflow is a good example of how to use subagents to build a workflow that leverages the connectors to perform tasks.

## Quick Start

1. Install a coding agent such as [Cursor](https://cursor.com/download), Claude Code, Codex, or another agent you trust.

2. Clone and open this repo:

```bash
git clone https://github.com/apssouza22/auto-pilot-agent.git
cd auto-pilot-agent
```

3. If needed, set up Python and Playwright:

```text
Read setup-python.md and prepare this repo.
```

4. Install the local runtime:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

5. Ask your agent to set up your personal AI assistant for work. The first step is connecting your tools:

```text
Read setup.md and set up my personal AI assistant for work.
```

For a tool that has no recipe yet, prompt:

```text
Set up and run sniffer to find out useful endpoints for the tool XXX.
```

Replace `XXX` with the tool name. See [`add-new-tool.md`](add-new-tool.md).

## Example Workflows and Prompts

**Enterprise search**

```text
Search for everything related to the decision to deprecate the v1 API.
```

The agent searches across connected tools, synthesizes the answer, and links back to source material.

**Available today: real-time web research**

```text
Research the current state of WebAssembly support across major browsers
and summarize what changed in the last 6 months.
```

The agent queries Google AI Mode for AI-synthesized answers grounded in live web sources, with multi-turn follow-up for deeper investigation. No API key — sign in to Google once.

**Coaching example: sprint triage**

```text
Review my Jira sprint, identify stale tickets, and draft follow-up comments.
```

The agent can learn this from connected Jira, docs, and PRs. Once the pattern is reliable, capture it as a workflow or skill.

**Coaching example: morning brief**

```text
Summarize what changed since yesterday across Slack, Jira, GitHub, and my calendar.
```

## Who This Is For

Auto Pilot Agent is for people who already use a coding agent and want it to become useful outside the code editor:

- Developers who want one agent to work across code, tickets, docs, and chat
- Engineering managers who want cross-tool status and follow-up automation
- Product managers, support engineers, analysts, sales teams, and operators who live across many tools
- Power users who want to coach their own personal AI assistant for work instead of waiting for a centralized platform rollout

The same stack works differently for each person because the tools, skills, and trusted workflows are personal.

## Legal

Some workflows in this repo automate actions on external platforms. Platform automation may violate Terms of Service. Read [`LEGAL_NOTICE.md`](LEGAL_NOTICE.md) before running automation scripts.

## License

MIT
