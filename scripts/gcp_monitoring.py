#!/usr/bin/env python3
"""Create or update Circuit's uptime checks, log-based metrics and alert policies in Google Cloud Monitoring.

Used through `make monitoring ENV=production` (scripts/gcp.py renders the files below and then runs `apply` on them).

  render()  infra/monitoring/*.json + variables  ->  plain JSON texts (no network, tested)
  apply()   those JSON texts -> Google's REST APIs: find each object by its name, create it or update it (safe to repeat)

Why the REST API and not `gcloud monitoring ...`: the alert-policy and uptime-check commands live in alpha/beta groups whose flags
change between gcloud releases. The REST API is the stable contract, and it needs nothing but a token, which comes from
`gcloud auth print-access-token` (the token is held in memory; it is never printed and never put on a command line).

Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from string import Template
from typing import Any

REPO = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO / "infra" / "monitoring"
MONITORING = "https://monitoring.googleapis.com/v3"
LOGGING = "https://logging.googleapis.com/v2"
CHANNEL_PREFIX = "channel:"  # in a rendered policy: "channel:<display name>", replaced by the channel's resource name when applied

# Which fields an update may change (updateMask). Everything else about an existing object is left alone.
ALERT_MASK = "displayName,documentation,combiner,conditions,notificationChannels,alertStrategy,enabled"
UPTIME_MASK = "displayName,httpCheck,period,timeout"

Http = Callable[[str, str, str, dict | None], tuple[int, dict]]


class MonitoringError(Exception):
    """Something the person can fix; printed without a traceback."""


def host_of(url: str, lenient: bool = False) -> str:
    """'https://circuit-app.vercel.app/some/path' -> 'circuit-app.vercel.app'. `lenient` (dry runs) lets a <placeholder> through."""
    match = re.fullmatch(r"https?://([^/:?#\s]+)(?::\d+)?(?:[/?#].*)?", url.strip())
    if not match:
        if lenient:
            return url.strip()
        raise MonitoringError(f"'{url}' is not a full web address (https://host)")
    return match.group(1)


def variables(
    *, project: str, env: str, service: str, api_url: str, app_url: str, landing_url: str, channels: list[str], lenient: bool = False
) -> dict[str, str]:
    if not channels:
        raise MonitoringError(
            "No notification channels: alerts would fire into the void. Create an email and an SMS channel in the Cloud Console "
            "(Monitoring > Alerting > Edit notification channels) and list their names under [monitoring] in deploy/gcp/<env>.toml"
        )
    return {
        "PROJECT": project,
        "ENV": env,
        "SERVICE": service,
        "API_HOST": host_of(api_url, lenient),
        "APP_HOST": host_of(app_url, lenient),
        "LANDING_HOST": host_of(landing_url, lenient),
        "CHANNELS": json.dumps([CHANNEL_PREFIX + c for c in channels]),
    }


def render(values: dict[str, str], template_dir: Path = TEMPLATE_DIR) -> dict[str, str]:
    """{file name: JSON text} for every template. A leftover ${NAME} or invalid JSON stops here, not in Google's error message."""
    out: dict[str, str] = {}
    for path in sorted(template_dir.glob("*.json")):
        try:
            text = Template(path.read_text()).substitute(values)
        except KeyError as exc:
            raise MonitoringError(f"{path.name} uses ${{{exc.args[0]}}}, which gcp_monitoring.variables() does not provide") from exc
        try:
            body = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MonitoringError(f"{path.name} is not valid JSON after filling in the variables: {exc}") from exc
        if body.get("kind") not in KINDS:
            raise MonitoringError(f"{path.name}: 'kind' must be one of {', '.join(KINDS)}")
        out[path.name] = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    if not out:
        raise MonitoringError(f"No templates found in {template_dir}")
    return out


# ---- talking to Google ----------------------------------------------------------------------------------------------------


def gcloud_token(run: Callable[..., Any] = subprocess.run) -> str:
    done = run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True)
    token = (done.stdout or "").strip()
    if done.returncode != 0 or not token:
        raise MonitoringError("Could not get an access token. Run `gcloud auth login` and try again.")
    return token


def urllib_http(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:  # noqa: S310 (https URLs built in this file)
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"error": {"message": raw.decode(errors="replace")[:300]}}


def _error_text(payload: dict) -> str:
    err = payload.get("error") or {}
    return str(err.get("message") or err or payload)[:300]


def _call(http: Http, method: str, url: str, token: str, body: dict | None = None) -> dict:
    status, payload = http(method, url, token, body)
    if status >= 300:
        raise MonitoringError(f"{method} {url.split('?')[0]} -> {status}: {_error_text(payload)}")
    return payload


def _list_all(http: Http, url: str, token: str, key: str) -> list[dict]:
    items: list[dict] = []
    page = ""
    while True:
        sep = "&" if "?" in url else "?"
        payload = _call(http, "GET", url + (f"{sep}pageToken={urllib.parse.quote(page)}" if page else ""), token)
        items += payload.get(key, [])
        page = payload.get("nextPageToken", "")
        if not page:
            return items


# ---- one handler per kind -------------------------------------------------------------------------------------------------


def _apply_log_metric(http: Http, token: str, project: str, body: dict, ctx: dict) -> str:
    base = f"{LOGGING}/projects/{project}/metrics"
    name = body["name"]
    existing = {m["name"] for m in _list_all(http, base, token, "metrics")}
    if name in existing:
        _call(http, "PUT", f"{base}/{urllib.parse.quote(name)}", token, body)
        return "updated"
    _call(http, "POST", base, token, body)
    return "created"


def _apply_uptime(http: Http, token: str, project: str, body: dict, ctx: dict) -> str:
    base = f"{MONITORING}/projects/{project}/uptimeCheckConfigs"
    found = [c for c in _list_all(http, base, token, "uptimeCheckConfigs") if c.get("displayName") == body["displayName"]]
    if not found:
        _call(http, "POST", base, token, body)
        return "created"
    current = found[0]
    if current.get("monitoredResource") != body["monitoredResource"]:
        # the host cannot be edited in place (e.g. the API moved to a custom domain): replace the check
        _call(http, "DELETE", f"{MONITORING}/{current['name']}", token)
        _call(http, "POST", base, token, body)
        return "replaced"
    _call(http, "PATCH", f"{MONITORING}/{current['name']}?updateMask={UPTIME_MASK}", token, body)
    return "updated"


def _apply_alert(http: Http, token: str, project: str, body: dict, ctx: dict) -> str:
    base = f"{MONITORING}/projects/{project}/alertPolicies"
    body = {**body, "notificationChannels": [ctx["channels"](c) for c in body.get("notificationChannels", [])]}
    found = [p for p in _list_all(http, base, token, "alertPolicies") if p.get("displayName") == body["displayName"]]
    if found:
        _call(http, "PATCH", f"{MONITORING}/{found[0]['name']}?updateMask={ALERT_MASK}", token, body)
        return "updated"
    _call(http, "POST", base, token, body)
    return "created"


KINDS: dict[str, Callable[[Http, str, str, dict, dict], str]] = {
    "logMetric": _apply_log_metric,  # first: alert policies read these metrics
    "uptimeCheck": _apply_uptime,
    "alertPolicy": _apply_alert,
}


def resolve_channels(http: Http, token: str, project: str) -> Callable[[str], str]:
    """'channel:Circuit on-call email' -> 'projects/.../notificationChannels/123'. A missing channel stops the run."""
    found = _list_all(http, f"{MONITORING}/projects/{project}/notificationChannels", token, "notificationChannels")
    by_name = {c.get("displayName", ""): c["name"] for c in found}

    def resolve(ref: str) -> str:
        label = ref.removeprefix(CHANNEL_PREFIX)
        if label not in by_name:
            have = ", ".join(sorted(n for n in by_name if n)) or "none"
            raise MonitoringError(
                f"No notification channel named '{label}' in the project (have: {have}). Create it in the Cloud Console, or fix "
                "[monitoring] notification_channels in deploy/gcp/<env>.toml."
            )
        return by_name[label]

    return resolve


def apply(rendered: dict[str, str], project: str, http: Http = urllib_http, token: str = "", out: Callable[[str], None] = print) -> list[str]:
    """Create or update every object. Returns one line per object. Metrics go first, then checks, then policies."""
    objects = [(name, json.loads(text)) for name, text in rendered.items()]
    resolve = resolve_channels(http, token, project)
    for _, body in objects:  # every channel must exist BEFORE anything is created, so a typo cannot leave half the alerts behind
        for ref in body.get("notificationChannels", []):
            resolve(ref)
    ctx = {"channels": resolve}
    results = []
    for kind in KINDS:
        for name, body in objects:
            if body["kind"] != kind:
                continue
            body = {k: v for k, v in body.items() if k != "kind"}
            label = body.get("displayName") or body.get("name")
            what = KINDS[kind](http, token, project, body, ctx)
            line = f"{what:<9} {kind:<11} {label}"
            out("  " + line)
            results.append(line)
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gcp_monitoring.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["apply"])
    ap.add_argument("--project", required=True)
    ap.add_argument("--dir", required=True, help="folder with the rendered JSON files (scripts/gcp.py writes it)")
    ap.add_argument("--files", nargs="+", required=True, help="which files of that folder to apply (a leftover from an old run is not)")
    args = ap.parse_args(argv)
    try:
        folder = Path(args.dir)
        missing = [f for f in args.files if not (folder / f).is_file()]
        if missing:
            raise MonitoringError(f"Not found in {folder}: {', '.join(missing)}. Run it through `make monitoring`.")
        rendered = {f: (folder / f).read_text() for f in args.files}
        results = apply(rendered, args.project, token=gcloud_token())
        print(f"\nDone: {len(results)} objects in project {args.project}.")
        return 0
    except MonitoringError as exc:
        print(f"\nStopped: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
