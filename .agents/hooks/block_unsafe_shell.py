#!/usr/bin/env python3
"""PreToolUse hook (matcher: Bash): deny unsafe Helm/git/Terraform commands.

This hook is a harness-level gate for the case where a raw `helm`/`git`/
`terraform` command reaches the Bash tool directly.

Denies `git push` because manifest-analyst and
terraform-analyst are each allowed a narrow, read-only git checkout of an
external repo (see .claude/agents/incident-investigator/manifest-analyst.md and
.claude/agents/incident-investigator/terraform-analyst.md), and this project is read-only by
default -- nothing here should ever push to a git remote.

Also denies mutating `terraform` subcommands (`apply`, `destroy`,
`state ...`) for the same read-only-by-default posture: terraform-analyst
only reads Terraform source as text and never invokes the `terraform`
binary itself, but this hook still gates raw Bash use elsewhere in the
session.

Read-only: it only inspects tool_input.command from the PreToolUse payload on
stdin. It never executes anything, and never calls Kubernetes, Helm, git,
Prometheus, IBM Cloud Logs, or the Claude API.

Disable locally: set INCIDENT_AGENT_HOOKS_DISABLED=1 in the environment (or in a
local .env sourced before launching Claude Code), or set
"disableAllHooks": true in .claude/settings.local.json. See README.md.
"""
from __future__ import annotations

import json
import os
import re
import sys

_SHELL_SEPARATORS = re.compile(r"&&|\|\||;|\|")

# Intentionally hardcoded rather than imported: this script must run
# standalone (no PYTHONPATH/venv dependency) with the stdlib only.
_DENY_PATTERNS = [
    (re.compile(r"\bhelm\b.*\bupgrade\b"), "helm upgrade"),
    (re.compile(r"\bgit\b.*\bpush\b"), "git push"),
    (re.compile(r"\bterraform\b.*\bapply\b"), "terraform apply"),
    (re.compile(r"\bterraform\b.*\bdestroy\b"), "terraform destroy"),
    (re.compile(r"\bterraform\b.*\bstate\b"), "terraform state"),
]


def _hooks_disabled() -> bool:
    return os.environ.get("INCIDENT_AGENT_HOOKS_DISABLED", "").strip().lower() in ("1", "true", "yes")


def _find_violation(command: str) -> str | None:
    # Check each shell-separated segment independently so a denied verb in
    # one clause doesn't false-positive off an unrelated helm/terraform call
    # elsewhere in the same line (e.g. "terraform plan | grep destroy").
    for segment in _SHELL_SEPARATORS.split(command):
        for pattern, label in _DENY_PATTERNS:
            if pattern.search(segment):
                return label
    return None


def main() -> int:
    if _hooks_disabled():
        return 0

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # fail open on malformed input -- nothing we can check

    if payload.get("tool_name") != "Bash":
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        return 0

    violation = _find_violation(command)
    if violation is None:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Blocked unsafe shell command matching '{violation}'. This project "
                "is read-only by default (see CLAUDE.md non-negotiable safety "
                "rules) -- destructive helm/terraform actions and git pushes "
                "require explicit human approval through an approved gate, not raw "
                "Bash."
            ),
        },
        "systemMessage": f"Blocked unsafe shell command ({violation}).",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
