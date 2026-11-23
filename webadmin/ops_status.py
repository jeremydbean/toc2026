"""Readiness and the operations summary, for monitors off the host (review,
2026-11-23).

/api/health answers 200 whenever the dashboard is up, game or no game, so a
monitor reading it could never see the game down. Two public routes now:

- /api/ready: 200 only when the game's loop answers MSSP with a player
  count -- the same question toc-game-probe and the deployer ask -- and 503
  otherwise (port closed, or open with no answer: a hung or half-started
  game). A monitor alarms on anything but 200.
- /api/ops-summary: the redacted JSON toc-ops-summary writes every five
  minutes (sync and backup freshness, disk, units, recovery), 200 when its
  overall verdict is "ok" and fresh, 503 when it is anything else, stale or
  missing. Nothing in it is private: it is the same file the state sync
  carries to the public repository, and addresses are masked again here.

Neither needs the admin token. Pure functions, so they test without FastAPI.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

SUMMARY_MAX_AGE = 900          # three runs of the five-minute timer
# The checks toc-ops-summary writes (deploy/windows-vm/toc-ops-summary).
CHECK_NAMES = ("game", "web", "public_sync", "mirror", "game_archives",
               "disk", "recovery", "units")
SUMMARY_MAX_BYTES = 64 * 1024
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def readiness(probe: Callable[[], tuple[bool, Optional[int]]]) -> tuple[int, dict[str, Any]]:
    reachable, players = probe()
    if reachable and players is not None:
        return 200, {"ready": True, "game": "answering"}
    if reachable:
        return 503, {"ready": False, "game": "not answering",
                     "detail": "the port is open but the game loop gave no count"}
    return 503, {"ready": False, "game": "down", "detail": "nothing is listening"}


def _masked(value: Any) -> Any:
    if isinstance(value, str):
        return _IPV4.sub("<address>", value)
    if isinstance(value, list):
        return [_masked(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _masked(item) for key, item in value.items()}
    return value


def parse_only(raw: Optional[str]) -> tuple[Optional[list[str]], Optional[str]]:
    """?only=a,b: the checks a monitor asks about, or why it cannot be read.
    Names are the summary's own check keys; nothing else is accepted."""
    if raw is None or raw.strip() == "":
        return None, None
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if len(names) > len(CHECK_NAMES):
        return None, "too many checks named"
    unknown = [name for name in names if name not in CHECK_NAMES]
    if unknown:
        return None, "unknown check: " + ", ".join(sorted(set(unknown)))[:200]
    return sorted(set(names)), None


def ops_summary(path: Path, now: Optional[float] = None,
                max_age: int = SUMMARY_MAX_AGE,
                only: Optional[list[str]] = None) -> tuple[int, dict[str, Any]]:
    """`only` judges just those checks (2026-11-23: one free UptimeRobot
    monitor per concern, so an encrypted backup not set up yet does not keep
    the sync's monitor red). Staleness always counts: a summary nobody is
    writing vouches for nothing."""
    now = time.time() if now is None else now
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return 503, {"overall": "unknown", "problems": ["no operations summary has been written"]}
    except OSError as error:
        return 503, {"overall": "unknown",
                     "problems": [f"the operations summary could not be read ({error.strerror})"]}
    if len(raw) > SUMMARY_MAX_BYTES:
        return 503, {"overall": "unknown", "problems": ["the operations summary is too large"]}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 503, {"overall": "unknown", "problems": ["the operations summary is not valid JSON"]}
    if not isinstance(data, dict):
        return 503, {"overall": "unknown", "problems": ["the operations summary is not an object"]}
    data = _masked(data)
    generated = data.get("generated")
    if not isinstance(generated, (int, float)) or isinstance(generated, bool):
        data["overall"] = "unknown"
        data.setdefault("problems", []).append("the summary carries no time")
        return 503, data
    age = int(now - generated)
    data["age_seconds"] = age
    if age > max_age:
        data["overall"] = "stale"
        data.setdefault("problems", []).append(
            f"the summary is {age // 60} minutes old; toc-heartbeat.timer is not running")
        return 503, data
    if only is None:
        return (200 if data.get("overall") == "ok" else 503), data
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    failing = [name for name in only
               if not (isinstance(checks.get(name), dict) and checks[name].get("ok") is True)]
    data["only"] = only
    data["verdict"] = "ok" if not failing else "degraded"
    data["failing"] = failing
    return (200 if not failing else 503), data
