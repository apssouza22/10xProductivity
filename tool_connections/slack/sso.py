"""
Slack SSO capture — plugin for playwright_sso.py discovery.

Opens the Slack workspace in the shared browser profile. Auth (xoxc token,
d cookie, localStorage) stays in ~/.browser_automation/profile/ — not
in .env. Only SLACK_WORKSPACE_URL belongs in .env.

Standalone usage:
    python3 tool_connections/slack/sso.py
    python3 tool_connections/slack/sso.py --force
    python3 tool_connections/slack/sso.py --account acme --force
"""

import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright

TOOL_NAME = "slack"
CONFIG_ENV_KEYS = ["SLACK_WORKSPACE_URL"]


def _profile_dir(env: dict | None = None) -> Path:
    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import SHARED_BROWSER_PROFILE
    return SHARED_BROWSER_PROFILE


def check(env: dict) -> bool:
    """Return True if the Slack browser profile has a valid session."""
    workspace_url = _normalize_workspace_url(env.get("SLACK_WORKSPACE_URL", ""))
    if not workspace_url or "yourcompany" in workspace_url:
        return False
    try:
        sys.path.insert(0, str(Path(__file__).parents[2]))
        from shared_utils.session_request import tool_request

        result = tool_request(
            "slack",
            "GET",
            "https://slack.com/api/auth.test",
            profile_dir=_profile_dir(env),
            warmup_url=workspace_url,
        )
        data = result.get("json") or {}
        return result.get("ok") is True and data.get("ok") is True
    except Exception:
        return False


def _normalize_workspace_url(workspace_url: str) -> str:
    if workspace_url and "://" not in workspace_url:
        workspace_url = f"https://{workspace_url}"
    parsed = urllib.parse.urlparse(workspace_url)
    if not parsed.netloc:
        return workspace_url
    return f"{parsed.scheme or 'https'}://{parsed.netloc}/"


def _account_prefix(account: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", account).strip("_").upper()
    if not prefix:
        raise ValueError("--account must contain at least one letter or number")
    return prefix


def _scoped_env_key(account: str, key: str) -> str:
    if "_" not in key:
        return f"{_account_prefix(account)}_{key}"
    namespace, suffix = key.split("_", 1)
    return f"{namespace}_{_account_prefix(account)}_{suffix}"


def _env_for_account(env: dict, account: str | None) -> dict:
    if not account:
        return dict(env)
    scoped = dict(env)
    for key in CONFIG_ENV_KEYS:
        scoped_key = _scoped_env_key(account, key)
        legacy_key = f"{_account_prefix(account)}_{key}"
        if scoped_key in env:
            scoped[key] = env[scoped_key]
        elif legacy_key in env:
            scoped[key] = env[legacy_key]
        else:
            scoped.pop(key, None)
    scoped["SSO_ACCOUNT"] = account
    scoped["SSO_ACCOUNT_PREFIX"] = _account_prefix(account)
    return scoped


def _wait_for_slack_login(page, workspace_url: str) -> None:
    deadline = time.time() + 180
    next_heartbeat = time.time() + 15
    while time.time() < deadline:
        time.sleep(2)
        if time.time() >= next_heartbeat:
            remaining = max(0, int(deadline - time.time()))
            print(f"    Still waiting... ({remaining}s remaining — Ctrl+C to abort)", flush=True)
            next_heartbeat = time.time() + 15
        try:
            xoxc = page.evaluate("""(workspaceUrl) => {
                const requestedHost = new URL(workspaceUrl).hostname.toLowerCase();
                const requestedDomain = requestedHost.split('.')[0];

                function tokenFromTeam(team) {
                    if (!team || typeof team !== 'object') return null;
                    const token = team.token || team.xoxc || team.client_token;
                    if (!token || !token.startsWith('xoxc')) return null;
                    const markers = [
                        team.domain, team.url, team.team_url, team.teamUrl,
                        team.name, team.team_name, team.enterprise_url,
                    ].filter(Boolean).map(String).join(' ').toLowerCase();
                    if (markers.includes(requestedHost) || markers.includes(requestedDomain)) {
                        return token;
                    }
                    return null;
                }

                try {
                    const cfg = JSON.parse(localStorage.getItem('localConfig_v2') || 'null');
                    if (cfg && cfg.teams) {
                        for (const team of Object.values(cfg.teams)) {
                            const token = tokenFromTeam(team);
                            if (token) return token;
                        }
                        const tokens = Object.values(cfg.teams)
                            .map(team => team && team.token)
                            .filter(token => token && token.startsWith('xoxc'));
                        if (tokens.length === 1) return tokens[0];
                    }
                } catch(e) {}
                return null;
            }""", workspace_url)
        except Exception:
            continue
        if xoxc:
            print("    Login detected!", flush=True)
            return
    raise RuntimeError(
        "No xoxc token found for the requested workspace — login may not "
        "have completed, or multiple teams are present and none matched "
        f"{workspace_url}."
    )


def capture(env: dict) -> dict:
    """Open Slack workspace in a persistent profile until login succeeds."""
    workspace_url = _normalize_workspace_url(env.get("SLACK_WORKSPACE_URL", ""))
    if not workspace_url or "yourcompany" in workspace_url:
        account = env.get("SSO_ACCOUNT")
        workspace_key = (
            _scoped_env_key(account, "SLACK_WORKSPACE_URL") if account else "SLACK_WORKSPACE_URL"
        )
        raise RuntimeError(
            f"{workspace_key} not set in .env. "
            f"Add {workspace_key}=https://yourcompany.slack.com/ and retry."
        )

    profile = _profile_dir(env)
    profile.mkdir(parents=True, exist_ok=True)
    print(f"  Opening Slack ({workspace_url}) — SSO should auto-complete...")
    print(f"  Profile: {profile}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            channel="chrome",
            headless=False,
            ignore_https_errors=True,
            args=["--window-size=900,600", "--window-position=100,100"],
        )
        page = ctx.new_page()
        page.goto(workspace_url, wait_until="commit", timeout=30_000)
        print("    Waiting for Slack login to complete (up to 3 min — Ctrl+C to abort)...", flush=True)
        try:
            _wait_for_slack_login(page, workspace_url)
        except KeyboardInterrupt:
            ctx.close()
            raise RuntimeError("Aborted by user — Slack login did not complete.")
        ctx.close()

    print("    Slack session saved in browser profile.")
    return {}


if __name__ == "__main__":
    import argparse

    sys.path.insert(0, str(Path(__file__).parents[2]))
    from shared_utils.browser import DEFAULT_ENV_FILE
    from shared_utils.playwright_sso import load_env, write_env

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--account", help="Account name for scoped SLACK_*_WORKSPACE_URL in .env")
    parser.add_argument("--workspace-url", help="Override SLACK_WORKSPACE_URL from .env")
    args = parser.parse_args()

    env = load_env(DEFAULT_ENV_FILE)
    workspace_override = {}
    if args.workspace_url:
        key = _scoped_env_key(args.account, "SLACK_WORKSPACE_URL") if args.account else "SLACK_WORKSPACE_URL"
        workspace_override[key] = _normalize_workspace_url(args.workspace_url)
        env[key] = workspace_override[key]

    plugin_env = _env_for_account(env, args.account)
    profile = _profile_dir(plugin_env)

    if not args.force and check(plugin_env):
        print(f"Slack session ok ({profile}) — nothing to do. Use --force to refresh.")
        sys.exit(0)

    capture(plugin_env)
    if workspace_override:
        write_env(workspace_override, DEFAULT_ENV_FILE)
    print(f"  Session profile: {profile}")
