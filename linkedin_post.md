From Coding Assistant to Personal Work Assistant

My new opensource project represents a paradigm shift in how we think about AI coding assistants. While tools like Cursor, Claude Code and Codex started as coding companions, they have evolved into something far more powerful: **general-purpose automation platforms that can interact with any tool on your laptop**.

This article explores how I am leveraging modern AI coding assistants to build sophisticated personal work assistants—without requiring company-wide platform rollouts, admin approvals, or new infrastructure.

A few things that make it work:

🔌 **Browser sessions as universal auth** — Sign in once through the agent's isolated browser profile. No OAuth apps, no API tokens. Your session cookies do the work.

🔍 **Read + Write + Act, not just search** — The agent doesn't just find the Jira ticket; it updates it. Doesn't just summarize the Slack thread; it posts the summary back. Writes always require explicit approval.

🤖 **Specialized multi-agent workflows** — An incident coordinator delegates to metrics-analyst, log-analyst, and runbook-analyst in parallel. Each has scoped tools and isolated context. Together they produce a structured incident report in minutes instead of the usual 30-60 minute manual triage.

🔒 **Security by locality** — No cloud middleware holds your credentials. The threat model is identical to you doing the work manually.  One command revokes all access.

The whole thing is local-first and markdown-driven. Workflows are executable documentation. Agent definitions are plain markdown with frontmatter. Tool connections are verified recipes that any agent can pick up.

The automation you need is already possible — you just need to connect it.

Project: https://github.com/apssouza22/auto-pilot-agent

#AI #Automation #DeveloperTools #AIAgents #Productivity #OpenSource #CodingAgents #LocalFirst
