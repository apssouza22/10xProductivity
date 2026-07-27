"""
Grafana SSO capture — plugin for playwright_sso.py discovery.

Navigates to your Grafana instance via a persistent browser profile, completes
SSO login, and captures the grafana_session cookie.

Standalone usage:
    python3 tool_connections/grafana/sso.py
    python3 tool_connections/grafana/sso.py --force
"""

import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TOOL_NAME = "grafana"
ENV_KEYS = ["GRAFANA_SESSION"]
ACCOUNT_ENV_KEYS = ["GRAFANA_BASE_URL"]


def _profile_dir() -> Path:
    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import BROWSER_AUTOMATION_DIR
    return BROWSER_AUTOMATION_DIR / "grafana_profile"


def check(env: dict) -> bool:
    """Return True if the Grafana browser session is valid."""
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
    """Open Grafana in a persistent profile, complete SSO, return grafana_session cookie."""
    base = env.get("GRAFANA_BASE_URL", "")
    if not base or "yourcompany" in base:
        raise RuntimeError(
            "GRAFANA_BASE_URL not set in .env. "
            "Add GRAFANA_BASE_URL=https://grafana.yourcompany.com and retry."
        )

    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    print(f"  Opening Grafana ({base}) — SSO should auto-complete...")
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

    print(f"    Grafana session captured ({len(session)} chars)")
    return {"GRAFANA_SESSION": session}


if __name__ == "__main__":
    import argparse
    import re
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import DEFAULT_ENV_FILE

    ENV_FILE = DEFAULT_ENV_FILE

    def _load_env():
        if not ENV_FILE.exists():
            return {}
        return {k.strip(): v.strip() for line in ENV_FILE.read_text().splitlines()
                if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}

    def _write_env(tokens):
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        for key, value in tokens.items():
            new_line = f"{key}={value}"
            if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
                content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
            elif "# --- Grafana" in content:
                content = content.replace("# --- Grafana\n", f"# --- Grafana\n{new_line}\n", 1)
            else:
                content += f"\n# --- Grafana\n{new_line}\n"
        ENV_FILE.write_text(content)

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = _load_env()
    if not args.force and check(env):
        print("GRAFANA_SESSION: ok — nothing to do. Use --force to refresh.")
        sys.exit(0)

    tokens = capture(env)
    _write_env(tokens)
    print(f"  Written to {ENV_FILE}")
