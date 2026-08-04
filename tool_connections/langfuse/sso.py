"""
Langfuse browser session capture — plugin for playwright_sso.py discovery.

Opens Langfuse Cloud in the shared browser profile. Session cookies
(NextAuth) stay in ~/.browser_automation/agent_profile/ — not in .env.

Standalone usage:
    python3 tool_connections/langfuse/sso.py
    python3 tool_connections/langfuse/sso.py --force
"""

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright

TOOL_NAME = "langfuse"
CONFIG_ENV_KEYS = ["LANGFUSE_BASE_URL", "LANGFUSE_PROJECT_ID"]


def _profile_dir() -> Path:
    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import profile_dir_for
    return profile_dir_for()


def _traces_url(env: dict) -> str:
    base = env.get("LANGFUSE_BASE_URL", "").rstrip("/")
    project = env.get("LANGFUSE_PROJECT_ID", "")
    if not base or not project or project == "your-project-id":
        return ""
    return f"{base}/project/{project}/traces"


def check(env: dict) -> bool:
    """Return True if the browser profile has a valid Langfuse session."""
    url = _traces_url(env)
    if not url:
        return False
    try:
        sys.path.insert(0, str(Path(__file__).parents[2]))
        from shared_utils.session_request import tool_request

        result = tool_request(
            "langfuse",
            "GET",
            url,
            warmup_url=url,
            via_page_fetch=True,
        )
        return result.get("ok") is True
    except Exception:
        return False


def capture(env: dict) -> dict:
    """Open Langfuse in a persistent profile until login succeeds."""
    base = env.get("LANGFUSE_BASE_URL", "")
    project = env.get("LANGFUSE_PROJECT_ID", "")
    if not base or not project or project == "your-project-id":
        raise RuntimeError(
            "LANGFUSE_BASE_URL and LANGFUSE_PROJECT_ID must be set in .env."
        )

    traces_url = _traces_url(env)
    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    print(f"  Opening Langfuse — sign in in the browser if prompted...")
    print(f"  URL: {traces_url}")
    print(f"  Profile: {profile}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            channel="chrome",
            headless=False,
            ignore_https_errors=True,
            args=["--window-size=1280,900", "--window-position=100,100"],
        )
        page = ctx.new_page()
        page.goto(traces_url, wait_until="domcontentloaded", timeout=90_000)
        time.sleep(2)

        logged_in = check(env)

        if not logged_in:
            print("  Waiting for sign-in (3 min timeout — Ctrl+C to abort)...", flush=True)
            deadline = time.time() + 180
            next_heartbeat = time.time() + 15
            try:
                while time.time() < deadline:
                    time.sleep(2)
                    current_url = page.url.lower()
                    if "/project/" in current_url and "sign" not in current_url:
                        logged_in = True
                        print("    Login detected!", flush=True)
                        break
                    if time.time() >= next_heartbeat:
                        remaining = max(0, int(deadline - time.time()))
                        print(
                            f"    Still waiting... ({remaining}s remaining — Ctrl+C to abort)",
                            flush=True,
                        )
                        next_heartbeat = time.time() + 15
            except KeyboardInterrupt:
                ctx.close()
                raise RuntimeError("Aborted by user — Langfuse login did not complete.")

        ctx.close()

    if not logged_in:
        raise RuntimeError("Langfuse sign-in did not complete.")

    print("    Langfuse session saved in browser profile.")
    return {}


if __name__ == "__main__":
    import argparse

    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import DEFAULT_ENV_FILE
    from shared_utils.playwright_sso import load_env

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = load_env(DEFAULT_ENV_FILE)
    profile = _profile_dir()

    if not args.force and check(env):
        print(f"Langfuse session ok ({profile}) — nothing to do. Use --force to refresh.")
        sys.exit(0)

    capture(env)
    print(f"  Session profile: {profile}")
