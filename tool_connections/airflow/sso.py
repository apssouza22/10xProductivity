"""
Apache Airflow browser session capture — plugin for playwright_sso.py discovery.

Opens Airflow via the shared browser profile. The FAB session cookie stays in
~/.browser_automation/agent_profile/ — not in .env.

Standalone usage:
    python3 tool_connections/airflow/sso.py
    python3 tool_connections/airflow/sso.py --force
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright

TOOL_NAME = "airflow"
CONFIG_ENV_KEYS = ["AIRFLOW_BASE_URL"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _profile_dir() -> Path:
    sys.path.insert(0, str(_repo_root()))
    from shared_utils.browser import profile_dir_for

    return profile_dir_for()


def _normalize_base(base: str) -> str:
    base = (base or "").strip().rstrip("/")
    if base and "://" not in base:
        base = f"http://{base}"
    return base


def _warmup_url(env: dict) -> str:
    return f"{_normalize_base(env.get("AIRFLOW_BASE_URL", ""))}/home"


def _probe_url(env: dict) -> str:
    return f"{_normalize_base(env.get("AIRFLOW_BASE_URL", ""))}/api/v1/dags?limit=1"


def _try_auto_login(page, env: dict) -> None:
    """Optional local FAB form fill — only during interactive sso capture, not API calls."""
    username = (env.get("AIRFLOW_USERNAME") or "").strip()
    password = (env.get("AIRFLOW_PASSWORD") or "").strip()
    if not username or not password:
        return
    if "/login" not in page.url:
        return
    try:
        page.get_by_label("Username").fill(username, timeout=5000)
        page.get_by_label("Password").fill(password, timeout=5000)
        page.get_by_role("button", name="Sign In").click()
        page.wait_for_load_state("domcontentloaded", timeout=30_000)
        time.sleep(1)
        print("    Auto-filled FAB login form.", flush=True)
    except Exception as exc:
        print(f"    Auto-login skipped: {exc}", flush=True)


def _api_ok(page, url: str) -> bool:
    try:
        payload = page.evaluate(
            """async (url) => {
                const r = await fetch(url, {
                    credentials: 'include',
                    headers: { 'Accept': 'application/json' },
                });
                const text = await r.text();
                return { status: r.status, text };
            }""",
            url,
        )
        if payload.get("status") != 200:
            return False
        data = json.loads(payload.get("text") or "{}")
        return "dags" in data or "version" in data
    except Exception:
        return False


def check(env: dict) -> bool:
    base = _normalize_base(env.get("AIRFLOW_BASE_URL", ""))
    if not base or "yourcompany" in base:
        return False
    try:
        sys.path.insert(0, str(_repo_root()))
        from shared_utils.session_request import tool_request

        result = tool_request(
            "airflow",
            "GET",
            _probe_url(env),
            warmup_url=_warmup_url(env),
            headers={"Accept": "application/json"},
            via_page_fetch=True,
        )
        data = result.get("json") or {}
        return result.get("ok") is True and "dags" in data
    except Exception:
        return False


def capture(env: dict) -> dict:
    base = _normalize_base(env.get("AIRFLOW_BASE_URL", ""))
    if not base:
        raise RuntimeError(
            "AIRFLOW_BASE_URL not set in .env. "
            "Add AIRFLOW_BASE_URL=http://localhost:8080 and retry."
        )

    profile = _profile_dir()
    profile.mkdir(parents=True, exist_ok=True)
    warmup = _warmup_url(env)
    login_url = f"{base}/login/?next={base}/home"
    print(f"  Opening Airflow ({warmup}) — sign in in the browser if prompted...")
    print(f"  Profile: {profile}")

    lock = profile / "SingletonLock"
    if lock.exists():
        lock.unlink(missing_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            channel="chrome",
            headless=False,
            ignore_https_errors=True,
            args=["--window-size=1400,900", "--window-position=100,100"],
        )
        page = ctx.new_page()
        page.goto(warmup, wait_until="domcontentloaded", timeout=120_000)
        time.sleep(2)

        if "/login" in page.url:
            _try_auto_login(page, env)

        if _api_ok(page, _probe_url(env)):
            print("    Session valid.", flush=True)
            ctx.close()
            return {}

        if "/login" in page.url:
            page.goto(login_url, wait_until="domcontentloaded", timeout=60_000)
            _try_auto_login(page, env)

        print("  Waiting for sign-in (3 min timeout — Ctrl+C to abort)...", flush=True)
        deadline = time.time() + 180
        next_heartbeat = time.time() + 15
        try:
            while time.time() < deadline:
                time.sleep(2)
                if _api_ok(page, _probe_url(env)):
                    print("    Login detected!", flush=True)
                    break
                if time.time() >= next_heartbeat:
                    remaining = max(0, int(deadline - time.time()))
                    print(f"    Still waiting... ({remaining}s) url={page.url[:80]}", flush=True)
                    next_heartbeat = time.time() + 15
            else:
                raise RuntimeError(
                    "Airflow login did not complete — /api/v1/dags still unauthorized. "
                    f"Last URL: {page.url}"
                )
        except KeyboardInterrupt:
            ctx.close()
            raise RuntimeError("Aborted by user — Airflow login did not complete.")

        ctx.close()

    print("    Airflow session saved in browser profile.")
    return {}


if __name__ == "__main__":
    import argparse

    sys.path.insert(0, str(_repo_root()))
    from shared_utils.browser import DEFAULT_ENV_FILE
    from shared_utils.playwright_sso import load_env

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    env = load_env(DEFAULT_ENV_FILE)
    profile = _profile_dir()

    if not args.force and check(env):
        print(f"Airflow session ok ({profile}) — nothing to do. Use --force to refresh.")
        sys.exit(0)

    capture(env)
    print(f"  Session profile: {profile}")
