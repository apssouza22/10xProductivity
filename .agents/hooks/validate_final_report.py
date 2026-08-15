#!/usr/bin/env python3
"""Stop hook: validate and persist a final incident report.

Complements `.claude/agents/incident-investigator/incident-reporter.md`, which defines the Markdown
incident-report format for the reporter subagent. This hook is a harness-level,
best-effort text check over the last assistant message in the session
transcript, so an incident report can't silently ship without the fields
CLAUDE.md requires.

When validation passes, the report is written to
`reports/<investigation_id>-report.md` under the project root (creating
`reports/` if needed). The investigation id is taken from the most recent
`runs/<investigation_id>/scratchpad` reference in the transcript.

Only enforced when the last assistant message looks like an attempted
incident report (contains a report-shaped marker such as "Subagent usage
audit" or "incident report"); ordinary conversational turns are left alone.

Reads the local transcript JSONL named in the Stop hook payload. Never calls
Kubernetes, Prometheus, IBM Cloud Logs, or the Claude API.

Disable locally: set INCIDENT_AGENT_HOOKS_DISABLED=1 in the environment, or set
"disableAllHooks": true in .claude/settings.local.json. See README.md.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Shared project-root resolver — portable across Claude Code, Cursor,
# Codex, and Copilot (see project_root.py).
_HOOKS_DIR = Path(__file__).parent
sys.path.insert(0, str(_HOOKS_DIR))
from project_root import project_root as _resolve_project_root

_REPORT_MARKERS = (
    "subagent usage audit",
    "incident report",
    "requires human",
    "## verdict",
)

_REQUIRED: dict[str, re.Pattern[str]] = {
    "evidence": re.compile(r"\bevidence\b", re.IGNORECASE),
    "Subagent usage audit": re.compile(r"subagent usage audit", re.IGNORECASE),
    "ruled_out": re.compile(r"ruled[ _]?out", re.IGNORECASE),
    "unknowns": re.compile(r"unknowns?\b", re.IGNORECASE),
    "confirmed/not-confirmed statement": re.compile(
        r"\b(not\s+confirmed|confirmed|verdict)\b", re.IGNORECASE
    ),
}

_SHARED_RUN_DIRS = frozenset({
    "manifests-repo",
    "infrastructure-repo",
    "service-repo",
})

_INVESTIGATION_ID_RE = re.compile(
    r"runs/([a-zA-Z0-9][a-zA-Z0-9._-]*)/scratchpad"
)


def _hooks_disabled() -> bool:
    return os.environ.get("INCIDENT_AGENT_HOOKS_DISABLED", "").strip().lower() in ("1", "true", "yes")


def _project_root() -> Path:
    return _resolve_project_root()


def _extract_text_blocks(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            out.append(node["text"])
        for value in node.values():
            _extract_text_blocks(value, out)
    elif isinstance(node, list):
        for item in node:
            _extract_text_blocks(item, out)


def _last_assistant_text(transcript_path: str) -> str | None:
    path = Path(transcript_path)
    if not path.exists():
        return None

    last_text: str | None = None
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = record.get("type") or (record.get("message") or {}).get("role")
            if role != "assistant":
                continue

            blocks: list[str] = []
            _extract_text_blocks(record, blocks)
            if blocks:
                last_text = "\n".join(blocks)

    return last_text


def _investigation_id_from_transcript(transcript_path: str) -> str | None:
    path = Path(transcript_path)
    if not path.exists():
        return None

    investigation_ids: list[str] = []
    with path.open() as f:
        for line in f:
            for match in _INVESTIGATION_ID_RE.finditer(line):
                investigation_id = match.group(1)
                if investigation_id not in _SHARED_RUN_DIRS:
                    investigation_ids.append(investigation_id)

    return investigation_ids[-1] if investigation_ids else None


def report_path_for_investigation(investigation_id: str, project_root: Path | None = None) -> Path:
    """Return the canonical on-disk path for an investigation report."""
    root = project_root or _project_root()
    return root / "reports" / f"{investigation_id}-report.md"


def persist_report(investigation_id: str, text: str, project_root: Path | None = None) -> Path:
    """Write the validated report to reports/<investigation_id>-report.md."""
    report_path = report_path_for_investigation(investigation_id, project_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    if _hooks_disabled():
        return 0

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    if payload.get("stop_hook_active"):
        # We already blocked once on our own feedback -- don't loop forever.
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return 0

    text = _last_assistant_text(transcript_path)
    if not text:
        return 0

    lowered = text.lower()
    if not any(marker in lowered for marker in _REPORT_MARKERS):
        return 0  # not an incident-report-shaped turn -- nothing to validate

    missing = [label for label, pattern in _REQUIRED.items() if not pattern.search(text)]
    if missing:
        reason = (
            "Final incident report is missing required elements: "
            + ", ".join(missing)
            + ". Per CLAUDE.md output rules, the report must include an evidence "
            "section, a 'Subagent usage audit' table, ruled_out, unknowns, and an "
            "explicit confirmed/not-confirmed verdict before stopping."
        )
        print(json.dumps({"decision": "block", "reason": reason}))
        return 0

    investigation_id = _investigation_id_from_transcript(transcript_path)
    if investigation_id:
        persist_report(investigation_id, text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
