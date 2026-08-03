"""
Grafana browser session capture — plugin for playwright_sso.py discovery.

Opens Grafana via the shared browser profile. The grafana_session cookie
stays in ~/.browser_automation/agent_profile/ — not in .env.
Only GRAFANA_BASE_URL belongs in .env.

Standalone usage:
    python3 tool_connections/grafana/sso.py
    python3 tool_connections/grafana/sso.py --force
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

TOOL_NAME = "grafana"
CONFIG_ENV_KEYS = ["GRAFANA_BASE_URL"]


def _profile_dir() -> Path:
    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import profile_dir_for
    return profile_dir_for()


def check(env: dict) -> bool:
    """Return True if the Grafana browser profile has a valid session."""
    base = env.get("GRAFANA_BASE_URL", "")
    if not base or "yourcompany" in base:
        return False
    try:
        sys.path.insert(0, str(Path(__file__).parents[2]))
        from shared_utils.session_request import tool_request

        result = tool_request(
            "grafana",
            "GET",
            f"{base.rstrip('/')}/api/user",
            warmup_url=base,
        )
        return result.get("ok") is True
    except Exception:
        return False


def capture(env: dict) -> dict:
    """Open Grafana in a persistent profile until login succeeds."""
    base = env.get("GRAFANA_BASE_URL", "")
    if not base or "yourcompany" in base:
        raise RuntimeError(
            "GRAFANA_BASE_URL not set in .env. "
            "Add GRAFANA_BASE_URL=https://grafana.yourcompany.com and retry."
        )

    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    print(f"  Opening Grafana ({base}) — complete sign-in in the browser if prompted...")
    print(f"  Profile: {profile}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            channel="chrome",
            headless=False,
            ignore_https_errors=True,
            args=["--window-size=1200,800", "--window-position=100,100"],
        )
        page = ctx.new_page()
        page.goto(base, wait_until="networkidle", timeout=60_000)
        time.sleep(2)

        session = None
        grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([base])}
        session = grafana_cookies.get("grafana_session")

        if not session:
            print("  Waiting for manual login (3 min timeout — Ctrl+C to abort)...", flush=True)
            deadline = time.time() + 180
            next_heartbeat = time.time() + 15
            try:
                while time.time() < deadline:
                    time.sleep(2)
                    grafana_cookies = {c["name"]: c["value"] for c in ctx.cookies([base])}
                    session = grafana_cookies.get("grafana_session")
                    if session:
                        print("    Login detected!", flush=True)
                        break
                    if time.time() >= next_heartbeat:
                        remaining = max(0, int(deadline - time.time()))
                        print(f"    Still waiting... ({remaining}s remaining — Ctrl+C to abort)", flush=True)
                        next_heartbeat = time.time() + 15
            except KeyboardInterrupt:
                ctx.close()
                raise RuntimeError("Aborted by user — Grafana login did not complete.")

        ctx.close()

    if not session:
        raise RuntimeError("No grafana_session cookie captured.")

    print("    Grafana session saved in browser profile.")
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
        print(f"Grafana session ok ({profile}) — nothing to do. Use --force to refresh.")
        sys.exit(0)

    capture(env)
    print(f"  Session profile: {profile}")
