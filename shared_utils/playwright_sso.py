#!/usr/bin/env python3
"""
Browser session refresher — discovery orchestrator.

Discovers all tool_connections/*/sso.py plugins and delegates to them.
Each plugin exposes: TOOL_NAME, check(env) -> bool, capture(env) -> dict.
Optional CONFIG_ENV_KEYS lists non-secret config vars that may be written to
.env (instance URLs, workspace URLs). Auth stays in each tool's browser profile
at ~/.browser_automation/{tool}_profile/ — never in .env.

Usage:
    python3 playwright_sso.py                  # refresh all expired sessions
    python3 playwright_sso.py --force          # refresh all regardless
    python3 playwright_sso.py --slack-only     # refresh Slack only
    python3 playwright_sso.py --grafana-only   # refresh Grafana only
    python3 playwright_sso.py --slack-only --account acme
    python3 playwright_sso.py --list           # list discovered plugins
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

try:
    from browser import DEFAULT_ENV_FILE, profile_dir_for
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from browser import DEFAULT_ENV_FILE, profile_dir_for

ENV_FILE = DEFAULT_ENV_FILE
TOOL_CONNECTIONS_DIR = Path(__file__).parents[1] / "tool_connections"


# ---------------------------------------------------------------------------
# .env helpers — config only; never store session tokens here
# ---------------------------------------------------------------------------

def clean_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env(env_path: Path = ENV_FILE) -> dict[str, str]:
    if not env_path.exists():
        return {}
    return {k.strip(): clean_env_value(v) for line in env_path.read_text().splitlines()
            if "=" in line and not line.startswith("#") for k, v in [line.split("=", 1)]}


def write_env(tokens: dict[str, str], env_path: Path = ENV_FILE) -> None:
    if not tokens:
        return
    env_path.parent.mkdir(parents=True, exist_ok=True)
    content = env_path.read_text() if env_path.exists() else ""
    for key, value in tokens.items():
        new_line = f"{key}={value}"
        if re.search(rf"^{re.escape(key)}=", content, flags=re.MULTILINE):
            content = re.sub(rf"^{re.escape(key)}=.*$", new_line, content, flags=re.MULTILINE)
        else:
            content += f"\n{new_line}\n"
    env_path.write_text(content)
    print(f"  Updated {env_path}")


def account_prefix(account: str) -> str:
    """Normalize a user-facing account name for .env key prefixes."""
    prefix = re.sub(r"[^A-Za-z0-9]+", "_", account).strip("_").upper()
    if not prefix:
        raise ValueError("--account must contain at least one letter or number")
    return prefix


def account_env_key(account: str, key: str) -> str:
    return f"{account_prefix(account)}_{key}"


def scoped_env_key(account: str, key: str) -> str:
    if "_" not in key:
        return account_env_key(account, key)
    namespace, suffix = key.split("_", 1)
    return f"{namespace}_{account_prefix(account)}_{suffix}"


def config_keys(mod: object) -> list[str]:
    return list(getattr(mod, "CONFIG_ENV_KEYS", []))


def filter_config_tokens(mod: object, tokens: dict[str, str]) -> dict[str, str]:
    allowed = set(config_keys(mod))
    return {k: v for k, v in tokens.items() if k in allowed}


def env_for_account(env: dict[str, str], mod: object, account: str | None) -> dict[str, str]:
    """Overlay account-scoped config values onto the plugin's normal env key names."""
    if not account:
        return dict(env)

    scoped_env = dict(env)
    for key in config_keys(mod):
        scoped_key = scoped_env_key(account, key)
        legacy_key = account_env_key(account, key)
        if scoped_key in env:
            scoped_env[key] = env[scoped_key]
        elif legacy_key in env:
            scoped_env[key] = env[legacy_key]
        else:
            scoped_env.pop(key, None)
    scoped_env["SSO_ACCOUNT"] = account
    scoped_env["SSO_ACCOUNT_PREFIX"] = account_prefix(account)
    return scoped_env


def tokens_for_account(tokens: dict[str, str], account: str | None) -> dict[str, str]:
    if not account:
        return tokens
    return {scoped_env_key(account, key): value for key, value in tokens.items()}


def profile_for_plugin(mod: object, account: str | None) -> Path:
    tool = getattr(mod, "TOOL_NAME", None)
    if not tool:
        raise ValueError(f"Plugin {mod!r} missing TOOL_NAME")
    return profile_dir_for(tool, account)


# ---------------------------------------------------------------------------
# Plugin discovery
# ---------------------------------------------------------------------------

def discover_plugins() -> dict[str, object]:
    plugins = {}
    for sso_path in sorted(TOOL_CONNECTIONS_DIR.glob("*/sso.py")):
        spec = importlib.util.spec_from_file_location(
            f"sso_{sso_path.parent.name}", sso_path
        )
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            print(f"  Warning: failed to load {sso_path}: {e}", file=sys.stderr)
            continue
        if hasattr(mod, "TOOL_NAME") and hasattr(mod, "check") and hasattr(mod, "capture"):
            plugins[mod.TOOL_NAME] = mod
    return plugins


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    plugins = discover_plugins()

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--env-file", type=Path, default=ENV_FILE, metavar="PATH")
    parser.add_argument("--force", action="store_true", help="Refresh even if session is valid")
    parser.add_argument("--list", action="store_true", help="List discovered plugins and exit")
    parser.add_argument(
        "--account",
        metavar="NAME",
        help=(
            "Account-scoped config (e.g. SLACK_ACME_WORKSPACE_URL in .env). "
            "Uses a separate profile at ~/.browser_automation/{tool}_{account}_profile/."
        ),
    )
    parser.add_argument(
        "--login-hint",
        metavar="EMAIL",
        help="Optional account/email hint for SSO plugins that support it.",
    )

    for name in plugins:
        parser.add_argument(f"--{name}-only", action="store_true",
                            help=f"Refresh {name} only")

    args = parser.parse_args()

    if args.list:
        print("Discovered SSO plugins (profiles: ~/.browser_automation/{tool}_profile/):")
        for name, mod in plugins.items():
            cfg = ", ".join(config_keys(mod)) or "(no .env config — profile only)"
            print(f"  {name:20s}  .env: {cfg}")
        return

    env = load_env(args.env_file)
    if args.login_hint:
        env["SSO_LOGIN_HINT"] = args.login_hint

    only_flags = {name: getattr(args, f"{name}_only", False) for name in plugins}
    any_only = any(only_flags.values())
    if args.account and sum(1 for selected in only_flags.values() if selected) != 1:
        parser.error("--account must be used with exactly one --<tool>-only flag")

    targets = {name: mod for name, mod in plugins.items()
               if not any_only or only_flags.get(name)}

    print("Browser session refresher")
    print(f"  .env (config only): {args.env_file}")
    print()

    for name, mod in targets.items():
        plugin_env = env_for_account(env, mod, args.account)
        label = f"{name}:{args.account}" if args.account else name
        profile = profile_for_plugin(mod, args.account)

        if not args.force:
            valid = mod.check(plugin_env)
            status = "ok" if valid else "expired or missing"
            print(f"  {label}: {status}  ({profile})")
            if valid:
                continue

        print(f"  Refreshing {label} → {profile}")
        try:
            raw_tokens = tokens_for_account(mod.capture(plugin_env), args.account)
            config_tokens = filter_config_tokens(mod, raw_tokens)
            if config_tokens:
                write_env(config_tokens, args.env_file)
                env.update(config_tokens)
                for k in config_tokens:
                    print(f"    Updated .env: {k}")
            print(f"    Session saved in browser profile: {profile}")
        except Exception as e:
            print(f"  ERROR refreshing {name}: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
