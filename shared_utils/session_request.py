#!/usr/bin/env python3
"""
One-shot HTTP client that reuses a Playwright persistent browser profile.

Opens the tool's saved Chromium profile, optionally warms up the session,
then performs GET/POST/PUT/PATCH/DELETE via context.request (cookies attached
automatically). Callable from CLI or imported by other Python scripts.

Usage:
    python3 shared_utils/session_request.py \\
        --profile ~/.browser_automation/agent_profile \\
        --warmup-url https://www.linkedin.com/feed/ \\
        --method GET \\
        --url https://www.linkedin.com/voyager/api/me \\
        --header "X-RestLi-Protocol-Version: 2.0.0" \\
        --csrf-from-cookie JSESSIONID \\
        --json

    # When the tool connection file has a sniffer: block:
    python3 shared_utils/session_request.py \\
        --tool linkedin --method GET --url '...' --json

Library:
    from shared_utils.session_request import tool_request

    result = tool_request("linkedin", "GET", "https://www.linkedin.com/voyager/api/me")
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(_REPO_ROOT))
from shared_utils.browser import AGENT_PROFILE_DIR, sync_playwright
from shared_utils.traffic_sniffer import _load_tool_config

_BODY_LIMIT = 1 * 1024 * 1024  # 1 MB cap for CLI/library responses
_LOGIN_HINTS = ("login", "signin", "sign-in", "accounts.google.com", "auth.")

# Tool-specific defaults applied by tool_request() / --tool CLI flag.
_TOOL_DEFAULTS: dict[str, dict[str, Any]] = {
    "linkedin": {
        "csrf_cookie": "JSESSIONID",
        "headers": {
            "X-RestLi-Protocol-Version": "2.0.0",
            "Accept": "application/json",
        },
    },
    "slack": {
        "via_page_fetch": True,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
    },
    "grafana": {},
    "confluence": {
        "via_page_fetch": True,
        "headers": {"Accept": "application/json"},
    },
    "langfuse": {
        "via_page_fetch": True,
        "headers": {"Accept": "application/json"},
    },
}


def _log(msg: str, *, json_mode: bool) -> None:
    if json_mode:
        print(msg, file=sys.stderr)
    else:
        print(msg)


def _parse_header(raw: str) -> tuple[str, str]:
    if ":" not in raw:
        raise ValueError(f"Invalid header (expected KEY:VALUE): {raw!r}")
    key, value = raw.split(":", 1)
    return key.strip(), value.strip()


def _looks_like_login(url: str) -> bool:
    lower = url.lower()
    return any(hint in lower for hint in _LOGIN_HINTS)


def _cookie_value(ctx, name: str, url: str) -> str | None:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    for cookie in ctx.cookies([origin]):
        if cookie.get("name") == name:
            return cookie.get("value", "").strip('"')
    for cookie in ctx.cookies():
        if cookie.get("name") == name:
            return cookie.get("value", "").strip('"')
    return None


def _build_headers(
    ctx,
    url: str,
    headers: dict[str, str] | None,
    csrf_cookie: str | None,
) -> dict[str, str]:
    out = dict(headers or {})
    if csrf_cookie:
        token = _cookie_value(ctx, csrf_cookie, url)
        if token:
            out.setdefault("Csrf-Token", token)
    return out


def _slack_auth_headers(page, ctx, warmup_url: str) -> dict[str, str]:
    """Extract xoxc + d cookie from an authenticated Slack workspace page."""
    xoxc = page.evaluate(
        """(workspaceUrl) => {
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
            } catch (e) {}
            return null;
        }""",
        warmup_url,
    )
    if not xoxc:
        return {}

    d_cookie = ""
    for origin in (warmup_url, "https://slack.com", "https://app.slack.com"):
        d_cookie = _cookie_value(ctx, "d", origin) or d_cookie
    headers = {"Authorization": f"Bearer {xoxc}"}
    if d_cookie:
        headers["Cookie"] = f"d={d_cookie}"
    return headers


def _confluence_auth_headers(page, ctx, warmup_url: str) -> dict[str, str]:
    """Atlassian Cloud needs X-Atlassian-Token; optional XSRF from cookie."""
    headers: dict[str, str] = {}
    if "atlassian.net" in warmup_url.lower():
        headers["X-Atlassian-Token"] = "no-check"
        xsrf = _cookie_value(ctx, "atlassian.xsrf.token", warmup_url)
        if xsrf:
            headers["atl-xsrf-token"] = xsrf.strip('"')
    return headers


def _serialize_body(body: str | bytes | dict | None) -> tuple[str | bytes | None, dict[str, str]]:
    extra_headers: dict[str, str] = {}
    if body is None:
        return None, extra_headers
    if isinstance(body, dict):
        extra_headers["Content-Type"] = "application/json"
        return json.dumps(body), extra_headers
    return body, extra_headers


def _shape_response(
    status: int,
    resp_headers: dict[str, str],
    body_bytes: bytes,
) -> dict[str, Any]:
    truncated = len(body_bytes) > _BODY_LIMIT
    if truncated:
        body_bytes = body_bytes[:_BODY_LIMIT]

    result: dict[str, Any] = {
        "ok": 200 <= status < 400,
        "status": status,
        "headers": resp_headers,
    }

    try:
        text = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        result["binary"] = True
        result["body"] = base64.b64encode(body_bytes).decode("ascii")
        if truncated:
            result["truncated"] = True
        return result

    result["body"] = text
    if truncated:
        result["truncated"] = True

    try:
        result["json"] = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    return result


def _request_via_context(
    ctx,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: str | bytes | None,
    timeout_ms: int,
) -> dict[str, Any]:
    req = ctx.request
    method_upper = method.upper()
    kwargs: dict[str, Any] = {"headers": headers, "timeout": timeout_ms}

    if payload is not None:
        if isinstance(payload, (dict, list)):
            kwargs["data"] = json.dumps(payload)
        else:
            kwargs["data"] = payload

    dispatch = {
        "GET": req.get,
        "POST": req.post,
        "PUT": req.put,
        "PATCH": req.patch,
        "DELETE": req.delete,
    }
    if method_upper not in dispatch:
        raise ValueError(f"Unsupported method: {method}")

    if method_upper == "GET":
        kwargs.pop("data", None)

    response = dispatch[method_upper](url, **kwargs)
    try:
        body_bytes = response.body()
    except Exception:
        body_bytes = b""
    return _shape_response(response.status, dict(response.headers), body_bytes)


def _request_via_page_fetch(
    page,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: str | bytes | None,
) -> dict[str, Any]:
    body_str: str | None
    if payload is None:
        body_str = None
    elif isinstance(payload, bytes):
        body_str = payload.decode("utf-8", errors="replace")
    else:
        body_str = payload

    result = page.evaluate(
        """async ({ url, method, headers, body }) => {
            const opts = { method, headers: headers || {}, credentials: 'include' };
            if (body != null) opts.body = body;
            const r = await fetch(url, opts);
            const text = await r.text();
            const out = { status: r.status, headers: {}, body: text };
            r.headers.forEach((v, k) => { out.headers[k] = v; });
            return out;
        }""",
        {"url": url, "method": method.upper(), "headers": headers, "body": body_str},
    )
    body_bytes = (result.get("body") or "").encode("utf-8", errors="replace")
    return _shape_response(int(result.get("status", 0)), dict(result.get("headers") or {}), body_bytes)


def session_request(
    *,
    profile_dir: Path,
    method: str,
    url: str,
    warmup_url: str | None = None,
    headers: dict[str, str] | None = None,
    body: str | bytes | dict | None = None,
    csrf_cookie: str | None = None,
    timeout_ms: int = 30_000,
    headless: bool = True,
    via_page_fetch: bool = False,
    json_mode: bool = False,
    post_warmup_headers: Callable[[Any, Any, str], dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Perform one HTTP call using a persistent Playwright profile.

    Returns {ok, status, headers, body, json?, binary?, truncated?, error?}.
    """
    profile_dir = Path(profile_dir).expanduser().resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    stale_lock = profile_dir / "SingletonLock"
    if stale_lock.exists():
        stale_lock.unlink()

    payload, body_headers = _serialize_body(body)
    ctx = None

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(profile_dir),
                channel="chrome",
                headless=headless,
                ignore_https_errors=True,
                args=["--window-size=1280,900", "--window-position=100,50"],
            )

            page = ctx.new_page()
            if warmup_url:
                _log(f"  Warmup: {warmup_url}", json_mode=json_mode)
                page.goto(warmup_url, wait_until="domcontentloaded", timeout=timeout_ms)
                if _looks_like_login(page.url) and not via_page_fetch:
                    return {
                        "ok": False,
                        "error": f"Session not logged in — redirected to {page.url}",
                    }

            merged_headers = _build_headers(ctx, url, headers, csrf_cookie)
            if post_warmup_headers and warmup_url:
                merged_headers.update(post_warmup_headers(page, ctx, warmup_url))
            merged_headers.update(body_headers)

            if via_page_fetch:
                _log("  Request via page.fetch()", json_mode=json_mode)
                result = _request_via_page_fetch(page, method, url, merged_headers, payload)
            else:
                _log(f"  {method.upper()} {url}", json_mode=json_mode)
                result = _request_via_context(ctx, method, url, merged_headers, payload, timeout_ms)

            ctx.close()
            ctx = None
            return result

    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def _env_expand(value: str) -> str:
    """Expand ${VAR} placeholders using .env and os.environ."""
    from shared_utils.browser import DEFAULT_ENV_FILE, load_env_file

    env = {**load_env_file(DEFAULT_ENV_FILE), **os.environ}

    def repl(match: re.Match[str]) -> str:
        return env.get(match.group(1), match.group(0))

    return re.sub(r"\$\{([^}]+)\}", repl, value)


def _resolve_profile_and_warmup(
    tool: str | None,
    profile: Path | None,
    warmup_url: str | None,
) -> tuple[Path, str | None]:
    if tool:
        cfg = _load_tool_config(tool)
        if profile is None:
            profile = cfg["profile"]
        if warmup_url is None:
            warmup_url = _env_expand(cfg["url"])
    if profile is None:
        profile = AGENT_PROFILE_DIR
    return profile, warmup_url


def _tool_post_warmup_headers(tool: str) -> Callable[[Any, Any, str], dict[str, str]] | None:
    if tool == "slack":
        return _slack_auth_headers
    if tool == "confluence":
        return _confluence_auth_headers
    return None


def tool_request(
    tool: str,
    method: str,
    url: str,
    *,
    profile_dir: Path | None = None,
    warmup_url: str | None = None,
    headers: dict[str, str] | None = None,
    body: str | bytes | dict | None = None,
    csrf_cookie: str | None = None,
    timeout_ms: int = 30_000,
    headless: bool = True,
    via_page_fetch: bool | None = None,
    json_mode: bool = False,
) -> dict[str, Any]:
    """
    Perform one HTTP call for a named tool using its connection sniffer: config.

    Reads profile and warmup URL from the tool's connection-*.md frontmatter.
    Applies tool-specific auth defaults (CSRF cookies, Slack xoxc extraction, etc.).
    Pass profile_dir to override the default shared profile (rare — most tools use agent_profile).
    """
    resolved_profile, resolved_warmup = _resolve_profile_and_warmup(tool, profile_dir, warmup_url)
    defaults = _TOOL_DEFAULTS.get(tool, {})
    merged_headers = dict(defaults.get("headers") or {})
    if headers:
        merged_headers.update(headers)

    return session_request(
        profile_dir=resolved_profile,
        method=method,
        url=url,
        warmup_url=resolved_warmup,
        headers=merged_headers or None,
        body=body,
        csrf_cookie=csrf_cookie or defaults.get("csrf_cookie"),
        timeout_ms=timeout_ms,
        headless=headless,
        via_page_fetch=via_page_fetch if via_page_fetch is not None else bool(defaults.get("via_page_fetch")),
        json_mode=json_mode,
        post_warmup_headers=_tool_post_warmup_headers(tool),
    )


def _main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--tool", default=None, help="Tool name — reads profile/warmup from connection sniffer: block")
    parser.add_argument("--profile", type=Path, default=None, help="Persistent Chromium profile directory")
    parser.add_argument("--warmup-url", default=None, help="Navigate here before the API call")
    parser.add_argument("--method", required=True, help="GET, POST, PUT, PATCH, or DELETE")
    parser.add_argument("--url", required=True, help="Full request URL")
    parser.add_argument("--header", dest="headers", action="append", default=[], metavar="KEY:VALUE",
                        help="Extra header (repeatable)")
    parser.add_argument("--body", default=None, help="Request body string")
    parser.add_argument("--body-file", type=Path, default=None, help="Read request body from file")
    parser.add_argument("--csrf-from-cookie", default=None, metavar="NAME",
                        help="Set Csrf-Token header from cookie value (e.g. JSESSIONID)")
    parser.add_argument("--timeout-ms", type=int, default=30_000, help="Request timeout in ms")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--via-page-fetch", action="store_true",
                        help="Use page.evaluate(fetch) instead of context.request")
    parser.add_argument("--json", action="store_true", help="Print only JSON result to stdout")
    args = parser.parse_args()

    headers = dict(_parse_header(h) for h in args.headers)

    body: str | bytes | dict | None = None
    if args.body_file is not None:
        raw = args.body_file.read_text()
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
    elif args.body is not None:
        try:
            body = json.loads(args.body)
        except json.JSONDecodeError:
            body = args.body

    if args.tool:
        defaults = _TOOL_DEFAULTS.get(args.tool, {})
        if not args.csrf_from_cookie and defaults.get("csrf_cookie"):
            args.csrf_from_cookie = defaults["csrf_cookie"]
        for key, value in (defaults.get("headers") or {}).items():
            headers.setdefault(key, value)
        if not args.via_page_fetch and defaults.get("via_page_fetch"):
            args.via_page_fetch = True

        if args.tool and not args.json:
            print(f"  Tool: {args.tool}")

        result = tool_request(
            args.tool,
            args.method,
            args.url,
            warmup_url=args.warmup_url,
            headers=headers or None,
            body=body,
            csrf_cookie=args.csrf_from_cookie,
            timeout_ms=args.timeout_ms,
            headless=not args.headed,
            via_page_fetch=args.via_page_fetch or None,
            json_mode=args.json,
        )
        profile, _ = _resolve_profile_and_warmup(args.tool, args.profile, args.warmup_url)
    else:
        try:
            profile, warmup_url = _resolve_profile_and_warmup(None, args.profile, args.warmup_url)
        except (FileNotFoundError, ValueError) as exc:
            print(f"  ✗ {exc}", file=sys.stderr)
            sys.exit(1)

        if not args.json:
            print(f"  Profile: {profile}")

        result = session_request(
            profile_dir=profile,
            method=args.method,
            url=args.url,
            warmup_url=warmup_url,
            headers=headers or None,
            body=body,
            csrf_cookie=args.csrf_from_cookie,
            timeout_ms=args.timeout_ms,
            headless=not args.headed,
            via_page_fetch=args.via_page_fetch,
            json_mode=args.json,
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        status = result.get("status", "?")
        print(f"\n  → HTTP {status}  ok={result.get('ok')}")
        if result.get("json") is not None:
            print(json.dumps(result["json"], indent=2, ensure_ascii=False)[:4000])
        elif result.get("body"):
            print(result["body"][:2000])
        if result.get("error"):
            print(f"  Error: {result['error']}", file=sys.stderr)

    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    _main()
