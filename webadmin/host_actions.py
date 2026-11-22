"""Maintenance actions the admin website may ask the host for.

Owner, 2026-11-22: the state sync had failed for a day, and the only way
to look at it or fix it was an SSH session from the desktop. The choice
taken was a fixed list, not a command box: the dashboard stays the
unprivileged, sandboxed toc user and never runs anything itself.

It asks by writing one file, ``<requests>/request``, holding ``<id>
<action>``; ``deploy/windows-vm/toc-host-action.path`` starts the root
helper ``toc-host-action`` whenever that file is there, and the helper runs
only the actions it names (the same list as ACTIONS below) and writes the
result to ``<results>/<id>``, its own directory, readable by group toc.
Nothing the dashboard writes is ever run or echoed. One request at a time:
a new one is refused while one waits or runs.

Both routes are behind the admin token (server.verify_token). The feature
is on only where the helper's results directory exists -- toc-deploy and
toc-restore make it -- so an install without the helper says so instead of
leaving a request nobody will read.
"""
from __future__ import annotations

import os
import re
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# The helper's own list must match this one: tests/test_host_actions.py
# holds them together.
ACTIONS: Dict[str, Dict[str, Any]] = {
    "state-sync": {
        "title": "Run the state sync now",
        "description": "Pushes player saves and logs to GitHub now, and shows "
                       "the sync's last journal lines -- the reason when it fails.",
        "danger": False,
    },
    "state-sync-reclone": {
        "title": "Repair the state sync",
        "description": "Moves the sync's git clone aside (kept, not deleted) and "
                       "runs the sync, which clones afresh. For a sync failing on "
                       "a broken clone, such as \"object file ... is empty\".",
        "danger": False,
    },
    "auto-deploy": {
        "title": "Check for a deploy now",
        "description": "Runs the auto-deployer's check at once instead of waiting "
                       "up to ten minutes. It still ships only code CI passed, and "
                       "still holds while anybody is playing.",
        "danger": False,
    },
    "deploy": {
        "title": "Deploy main now",
        "description": "Builds and ships the tip of main at once, as toc-deploy "
                       "run by hand does: players are warned and saved, the game "
                       "restarts, and it rolls back by itself if the new code does "
                       "not come back healthy.",
        "danger": True,
        "phrase": "DEPLOY",
    },
    "restart-web": {
        "title": "Restart the website",
        "description": "Restarts the dashboard service. This page reconnects in a "
                       "few seconds; the game is not touched.",
        "danger": False,
    },
    "status": {
        "title": "Show the host's health",
        "description": "Changes nothing: which services and timers are up, the "
                       "state sync's last result, disk, memory, and the recent "
                       "journal of the sync, recovery and auto-deployer.",
        "danger": False,
    },
}

# What a request committed to ops/host-requests.txt may ask for (the
# auto-deployer reads it; see toc-auto-deploy). Never "deploy": a push to
# main is already a deploy, through CI and the player hold, and a request
# file must not be a way round either. Nor "auto-deploy", which is the
# reader itself. toc-auto-deploy's own list is held to this one by
# tests/test_host_actions.py.
GIT_ACTIONS = ("state-sync", "state-sync-reclone", "restart-web", "status")

ID_RE = re.compile(r"^[0-9a-f]{32}$")
REQUEST_NAME = "request"
# A result left "running" longer than this belongs to a helper that died;
# it no longer blocks a new request.
RUNNING_STALE_SECONDS = 2 * 60 * 60
OUTPUT_MAX = 65536
RESULTS_SHOWN = 10


class HostActionError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def request_dir() -> Path:
    return Path(os.getenv("TOC_HOST_ACTION_REQUESTS", "/var/lib/toc/host-actions"))


def result_dir() -> Path:
    return Path(os.getenv("TOC_HOST_ACTION_RESULTS", "/var/lib/toc-host-actions"))


def available(results: Optional[Path] = None) -> bool:
    results = results or result_dir()
    return results.is_dir() and os.access(results, os.R_OK | os.X_OK)


def _number(text: str) -> Optional[int]:
    text = text.strip()
    return int(text) if re.fullmatch(r"-?\d{1,19}", text) else None


def parse_result(text: str) -> Optional[Dict[str, Any]]:
    """A result file: ``key value`` lines, a blank line, then the output."""
    head, _, output = text.partition("\n\n")
    fields: Dict[str, str] = {}
    for line in head.splitlines():
        key, _, value = line.partition(" ")
        fields[key] = value
    if not ID_RE.match(fields.get("id", "")):
        return None
    action = fields.get("action", "")
    return {
        "id": fields["id"],
        "action": action if action in ACTIONS else "unknown",
        "title": ACTIONS.get(action, {}).get("title", "Refused request"),
        "state": fields.get("state", "unknown"),
        "started": _number(fields.get("started", "")),
        "finished": _number(fields.get("finished", "")) or None,
        "exit": _number(fields.get("exit", "")),
        "output": output[-OUTPUT_MAX:],
    }


def read_results(results: Optional[Path] = None, limit: int = RESULTS_SHOWN) -> List[Dict[str, Any]]:
    results = results or result_dir()
    found: List[Dict[str, Any]] = []
    try:
        names = [p for p in results.iterdir() if ID_RE.match(p.name) and p.is_file()]
    except OSError:
        return []
    for path in names:
        try:
            parsed = parse_result(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if parsed is not None:
            found.append(parsed)
    found.sort(key=lambda r: (r["started"] or 0, r["id"]), reverse=True)
    return found[:limit]


def busy(requests: Path, found: List[Dict[str, Any]], now: float) -> Optional[str]:
    if (requests / REQUEST_NAME).exists():
        return "waiting"
    for result in found:
        if result["state"] == "running" and (result["started"] or 0) > now - RUNNING_STALE_SECONDS:
            return "running"
    return None


def snapshot(now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    results = result_dir()
    ok = available(results)
    found = read_results(results) if ok else []
    return {
        "available": ok,
        "busy": busy(request_dir(), found, now) if ok else None,
        "actions": [dict(name=name, **{k: v for k, v in spec.items()})
                    for name, spec in ACTIONS.items()],
        "results": found,
        "generated": now,
    }


def submit(action: str, confirm: str, now: Optional[float] = None) -> Dict[str, Any]:
    """Ask the helper for an action. Raises HostActionError with an HTTP status."""
    now = time.time() if now is None else now
    if action not in ACTIONS:
        raise HostActionError(400, "No such action.")
    if confirm != action:
        raise HostActionError(400, "The action was not confirmed.")
    results = result_dir()
    if not available(results):
        raise HostActionError(503, "Host actions are not installed on this server "
                                   "(toc-deploy installs them).")
    requests = request_dir()
    state = busy(requests, read_results(results), now)
    if state:
        raise HostActionError(409, f"Another action is {state}; wait for it to finish.")
    try:
        requests.mkdir(mode=0o750, parents=True, exist_ok=True)
    except OSError as exc:
        raise HostActionError(500, f"Could not make the request directory: {exc.strerror}")
    action_id = secrets.token_hex(16)
    tmp = requests / f".request.{action_id}.tmp"
    try:
        with open(tmp, "x", encoding="ascii") as handle:
            handle.write(f"{action_id} {action}\n")
        # Linked in whole, and only if no request is there: the helper is
        # started the moment the name appears, and must never read half a
        # line, nor a second request overwrite the first.
        os.link(tmp, requests / REQUEST_NAME)
    except FileExistsError:
        raise HostActionError(409, "Another action is waiting; wait for it to finish.")
    except OSError as exc:
        raise HostActionError(500, f"Could not write the request: {exc.strerror}")
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    return {"id": action_id, "action": action, "requested": now}
