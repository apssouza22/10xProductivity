#!/usr/bin/env python3
"""
LinkedIn session capture via Playwright.

Uses a persistent browser profile at ~/.browser_automation/linkedin_profile/ so
LinkedIn treats the browser as a known device — no 2FA after the first login.
Auth cookies (li_at, JSESSIONID) stay in the profile — not in .env.

Usage:
    python3 tool_connections/linkedin/sso.py
    python3 tool_connections/linkedin/sso.py --force
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared_utils.browser import (
    sync_playwright,
    DEFAULT_ENV_FILE,
    profile_dir_for,
)

TOOL_NAME = "linkedin"
CONFIG_ENV_KEYS: list[str] = []
PROFILE_DIR = profile_dir_for(TOOL_NAME)


def _open_persistent(p):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return p.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        channel="chrome",
        headless=False,
        args=["--window-size=1024,768", "--window-position=100,100"],
        ignore_https_errors=True,
    )


def check(env: dict | None = None) -> bool:
    """Return True if the LinkedIn browser profile has a valid session."""
    try:
        from shared_utils.session_request import tool_request

        result = tool_request(
            "linkedin",
            "GET",
            "https://www.linkedin.com/voyager/api/me",
        )
        return result.get("ok") is True
    except Exception:
        return False


def capture(env: dict | None = None) -> dict:
    """Open LinkedIn in the persistent profile until login succeeds."""
    print(f"  Using persistent profile: {PROFILE_DIR}")
    print("  Opening LinkedIn login page...")
    with sync_playwright() as p:
        ctx = _open_persistent(p)
        page = ctx.new_page()

        page.goto("https://www.linkedin.com/login", wait_until="commit", timeout=30_000)
        print("  Log in to LinkedIn in the browser window.")
        print("  (If already logged in from a previous run, it will skip straight to feed.)")
        print("  Waiting for feed to load (up to 3 min — Ctrl+C to abort)...", flush=True)

        deadline = time.time() + 180
        next_heartbeat = time.time() + 15
        try:
            while time.time() < deadline:
                time.sleep(2)
                cookies = {c["name"]: c["value"] for c in ctx.cookies(["https://www.linkedin.com"])}
                li_at = cookies.get("li_at")
                jsession = cookies.get("JSESSIONID", "").strip('"')
                current_url = page.url
                if li_at and jsession and (
                    "linkedin.com/feed" in current_url
                    or "linkedin.com/in/" in current_url
                    or "linkedin.com/mynetwork" in current_url
                ):
                    print("    Login detected!", flush=True)
                    break
                if time.time() >= next_heartbeat:
                    remaining = max(0, int(deadline - time.time()))
                    print(f"    Still waiting... ({remaining}s remaining — Ctrl+C to abort)", flush=True)
                    next_heartbeat = time.time() + 15
            else:
                raise RuntimeError("No li_at cookie found — login may not have completed within 3 minutes.")
        except KeyboardInterrupt:
            ctx.close()
            raise RuntimeError("Aborted by user — LinkedIn login did not complete.")

        ctx.close()

    print("    LinkedIn session saved in browser profile.")
    return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="Refresh even if session is still valid")
    args = parser.parse_args()

    if not args.force and check():
        print(f"LinkedIn session ok ({PROFILE_DIR}) — nothing to do. Use --force to refresh.")
        return

    capture()
    print(f"  Session profile: {PROFILE_DIR}")


if __name__ == "__main__":
    main()
