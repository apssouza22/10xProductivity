"""
Confluence browser session capture — plugin for playwright_sso.py discovery.

Opens Confluence via the shared browser profile. Session cookies stay in
~/.browser_automation/agent_profile/ — not in .env. Only CONFLUENCE_BASE_URL
belongs in .env.

Works for Confluence Cloud (atlassian.net/wiki) and Server/Data Center with
corporate SSO.

Standalone usage:
    python3 tool_connections/confluence/sso.py
    python3 tool_connections/confluence/sso.py --force
"""

import json
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

TOOL_NAME = "confluence"
CONFIG_ENV_KEYS = ["CONFLUENCE_BASE_URL"]


def _profile_dir() -> Path:
    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import profile_dir_for
    return profile_dir_for()


def _normalize_base_url(base: str) -> str:
    base = (base or "").strip().rstrip("/")
    if base and "://" not in base:
        base = f"https://{base}"
    return base


def _api_root(base: str) -> str:
    return f"{_normalize_base_url(base)}/rest/api"


def check(env: dict) -> bool:
    """Return True if the Confluence browser session is valid."""
    base = env.get("CONFLUENCE_BASE_URL", "")
    if not base or "yourcompany" in base:
        return False
    try:
        sys.path.insert(0, str(Path(__file__).parents[2]))
        from shared_utils.session_request import tool_request

        result = tool_request(
            "confluence",
            "GET",
            f"{_api_root(base)}/user/current",
            warmup_url=_normalize_base_url(base),
        )
        user = result.get("json") or {}
        if user.get("type") == "anonymous" or user.get("displayName") == "Anonymous":
            return False
        return result.get("ok") is True and bool(user.get("displayName") or user.get("username"))
    except Exception:
        return False


def _session_valid(page, base: str) -> bool:
    """Probe the REST API from the page context (cookies attached)."""
    try:
        payload = page.evaluate(
            """async (base) => {
                const url = base.replace(/\\/$/, '') + '/rest/api/user/current';
                const headers = { 'Accept': 'application/json' };
                if (base.includes('atlassian.net')) {
                    headers['X-Atlassian-Token'] = 'no-check';
                }
                const r = await fetch(url, { credentials: 'include', headers });
                const text = await r.text();
                return { status: r.status, text };
            }""",
            _normalize_base_url(base),
        )
        if payload.get("status") != 200:
            return False
        data = json.loads(payload.get("text") or "{}")
        if data.get("type") == "anonymous" or data.get("displayName") == "Anonymous":
            return False
        return bool(data.get("displayName") or data.get("username"))
    except Exception:
        return False


def capture(env: dict) -> dict:
    """Open Confluence in the persistent profile until browser sign-in succeeds."""
    base = _normalize_base_url(env.get("CONFLUENCE_BASE_URL", ""))
    if not base or "yourcompany" in base:
        raise RuntimeError(
            "CONFLUENCE_BASE_URL not set in .env. "
            "Add CONFLUENCE_BASE_URL=https://yourcompany.atlassian.net/wiki "
            "or https://confluence.yourcompany.com and retry."
        )

    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    print(f"  Opening Confluence ({base}) — complete sign-in in the browser if prompted...")
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
        page.goto(base, wait_until="domcontentloaded", timeout=60_000)
        time.sleep(2)

        if _session_valid(page, base):
            print("    Already logged in.", flush=True)
            ctx.close()
            print("    Confluence session saved in browser profile.")
            return {}

        print("  Waiting for sign-in to complete (3 min timeout — Ctrl+C to abort)...", flush=True)
        deadline = time.time() + 180
        next_heartbeat = time.time() + 15
        try:
            while time.time() < deadline:
                time.sleep(2)
                if _session_valid(page, base):
                    print("    Login detected!", flush=True)
                    break
                if time.time() >= next_heartbeat:
                    remaining = max(0, int(deadline - time.time()))
                    hint = page.url[:80]
                    print(f"    Still waiting... ({remaining}s) url={hint}", flush=True)
                    next_heartbeat = time.time() + 15
            else:
                raise RuntimeError(
                    "Confluence login did not complete — REST API still returns unauthorized. "
                    f"Last URL: {page.url}"
                )
        except KeyboardInterrupt:
            ctx.close()
            raise RuntimeError("Aborted by user — Confluence login did not complete.")

        ctx.close()

    print("    Confluence session saved in browser profile.")
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
        print(f"Confluence session ok ({profile}) — nothing to do. Use --force to refresh.")
        sys.exit(0)

    capture(env)
    print(f"  Session profile: {profile}")
