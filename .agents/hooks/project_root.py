#!/usr/bin/env python3
"""Shared project-root resolver for agent hooks.

Different coding agents expose the project directory through different
environment variables, and some (e.g. Copilot) don't expose it at all and
run hooks from cwd `/`. This helper resolves the project root portably:

    1. CLAUDE_PROJECT_DIR   (Claude Code — native; Cursor — compat alias)
    2. CURSOR_PROJECT_DIR   (Cursor — native)
    3. COPILOT_PROJECT_DIR  (Copilot CLI / VS Code)
    4. CODEX_PROJECT_DIR    (Codex — if/when set)
    5. Git top-level        (git rev-parse --show-toplevel)
    6. Current working dir  (last resort)

Usage (Python hooks):

    from project_root import project_root
    root = project_root()        # Path
    hooks_dir = root / ".agents" / "hooks"

Usage (shell hooks) — prints the path to stdout:

    REPO_ROOT=$(python3 "$HOOK_DIR/project_root.py")
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Order matters: check each agent's native var, then generic fallbacks.
_PROJECT_DIR_VARS = (
    "CLAUDE_PROJECT_DIR",
    "CURSOR_PROJECT_DIR",
    "COPILOT_PROJECT_DIR",
    "CODEX_PROJECT_DIR",
    "AGENTLINT_PROJECT_DIR",  # agentlint sets this explicitly
)


def project_root() -> Path:
    """Return the project root, resolved portably across agents."""
    for var in _PROJECT_DIR_VARS:
        value = os.environ.get(var, "").strip()
        if value and value != "/":
            return Path(value).expanduser().resolve()

    # Git root — works regardless of which agent launched the hook or from
    # which subdirectory, as long as the hook lives inside a git repo.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass

    # Last resort: the current working directory. Copilot may run hooks from
    # `/`, so this is unreliable there — but it's the only remaining option.
    return Path.cwd().resolve()


if __name__ == "__main__":
    print(project_root())
