#!/usr/bin/env python3
"""SubagentStart/SubagentStop hook: append lifecycle events to runs/subagent-audit.jsonl.

Wired twice in settings.json (once per event) with the event name passed as
argv[1] -- the hook payload on stdin is not guaranteed to say which lifecycle
event fired, so each settings.json entry states it explicitly rather than
guessing from payload shape.

Per https://code.claude.com/docs/en/hooks, the SubagentStart/SubagentStop
payload only carries `agent_type` (plus common fields like session_id and
transcript_path) -- there is no description/task/prompt field, so reading
those directly off the payload always returns None. The subagent's actual
instructions only exist as the `input.description`/`input.prompt` of the
`Agent` (or legacy `Task`) tool_use call that spawned it, recorded in the
parent session's `transcript_path` JSONL. We recover them from there by
scanning for the last matching tool_use call. If several subagents of the
same type are spawned in parallel this can't disambiguate between them --
it always attributes to the most recent matching call.

Read-only except for appending to runs/subagent-audit.jsonl (an existing
generated/output directory -- see CLAUDE.md). Never calls Kubernetes,
Prometheus, IBM Cloud Logs, or the Claude API; only inspects the hook
payload already provided on stdin plus the transcript file it points to.

Disable locally: set INCIDENT_AGENT_HOOKS_DISABLED=1 in the environment, or set
"disableAllHooks": true in .claude/settings.local.json. See README.md.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

# Shared project-root resolver — portable across Claude Code, Cursor,
# Codex, and Copilot (see project_root.py).
_HOOKS_DIR = Path(__file__).parent
sys.path.insert(0, str(_HOOKS_DIR))
from project_root import project_root as _resolve_project_root

def _hooks_disabled() -> bool:
    return os.environ.get("INCIDENT_AGENT_HOOKS_DISABLED", "").strip().lower() in ("1", "true", "yes")


def _project_root() -> Path:
    return _resolve_project_root()


def main() -> int:
    if _hooks_disabled():
        return 0

    event = sys.argv[1] if len(sys.argv) > 1 else "unknown"

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    agent_type = payload.get("agent_type")

    entry = {
        "event": event,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "subagent_type": agent_type,
        "description": payload,
    }

    runs_dir = _project_root()
    runs_dir.mkdir(parents=True, exist_ok=True)
    audit_path = runs_dir / "subagent-audit.jsonl"
    with audit_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
