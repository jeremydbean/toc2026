from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from starlette.datastructures import Address
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Shared-secret authentication for operational endpoints. An unset token
# disables those endpoints instead of exposing immortal commands anonymously.
_WEB_ADMIN_TOKEN: str = os.environ.get("WEB_ADMIN_TOKEN", "")
_WEB_ADMIN_BIND: str = os.environ.get("WEB_ADMIN_BIND", "127.0.0.1").strip().lower()
_LOCAL_ADMIN_UNLOCK_REQUESTED: bool = (
    os.environ.get("WEB_ADMIN_LOCAL_UNLOCK", "0").strip().lower()
    in {"1", "true", "yes", "on"}
)
HOST_STATUS_ENABLED: bool = (
    os.environ.get("WEB_ADMIN_HOST_STATUS", "0").strip().lower()
    in {"1", "true", "yes", "on"}
)
LOCAL_ADMIN_COOKIE = "toc_admin_session"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def set_bind_address(host: str) -> None:
    """Record the address actually bound, so the unlock gate can see it.

    The gate used to read WEB_ADMIN_BIND while uvicorn bound whatever --host
    said. Nothing reconciled the two, so a service started with --host 0.0.0.0
    and no WEB_ADMIN_BIND -- which is exactly how the production unit runs --
    still looked loopback-bound to the gate.
    """
    global _WEB_ADMIN_BIND
    _WEB_ADMIN_BIND = (host or "").strip().lower()


def bound_to_loopback() -> bool:
    return _WEB_ADMIN_BIND in LOOPBACK_HOSTS


def local_admin_unlock_enabled() -> bool:
    return _LOCAL_ADMIN_UNLOCK_REQUESTED and bound_to_loopback()


def loopback_peer(client: Optional[Address]) -> bool:
    """Is the far end of this connection actually on the loopback interface?

    The peer address is the only part of a request the caller cannot choose.
    """
    if client is None or not client.host:
        return False
    try:
        return ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        return False


def local_admin_session_value() -> str:
    if not _WEB_ADMIN_TOKEN:
        return ""
    return hmac.new(
        _WEB_ADMIN_TOKEN.encode("utf-8"),
        b"toc-local-admin-session-v1",
        hashlib.sha256,
    ).hexdigest()


def local_admin_request_allowed(request: Request) -> bool:
    """Loopback unlock, decided by the connection rather than by the request.

    This used to trust the Host header, which any client sets to anything it
    likes: `Host: 127.0.0.1` from the far side of the internet was enough to
    be issued an admin session cookie. Gate on the peer address instead.
    """
    return (
        bool(_WEB_ADMIN_TOKEN)
        and local_admin_unlock_enabled()
        and loopback_peer(request.client)
    )


def local_admin_websocket_authenticated(websocket: WebSocket) -> bool:
    if not local_admin_unlock_enabled() or not loopback_peer(websocket.client):
        return False
    supplied = websocket.cookies.get(LOCAL_ADMIN_COOKIE, "")
    expected = local_admin_session_value()
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


async def verify_token(request: Request, x_admin_token: str = Header(default="")) -> None:
    """Require the shared token or a valid loopback-only browser session."""
    if not _WEB_ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Admin API disabled: configure WEB_ADMIN_TOKEN",
        )
    if x_admin_token and secrets.compare_digest(x_admin_token, _WEB_ADMIN_TOKEN):
        return
    if local_admin_request_allowed(request):
        supplied = request.cookies.get(LOCAL_ADMIN_COOKIE, "")
        expected = local_admin_session_value()
        if supplied and expected and secrets.compare_digest(supplied, expected):
            return
    raise HTTPException(status_code=403, detail="Forbidden")

try:
    from webadmin.area_health import build_area_health
    from webadmin.area_parser import AreaParser, APPLY_LOCATIONS
    from webadmin.area_parser import decode_applies, decode_flags, ITEM_FLAGS, ITEM_FLAGS2, WEAR_FLAGS, ITEM_TYPES, interpret_values, interpret_mob_values, SECTOR_TYPES
    from webadmin.area_parser import ACT_FLAGS, OFF_FLAGS, IMM_FLAGS, RES_FLAGS, VULN_FLAGS, FORM_FLAGS, PART_FLAGS, AFFECTED_FLAGS, ROOM_FLAGS
    from webadmin import oracle
except ImportError:
    from area_health import build_area_health
    from area_parser import AreaParser, APPLY_LOCATIONS
    from area_parser import decode_applies, decode_flags, ITEM_FLAGS, ITEM_FLAGS2, WEAR_FLAGS, ITEM_TYPES, interpret_values, interpret_mob_values, SECTOR_TYPES
    from area_parser import ACT_FLAGS, OFF_FLAGS, IMM_FLAGS, RES_FLAGS, VULN_FLAGS, FORM_FLAGS, PART_FLAGS, AFFECTED_FLAGS, ROOM_FLAGS
    import oracle

# Default paths
QUEUE_PATH: Path = Path(os.getenv("QUEUE_PATH", "area/webadmin.queue"))
DEFAULT_LOG: Path = Path(os.getenv("LOG_FILE", "log/toc.log"))
EVENT_LOG: Path = Path(os.getenv("EVENT_LOG_FILE", "log/webadmin-events.tsv"))
AREA_PATH: Path = Path(os.getenv("AREA_PATH", "area"))
BACKUP_PATH: Path = Path(os.getenv("BACKUP_PATH", "backups"))
PLAYER_PATH: Path = Path(os.getenv("PLAYER_PATH", "player"))
# The game appends one row per login, and since this release one per logout
# too. It writes it as ../log/logins.tsv from the area directory.
LOGIN_JOURNAL: Path = Path(os.getenv("LOGIN_JOURNAL", "log/logins.tsv"))
# The game appends every line that reaches a shared channel here, in
# the same tab-separated shape. Tells are deliberately absent: they
# live per-character in memory and never reach this file.
CHANNEL_JOURNAL: Path = Path(
    os.getenv("CHANNEL_JOURNAL", "log/channels.tsv")
)
UPDATE_REQUEST_PATH: Optional[Path] = (
    Path(update_request_path)
    if (update_request_path := os.getenv("TOC_UPDATE_REQUEST_PATH", "").strip())
    else None
)
STATIC_PATH = Path(__file__).resolve().parent / "static"
REPOSITORY_ROOT = Path(
    os.getenv("TOC_REPOSITORY_ROOT", str(Path(__file__).resolve().parents[1]))
).resolve()
DEPLOYED_COMMIT_FILE = Path(
    os.getenv("TOC_DEPLOYED_COMMIT_FILE", "/var/lib/toc2026/deployed-commit")
)

def _units_from_env(name: str, default: tuple) -> tuple:
    """Unit names for this host, or the appliance's if unset.

    The dashboard used to hard-code the Raspberry Pi appliance's unit
    names, so on the Hyper-V VM -- where they are toc-game.service and
    friends -- the services and timers tables came back empty and the
    whole host panel looked broken. The names belong in the
    environment, beside the rest of the host's configuration.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return tuple(u.strip() for u in raw.replace(",", " ").split() if u.strip())


HOST_SERVICE_UNITS = _units_from_env("TOC_HOST_SERVICE_UNITS", (
    "toc2026-game.service",
    "toc2026-web.service",
    "toc2026-recovery.service",
    "toc2026-stable.service",
    "toc2026-healthcheck.service",
    "toc2026-update.service",
    "toc2026-maintenance.service",
    "toc2026-player-backup.service",
    "toc2026-namecheap-ddns.service",
    "toc2026-led.service",
))
HOST_TIMER_UNITS = _units_from_env("TOC_HOST_TIMER_UNITS", (
    "toc2026-update.timer",
    "toc2026-healthcheck.timer",
    "toc2026-maintenance.timer",
    "toc2026-player-backup.timer",
    "toc2026-namecheap-ddns.timer",
))
HOST_JOURNAL_UNITS = _units_from_env("TOC_HOST_JOURNAL_UNITS", (
    "toc2026-game.service",
    "toc2026-web.service",
    "toc2026-recovery.service",
    "toc2026-stable.service",
    "toc2026-healthcheck.service",
    "toc2026-update.service",
    "toc2026-maintenance.service",
    "toc2026-player-backup.service",
    "toc2026-namecheap-ddns.service",
))
HOST_COMMANDS = {"git", "journalctl", "systemctl"}
HOST_COMMAND_OUTPUT_LIMIT = 1024 * 1024
HOST_RESOURCE_SAMPLE_MIN_INTERVAL = 0.2
_HOST_RESOURCE_LOCK = threading.Lock()
_HOST_RESOURCE_SAMPLE: Optional[Dict[str, float]] = None
_HOST_RESOURCE_RATES: Dict[str, Optional[float]] = {
    "cpu_percent": None,
    "receive_bytes_per_second": None,
    "transmit_bytes_per_second": None,
}

MUD_HOST = os.getenv("MUD_HOST", "127.0.0.1")
MUD_PORT = int(os.getenv("MUD_PORT", 9000))

# What the dashboard *shows* as the game endpoint. MUD_HOST is where this
# service dials, which is loopback because both run on the same box -- so
# displaying it told a reader nothing they could connect to. The DDNS name
# is the default because it follows the external IP instead of going stale
# the next time the lease changes.
MUD_PUBLIC_HOST = os.getenv("MUD_PUBLIC_HOST", "toc.jeremybean.com")
MUD_PUBLIC_PORT = int(os.getenv("MUD_PUBLIC_PORT", MUD_PORT))

# Resolved form of MUD_PUBLIC_HOST, so the dashboard shows the address
# rather than a name somebody then has to look up. Cached because config is
# polled and the answer changes a few times a year at most.
_PUBLIC_IP_CACHE: tuple[float, str] = (0.0, "")
_PUBLIC_IP_TTL = 300.0


def public_game_host() -> str:
    """The game's address as a player would dial it.

    Resolving the configured name keeps this current through a DDNS update,
    which a hard-coded address would not. A name that will not resolve is
    returned unchanged -- still more use than loopback, and the same path a
    literal IP in MUD_PUBLIC_HOST takes.
    """
    global _PUBLIC_IP_CACHE

    host = MUD_PUBLIC_HOST
    if not host:
        return MUD_HOST

    cached_at, cached = _PUBLIC_IP_CACHE
    now = time.monotonic()
    if cached and now - cached_at < _PUBLIC_IP_TTL:
        return cached

    resolved = host
    try:
        resolved = socket.gethostbyname(host)
    except OSError:
        pass

    _PUBLIC_IP_CACHE = (now, resolved)
    return resolved
WEB_ADMIN_PORT = int(os.getenv("WEB_ADMIN_PORT", 9001))
QUEUE_LINE_MAX_BYTES = 4094
COMMAND_MAX_LENGTH = 255
TELNET_IAC = 255
TELNET_WILL = 251
TELNET_WONT = 252
TELNET_DO = 253
TELNET_DONT = 254
TELNET_SUPPORTED_SERVER_OPTIONS = {1, 3}  # ECHO and SUPPRESS-GO-AHEAD
MAX_GAME_FRAME_BYTES = 8192
MAX_EVENT_HISTORY = 1000
WEB_ALLOWED_ORIGINS = {
    origin.strip().rstrip("/").lower()
    for origin in os.getenv("WEB_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}

try:
    import fcntl as _fcntl
except ImportError:  # Windows development; the game server runs on POSIX.
    _fcntl = None

# QueueWriter for inter-process communication with the MUD server
class QueueWriter:
    def __init__(self, queue_path: Path) -> None:
        self.queue_path = queue_path
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.queue_path.touch(exist_ok=True)
        self._thread_lock = threading.Lock()

    def append(self, line: str) -> None:
        if "\n" in line or "\r" in line or "\0" in line:
            raise ValueError("Queue actions must fit on one line")
        if len(line.encode("utf-8")) > QUEUE_LINE_MAX_BYTES:
            raise ValueError("Queue action is too long")

        with self._thread_lock:
            with self.queue_path.open("a", encoding="utf-8") as queue_file:
                if _fcntl is not None:
                    _fcntl.lockf(queue_file.fileno(), _fcntl.LOCK_EX)
                try:
                    queue_file.write(line + "\n")
                    queue_file.flush()
                finally:
                    if _fcntl is not None:
                        _fcntl.lockf(queue_file.fileno(), _fcntl.LOCK_UN)


queue_writer: Optional[QueueWriter] = None


def require_queue_writer() -> QueueWriter:
    if queue_writer is None:
        raise HTTPException(status_code=503, detail="Queue writer is not ready")
    return queue_writer


# How often the Oracle poller drains the game's question spool. The feed is
# tiny and rate-limited, so a couple of seconds is ample.
ORACLE_POLL_SECONDS = float(os.getenv("ORACLE_POLL_SECONDS", "2.0"))

# Question words that make a best-in-slot lookup worth the tokens. Current
# gear is always supplied (it is small); BiS only when the question is clearly
# about gear.
_ORACLE_GEAR_HINTS = (
    "gear", "upgrade", "item", "weapon", "armor", "armour", "wield", "wear",
    "equip", "slot", "best", "bis", "ring", "amulet", "neck", "shield",
    "sword", "mace", "dagger", "boots", "helm", "cloak", "drop", "where",
    "better", "worn", "wearing",
)

# A "where is it / who has it" question is worth a live lookup in the running
# game; these mark one. The stopwords carry no item meaning.
_ORACLE_LIVE_TRIGGERS = (
    "who has", "who carries", "who is carrying", "who's carrying",
    "who is wearing", "who's wearing", "who is holding", "who is wielding",
    "who owns", "who got", "where is", "where's", "where are", "what room",
    "what area", "located", "find the", "find a",
)
_ORACLE_STOPWORDS = frozenset((
    "the a an of is are was were right now currently who whos has have carries "
    "carrying wearing wielding holding owns got where wheres what which room "
    "area located find in on at does do anyone someone today still it there any "
    "my me i can get to you know tell please oracle s").split())
_ORACLE_DIR_HINTS = (
    "how do i get", "how to get", "how can i get", "directions", "direction to",
    "route", "walk to", "path to", "way to", "get to", "how far",
)
_ORACLE_LEVEL_HINTS = (
    "leveling", "levelling", "level up", "exp ", "experience", " xp", "grind",
    "what mobs", "which mobs", "mobs to", "where should i level",
    "best place to level", "kill for",
)
# Questions about the asker's own current state, which must never be answered
# from the cache.
_ORACLE_PERSONAL_HINTS = (
    "my gear", "my eq", "my equipment", "i'm wearing", "im wearing",
    "i am wearing", "i have", "my current", "what i have", "upgrade",
    "online", "who's on", "whos on", "right now", "currently",
)


def _oracle_live_keyword(question: str) -> str:
    """The item or mob a "where is / who has" question is about, as up to four
    content words for the game's own keyword match -- or "" if the question is
    not that kind. Deterministic: the model never chooses what is looked up."""
    ql = (question or "").lower()
    hit = None
    for trigger in _ORACLE_LIVE_TRIGGERS:
        i = ql.find(trigger)
        if i != -1 and (hit is None or i < hit[0]):
            hit = (i, trigger)
    if hit is None:
        return ""
    tail = ql[hit[0] + len(hit[1]):]
    words = [w for w in re.findall(r"[a-z]{2,20}", tail) if w not in _ORACLE_STOPWORDS]
    return " ".join(_oracle_correct(words[:4], "any"))


# "Is Augustus wearing the sword of justice?", "what is the cityguard
# wielding?", "does the dragon have a ring?" -- a question about what one
# particular someone has on. The subject is looked up as a mobile (players
# are found by name separately), the item as an object. Matched by shape,
# so "what should I be wearing at 20?" is not mistaken for one.
_ORACLE_WEAR_VERBS = r"(?:wearing|wielding|carrying|holding|using|equipped with)"
_ORACLE_WEAR_PATTERNS = (
    re.compile(r"\b(?:is|was)\s+(?P<subj>[a-z' ]{2,40}?)\s+(?:still\s+)?"
               + _ORACLE_WEAR_VERBS + r"\b(?P<item>.*)"),
    re.compile(r"\bwhat(?:\s+is|'s|s)\s+(?P<subj>[a-z' ]{2,40}?)\s+"
               + _ORACLE_WEAR_VERBS + r"\b(?P<item>)"),
    re.compile(r"\bwhat\s+(?:does|do)\s+(?P<subj>[a-z' ]{2,40}?)\s+"
               r"(?:wear|wield|carry|hold|use|have)\b(?P<item>)"),
    re.compile(r"\bdoes\s+(?P<subj>[a-z' ]{2,40}?)\s+"
               r"(?:have|wear|wield|carry|hold)\b(?P<item>.*)"),
)
# Pronouns and the like: "is it wearing", "what are you wearing".
_ORACLE_NOT_A_SUBJECT = frozenset("i me my you your he she they them it this that "
                                  "someone anyone somebody anybody he's she's".split())


def _oracle_wear_question(question: str) -> Tuple[str, str]:
    """(subject words, item words) for a "what is X wearing" question, or
    ("", "") when it is not one."""
    ql = " ".join((question or "").lower().replace("?", " ").split())
    for pat in _ORACLE_WEAR_PATTERNS:
        m = pat.search(ql)
        if not m:
            continue
        subj = [w for w in re.findall(r"[a-z]{2,20}", m.group("subj"))
                if w not in _ORACLE_STOPWORDS and w not in _ORACLE_NOT_A_SUBJECT]
        if not subj:
            continue
        item = [w for w in re.findall(r"[a-z]{2,20}", m.group("item") or "")
                if w not in _ORACLE_STOPWORDS]
        return " ".join(subj[:3]), " ".join(item[:4])
    return "", ""


# Keyword vocabularies from the world, for correcting a misspelt name before
# the game's exact keyword match sees it: the first live question anybody
# asked her was about "agustus", and Augustus is spelt with a u.
_ORACLE_VOCAB: Dict[str, Any] = {"parser": None}


def _oracle_vocab(kind: str) -> list:
    if _ORACLE_VOCAB.get("parser") is not parser:
        def words(table) -> list:
            out = set()
            for rec in (table or {}).values():
                out.update(re.findall(r"[a-z]{3,20}",
                                      str(getattr(rec, "keywords", "")).lower()))
            return sorted(out)
        objs = words(getattr(parser, "objects", {}))
        mobs = words(getattr(parser, "mobiles", None) or getattr(parser, "mobs", {}))
        _ORACLE_VOCAB.update({"parser": parser, "obj": objs, "mob": mobs,
                              "any": sorted(set(objs) | set(mobs))})
    return _ORACLE_VOCAB.get(kind) or []


def _oracle_correct(words, kind: str) -> list:
    """Each word as it is, if the world knows it; otherwise the closest word
    the world does know, if one is close enough; otherwise as it is."""
    import difflib

    vocab = _oracle_vocab(kind)
    if not vocab:
        return list(words)
    known = set(vocab)
    out = []
    for w in words:
        if w in known or len(w) < 4:
            out.append(w)
            continue
        near = difflib.get_close_matches(w, vocab, n=1, cutoff=0.8)
        out.append(near[0] if near else w)
    return out


# "Where does the X drop?" -- answered from the area files: which mobiles
# load it, which rooms it lies in, which containers hold it.
_ORACLE_DROP_HINTS = (
    "drop", "dropped", "where can i get", "where can i find", "where do i get",
    "where do i find", "how do i get", "how can i get", "how to get", "obtain",
    "loot", "comes from", "come from", "where does", "who has a", "farm",
)
_ORACLE_DROP_FILLER = frozenset(
    "drop drops dropped get find obtain loot comes come from does can how "
    "where who farm best good one some".split())


def _oracle_drop_lines(question: str, objs: dict, mobs: dict, rooms: dict) -> list:
    """Where an item named in the question comes from, from the world data.
    Only items whose keywords contain every word asked about are reported --
    a near miss is a guess, and she should not guess where loot is."""
    ql = (question or "").lower()
    if not any(h in ql for h in _ORACLE_DROP_HINTS) or "get to" in ql:
        return []
    words = [w for w in re.findall(r"[a-z]{3,20}", ql)
             if w not in _ORACLE_STOPWORDS and w not in _ORACLE_DROP_FILLER]
    words = _oracle_correct(words[:4], "obj")
    if not words:
        return []

    matches = []
    for vnum, obj in objs.items():
        kw = set(re.findall(r"[a-z]+", str(getattr(obj, "keywords", "")).lower()))
        if all(w in kw for w in words):
            matches.append(obj)
    if not matches or len(matches) > 12:
        return []   # nothing, or so many that the question was not specific

    in_rooms: Dict[int, list] = {}
    for rv, room in rooms.items():
        for ov in getattr(room, "objects", []) or []:
            in_rooms.setdefault(ov, []).append(room)

    def sources(obj) -> list:
        out = []
        for mv in (getattr(obj, "carried_by", None) or [])[:3]:
            mob = mobs.get(mv)
            if mob is not None:
                out.append("carried by %s (lvl %s) in %s" % (
                    getattr(mob, "short_desc", "?"), getattr(mob, "level", "?"),
                    getattr(mob, "area_name", "?")))
        for room in in_rooms.get(getattr(obj, "vnum", None), [])[:2]:
            out.append("lies in %s in %s" % (getattr(room, "name", "?"),
                                              getattr(room, "area_name", "?")))
        for cv in (getattr(obj, "contained_by", None) or [])[:2]:
            box = objs.get(cv)
            if box is not None:
                out.append("inside %s in %s" % (getattr(box, "short_desc", "?"),
                                                getattr(box, "area_name", "?")))
        return out

    matches.sort(key=lambda o: (-len(sources(o)), getattr(o, "vnum", 0)))
    lines = []
    for obj in matches[:3]:
        src = sources(obj)
        lines.append("Where %s (lvl %s) comes from, per the area files -- %s." % (
            getattr(obj, "short_desc", "?"), getattr(obj, "level", "?"),
            "; ".join(src) if src else "nothing in the world loads it"))
    return lines


# HELP entries that answer the question, so she can quote the game's own
# help on a spell, skill or command instead of guessing at it.
_ORACLE_HELP_SKIP = frozenset(
    "help level levels class classes race races game player players time "
    "what where when how who which mud times chaos".split())


_ORACLE_HELP_INDEX: Dict[str, Any] = {"entries": None, "records": []}


def _oracle_help_records(entries: list) -> list:
    """Each help entry as a searchable record, rebuilt when the list changes."""
    if _ORACLE_HELP_INDEX["entries"] is not entries:
        records = []
        for entry in entries:
            body = re.sub(r"\{(?:[0-9A-Fa-f]{2}|.)", "", entry.get("body", ""))
            # A help entry's keywords say what it is about far more surely
            # than a passing mention in a long body: AQUEST names "gamble"
            # four times and is not where anybody goes to gamble.
            rec = oracle.term_counts(body, " ".join(entry.get("keywords", [])),
                                     title_weight=6)
            rec["entry"] = entry
            records.append(rec)
        _ORACLE_HELP_INDEX.update({"entries": entries, "records": records})
    return _ORACLE_HELP_INDEX["records"]


def _oracle_help_lines(question: str, entries: list, limit: int = 2) -> list:
    """The help entries that answer the question. A keyword named outright
    ("sanctuary") wins; otherwise the bodies are searched, so "where can I
    store my loot?" still finds STASH, which it never names."""
    ql = " " + " ".join(re.findall(r"[a-z0-9']+", (question or "").lower())) + " "
    picked: list = []
    named = []
    for entry in entries:
        best = 0
        for kw in entry.get("keywords", []):
            k = " ".join(re.findall(r"[a-z0-9']+", kw.lower()))
            if len(k) < 4 or k in _ORACLE_STOPWORDS or k in _ORACLE_HELP_SKIP:
                continue
            if (" " + k + " ") in ql:
                best = max(best, len(k))
        if best:
            named.append((best, len(entry.get("body", "")), entry))
    named.sort(key=lambda s: (-s[0], s[1]))
    # A topic named outright comes first; the search fills what is left, since
    # the topic named is not always the one that answers ("what was said on
    # gossip while I was offline" names GOSSIP and wants HISTORY).
    picked = [e for _b, _l, e in named[:limit]]
    for _s, rec in oracle.rank(question, _oracle_help_records(entries)):
        if len(picked) >= limit:
            break
        if rec["entry"] not in picked:
            picked.append(rec["entry"])
    lines = []
    for entry in picked:
        body = re.sub(r"\{(?:[0-9A-Fa-f]{2}|.)", "", entry.get("body", ""))
        body = " ".join(body.split())[:1500]
        lines.append("HELP %s -- %s" % (entry.get("title", "?").upper(), body))
    return lines


_ORACLE_TOP_HINTS = ("most powerful", "strongest", "best weapon", "deadliest",
                     "top weapon", "highest damage", "most damage", "best sword",
                     "best axe", "best mace", "best dagger")
_ORACLE_WEAPON_WORDS = ("weapon", "sword", "axe", "mace", "dagger", "whip",
                        "spear", "flail", "polearm", "staff", "blade")
_ORACLE_WORLD_HINTS = ("in the game", "in the world", "overall", "anywhere",
                       "in existence", "of all", "ever", "there is", "on the mud")
# The highest level a mortal reaches (the fifth remort's life).
_ORACLE_MORTAL_CAP = 59

_ORACLE_WHO_HINTS = (
    "online", "who's on", "whos on", "who is on", "anyone on", "anybody on",
    "who is playing", "who's playing", "whos playing", "logged in", "logged on",
    "how many players", "players on",
)


def _oracle_live_lookup(reqs, timeout: float = 2.5, asker: str = "") -> list:
    """Ask the running game a few read-only questions and wait for the answers.

    reqs is a list of (kind, arg) with kind in obj/mob/eq. They are appended to
    area/oracle.query; the game drains that on its pulse, runs a fixed
    read-only scan for each, and appends "<id>\\t<finding>" to
    area/oracle.queryresult. Returns findings in request order ("" for any
    that did not come back in time). Never raises."""
    if not reqs:
        return []
    base = QUEUE_PATH.parent
    qpath = base / "oracle.query"
    rpath = base / "oracle.queryresult"
    stamp = int(time.time() * 1000)
    ids: list = []
    out_lines = []
    # The game answers every lookup as the asker would see it: no staff,
    # nobody stealthed or melded, nothing hidden from them. "-" names nobody,
    # which the game treats as an asker with no detections at all.
    who = "".join(re.findall(r"[A-Za-z]", str(asker or "")))[:12] or "-"
    for i, (kind, arg) in enumerate(reqs):
        clean = " ".join(re.findall(r"[A-Za-z]+", str(arg)))[:60]
        if kind not in ("obj", "mob", "eq", "mobeq", "who") or not clean:
            ids.append(None)
            continue
        rid = "q%d_%d" % (stamp, i)
        ids.append(rid)
        out_lines.append("%s\t%s\t%s\t%s" % (rid, kind, who, clean))
    if not out_lines:
        return ["" for _ in reqs]
    try:
        with open(qpath, "a", encoding="utf-8") as fh:
            oracle._lock_ex(fh)
            fh.write("\n".join(out_lines) + "\n")
    except OSError:
        return ["" for _ in reqs]

    wanted = {r for r in ids if r}
    got: Dict[str, str] = {}
    deadline = time.time() + timeout
    while time.time() < deadline and len(got) < len(wanted):
        time.sleep(0.15)
        try:
            text = rpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            rid, _, rest = line.partition("\t")
            if rid in wanted and rid not in got:
                got[rid] = rest.strip()

    # Only one lookup batch is ever outstanding (the poller is one thread), so
    # clearing the whole result file is safe; a straggler from an earlier,
    # timed-out batch is simply discarded.
    try:
        with open(rpath, "r+", encoding="utf-8") as fh:
            oracle._lock_ex(fh)
            fh.seek(0)
            fh.truncate(0)
    except OSError:
        pass
    return [got.get(r, "") if r else "" for r in ids]


def _oracle_context(player: str, question: str) -> str:
    """Build live grounding for one question: the asker's level, class and worn
    gear, and -- for gear questions -- the obtainable best-in-slot for their
    class and level, with where it drops. Runs in the poller's thread; the
    dashboard already reads player files and parses the world here."""
    # Without a readable player file there is nothing personal to say, but
    # the help, the drop tables and the live world still answer the question.
    prof = parse_player_file(player) or {}

    cls = str(prof.get("class_name", "")).lower()
    race = str(prof.get("race", "")).lower()
    try:
        lvl = max(1, min(70, int(prof.get("level", 1) or 1)))
    except (TypeError, ValueError):
        lvl = 1

    objs = getattr(parser, "objects", {}) or {}
    # The parser calls its mob table `mobiles`.
    mobs = getattr(parser, "mobiles", None) or getattr(parser, "mobs", {}) or {}
    rooms = getattr(parser, "rooms", {}) or {}

    lines = (["Supplicant: %s, a level %d %s %s." % (player, lvl, race or "?", cls or "?")]
             if prof else [])
    ql = (question or "").lower()

    # Who is connected is asked of the game itself (the "who" lookup below),
    # never read from the login journal: the journal does not know who is
    # wizinvis, and she told mortals which hidden immortals were on.

    worn = []
    for it in prof.get("equipment", []):
        obj = objs.get(it.get("vnum"))
        name = getattr(obj, "short_desc", None) or ("item %s" % it.get("vnum"))
        slot = WEAR_SLOT_NAMES.get(it.get("wear", -1), "worn")
        worn.append("%s: %s (lvl %s)" % (slot, name, it.get("level", "?")))
    if prof:
        lines.append("Currently worn -- " + ("; ".join(worn[:20]) if worn
                                              else "nothing of note") + ".")

    # Other players named in the question, so she can answer "is X wearing Y?".
    # Only their names are taken from here. What they have on comes from the
    # game's live "eq" lookup, which answers only for somebody the asker could
    # see -- never staff, never anyone stealthed, melded or hidden. Their saved
    # file is not read: an offline player's kit, level or class is nothing a
    # player could look at, and a file names a hidden immortal as readily as
    # anyone else.
    seen = {player.casefold()}
    named: list = []
    for tok in re.findall(r"[A-Za-z]{3,12}", question or ""):
        cap = tok.capitalize()
        if cap.casefold() in seen:
            continue
        seen.add(cap.casefold())
        try:
            if not (PLAYER_PATH / cap).is_file():
                continue
        except OSError:
            continue
        named.append(cap)
        if len(named) >= 2:
            break

    # Live, from the running game (read-only): the current gear of any player
    # named in the question, and -- for "where is / who has" -- where an item
    # or mob is right now. The poller chooses these lookups, never the model.
    reqs = [("eq", n) for n in named]
    live_kw = _oracle_live_keyword(question)
    if live_kw:
        reqs += [("obj", live_kw), ("mob", live_kw)]
    # "Is Augustus wearing the sword of justice?" -- a mobile's gear, and the
    # item asked about wherever it is. A subject that is a player was already
    # handled by name above.
    subj, item = _oracle_wear_question(question)
    if subj and not any(subj.casefold() == n.casefold() for n in named):
        reqs.append(("mobeq", " ".join(_oracle_correct(subj.split(), "mob"))))
    if item and not live_kw:
        reqs.append(("obj", " ".join(_oracle_correct(item.split(), "obj"))))
    if any(h in ql for h in _ORACLE_WHO_HINTS):
        reqs.append(("who", "all"))
    live_rooms: list = []
    if reqs:
        for (kind, _arg), found in zip(reqs, _oracle_live_lookup(reqs, asker=player)):
            if not found:
                continue
            if kind == "mob" and found.startswith("No '"):
                continue   # it was an item, not a mob
            lines.append("Live right now -- %s" % found)
            if kind in ("obj", "mob", "mobeq"):
                live_rooms += [int(v) for v in re.findall(r"\((\d+)\)", found)]

    # A route to wherever the live lookup found it, from the Directions data.
    if live_rooms:
        try:
            all_routes = load_directions().get("routes") or []
        except Exception:
            all_routes = []
        by_area: Dict[str, Any] = {}
        for r in all_routes:
            for k in (r.get("area"), r.get("area_display")):
                if k:
                    by_area.setdefault(" ".join(str(k).split()), r)
        done = set()
        for v in live_rooms:
            area = getattr(rooms.get(v), "area_name", "") or ""
            key = " ".join(area.split())
            if not key or key in done:
                continue
            done.add(key)
            r = by_area.get(key)
            if r:
                lines.append("Route to %s, where that is (%s rooms from the Oak "
                             "Tree Square): %s" % (r.get("area_display") or key,
                                                   r.get("rooms_away", "?"),
                                                   r.get("commands", "")))
            if len(done) >= 2:
                break

    # Where an item comes from, from the area files.
    try:
        lines += _oracle_drop_lines(question, objs, mobs, rooms)
    except Exception:
        pass

    # The game's own help on whatever spell, skill or command was named.
    try:
        lines += _oracle_help_lines(question, load_player_help())
    except Exception:
        pass

    if cls in CLASS_WEIGHTS and race in RACE_FLAGS \
            and any(k in ql for k in _ORACLE_GEAR_HINTS):
        try:
            best = asyncio.run(get_best_gear(
                class_name=cls, race_name=race, level=lvl, limit=1))
        except Exception:
            best = {}
        bis = []
        for slot, items in best.items():
            if not items:
                continue
            top = items[0]
            where = top.get("area", "?")
            obj = objs.get(top.get("vnum"))
            carriers = getattr(obj, "carried_by", None) or []
            if carriers:
                carrier = getattr(mobs.get(carriers[0]), "short_desc", None)
                if carrier:
                    where = "%s in %s" % (carrier, where)
            bis.append("%s: %s (lvl %s) from %s" % (
                slot, top.get("name", "?"), top.get("level", "?"), where))
        if bis:
            lines.append("Obtainable best-in-slot for this class and level -- "
                         + "; ".join(bis) + ".")

    # "The most powerful weapon in the game" is not a best-in-slot question --
    # it has no level -- so answer it at the mortal cap, from the same finder.
    if any(h in ql for h in _ORACLE_TOP_HINTS) \
            and any(w in ql for w in _ORACLE_WEAPON_WORDS) \
            and (any(w in ql for w in _ORACLE_WORLD_HINTS) or not prof):
        c = cls if cls in CLASS_WEIGHTS else "warrior"
        r = race if race in RACE_FLAGS else "human"
        try:
            top = asyncio.run(get_best_gear(class_name=c, race_name=r,
                                            level=_ORACLE_MORTAL_CAP, limit=3))
        except Exception:
            top = {}
        picks = []
        for it in (top.get("Wielded") or [])[:3]:
            where = it.get("area", "?")
            carriers = getattr(objs.get(it.get("vnum")), "carried_by", None) or []
            carrier = getattr(mobs.get(carriers[0]), "short_desc", None) if carriers else None
            if carrier:
                where = "%s in %s" % (carrier, where)
            picks.append("%s (lvl %s) from %s" % (it.get("name", "?"),
                                                  it.get("level", "?"), where))
        if picks:
            # Stated as a fact about the game. Worded as "what a warrior can
            # wield", she hedged that she could not see the asker's class.
            whose = ("for a %s like the supplicant" % c) if cls in CLASS_WEIGHTS \
                else "overall"
            lines.append("The most powerful weapons in the game %s, as the gear "
                         "finder ranks them at the mortal cap (level %d) -- %s. "
                         "Answer with the first of these." % (
                             whose, _ORACLE_MORTAL_CAP, "; ".join(picks)))

    # The website's Directions data: walking routes from the Oak Tree Square.
    if any(h in ql for h in _ORACLE_DIR_HINTS) or "where is" in ql:
        try:
            routes = load_directions().get("routes") or []
        except Exception:
            routes = []
        words = [w for w in re.findall(r"[a-z]{3,20}", ql)
                 if w not in _ORACLE_STOPWORDS
                 and w not in ("how", "directions", "direction", "route", "walk",
                               "path", "way", "far", "from", "here", "there")]
        scored = []
        for r in routes:
            hay = " ".join(str(r.get(k, "")) for k in
                           ("name", "area", "area_display", "room")).lower()
            score = sum(1 for w in words if w in hay)
            if score:
                scored.append((score, r))
        if scored:
            scored.sort(key=lambda x: (-x[0], x[1].get("rooms_away") or 9999))
            best_score = scored[0][0]
            for score, r in [s for s in scored if s[0] == best_score][:2]:
                lines.append("Route to %s (%s rooms from the Oak Tree Square): %s" % (
                    r.get("area_display") or r.get("name"),
                    r.get("rooms_away", "?"), r.get("commands", "")))

    # The website's Leveling guide: best mobs for the asker's level.
    if any(h in ql for h in _ORACLE_LEVEL_HINTS):
        try:
            lv = asyncio.run(get_leveling(level=lvl, limit=5))
        except Exception:
            lv = {}
        picks = []
        for m in (lv.get("mobs") or [])[:5]:
            picks.append("%s (lvl %s) in %s: %s xp/kill, ~%s xp/hr, %s around%s%s" % (
                m.get("name"), m.get("level"), m.get("area"), m.get("xp_per_kill"),
                m.get("xp_per_hour"), m.get("count"),
                ", aggressive" if m.get("aggressive") else "",
                ("; route: " + m["directions"]) if m.get("directions") else ""))
        if picks:
            lines.append("Best leveling for level %d (the site's leveling guide) -- %s."
                         % (lvl, " | ".join(picks)))

    return "\n".join(lines)[:9000]


def _oracle_cache_key(player: str, question: str):
    """A cache key for a question whose answer depends only on class, race and
    level -- "best sword for my level", "how do I remort", "where should I
    level" -- or None for anything about the asker's own current state, a named
    player, or a live "where is / who has" lookup, which must be fresh."""
    ql = " ".join(re.findall(r"[a-z0-9']+", (question or "").lower()))
    if not ql:
        return None
    if any(h in ql for h in _ORACLE_PERSONAL_HINTS) or _oracle_live_keyword(question) \
            or _oracle_wear_question(question)[0] \
            or any(h in ql for h in _ORACLE_WHO_HINTS):
        return None
    for tok in re.findall(r"[A-Za-z]{3,12}", question or ""):
        cap = tok.capitalize()
        if cap.casefold() == (player or "").casefold():
            continue
        try:
            if (PLAYER_PATH / cap).is_file():
                return None
        except OSError:
            return None
    prof = parse_player_file(player) or {}
    return "|".join((ql, str(prof.get("class_name", "")).lower(),
                     str(prof.get("race", "")).lower(), str(prof.get("level", ""))))


def _oracle_provider(player: str, question: str):
    """What the poller hands each question: (live grounding, cache key)."""
    return _oracle_context(player, question), _oracle_cache_key(player, question)


async def _oracle_poll_loop():
    """Drain the Oracle's ask spool and write answers, beside the game's queue.

    Runs for the life of the web service and never raises out: a bad batch is
    swallowed so this can never take the dashboard down. poll_once itself does
    nothing (bar a quiet reply) until the Oracle is enabled with an API key.
    """
    ask = QUEUE_PATH.parent / "oracle.ask"
    answer = QUEUE_PATH.parent / "oracle.answer"
    while True:
        try:
            await asyncio.to_thread(oracle.poll_once, ask, answer, _oracle_provider)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(ORACLE_POLL_SECONDS)


def oracle_report(limit: int = 50) -> Dict[str, Any]:
    """Aggregate the Oracle usage log for the admin dashboard: recent calls
    (question, answer, tokens, cost), per-player totals, grand totals, and
    today's spend against the daily cap."""
    usage_path = Path(os.environ.get("ORACLE_USAGE")
                      or (QUEUE_PATH.parent.parent / "log" / "oracle_usage.tsv"))
    calls: list = []
    per_player: dict = {}
    totals = {"chats": 0, "tokens": 0, "cost": 0.0, "cached": 0}

    try:
        text = usage_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 10:
            continue
        try:
            epoch = int(parts[0]); inp = int(parts[3]); out = int(parts[4])
            cread = int(parts[5]); cwrite = int(parts[6]); cost = float(parts[7])
        except ValueError:
            continue
        tokens = inp + out + cread + cwrite
        cached = len(parts) > 10 and parts[10] == "1"
        calls.append({
            "time": epoch, "player": parts[1], "model": parts[2],
            "input": inp, "output": out, "cache_read": cread,
            "cache_write": cwrite, "tokens": tokens, "cost": round(cost, 6),
            "question": parts[8], "answer": parts[9],
            "off_topic": parts[9] == "__OFFTOPIC__",
            "cached": cached,
        })
        pp = per_player.setdefault(
            parts[1], {"player": parts[1], "chats": 0, "tokens": 0, "cost": 0.0})
        pp["chats"] += 1; pp["tokens"] += tokens; pp["cost"] += cost
        totals["chats"] += 1; totals["tokens"] += tokens; totals["cost"] += cost
        if cached:
            totals["cached"] += 1

    players = sorted(per_player.values(), key=lambda p: -p["cost"])
    for p in players:
        p["cost"] = round(p["cost"], 6)
    totals["cost"] = round(totals["cost"], 6)

    try:
        state = oracle._load_state()
    except Exception:
        state = {}
    return {
        "enabled": _safe(lambda: oracle.is_enabled(), False),
        "spent_today": round(float(state.get("spent", 0.0)), 6) if state else 0.0,
        "daily_cap": _safe(lambda: oracle._daily_cap_usd(), 0.0),
        "totals": totals,
        "per_player": players,
        "calls": calls[-limit:][::-1],
    }


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


@asynccontextmanager
async def lifespan(app: FastAPI):
    global AREA_HEALTH_CACHE, parser, queue_writer
    queue_writer = QueueWriter(QUEUE_PATH)
    parser = await asyncio.to_thread(load_area_parser, AREA_PATH)
    AREA_MAP_CACHE.clear()
    AREA_HEALTH_CACHE = None
    # Co-locate the Oracle usage log with the transcript, in the game's log dir,
    # unless the host overrides it. The worker (same process) reads this env.
    os.environ.setdefault(
        "ORACLE_USAGE", str(QUEUE_PATH.parent.parent / "log" / "oracle_usage.tsv"))
    oracle_task = asyncio.create_task(_oracle_poll_loop())
    try:
        yield
    finally:
        oracle_task.cancel()
        try:
            await oracle_task
        except asyncio.CancelledError:
            pass
        queue_writer = None


app = FastAPI(
    title="ToC Web Admin",
    version="2.1",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_PATH), name="static")


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' ws: wss:; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'self'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


class CommandRequest(BaseModel):
    command: str


class AnnounceRequest(BaseModel):
    message: str


class WizinfoRequest(BaseModel):
    message: str
    level: Optional[int] = None


def validated_queue_payload(value: str, label: str, max_length: int) -> str:
    """Validate one payload field for the line-oriented queue protocol."""
    value = value.strip()
    if not value:
        raise HTTPException(status_code=400, detail=f"{label} cannot be empty")
    if len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"{label} cannot exceed {max_length} characters",
        )
    if "|" in value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise HTTPException(
            status_code=400,
            detail=f"{label} contains unsupported control characters",
        )
    return value


def append_queue_action(line: str) -> None:
    """Append a validated action and translate filesystem errors for the API."""
    try:
        require_queue_writer().append(line)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Command queue unavailable") from exc


def telnet_negotiation_responses(data: bytes) -> bytes:
    """Build minimal Telnet replies for the browser-to-MUD bridge."""
    replies = bytearray()
    index = 0
    while index + 2 < len(data):
        if data[index] != TELNET_IAC:
            index += 1
            continue
        command = data[index + 1]
        option = data[index + 2]
        if command == TELNET_WILL:
            reply = TELNET_DO if option in TELNET_SUPPORTED_SERVER_OPTIONS else TELNET_DONT
        elif command == TELNET_WONT:
            reply = TELNET_DONT
        elif command in (TELNET_DO, TELNET_DONT):
            reply = TELNET_WONT
        else:
            index += 2
            continue
        replies.extend((TELNET_IAC, reply, option))
        index += 3
    return bytes(replies)


def websocket_origin_allowed(websocket: WebSocket) -> bool:
    """Allow native clients and same-origin browsers, plus explicit origins."""
    origin = websocket.headers.get("origin")
    if not origin:
        return True
    normalized_origin = origin.rstrip("/").lower()
    if normalized_origin in WEB_ALLOWED_ORIGINS:
        return True
    parsed = urlparse(origin)
    request_host = websocket.headers.get("host", "").lower()
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == request_host


# Class stat weights for Best Gear scoring.
#
# These are DAMAGE-FORWARD on purpose: a recommendation should rank an item
# above another mainly because it makes you hit harder, not because it pads
# your hit points.  The one trap to design around is MAGNITUDE.  Hit points
# and mana roll onto gear in large numbers -- tens to hundreds -- while
# hitroll, damroll and the six stats roll in single digits.  Score each by a
# flat per-point weight and a fat +60 hp roll (60 x anything) buries a real
# +6 damroll upgrade every time, which is exactly the "it keeps recommending
# HP" complaint.
#
# So the survivability stats carry deliberately small per-point weights, and
# the damage stats -- hitroll, damroll, and each class's prime
# fighting/casting stat -- carry large ones.  The arithmetic then lands where
# it should: an ordinary damage upgrade outranks an ordinary hp roll, but a
# genuinely huge hp bump (say +150) still wins over a marginal damage gain.
# Constitution only feeds hp for most classes, so it is weighted like hp --
# except for the monk, whose unarmed damage keys off CON, so there it stays a
# prime (damage) stat.  Weapon dice are scaled by the class's melee weight
# below, so a weapon matters to a fighter and barely moves a caster.

CLASS_WEIGHTS = {
    "mage": {
        # Pure caster: spell damage rides on INT.
        "intelligence": 3.0,      # Prime: spell damage / learning
        "save vs spell": 0.8,     # Resist enemy spells
        "mana": 0.4,              # Large magnitude -> small per-point
        "wisdom": 0.4,            # Some mana benefit
        "dexterity": 0.3,         # Minimal AC benefit
        "constitution": 0.25,     # Survivability (hp) only
        "hit points": 0.12,       # Large magnitude -> small per-point
        "hitroll": 0.2,           # Rarely melee
        "damroll": 0.2,           # Rarely melee
        "strength": 0.1,          # Carry capacity only
    },
    "cleric": {
        # Prime WIS caster who can also swing a mace.
        "wisdom": 3.0,            # Prime: cleric spells
        "hitroll": 1.5,           # Melee damage
        "damroll": 1.5,           # Melee damage
        "strength": 0.8,          # Bonus hit/dam
        "save vs spell": 0.8,     # Resist debuffs
        "mana": 0.4,              # Large magnitude -> small per-point
        "dexterity": 0.3,         # AC benefit
        "intelligence": 0.3,      # Minor mana benefit
        "constitution": 0.25,     # Survivability (hp) only
        "hit points": 0.15,       # Large magnitude -> small per-point
    },
    "thief": {
        # Melee DPS: hit/dam are multiplied by backstab.
        "hitroll": 4.0,           # Critical for backstab to land
        "damroll": 4.0,           # Multiplied by backstab
        "dexterity": 3.0,         # Prime: skills / dodge
        "strength": 1.8,          # Bonus hit/dam
        "save vs spell": 0.4,     # Some spell resist
        "constitution": 0.3,      # Survivability (hp) only
        "hit points": 0.2,        # Large magnitude -> small per-point
        "intelligence": 0.2,      # Minor
        "wisdom": 0.2,            # Minor
        "mana": 0.0,              # Thieves don't cast
    },
    "warrior": {
        # Pure melee: damage first, hp is a tie-breaker.
        "hitroll": 4.0,           # Must hit to deal damage
        "damroll": 4.0,           # Direct damage boost
        "strength": 2.5,          # Bonus hit/dam via str_app
        "dexterity": 1.0,         # AC, parry
        "save vs spell": 0.4,     # Some magic resist
        "constitution": 0.3,      # Survivability (hp) only
        "hit points": 0.2,        # Large magnitude -> small per-point
        "wisdom": 0.1,            # Useless
        "intelligence": 0.1,      # Useless
        "mana": 0.0,              # Warriors don't cast
    },
    "monk": {
        # Unarmed fighter whose damage keys off CON, so CON stays a prime.
        "hitroll": 4.0,           # Need to hit
        "damroll": 4.0,           # Unarmed damage
        "constitution": 2.5,      # Prime: unarmed damage (and hp)
        "strength": 1.8,          # Bonus hit/dam
        "dexterity": 1.5,         # Dodge / AC
        "save vs spell": 0.4,     # Magic resist
        "hit points": 0.2,        # Large magnitude -> small per-point
        "wisdom": 0.3,            # Minor
        "intelligence": 0.2,      # Minor
        "mana": 0.1,              # A few monk abilities use mana
    },
    "necromancer": {
        # Dark caster: spell damage rides on INT.
        "intelligence": 3.0,      # Prime: spell damage
        "save vs spell": 0.8,     # Resist enemy magic
        "mana": 0.4,              # Large magnitude -> small per-point
        "wisdom": 0.4,            # Some mana benefit
        "dexterity": 0.3,         # AC
        "constitution": 0.25,     # Survivability (hp) only
        "hit points": 0.15,       # Large magnitude -> small per-point
        "hitroll": 0.3,           # Rarely melee
        "damroll": 0.3,           # Rarely melee
        "strength": 0.2,          # Minor
    },
}

# Race flag mapping
RACE_FLAGS = {
    "human": "human-only",
    "elf": "elf-only",
    "dwarf": "dwarf-only",
    "hobbit": "halfling-only",
    "saurian": "saurian-only",
}

CLASS_NAMES = ["mage", "cleric", "thief", "warrior", "monk", "necromancer"]
GUILD_NAMES = ["mage", "cleric", "thief", "warrior", "monk", "necromancer",
               "?", "?", "?", "?", "any", "none"]
RACE_NAMES  = ["human", "elf", "dwarf", "hobbit", "saurian"]
WEAR_SLOT_NAMES = {
    0:  "Light",       1:  "Left Finger",  2:  "Right Finger",
    3:  "Neck (1st)",  4:  "Neck (2nd)",   5:  "Body",
    6:  "Head",        7:  "Legs",         8:  "Feet",
    9:  "Hands",       10: "Arms",         11: "Shield",
    12: "About Body",  13: "Waist",        14: "Left Wrist",
    15: "Right Wrist", 16: "Wielded",      17: "Held",
}

# The gear finder's slots: every place the game equips, in wear-location
# order (WEAR_LIGHT .. WEAR_HOLD), each with the wear flag that lets an
# item go there. Rings, necks and wrists are pairs: the second of each is
# ranked without the first one's top pick, so the best two differ.
GEAR_FINDER_SLOTS = [
    ("light",  "Light"),
    ("finger", "Left Finger"),
    ("finger", "Right Finger"),
    ("neck",   "Neck (1st)"),
    ("neck",   "Neck (2nd)"),
    ("body",   "Body"),
    ("head",   "Head"),
    ("legs",   "Legs"),
    ("feet",   "Feet"),
    ("hands",  "Hands"),
    ("arms",   "Arms"),
    ("shield", "Shield"),
    ("about",  "About Body"),
    ("waist",  "Waist"),
    ("wrist",  "Left Wrist"),
    ("wrist",  "Right Wrist"),
    ("wield",  "Wielded"),
    ("hold",   "Held"),
]
# apply_ac() in handler.c: armour counts three times on the body, twice on
# the head, the legs and about the body, and once anywhere else.
GEAR_AC_MULTIPLIER = {"body": 3, "head": 2, "legs": 2, "about": 2}
ITEM_TYPE_LIGHT = 1
ITEM_TYPE_WEAPON = 5
ITEM_TYPE_ARMOR = 9

SEX_NAMES = ["neutral", "male", "female"]
PLAYER_NAME_RE = re.compile(r"^[A-Za-z]{1,20}$")
ALIGN_NAMES = [
    (-1000, -700, "Diabolic"),
    (-700,  -350, "Evil"),
    (-350,  -100, "Mean"),
    (-100,   100, "Neutral"),
    ( 100,   350, "Kind"),
    ( 350,   700, "Good"),
    ( 700,  1000, "Angelic"),
]

def align_str(alig: int) -> str:
    for lo, hi, label in ALIGN_NAMES:
        if lo <= alig < hi:
            return label
    return "Angelic" if alig >= 700 else "Diabolic"


def resolve_player_path(name: str) -> Path | None:
    """Resolve a valid player name without changing its filename casing."""
    if not PLAYER_NAME_RE.fullmatch(name):
        return None
    try:
        direct = PLAYER_PATH / name
        if direct.is_file() and not direct.is_symlink():
            return direct
        folded = name.casefold()
        for candidate in PLAYER_PATH.iterdir():
            if (
                candidate.name.casefold() == folded
                and PLAYER_NAME_RE.fullmatch(candidate.name)
                and candidate.is_file()
                and not candidate.is_symlink()
            ):
                return candidate
    except OSError:
        return None
    return None


def parse_player_file(name: str) -> dict | None:
    """Parse a MUD player file and return a structured dict."""
    path = resolve_player_path(name)
    if path is None:
        return None
    cname = path.name

    data: dict = {
        "name": cname, "race": "human", "sex": 1,
        "class_num": 0, "class_name": "mage",
        "guild_num": 11, "guild_name": "none",
        "level": 1,
        "hp_cur": 0, "hp_max": 0,
        "mana_cur": 0, "mana_max": 0,
        "mv_cur": 0, "mv_max": 0,
        "str_base": 13, "int_base": 13, "wis_base": 13, "dex_base": 13, "con_base": 13,
        "str_mod": 0,  "int_mod": 0,  "wis_mod": 0,  "dex_mod": 0,  "con_mod": 0,
        "ac_pierce": 0, "ac_slash": 0, "ac_bash": 0, "ac_exotic": 0,
        "hitroll": 0, "damroll": 0, "exp": 0,
        "practices": 0, "trains": 0, "quest_points": 0,
        "alignment": 0, "title": "", "description": "",
        "gold": 0, "platinum": 0, "num_remorts": 0,
        "skills": [], "affects": [],
        "equipment": [],  # worn items (Wear >= 0)
        "inventory": [],  # carried items (Wear == -1)
    }

    try:
        text = path.read_text(encoding="latin-1")
    except Exception:
        return None

    in_player = False
    in_object = False
    cur_obj: dict[str, Any] = {}
    collecting_desc = False
    desc_lines: list[str] = []

    for line in text.splitlines():
        ls = line.strip()

        if ls == "#PLAYER":
            in_player = True
            in_object = False
            continue

        if ls == "#END":
            if in_object and cur_obj:
                target = data["equipment"] if cur_obj.get("wear", -1) >= 0 else data["inventory"]
                target.append(cur_obj)
            break

        if ls == "#O":
            if in_object and cur_obj:
                target = data["equipment"] if cur_obj.get("wear", -1) >= 0 else data["inventory"]
                target.append(cur_obj)
            cur_obj = {}
            in_object = True
            in_player = False
            continue

        if in_object:
            parts = ls.split()
            if not parts:
                continue
            k = parts[0]
            if k == "Vnum"   and len(parts) >= 2: cur_obj["vnum"] = int(parts[1])
            elif k == "Wear" and len(parts) >= 2: cur_obj["wear"] = int(parts[1])
            elif k == "Lev"  and len(parts) >= 2: cur_obj["level"] = int(parts[1])
            elif k == "End":
                if cur_obj:
                    target = data["equipment"] if cur_obj.get("wear", -1) >= 0 else data["inventory"]
                    target.append(cur_obj)
                cur_obj = {}
                in_object = False
            continue

        if in_player:
            if collecting_desc:
                if ls.endswith("~"):
                    # Don't append the terminator line; just strip trailing ~
                    tail = line.rstrip()
                    if tail.rstrip("~").strip():  # non-empty content before ~
                        desc_lines.append(tail.rstrip().rstrip("~"))
                    # Strip trailing blank lines caused by bare \r in CRLF files
                    while desc_lines and not desc_lines[-1].strip():
                        desc_lines.pop()
                    data["description"] = "\n".join(desc_lines)
                    collecting_desc = False
                    desc_lines = []
                else:
                    desc_lines.append(line.rstrip())
                continue

            parts = ls.split()
            if not parts:
                continue
            k = parts[0]

            try:
                if   k == "Name"      and len(parts) >= 2: data["name"] = parts[1].rstrip("~")
                elif k == "Race"      and len(parts) >= 2: data["race"] = parts[1].rstrip("~").lower()
                elif k == "Sex"       and len(parts) >= 2: data["sex"] = int(parts[1])
                elif k == "Cla"       and len(parts) >= 2:
                    cn = int(parts[1])
                    data["class_num"] = cn
                    data["class_name"] = CLASS_NAMES[cn] if 0 <= cn < len(CLASS_NAMES) else "unknown"
                elif k == "Gui"       and len(parts) >= 2:
                    gn = int(parts[1])
                    data["guild_num"] = gn
                    data["guild_name"] = GUILD_NAMES[gn] if 0 <= gn < len(GUILD_NAMES) else "unknown"
                elif k == "Levl"      and len(parts) >= 2: data["level"] = int(parts[1])
                elif k == "HMV"       and len(parts) >= 7:
                    data["hp_cur"]   = int(parts[1]); data["hp_max"]   = int(parts[2])
                    data["mana_cur"] = int(parts[3]); data["mana_max"] = int(parts[4])
                    data["mv_cur"]   = int(parts[5]); data["mv_max"]   = int(parts[6])
                elif k == "Attr"      and len(parts) >= 6:
                    data["str_base"] = int(parts[1]); data["int_base"] = int(parts[2])
                    data["wis_base"] = int(parts[3]); data["dex_base"] = int(parts[4])
                    data["con_base"] = int(parts[5])
                elif k == "AMod"      and len(parts) >= 6:
                    data["str_mod"]  = int(parts[1]); data["int_mod"]  = int(parts[2])
                    data["wis_mod"]  = int(parts[3]); data["dex_mod"]  = int(parts[4])
                    data["con_mod"]  = int(parts[5])
                elif k == "ACs"       and len(parts) >= 5:
                    data["ac_pierce"] = int(parts[1]); data["ac_slash"]  = int(parts[2])
                    data["ac_bash"]   = int(parts[3]); data["ac_exotic"] = int(parts[4])
                elif k == "Hit"       and len(parts) >= 2: data["hitroll"]     = int(parts[1])
                elif k == "Dam"       and len(parts) >= 2: data["damroll"]     = int(parts[1])
                elif k == "Exp"       and len(parts) >= 2: data["exp"]         = int(parts[1])
                elif k == "Prac"      and len(parts) >= 2: data["practices"]   = int(parts[1])
                elif k == "Trai"      and len(parts) >= 2: data["trains"]      = int(parts[1])
                elif k == "QuestPnts" and len(parts) >= 2: data["quest_points"] = int(parts[1])
                elif k == "Alig"      and len(parts) >= 2: data["alignment"]   = int(parts[1])
                elif k == "NewGold"   and len(parts) >= 2: data["gold"]       = int(parts[1])
                elif k == "NewPlat"   and len(parts) >= 2: data["platinum"]   = int(parts[1])
                elif k == "NumRemorts" and len(parts) >= 2: data["num_remorts"] = int(parts[1])
                elif k == "Titl":
                    data["title"] = ls[5:].strip().rstrip("~")
                elif k == "Desc":
                    rest = ls[5:].strip()
                    if rest.endswith("~"):
                        data["description"] = rest[:-1]
                    elif rest:
                        desc_lines = [line[5:].rstrip()]  # preserve original indentation
                        collecting_desc = True
                    else:
                        desc_lines = []
                        collecting_desc = True
                elif k == "Sk" and len(parts) >= 3:
                    skill_pct = int(parts[1])
                    skill_name = " ".join(parts[2:]).strip("'")
                    data["skills"].append({"name": skill_name, "pct": skill_pct})
                elif k == "AffD":
                    aff_line = ls[5:].strip()
                    if aff_line.startswith("'"):
                        end_q = aff_line.find("'", 1)
                        spell_name = aff_line[1:end_q] if end_q > 0 else aff_line
                        rest_parts = aff_line[end_q+2:].split() if end_q > 0 else []
                    else:
                        sp = aff_line.split()
                        spell_name = sp[0] if sp else ""
                        rest_parts = sp[1:]
                    # save.c format: 'name' level duration modifier location bitvec bitvec2
                    # rest_parts[0]=level  [1]=duration  [2]=modifier  [3]=location
                    aff: dict[str, Any] = {"spell": spell_name}
                    if len(rest_parts) >= 4:
                        aff["level"]    = int(rest_parts[0])
                        aff["duration"] = int(rest_parts[1])
                        aff["modifier"] = int(rest_parts[2])
                        loc_id = int(rest_parts[3])
                        aff["location"] = APPLY_LOCATIONS.get(loc_id, str(loc_id))
                    data["affects"].append(aff)
            except (ValueError, IndexError):
                pass  # Silently skip malformed lines

    # Compute totals
    data["str_total"] = data["str_base"] + data["str_mod"]
    data["int_total"] = data["int_base"] + data["int_mod"]
    data["wis_total"] = data["wis_base"] + data["wis_mod"]
    data["dex_total"] = data["dex_base"] + data["dex_mod"]
    data["con_total"] = data["con_base"] + data["con_mod"]

    # Enrich equipment items with area parser data
    for item in data["equipment"]:
        vnum = item.get("vnum", 0)
        item["wear_slot"] = WEAR_SLOT_NAMES.get(item.get("wear", -1), "Unknown")
        obj = parser.objects.get(vnum)
        if obj:
            item["name"]      = obj.short_desc
            item["item_type"] = obj.item_type
            item["area"]      = obj.area_name
            item["affects"]   = decode_applies(obj.affects)
        else:
            item["name"]      = f"Unknown Item #{vnum}"
            item["item_type"] = "?"
            item["area"]      = "Unknown"
            item["affects"]   = []

    # Don't expose inventory — can be 500+ items and is not used by the UI
    del data["inventory"]

    return data


def load_area_parser(area_path: Path) -> AreaParser:
    """Create and populate an AreaParser for the configured area directory."""
    loaded_parser = AreaParser(area_path)
    try:
        loaded_parser.parse_all()
    except Exception as e:
        print(f"Warning: Failed to parse areas from {area_path}: {e}")
    return loaded_parser


# The lifespan loads this parser once startup arguments and environment values
# are final. Keeping import side effects light also makes tests and tooling fast.
parser = AreaParser(AREA_PATH)
AREA_MAP_CACHE: Dict[str, Dict[str, Any]] = {}
AREA_HEALTH_CACHE: Optional[Dict[str, Any]] = None


def current_area_health() -> Dict[str, Any]:
    global AREA_HEALTH_CACHE
    if AREA_HEALTH_CACHE is None:
        AREA_HEALTH_CACHE = build_area_health(parser, AREA_PATH)
    return AREA_HEALTH_CACHE


# Telnet bytes needed to ask the game for MSSP. The game sends WILL MSSP
# on connect and answers a DO with its status block.
_IAC, _SE, _SB, _DO = 255, 240, 250, 253
_TELOPT_MSSP = 70
_MSSP_VAR, _MSSP_VAL = 1, 2

# One short loopback probe answers both "is the game up" and "how many are
# playing", and the status endpoint asks both. Hold the answer briefly so
# a five-second dashboard poll does not open two connections each time.
_GAME_PROBE_TTL = 2.0
_GAME_PROBE_CACHE: tuple[float, bool, Optional[int]] | None = None


def _parse_mssp(payload: bytes) -> Dict[str, str]:
    """Decode an MSSP subnegotiation body into a plain dict."""
    out: Dict[str, str] = {}
    for chunk in payload.split(bytes([_MSSP_VAR])):
        if not chunk or bytes([_MSSP_VAL]) not in chunk:
            continue
        name, _, value = chunk.partition(bytes([_MSSP_VAL]))
        out[name.decode("latin-1", "replace")] = value.decode("latin-1", "replace")
    return out


def probe_game(timeout: float = 1.0) -> tuple[bool, Optional[int]]:
    """(reachable, players) from one connection to the game port.

    players is the game's own count of descriptors in CON_PLAYING, or None
    if it did not answer in time. Never raises.
    """
    global _GAME_PROBE_CACHE

    now = time.monotonic()
    if _GAME_PROBE_CACHE is not None and now - _GAME_PROBE_CACHE[0] < _GAME_PROBE_TTL:
        return _GAME_PROBE_CACHE[1], _GAME_PROBE_CACHE[2]

    reachable = False
    players: Optional[int] = None
    try:
        with socket.create_connection((MUD_HOST, MUD_PORT), timeout=timeout) as sock:
            reachable = True
            sock.sendall(bytes([_IAC, _DO, _TELOPT_MSSP]))
            sock.settimeout(timeout)

            deadline = time.monotonic() + timeout
            buf = b""
            marker = bytes([_IAC, _SB, _TELOPT_MSSP])
            end = bytes([_IAC, _SE])
            while time.monotonic() < deadline and len(buf) < 65536:
                try:
                    chunk = sock.recv(4096)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                start = buf.find(marker)
                if start < 0:
                    continue
                stop = buf.find(end, start + len(marker))
                if stop < 0:
                    continue
                fields = _parse_mssp(buf[start + len(marker):stop])
                raw = fields.get("PLAYERS", "")
                if raw.strip().lstrip("-").isdigit():
                    players = max(0, int(raw.strip()))
                break
    except OSError:
        reachable = False

    _GAME_PROBE_CACHE = (now, reachable, players)
    return reachable, players


def read_process_health() -> dict[str, bool]:
    """Return runtime reachability without probing the dashboard itself."""
    mud_online, _players = probe_game(timeout=0.5)
    return {
        "merc": mud_online,
        # Serving this request proves the web process is available. Probing a
        # separately configured port gave false negatives for --port launches.
        "webadmin": True,
    }


def game_process_uptime() -> float | None:
    """Seconds the game process has been running, or None if not found.

    The host's uptime says when the Pi last rebooted, which is a different
    question: the game restarts on every deploy and the hardware does not.
    """
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            try:
                command = (entry / "comm").read_text(encoding="ascii").strip()
            except OSError:
                continue
            if command not in ("merc", "rom"):
                continue
            started = entry.stat().st_mtime
            return max(0.0, time.time() - started)
    except OSError:
        pass
    return None


def players_online() -> Dict[str, Any]:
    """Who the journal thinks is connected, bounded by the game's own count.

    A session that ends without a recorded close leaves a stale connect in
    the journal, so the names alone over-report -- only ever upward. The
    game counts descriptors in CON_PLAYING and publishes that over MSSP,
    and that number is the authority on how many; the names explain who.

    `source` says which it is: "game" when the count came from the game,
    "journal" when the game could not be asked and the names are all there
    is. A deploy gate wants "game", and should treat "journal" as an
    upper bound rather than a reading.
    """
    names: list[str] = []
    try:
        rows = parse_login_journal(LOGIN_JOURNAL)
    except OSError:
        rows = []

    # parse_login_journal yields file order, oldest first, so the last row
    # seen for a name is its most recent event, and later rows are the more
    # recent sessions.
    latest: Dict[str, str] = {}
    order: list[str] = []
    for row in rows:
        name = row.get("name")
        event = row.get("event")
        if name and event:
            if name not in latest:
                order.append(name)
            latest[name] = event
    open_names = [name for name in order
                  if latest[name] in ("connect", "new", "reconnect")]

    _reachable, playing = probe_game()

    if playing is None:
        return {"names": sorted(open_names), "count": len(open_names),
                "source": "journal"}

    # The game is the authority. Where the journal has kept more names than
    # there are players, the stale ones are the older sessions, so trust
    # the most recent few; where it has fewer, the names simply cannot say
    # who the rest are.
    if playing < len(open_names):
        open_names = open_names[len(open_names) - playing:]

    return {"names": sorted(open_names), "count": playing, "source": "game"}


def file_status(path: Path) -> Dict[str, Any]:
    """Return non-sensitive metadata for an operator-visible runtime file."""
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "size_bytes": 0, "modified": None}
    return {
        "exists": path.is_file(),
        "size_bytes": stat.st_size,
        "modified": stat.st_mtime,
    }


def pending_queue_status(path: Path, max_bytes: int = 1024 * 1024) -> Dict[str, Any]:
    """Count queued actions without exposing their privileged payloads."""
    metadata = file_status(path)
    if not metadata["exists"]:
        return {**metadata, "pending_actions": 0, "truncated": False, "readable": True}

    try:
        with path.open("rb") as queue_file:
            payload = queue_file.read(max_bytes + 1)
    except OSError:
        return {**metadata, "pending_actions": 0, "truncated": False, "readable": False}

    truncated = len(payload) > max_bytes
    visible = payload[:max_bytes]
    pending = sum(1 for line in visible.splitlines() if line.strip())
    return {
        **metadata,
        "pending_actions": pending,
        "truncated": truncated,
        "readable": True,
    }


def backup_records() -> list[Dict[str, Any]]:
    if not BACKUP_PATH.is_dir():
        return []

    backups: list[Dict[str, Any]] = []
    for path in BACKUP_PATH.glob("*.tar.gz"):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            # A backup can be pruned between directory enumeration and stat.
            continue
        backups.append(
            {
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            }
        )

    backups.sort(key=lambda item: item["modified"], reverse=True)
    return backups


def player_save_summary(limit: int = 8) -> Dict[str, Any]:
    players: list[Dict[str, Any]] = []
    try:
        candidates = PLAYER_PATH.iterdir()
        for path in candidates:
            try:
                if (
                    not PLAYER_NAME_RE.fullmatch(path.name)
                    or path.is_symlink()
                    or not path.is_file()
                ):
                    continue
                stat = path.stat()
            except OSError:
                continue
            players.append({"name": path.name, "modified": stat.st_mtime})
    except OSError:
        return {"count": 0, "recent": []}

    players.sort(key=lambda item: item["modified"], reverse=True)
    return {"count": len(players), "recent": players[:limit]}


def admin_status_snapshot() -> Dict[str, Any]:
    backups = backup_records()
    return {
        "generated": time.time(),
        "runtime": read_process_health(),
        "online": players_online(),
        "game_uptime_seconds": game_process_uptime(),
        "queue": pending_queue_status(QUEUE_PATH),
        "backups": {
            "count": len(backups),
            "latest": backups[0] if backups else None,
        },
        "players": player_save_summary(),
        "activity": {
            "log": file_status(DEFAULT_LOG),
            "events": file_status(EVENT_LOG),
        },
    }


def safe_host_text(value: Any, limit: int = 1200) -> str:
    """Return bounded printable text suitable for the host-status response."""
    text = str(value or "")
    printable = "".join(
        character if character in "\t\n" or ord(character) >= 32 else " "
        for character in text
    )
    return printable[:limit]


def run_host_command(
    arguments: tuple[str, ...], timeout: float = 4.0
) -> Optional[subprocess.CompletedProcess[str]]:
    """Run one fixed telemetry command without a shell or caller-controlled arguments."""
    if not arguments or arguments[0] not in HOST_COMMANDS:
        return None
    executable = shutil.which(arguments[0])
    if not executable:
        return None
    environment = os.environ.copy()
    environment.update({"LANG": "C", "LC_ALL": "C"})
    try:
        result = subprocess.run(
            (executable, *arguments[1:]),
            cwd=REPOSITORY_ROOT if arguments[0] == "git" else None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if len(result.stdout) > HOST_COMMAND_OUTPUT_LIMIT:
        result.stdout = result.stdout[:HOST_COMMAND_OUTPUT_LIMIT]
    return result


def parse_systemctl_records(output: str) -> Dict[str, Dict[str, str]]:
    records: Dict[str, Dict[str, str]] = {}
    for block in re.split(r"\n\s*\n", output.strip()):
        values: Dict[str, str] = {}
        for line in block.splitlines():
            key, separator, value = line.partition("=")
            if separator and key:
                values[key] = safe_host_text(value, 500)
        unit_id = values.get("Id", "")
        if unit_id:
            records[unit_id] = values
    return records


def systemd_unit_status(
    units: tuple[str, ...], timer: bool = False
) -> Optional[list[Dict[str, Any]]]:
    properties = (
        "Id,Description,LoadState,ActiveState,SubState,Result,LastTriggerUSec,NextElapseUSecRealtime"
        if timer
        else "Id,Description,LoadState,ActiveState,SubState,Result,MainPID,NRestarts,ActiveEnterTimestamp,ExecMainStatus"
    )
    result = run_host_command((
        "systemctl", "show", *units, "--no-pager", f"--property={properties}",
    ))
    if result is None or (result.returncode != 0 and not result.stdout.strip()):
        return None
    records = parse_systemctl_records(result.stdout)
    statuses: list[Dict[str, Any]] = []
    for unit in units:
        values = records.get(unit, {})
        status: Dict[str, Any] = {
            "unit": unit,
            "description": values.get("Description", ""),
            "load_state": values.get("LoadState", "not-found"),
            "active_state": values.get("ActiveState", "unknown"),
            "sub_state": values.get("SubState", "unknown"),
            "result": values.get("Result", ""),
        }
        if timer:
            status.update({
                "last_trigger": values.get("LastTriggerUSec", ""),
                "next_trigger": values.get("NextElapseUSecRealtime", ""),
            })
        else:
            status.update({
                "pid": int(values.get("MainPID", "0")) if values.get("MainPID", "0").isdigit() else 0,
                "restarts": int(values.get("NRestarts", "0")) if values.get("NRestarts", "0").isdigit() else 0,
                "since": values.get("ActiveEnterTimestamp", ""),
                "exit_status": values.get("ExecMainStatus", ""),
            })
        statuses.append(status)
    return statuses


def parse_journal_output(output: str, default_source: str = "") -> list[Dict[str, Any]]:
    entries: list[Dict[str, Any]] = []
    for line in output.splitlines():
        try:
            record = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        message = record.get("MESSAGE", "")
        if isinstance(message, list):
            message = " ".join(str(part) for part in message)
        timestamp_text = str(record.get("__REALTIME_TIMESTAMP", ""))
        timestamp = int(timestamp_text) / 1_000_000 if timestamp_text.isdigit() else 0
        source = default_source or record.get("_SYSTEMD_UNIT") or record.get("SYSLOG_IDENTIFIER")
        entries.append({
            "timestamp": timestamp,
            "source": safe_host_text(source, 100),
            "priority": safe_host_text(record.get("PRIORITY", ""), 10),
            "message": safe_host_text(message),
            "boot_id": safe_host_text(record.get("_BOOT_ID", ""), 40)[:12],
        })
    return entries


def host_journal_status() -> Optional[list[Dict[str, Any]]]:
    arguments = [
        "journalctl", "--output=json", "--no-pager", "--lines=160", "--since=-7 days",
    ]
    for unit in HOST_JOURNAL_UNITS:
        arguments.extend(("--unit", unit))
    result = run_host_command(tuple(arguments), timeout=6.0)
    if result is None or result.returncode != 0:
        return None
    entries = parse_journal_output(result.stdout)

    shutdowns = run_host_command((
        "journalctl", "--identifier=systemd-shutdown", "--output=json", "--no-pager",
        "--lines=20", "--since=-30 days",
    ))
    if shutdowns is not None and shutdowns.returncode == 0:
        entries.extend(parse_journal_output(shutdowns.stdout, "systemd-shutdown"))
    entries.sort(key=lambda item: item["timestamp"])
    return entries[-180:]


def boot_history_status() -> Optional[list[Dict[str, str]]]:
    result = run_host_command(("journalctl", "--list-boots", "--no-pager", "--lines=8"))
    if result is None or result.returncode != 0:
        return None
    boots: list[Dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3 or not re.fullmatch(r"-?\d+", parts[0]):
            continue
        boots.append({
            "index": parts[0],
            "boot_id": safe_host_text(parts[1], 40)[:12],
            "range": safe_host_text(parts[2], 240),
        })
    return boots


def repository_status() -> Dict[str, Any]:
    def git_output(*arguments: str, limit: int = 200) -> str:
        result = run_host_command(("git", "-C", str(REPOSITORY_ROOT), *arguments))
        if result is None or result.returncode != 0:
            return ""
        return safe_host_text(result.stdout.strip(), limit)

    head = git_output("rev-parse", "--short=12", "HEAD")
    known_remote = git_output("rev-parse", "--short=12", "origin/main")
    divergence = git_output("rev-list", "--left-right", "--count", "HEAD...origin/main")
    dirty = git_output(
        "status", "--porcelain", "--untracked-files=no",
        limit=HOST_COMMAND_OUTPUT_LIMIT,
    )
    ahead = behind = None
    divergence_parts = divergence.split()
    if len(divergence_parts) == 2 and all(part.isdigit() for part in divergence_parts):
        ahead, behind = (int(part) for part in divergence_parts)
    deployed = ""
    try:
        deployed = safe_host_text(DEPLOYED_COMMIT_FILE.read_text(encoding="ascii").strip(), 40)
    except (OSError, UnicodeError):
        pass
    return {
        "head": head,
        "known_origin_main": known_remote,
        "deployed": deployed[:12],
        "tracked_changes": len(dirty.splitlines()) if dirty else 0,
        "ahead": ahead,
        "behind": behind,
        "matches_known_origin": bool(head and known_remote and head == known_remote),
    }


def parse_cpu_counters(text: str) -> Optional[tuple[int, int]]:
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0] != "cpu" or len(fields) < 5:
            continue
        try:
            values = [int(value) for value in fields[1:9]]
        except ValueError:
            return None
        total = sum(values)
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return total, idle
    return None


def parse_network_counters(text: str) -> tuple[int, int]:
    received = transmitted = 0
    for line in text.splitlines():
        interface, separator, values_text = line.partition(":")
        if not separator or interface.strip() == "lo":
            continue
        values = values_text.split()
        if len(values) < 9:
            continue
        try:
            received += int(values[0])
            transmitted += int(values[8])
        except ValueError:
            continue
    return received, transmitted


def host_rate_status() -> Dict[str, Optional[float]]:
    global _HOST_RESOURCE_SAMPLE, _HOST_RESOURCE_RATES
    try:
        cpu_text = Path("/proc/stat").read_text(encoding="ascii")
        network_text = Path("/proc/net/dev").read_text(encoding="ascii")
    except OSError:
        return dict(_HOST_RESOURCE_RATES)
    cpu = parse_cpu_counters(cpu_text)
    if cpu is None:
        return dict(_HOST_RESOURCE_RATES)
    received, transmitted = parse_network_counters(network_text)
    now = time.monotonic()
    current = {
        "time": now,
        "cpu_total": float(cpu[0]),
        "cpu_idle": float(cpu[1]),
        "received": float(received),
        "transmitted": float(transmitted),
    }
    with _HOST_RESOURCE_LOCK:
        previous = _HOST_RESOURCE_SAMPLE
        elapsed = now - previous["time"] if previous else 0
        if previous and elapsed >= HOST_RESOURCE_SAMPLE_MIN_INTERVAL:
            total_delta = current["cpu_total"] - previous["cpu_total"]
            idle_delta = current["cpu_idle"] - previous["cpu_idle"]
            cpu_percent = None
            if total_delta > 0:
                cpu_percent = max(0.0, min(100.0, (total_delta - idle_delta) * 100 / total_delta))
            _HOST_RESOURCE_RATES = {
                "cpu_percent": cpu_percent,
                "receive_bytes_per_second": max(0.0, current["received"] - previous["received"]) / elapsed,
                "transmit_bytes_per_second": max(0.0, current["transmitted"] - previous["transmitted"]) / elapsed,
            }
            _HOST_RESOURCE_SAMPLE = current
        elif previous is None:
            _HOST_RESOURCE_SAMPLE = current
        return dict(_HOST_RESOURCE_RATES)


def host_resource_status() -> Dict[str, Any]:
    uptime = 0.0
    boot_id = ""
    temperature = None
    memory: Dict[str, int] = {}
    try:
        uptime = float(Path("/proc/uptime").read_text(encoding="ascii").split()[0])
    except (OSError, ValueError, IndexError):
        pass
    try:
        boot_id = safe_host_text(Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip(), 40)[:12]
    except OSError:
        pass
    try:
        temperature = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text(encoding="ascii").strip()) / 1000
    except (OSError, ValueError):
        pass
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, separator, value = line.partition(":")
            if separator:
                fields = value.split()
                if fields and fields[0].isdigit():
                    memory[key] = int(fields[0]) * 1024
    except OSError:
        pass
    try:
        disk = shutil.disk_usage("/")
        root_filesystem = {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        }
    except OSError:
        root_filesystem = {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0}
    total_memory = memory.get("MemTotal", 0)
    available_memory = memory.get("MemAvailable", 0)
    total_swap = memory.get("SwapTotal", 0)
    free_swap = memory.get("SwapFree", 0)
    try:
        load_average = list(os.getloadavg())
    except OSError:
        load_average = []
    resources = {
        "hostname": safe_host_text(socket.gethostname(), 255),
        "boot_id": boot_id,
        "uptime_seconds": uptime,
        "cpu_count": os.cpu_count() or 0,
        "load_average": load_average,
        "temperature_c": temperature,
        "memory": {
            "total_bytes": total_memory,
            "available_bytes": available_memory,
            "used_bytes": max(0, total_memory - available_memory),
        },
        "swap": {
            "total_bytes": total_swap,
            "free_bytes": free_swap,
            "used_bytes": max(0, total_swap - free_swap),
        },
        "root_filesystem": root_filesystem,
    }
    resources.update(host_rate_status())
    resources["network"] = {
        "receive_bytes_per_second": resources.pop("receive_bytes_per_second"),
        "transmit_bytes_per_second": resources.pop("transmit_bytes_per_second"),
    }
    return resources


def host_resource_snapshot() -> Dict[str, Any]:
    return {
        "generated": time.time(),
        "read_only": True,
        "host": host_resource_status(),
    }


def host_status_snapshot() -> Dict[str, Any]:
    errors: list[str] = []
    services = systemd_unit_status(HOST_SERVICE_UNITS)
    timers = systemd_unit_status(HOST_TIMER_UNITS, timer=True)
    boots = boot_history_status()
    journal = host_journal_status()
    if services is None:
        services = []
        errors.append("Service status is unavailable.")
    if timers is None:
        timers = []
        errors.append("Timer status is unavailable.")
    if boots is None:
        boots = []
        errors.append("Boot history is unavailable.")
    if journal is None:
        journal = []
        errors.append("Operational journal history is unavailable.")
    return {
        "generated": time.time(),
        "read_only": True,
        # The Host tab used to take this from /api/admin/status and showed
        # "Locked" whenever that call was not available to it, sitting next
        # to a host uptime that was working. It is host telemetry; it
        # belongs here.
        "game_uptime_seconds": game_process_uptime(),
        "host": host_resource_status(),
        "repository": repository_status(),
        "services": services,
        "timers": timers,
        "boots": boots,
        "journal": journal,
        "errors": errors,
    }


@app.get("/", response_class=FileResponse, include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_PATH / "index.html")


@app.get("/client", response_class=FileResponse, include_in_schema=False)
@app.get("/client/", response_class=FileResponse, include_in_schema=False)
async def game_client() -> FileResponse:
    return FileResponse(STATIC_PATH / "client.html")


# --------------------------------------------------------------------------
# Player help, read out of the area files.
#
# The game serves this same text to HELP, so reading the area files rather
# than keeping a copy means the website cannot drift out of step with it.
# --------------------------------------------------------------------------

# Above this level an entry is staff documentation and stays off the public
# page. This filter is the whole security model, so it runs at parse time.
HELP_PUBLIC_MAX_LEVEL = 0

_HELP_CACHE: tuple[float, list[Dict[str, Any]]] = (0.0, [])
_HELP_TTL = 60.0


def _parse_help_section(text: str) -> list[Dict[str, Any]]:
    """Entries from one #HELPS block: level, keywords, body."""
    entries: list[Dict[str, Any]] = []
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        header = lines[index].strip()
        index += 1
        if not header:
            continue
        if header.startswith("#"):
            break

        # "<level> <KEYWORDS>~", where a keyword group may be quoted.
        if not header.endswith("~"):
            continue
        header = header[:-1].strip()
        parts = header.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            level = int(parts[0])
        except ValueError:
            continue

        keywords = parts[1].strip()
        if keywords == "$":
            break

        body: list[str] = []
        while index < len(lines) and lines[index].rstrip() != "~":
            body.append(lines[index])
            index += 1
        index += 1  # step over the closing tilde

        if level > HELP_PUBLIC_MAX_LEVEL:
            continue

        names = [name.strip("'\"") for name in keywords.split()
                 if name.strip("'\"")]
        if not names:
            continue

        entries.append({
            "level": level,
            "keywords": names,
            "title": names[0].title(),
            "body": "\n".join(body).strip("\n"),
        })

    return entries


def load_player_help() -> list[Dict[str, Any]]:
    """Every player-visible help entry, cached briefly."""
    global _HELP_CACHE

    cached_at, cached = _HELP_CACHE
    now = time.monotonic()
    if cached and now - cached_at < _HELP_TTL:
        return cached

    entries: list[Dict[str, Any]] = []
    seen: set[str] = set()
    try:
        files = sorted(AREA_PATH.glob("*.are"))
    except OSError:
        files = []

    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        marker = content.find("#HELPS")
        if marker == -1:
            continue
        for entry in _parse_help_section(content[marker + len("#HELPS"):]):
            # First definition wins, matching how the game resolves a
            # keyword that more than one file claims.
            key = entry["keywords"][0].lower()
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)

    entries.sort(key=lambda item: item["title"].lower())
    _HELP_CACHE = (now, entries)
    return entries


_DIRECTIONS_PATH = Path(__file__).resolve().parent / "directions.json"
_DIRECTIONS_CACHE: Tuple[float, Dict[str, Any]] | None = None


def load_directions() -> Dict[str, Any]:
    """The route list, rebuilt from the area files by tools/build_directions.

    Cached on the file's mtime: it changes when somebody regenerates it, not
    on a timer, and it is read on every open of the Routes tab.
    """
    global _DIRECTIONS_CACHE

    try:
        stamp = _DIRECTIONS_PATH.stat().st_mtime
    except OSError:
        return {"start": {}, "counts": {}, "routes": []}

    if _DIRECTIONS_CACHE is not None and _DIRECTIONS_CACHE[0] == stamp:
        return _DIRECTIONS_CACHE[1]

    try:
        data = json.loads(_DIRECTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"start": {}, "counts": {}, "routes": []}

    _DIRECTIONS_CACHE = (stamp, data)
    return data


@app.get("/api/directions")
async def directions_index() -> Dict[str, Any]:
    """Travel routes from the Oak Tree Square. Public, like the help text."""
    return await asyncio.to_thread(load_directions)


@app.get("/api/help")
async def help_index() -> Dict[str, Any]:
    """Player help topics. Deliberately unauthenticated: it is public text."""
    entries = await asyncio.to_thread(load_player_help)
    return {
        "topics": [
            {
                "title": entry["title"],
                "keywords": entry["keywords"],
                "summary": next(
                    (line.strip() for line in entry["body"].splitlines()
                     if line.strip()), ""),
            }
            for entry in entries
        ],
        "total": len(entries),
    }


@app.get("/api/help/{topic}")
async def help_topic(topic: str) -> Dict[str, Any]:
    entries = await asyncio.to_thread(load_player_help)
    wanted = topic.strip().lower()

    for entry in entries:
        if any(word.lower() == wanted for word in entry["keywords"]):
            return {
                "title": entry["title"],
                "keywords": entry["keywords"],
                "body": entry["body"],
            }

    for entry in entries:
        if any(word.lower().startswith(wanted) for word in entry["keywords"]):
            return {
                "title": entry["title"],
                "keywords": entry["keywords"],
                "body": entry["body"],
            }

    raise HTTPException(status_code=404, detail="No help on that topic.")


@app.get("/api/health")
async def health() -> dict[str, bool | str]:
    status = await asyncio.to_thread(read_process_health)
    return {"status": "ok", **status}


@app.get("/api/admin/status")
async def admin_status(_: None = Depends(verify_token)) -> Dict[str, Any]:
    return await asyncio.to_thread(admin_status_snapshot)


@app.get("/api/host/status")
async def host_status(_: None = Depends(verify_token)) -> Dict[str, Any]:
    if not HOST_STATUS_ENABLED:
        raise HTTPException(status_code=503, detail="Host status is not enabled")
    return await asyncio.to_thread(host_status_snapshot)


@app.get("/api/host/resources")
async def host_resources(_: None = Depends(verify_token)) -> Dict[str, Any]:
    if not HOST_STATUS_ENABLED:
        raise HTTPException(status_code=503, detail="Host status is not enabled")
    return await asyncio.to_thread(host_resource_snapshot)


@app.get("/api/config")
async def get_config(request: Request) -> Dict[str, Any]:
    return {
        "version": app.version,
        "admin_token_configured": bool(_WEB_ADMIN_TOKEN),
        "local_admin_unlock": local_admin_request_allowed(request),
        "mud_endpoint": f"{public_game_host()}:{MUD_PUBLIC_PORT}",
        "mud_endpoint_host": MUD_PUBLIC_HOST,
        "client_path": "/client",
        "game_websocket_auth": "same-origin",
        "player_data_protected": True,
        "log_websocket_auth": "cookie-or-first-message",
        "event_websocket_auth": "cookie-or-first-message",
        "update_available": UPDATE_REQUEST_PATH is not None,
        "host_status_available": HOST_STATUS_ENABLED,
    }


@app.post("/api/auth/local")
async def start_local_admin_session(request: Request, response: Response) -> Dict[str, str | bool]:
    if not _WEB_ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Admin API disabled: configure WEB_ADMIN_TOKEN",
        )
    if not local_admin_request_allowed(request):
        raise HTTPException(status_code=403, detail="Local admin unlock is unavailable")
    response.set_cookie(
        key=LOCAL_ADMIN_COOKIE,
        value=local_admin_session_value(),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "mode": "local"}


@app.post("/api/auth/logout")
async def end_local_admin_session(response: Response) -> Dict[str, bool]:
    response.delete_cookie(key=LOCAL_ADMIN_COOKIE, path="/")
    return {"authenticated": False}


@app.get("/api/logins")
async def logins(
    limit: int = Query(default=500, ge=1, le=100000),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    """Login history and playtime. Token-gated: the rows carry player IPs.

    Pairing has to run over the whole journal before any window is taken, or
    a session whose start and end straddle the page boundary loses its
    duration. So read everything, pair it, then slice.
    """
    rows = parse_login_journal(LOGIN_JOURNAL)
    sessions = pair_login_sessions(rows)
    window = sessions[offset:offset + limit]
    return {
        "generated": time.time(),
        "journal_present": LOGIN_JOURNAL.exists(),
        "sessions": window,
        "total": len(sessions),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(window) < len(sessions),
        "players": player_playtime_totals(),
    }


def parse_channel_journal(
    path: Path, limit: int = 500, channel: str = "", search: str = ""
) -> tuple[list[Dict[str, Any]], list[str]]:
    """Read the channel journal newest-first, with the channels it holds.

    The channel list is built from the whole file rather than from the
    window, or filtering to a quiet channel would remove it from its own
    dropdown. Malformed rows are skipped rather than raising: this file
    is appended to by a live game and a read can land mid-write.
    """
    rows: list[Dict[str, Any]] = []
    channels: set[str] = set()
    wanted = channel.strip().lower()
    needle = search.strip().lower()

    try:
        text = path.read_text(encoding="latin-1", errors="replace")
    except OSError:
        return [], []

    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        when, name, said = parts[0], parts[2], "\t".join(parts[3:])
        chan = parts[1]
        channels.add(chan)
        if wanted and chan.lower() != wanted:
            continue
        if needle and needle not in said.lower() and needle not in name.lower():
            continue
        try:
            stamp = float(when)
        except ValueError:
            continue
        rows.append(
            {"when": stamp, "channel": chan, "speaker": name, "text": said}
        )

    rows.reverse()
    return rows[:limit], sorted(channels)


@app.get("/api/channels")
async def channels(
    limit: int = Query(default=200, ge=1, le=2000),
    channel: str = Query(default=""),
    search: str = Query(default=""),
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    """Shared-channel history. Token-gated, like the other player views.

    The in-game HISTORY command reads memory and forgets on a reboot;
    this reads the journal the game writes beside it, so the dashboard
    can answer the same question after a restart. Tells are not in it.
    """
    rows, names = parse_channel_journal(
        CHANNEL_JOURNAL, limit=limit, channel=channel, search=search
    )
    return {
        "generated": time.time(),
        "journal_present": CHANNEL_JOURNAL.exists(),
        "lines": rows,
        "channels": names,
        "limit": limit,
    }


@app.get("/api/oracle")
async def oracle_usage(
    limit: int = Query(default=50, ge=1, le=500),
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    """Oracle usage: recent Q&A with tokens and cost, per-player and grand
    totals, and today's spend. Token-gated, like the other player views."""
    return await asyncio.to_thread(oracle_report, limit)


@app.get("/api/auth/check")
async def check_auth(_: None = Depends(verify_token)) -> Dict[str, bool]:
    return {"authenticated": True}


LOGIN_EVENTS_START = {"connect", "new", "reconnect"}
LOGIN_EVENTS_END = {"quit", "linkdead", "shutdown"}


def parse_login_journal(path: Path, limit: Optional[int] = None) -> list[Dict[str, Any]]:
    """Read the game's login journal into rows, in file order: oldest first.

    Written by the game as tab-separated `when, name, host, event` with a
    fifth `duration` column on the rows that end a session. Anything
    malformed is skipped rather than failing the whole listing: this is an
    append-only file a crash can truncate mid-row.
    """
    try:
        raw = path.read_text(encoding="latin-1", errors="replace")
    except (OSError, ValueError):
        return []

    rows: list[Dict[str, Any]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        try:
            when = int(parts[0])
        except ValueError:
            continue
        event = parts[3].strip().lower()
        duration: Optional[int] = None
        if len(parts) >= 5:
            try:
                duration = max(0, int(parts[4]))
            except ValueError:
                duration = None
        rows.append({
            "when": when,
            "name": parts[1].strip(),
            "host": parts[2].strip(),
            "event": event,
            "duration": duration,
        })

    rows.sort(key=lambda row: row["when"])
    return rows[-limit:] if limit else rows


def pair_login_sessions(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Turn the flat journal into sessions, newest first.

    A start row opens a session for that character and the next end row for
    the same character closes it. A start with no end is still in progress,
    or was lost to a hard crash, and is reported with a null duration rather
    than a guess.
    """
    open_by_name: Dict[str, Dict[str, Any]] = {}
    sessions: list[Dict[str, Any]] = []

    for row in rows:
        name = row["name"]
        if row["event"] in LOGIN_EVENTS_START:
            session = {
                "name": name,
                "host": row["host"],
                "login": row["when"],
                "event": row["event"],
                "logout": None,
                "duration": None,
                "ended": None,
            }
            open_by_name[name.lower()] = session
            sessions.append(session)
        elif row["event"] in LOGIN_EVENTS_END:
            session = open_by_name.pop(name.lower(), None)
            if session is None:
                # An ending with no beginning: the journal was trimmed past
                # its start. Report it rather than dropping the playtime.
                sessions.append({
                    "name": name,
                    "host": row["host"],
                    "login": None,
                    "event": None,
                    "logout": row["when"],
                    "duration": row["duration"],
                    "ended": row["event"],
                })
                continue
            session["logout"] = row["when"]
            session["ended"] = row["event"]
            if row["duration"] is not None:
                session["duration"] = row["duration"]
            elif session["login"] is not None:
                session["duration"] = max(0, row["when"] - session["login"])

    sessions.sort(key=lambda s: s["logout"] or s["login"] or 0, reverse=True)
    return sessions


def player_playtime_totals() -> Dict[str, Dict[str, Any]]:
    """Lifetime totals straight from the save files.

    The journal only knows about sessions it has seen; `Plyd` is the whole
    history of the character, and `SesDur` is the last completed session as
    the game itself recorded it.
    """
    totals: Dict[str, Dict[str, Any]] = {}
    try:
        entries = sorted(PLAYER_PATH.iterdir())
    except OSError:
        return totals

    for entry in entries:
        if not entry.is_file() or not PLAYER_NAME_RE.fullmatch(entry.name):
            continue
        record: Dict[str, Any] = {"played": None, "last_session": None,
                                  "last_login": None, "level": None}
        try:
            with entry.open("r", encoding="latin-1", errors="replace") as handle:
                for index, line in enumerate(handle):
                    # The character's own fields run to the first object; every
                    # #O section after it carries its own Levl and Room.
                    if index and line.startswith("#"):
                        break
                    key, _, value = line.partition(" ")
                    # "SesDur" is written with padding, so split on the first
                    # space and strip rather than assuming one separator.
                    value = value.strip()
                    try:
                        if key == "Plyd":
                            record["played"] = int(value)
                        elif key == "SesDur":
                            record["last_session"] = int(value)
                        elif key == "SesLogin":
                            record["last_login"] = int(value)
                        elif key == "Levl":
                            record["level"] = int(value)
                        elif key == "LogO":
                            record["logout"] = int(value)
                    except ValueError:
                        continue
        except OSError:
            continue
        totals[entry.name] = record
    return totals


def tail_log_file(path: Path, lines: int) -> str:
    """Read a bounded number of trailing lines without loading a large log."""
    block_size = 64 * 1024
    with path.open("rb") as log_file:
        log_file.seek(0, os.SEEK_END)
        position = log_file.tell()
        chunks: deque[bytes] = deque()
        newline_count = 0
        while position > 0 and newline_count <= lines:
            size = min(block_size, position)
            position -= size
            log_file.seek(position)
            chunk = log_file.read(size)
            chunks.appendleft(chunk)
            newline_count += chunk.count(b"\n")
    data = b"".join(chunks).decode("utf-8", errors="replace")
    return "".join(data.splitlines(keepends=True)[-lines:])


def parse_server_event_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse one tab-separated event emitted by the game process."""
    parts = line.rstrip("\r\n").split("\t", 3)
    if len(parts) != 4:
        return None
    timestamp_text, channel, level_text, message = parts
    if channel not in {"info", "wizinfo"} or not message:
        return None
    try:
        timestamp = int(timestamp_text)
        level = int(level_text)
    except ValueError:
        return None
    if timestamp <= 0 or level < 0 or level > 70:
        return None
    return {
        "timestamp": timestamp,
        "channel": channel,
        "level": level if channel == "wizinfo" else None,
        "message": message,
    }


def snapshot_server_events(path: Path, limit: int) -> tuple[list[Dict[str, Any]], int]:
    """Read a bounded snapshot and the exact file position it represents."""
    block_size = 64 * 1024
    try:
        with path.open("rb") as event_file:
            event_file.seek(0, os.SEEK_END)
            end_position = event_file.tell()
            position = end_position
            chunks: deque[bytes] = deque()
            newline_count = 0
            while position > 0 and newline_count <= limit:
                size = min(block_size, position)
                position -= size
                event_file.seek(position)
                chunk = event_file.read(size)
                chunks.appendleft(chunk)
                newline_count += chunk.count(b"\n")
    except FileNotFoundError:
        return [], 0

    text = b"".join(chunks).decode("utf-8", errors="replace")
    events = [parse_server_event_line(line) for line in text.splitlines()]
    return [event for event in events if event is not None][-limit:], end_position


def tail_server_events(path: Path, limit: int) -> list[Dict[str, Any]]:
    return snapshot_server_events(path, limit)[0]


@app.get("/api/logs")
async def tail_logs(lines: int = 200, _: None = Depends(verify_token)) -> PlainTextResponse:
    lines = max(1, min(lines, 5000))
    if not DEFAULT_LOG.exists():
        return PlainTextResponse("Log file not found.", status_code=404)
    try:
        return PlainTextResponse(await asyncio.to_thread(tail_log_file, DEFAULT_LOG, lines))
    except OSError:
        return PlainTextResponse("Error reading log file.", status_code=500)


@app.get("/api/logs/page")
async def log_page(
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: None = Depends(verify_token),
) -> Dict[str, Any]:
    """One page of the game log, counted back from the newest line.

    The plain /api/logs tail caps how far back you can see; this pages
    instead, so an old entry is reachable rather than merely beyond the
    ceiling. Offset 0 is the newest page.
    """
    if not DEFAULT_LOG.exists():
        return {
            "present": False, "lines": [], "total": 0,
            "offset": offset, "limit": limit, "has_more": False,
        }

    def read() -> list[str]:
        with DEFAULT_LOG.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read().splitlines()

    try:
        every = await asyncio.to_thread(read)
    except OSError:
        raise HTTPException(status_code=500, detail="Error reading log file")

    # Newest first, so paging forward walks backwards through history.
    every.reverse()
    window = every[offset:offset + limit]
    return {
        "present": True,
        "lines": window,
        "total": len(every),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(window) < len(every),
    }


@app.get("/api/events")
async def server_events(
    limit: int = Query(default=200, ge=1, le=MAX_EVENT_HISTORY),
    offset: int = Query(default=0, ge=0),
    paged: bool = Query(default=False),
    _: None = Depends(verify_token),
) -> Any:
    """Server activity, newest first.

    Returns a bare list by default because that is what the existing
    callers expect; `paged=1` asks for the envelope with a total, which is
    what the dashboard needs to show "page 2 of 9" rather than guessing.
    """
    try:
        every = await asyncio.to_thread(
            tail_server_events, EVENT_LOG, MAX_EVENT_HISTORY)
    except OSError:
        raise HTTPException(status_code=500, detail="Error reading server activity")

    # snapshot_server_events returns file order, oldest first. The bare-list
    # callers expect the newest `limit` in that order, so preserve it.
    if not paged:
        return every[-limit:]

    # Paging counts back from the newest, so offset 0 is the current page.
    newest_first = list(reversed(every))
    window = newest_first[offset:offset + limit]
    return {
        "events": window,
        "total": len(every),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(window) < len(every),
    }


async def accept_admin_websocket(websocket: WebSocket) -> bool:
    """Accept a protected WebSocket using a local session or shared token."""
    local_session = local_admin_websocket_authenticated(websocket)
    await websocket.accept()
    if local_session:
        return True
    try:
        auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        auth_payload = json.loads(auth_message)
        supplied_token = auth_payload.get("token", "") if isinstance(auth_payload, dict) else ""
        if (
            not isinstance(auth_payload, dict)
            or auth_payload.get("type") != "auth"
            or not _WEB_ADMIN_TOKEN
            or not secrets.compare_digest(str(supplied_token), _WEB_ADMIN_TOKEN)
        ):
            await websocket.close(code=4003)
            return False
    except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
        try:
            await websocket.close(code=4003)
        except RuntimeError:
            pass
        return False
    return True


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008)
        return
    if not await accept_admin_websocket(websocket):
        return

    async def watch_disconnect() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text"):
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and payload.get("type") == "close":
                    return

    async def follow_log() -> None:
        initial = ""
        if DEFAULT_LOG.exists():
            initial = await asyncio.to_thread(tail_log_file, DEFAULT_LOG, 200)
        await websocket.send_text(initial)
        last_pos = DEFAULT_LOG.stat().st_size if DEFAULT_LOG.exists() else 0

        while True:
            await asyncio.sleep(1)
            if not DEFAULT_LOG.exists():
                last_pos = 0
                continue
            current_pos = DEFAULT_LOG.stat().st_size
            if current_pos < last_pos:
                rotated = await asyncio.to_thread(tail_log_file, DEFAULT_LOG, 200)
                if rotated:
                    await websocket.send_text(rotated)
                last_pos = current_pos
            elif current_pos > last_pos:
                with DEFAULT_LOG.open("rb") as log_file:
                    log_file.seek(last_pos)
                    new_data = log_file.read(current_pos - last_pos)
                if new_data:
                    await websocket.send_text(new_data.decode("utf-8", errors="replace"))
                last_pos = current_pos

    tasks = {
        asyncio.create_task(watch_disconnect()),
        asyncio.create_task(follow_log()),
    }
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        # Test clients and ASGI servers can cancel the endpoint instead of
        # delivering a final disconnect frame. Treat that as a normal close.
        pass
    finally:
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, OSError):
                print(f"Log WebSocket error: {result}")
        try:
            await websocket.close()
        except RuntimeError:
            pass


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008)
        return
    if not await accept_admin_websocket(websocket):
        return

    async def watch_disconnect() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text"):
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and payload.get("type") == "close":
                    return

    async def follow_events() -> None:
        initial, last_pos = await asyncio.to_thread(
            snapshot_server_events, EVENT_LOG, min(300, MAX_EVENT_HISTORY)
        )
        await websocket.send_json({"type": "snapshot", "events": initial})

        while True:
            await asyncio.sleep(1)
            if not EVENT_LOG.exists():
                last_pos = 0
                continue
            current_pos = EVENT_LOG.stat().st_size
            if current_pos < last_pos:
                rotated, last_pos = await asyncio.to_thread(
                    snapshot_server_events, EVENT_LOG, min(300, MAX_EVENT_HISTORY)
                )
                await websocket.send_json({"type": "snapshot", "events": rotated})
            elif current_pos > last_pos:
                with EVENT_LOG.open("rb") as event_file:
                    event_file.seek(last_pos)
                    new_data = event_file.read(current_pos - last_pos)
                events = [
                    parse_server_event_line(line)
                    for line in new_data.decode("utf-8", errors="replace").splitlines()
                ]
                parsed = [event for event in events if event is not None][-MAX_EVENT_HISTORY:]
                if parsed:
                    await websocket.send_json({"type": "events", "events": parsed})
                last_pos = current_pos

    tasks = {
        asyncio.create_task(watch_disconnect()),
        asyncio.create_task(follow_events()),
    }
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        pass
    finally:
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, OSError):
                print(f"Event WebSocket error: {result}")
        try:
            await websocket.close()
        except RuntimeError:
            pass


@app.post("/api/announce")
async def send_announcement(
    request: AnnounceRequest, _: None = Depends(verify_token)
) -> str:
    """Send a framed message to every player who is online.

    Distinct from /api/wizinfo, which only reaches immortals at or above a
    level -- an operator sending one of those sees nothing happen and
    reasonably concludes the dashboard is broken.
    """
    message = validated_queue_payload(request.message, "Announcement", 400)
    append_queue_action(f"announce|{message}")
    return "queued"


@app.post("/api/wizinfo")
async def send_wizinfo(request: WizinfoRequest, _: None = Depends(verify_token)) -> str:
    message = validated_queue_payload(request.message, "Message", 4000)
    level = request.level if request.level is not None else 62
    if level < 1 or level > 70:
        raise HTTPException(status_code=400, detail="Level must be between 1 and 70")
    append_queue_action(f"wizinfo|{level}|{message}")
    return "queued"


@app.post("/api/command")
async def run_command(request: CommandRequest, _: None = Depends(verify_token)) -> str:
    command = validated_queue_payload(
        request.command,
        "Command",
        COMMAND_MAX_LENGTH,
    )
    append_queue_action(f"command|{command}")
    return "queued"


@app.post("/api/backup")
async def run_backup(_: None = Depends(verify_token)) -> str:
    append_queue_action("backup")
    return "queued"


@app.post("/api/update")
async def run_update(_: None = Depends(verify_token)) -> Dict[str, str]:
    """Request the host-managed updater without granting the web process sudo."""
    if UPDATE_REQUEST_PATH is None:
        raise HTTPException(
            status_code=503,
            detail="Host updates are not configured on this installation",
        )
    try:
        await asyncio.to_thread(UPDATE_REQUEST_PATH.touch, mode=0o600, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Unable to request a host update") from exc
    return {"status": "queued"}


@app.get("/api/backups")
async def list_backups(_: None = Depends(verify_token)) -> list[Dict[str, Any]]:
    return (await asyncio.to_thread(backup_records))[:100]


@app.post("/api/shutdown")
async def run_shutdown(_: None = Depends(verify_token)) -> str:
    append_queue_action("shutdown")
    return "queued"


@app.post("/api/reload")
async def reload_areas(_: None = Depends(verify_token)) -> Dict[str, Any]:
    """Refresh the dashboard's area snapshot without changing the game state."""
    global AREA_HEALTH_CACHE, parser

    def build_snapshot() -> tuple[AreaParser, Dict[str, Any]]:
        candidate = AreaParser(AREA_PATH)
        candidate.parse_all()
        return candidate, build_area_health(candidate, AREA_PATH)

    try:
        new_parser, health = await asyncio.to_thread(build_snapshot)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload failed: {e}")

    critical_issues = [
        issue
        for issue in health["issues"]
        if issue.get("severity") == "critical"
    ]
    if critical_issues:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Reload rejected; the current area data remains active",
                "summary": health["summary"],
                "issues": critical_issues[:100],
            },
        )

    # A single assignment preserves the last known-good parser until validation
    # succeeds and includes resets/errors as well as the primary dictionaries.
    parser = new_parser
    AREA_HEALTH_CACHE = health
    AREA_MAP_CACHE.clear()
    return {
        "status": "ok",
        "areas": len(parser.areas),
        "mobiles": len(parser.mobiles),
        "objects": len(parser.objects),
        "rooms": len(parser.rooms),
        "parse_errors": parser.errors,
    }


@app.get("/api/objects/{vnum}")
async def get_object(vnum: int) -> Dict[str, Any]:
    obj = parser.objects.get(vnum)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    carried_by_with_rates = []
    for mob_vnum in obj.carried_by:
        mob = parser.mobiles.get(mob_vnum)
        if mob:
            carried_by_with_rates.append({
                "vnum": mob.vnum,
                "name": mob.short_desc,
                "level": mob.level,
                "area": mob.area_name,
                "drop_rate": 0
            })
    
    # Decode affects to human-readable format
    decoded_affects = decode_applies(obj.affects)
    item_type_num = int(obj.item_type) if obj.item_type.isdigit() else 0
    decoded_item_type = ITEM_TYPES.get(item_type_num, obj.item_type)
    decoded_extra_flags = decode_flags(obj.extra_flags, ITEM_FLAGS)
    decoded_extra_flags2 = decode_flags(obj.extra_flags2, ITEM_FLAGS2)
    decoded_wear_flags = decode_flags(obj.wear_flags, WEAR_FLAGS)
    
    # Interpret values
    values_interpreted = interpret_values(item_type_num, obj.values, obj.level)
    
    return {
        "vnum": obj.vnum,
        "keywords": obj.keywords,
        "short_desc": obj.short_desc,
        "long_desc": obj.long_desc,
        "material": obj.material,
        "item_type": decoded_item_type,
        "item_type_raw": obj.item_type,
        "level": obj.level,
        "weight": obj.weight,
        "cost": obj.cost,
        "condition": obj.condition,
        "extra_flags": decoded_extra_flags + decoded_extra_flags2,
        "extra_flags_raw": obj.extra_flags,
        "wear_flags": decoded_wear_flags,
        "wear_flags_raw": obj.wear_flags,
        "values": obj.values,
        "values_interpreted": values_interpreted,
        "affects": decoded_affects,
        "affects_raw": obj.affects,
        "extra_descr": obj.extra_descr,
        "area": obj.area_name,
        "area_file": obj.area_file,
        "carried_by": carried_by_with_rates
    }


@app.get("/api/stats")
async def get_stats() -> Dict[str, int]:
    return {
        "mobiles": len(parser.mobiles),
        "objects": len(parser.objects),
        "rooms": len(parser.rooms),
        "areas": len(parser.areas)
    }


@app.get("/api/area_health")
async def get_area_health(include_issues: bool = True) -> Dict[str, Any]:
    report = await asyncio.to_thread(current_area_health)
    if include_issues:
        return report
    return {"summary": report["summary"]}


@app.get("/api/players")
async def list_players(_: None = Depends(verify_token)) -> list[str]:
    """Return sorted list of all player names (extension-less files only)."""
    try:
        return sorted(
            (
                p.name for p in PLAYER_PATH.iterdir()
                if PLAYER_NAME_RE.fullmatch(p.name) and p.is_file() and not p.is_symlink()
            ),
            key=str.lower,
        )
    except OSError:
        return []


@app.get("/api/player/{name}")
async def get_player(name: str, _: None = Depends(verify_token)) -> Dict[str, Any]:
    """Return full parsed player profile."""
    if not PLAYER_NAME_RE.fullmatch(name):
        raise HTTPException(status_code=400, detail="Invalid player name")
    data = parse_player_file(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Player '{name}' not found")
    return data


@app.get("/api/mobs")
async def get_mobs(
    response: Response,
    limit: int = 10000,
    offset: int = 0,
    q: Optional[str] = None,
) -> list:
    limit = max(1, min(limit, 50000))
    offset = max(0, offset)
    query = (q or "").strip().casefold()
    matching = [
        mob
        for _, mob in sorted(parser.mobiles.items())
        if not query
        or query in str(mob.vnum)
        or query in mob.short_desc.casefold()
        or query in mob.keywords.casefold()
        or query in mob.race.casefold()
        or query in mob.area_name.casefold()
    ]
    response.headers["X-Total-Count"] = str(len(matching))
    result = []
    for mob in matching[offset:offset + limit]:
        result.append({
            "vnum": mob.vnum,
            "short_desc": mob.short_desc,
            "long_desc": mob.long_desc,
            "level": mob.level,
            "race": mob.race,
            "keywords": mob.keywords,
            "area": mob.area_name,
            "area_file": mob.area_file
        })
    return result


@app.get("/api/rooms")
async def get_rooms(
    response: Response,
    limit: int = 10000,
    offset: int = 0,
    q: Optional[str] = None,
) -> list:
    limit = max(1, min(limit, 50000))
    offset = max(0, offset)
    query = (q or "").strip().casefold()
    matching = [
        room
        for _, room in sorted(parser.rooms.items())
        if not query
        or query in str(room.vnum)
        or query in room.name.casefold()
        or query in room.description.casefold()
        or query in room.area_name.casefold()
    ]
    response.headers["X-Total-Count"] = str(len(matching))
    result = []
    for room in matching[offset:offset + limit]:
        # Decode room flags
        decoded_flags = decode_flags(room.room_flags, ROOM_FLAGS)
        
        # Decode sector type
        sector_num = int(room.sector_type) if room.sector_type.isdigit() else 0
        decoded_sector = SECTOR_TYPES.get(sector_num, room.sector_type)
        
        result.append({
            "vnum": room.vnum,
            "name": room.name,
            "description": room.description,
            "sector_type": decoded_sector,
            "sector_type_raw": room.sector_type,
            "room_flags": decoded_flags,
            "room_flags_raw": room.room_flags,
            "area": room.area_name,
            "area_file": room.area_file,
            "exits_count": len(room.exits),
            "mob_count": len(room.mobs),
            "obj_count": len(room.objects)
        })
    return result


# Help/documentation area files that should be hidden from the database view
HELP_AREA_FILES = {'commands.are', 'skills.are', 'spells.are', 'masters.are', 'toc.are', 'help.are', 'social.are'}

@app.get("/api/areas")
async def get_areas() -> list:
    result = []
    try:
        for area in parser.areas.values():
            # Skip help/documentation files
            if area.filename in HELP_AREA_FILES:
                continue
            
            # Parse area name: "Builder    Area Name" -> separate fields
            full_name = area.name
            parts = full_name.split(None, 1)  # Split on first whitespace
            if len(parts) == 2:
                builder = parts[0].strip()
                area_name = parts[1].strip()
            else:
                builder = ""
                area_name = full_name.strip()
            
            result.append({
                "name": area_name,
                "full_name": full_name,
                "builder": builder,
                "filename": area.filename,
                "builders": area.builders,
                "vnums": getattr(area, "vnums", "")
            })
    except Exception as e:
        print(f"Error in get_areas: {e}")
        # Return partial result or empty list instead of 500
        return result
    # Sort by area name (case-insensitive)
    result.sort(key=lambda a: a["name"].lower())
    return result


@app.get("/api/areas/{filename}/map")
async def get_area_map(filename: str) -> Dict[str, Any]:
    """Generate map data for an area with room positions calculated using BFS layout."""
    cached = AREA_MAP_CACHE.get(filename)
    if cached is not None:
        return cached
    
    # Find the area
    area = parser.areas.get(filename)
    if not area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    # Get all rooms in this area
    area_rooms = [r for r in parser.rooms.values() if r.area_file == filename]
    if not area_rooms:
        raise HTTPException(status_code=404, detail="No rooms found in area")
    
    # Build adjacency and calculate positions using BFS
    # Direction offsets: 0=north(y-1), 1=east(x+1), 2=south(y+1), 3=west(x-1), 4=up, 5=down
    DIR_OFFSETS = {
        0: (0, -1),   # north
        1: (1, 0),    # east
        2: (0, 1),    # south
        3: (-1, 0),   # west
        4: (0, 0),    # up (same visual position, noted differently)
        5: (0, 0),    # down (same visual position)
    }
    
    room_vnums = {r.vnum for r in area_rooms}
    positions = {}
    occupied_positions = set()
    visited = set()
    
    # Start BFS from first room
    from collections import deque
    queue = deque()
    start_room = area_rooms[0]
    positions[start_room.vnum] = (0, 0)
    occupied_positions.add((0, 0))
    visited.add(start_room.vnum)
    queue.append(start_room.vnum)
    
    while queue:
        current_vnum = queue.popleft()
        current_pos = positions[current_vnum]
        current_room = parser.rooms.get(current_vnum)
        
        if not current_room:
            continue
            
        for ex in current_room.exits:
            if ex.to_room in room_vnums and ex.to_room not in visited:
                dx, dy = DIR_OFFSETS.get(ex.direction, (0, 0))
                
                # For up/down, try to find a free adjacent spot
                if ex.direction in (4, 5):
                    # Try to place near current room
                    for test_dx, test_dy in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)]:
                        test_pos = (current_pos[0] + test_dx, current_pos[1] + test_dy)
                        if test_pos not in occupied_positions:
                            dx, dy = test_dx, test_dy
                            break
                
                new_pos = (current_pos[0] + dx, current_pos[1] + dy)
                
                # Handle collisions - find nearest free spot
                attempts = 0
                while new_pos in occupied_positions and attempts < 50:
                    # Spiral outward to find free spot
                    attempts += 1
                    spiral_x = (attempts % 7) - 3
                    spiral_y = (attempts // 7) - 3
                    new_pos = (current_pos[0] + dx + spiral_x, current_pos[1] + dy + spiral_y)
                
                positions[ex.to_room] = new_pos
                occupied_positions.add(new_pos)
                visited.add(ex.to_room)
                queue.append(ex.to_room)
    
    # Handle disconnected rooms (place them in a row below)
    max_y = max(p[1] for p in positions.values()) if positions else 0
    disconnected_x = 0
    for room in area_rooms:
        if room.vnum not in positions:
            while (disconnected_x, max_y + 2) in occupied_positions:
                disconnected_x += 1
            positions[room.vnum] = (disconnected_x, max_y + 2)
            occupied_positions.add((disconnected_x, max_y + 2))
            disconnected_x += 1
    
    # Build result
    result_rooms = []
    for room in area_rooms:
        pos = positions.get(room.vnum, (0, 0))
        
        # Get mob/object info
        mob_names = []
        for mob_vnum in room.mobs:
            mob = parser.mobiles.get(mob_vnum)
            if mob:
                mob_names.append(mob.short_desc)
        
        obj_names = []
        for obj_vnum in room.objects:
            obj = parser.objects.get(obj_vnum)
            if obj:
                obj_names.append(obj.short_desc)
        
        result_rooms.append({
            "vnum": room.vnum,
            "name": room.name,
            "description": room.description,
            "x": pos[0],
            "y": pos[1],
            "exits": [{"direction": ex.direction, "to_room": ex.to_room, "keyword": ex.keyword} for ex in room.exits],
            "mob_count": len(room.mobs),
            "obj_count": len(room.objects),
            "mob_names": mob_names[:3],  # Limit to first 3
            "obj_names": obj_names[:3],
        })
    
    map_result = {
        "area_name": area.name,
        "filename": filename,
        "rooms": result_rooms
    }

    AREA_MAP_CACHE[filename] = map_result
    return map_result


@app.get("/api/objects")
async def get_objects(
    response: Response,
    limit: int = 10000,
    offset: int = 0,
    name: Optional[str] = None,
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    item_type: Optional[str] = None,
    wear_flag: Optional[str] = None,
    extra_flags: Optional[str] = None,
    stat_filter: Optional[str] = None
) -> list:
    limit = max(1, min(limit, 50000))
    offset = max(0, offset)
    result = []
    total = 0
    
    for _, obj in sorted(parser.objects.items()):
        # Filters
        if name and name.lower() not in obj.short_desc.lower() and name.lower() not in obj.keywords.lower():
            continue
        if min_level is not None and obj.level < min_level:
            continue
        if max_level is not None and obj.level > max_level:
            continue
            
        # Get item type number and name
        try:
            item_type_num = int(obj.item_type) if obj.item_type.isdigit() else 0
        except:
            item_type_num = 0
            
        item_type_name = ITEM_TYPES.get(item_type_num, obj.item_type)
        
        if item_type and item_type.lower() not in item_type_name.lower():
            continue
            
        # Decode flags
        flags_decoded = decode_flags(obj.extra_flags, ITEM_FLAGS)
        flags2_decoded = decode_flags(obj.extra_flags2, ITEM_FLAGS2)
        wear_decoded = decode_flags(obj.wear_flags, WEAR_FLAGS)
        
        if wear_flag:
            found_wear = False
            for flag in wear_decoded:
                if wear_flag.lower() in flag.lower():
                    found_wear = True
                    break
            if not found_wear:
                continue

        if extra_flags:
            # Expect comma-separated list of required flags
            req_flags = [f.strip().lower() for f in extra_flags.split(',')]
            all_obj_flags = [f.lower() for f in flags_decoded + flags2_decoded]
            if not all(rf in all_obj_flags for rf in req_flags):
                continue
        
        # Stat filter (e.g. "hitroll>5")
        if stat_filter:
            try:
                if '>' in stat_filter:
                    s_name, s_val = stat_filter.split('>')
                    s_val = int(s_val)
                    found_stat = False
                    for aff in obj.affects:
                        loc_name = APPLY_LOCATIONS.get(aff.get('location', 0), '').lower()
                        if s_name.lower() in loc_name and aff.get('modifier', 0) > s_val:
                            found_stat = True
                            break
                    if not found_stat:
                        continue
            except:
                pass

        total += 1
        if total <= offset or len(result) >= limit:
            continue

        affects_decoded = decode_applies(obj.affects)
        
        # Interpret values based on item type
        values_interpreted = interpret_values(item_type_num, obj.values, obj.level)
        
        # Get mobs that carry this object
        carriers = []
        for mob_vnum in obj.carried_by:
            if mob_vnum in parser.mobiles:
                mob = parser.mobiles[mob_vnum]
                carriers.append({
                    "vnum": mob.vnum,
                    "name": mob.short_desc,
                    "level": mob.level,
                    "area": mob.area_name
                })
        
        result.append({
            "vnum": obj.vnum,
            "keywords": obj.keywords,
            "short_desc": obj.short_desc,
            "long_desc": obj.long_desc,
            "material": obj.material,
            "item_type": item_type_name,
            "item_type_num": item_type_num,
            "level": obj.level,
            "weight": obj.weight,
            "cost": obj.cost,
            "condition": obj.condition,
            "flags": flags_decoded,
            "flags2": flags2_decoded,
            "wear_locations": wear_decoded,
            "affects": affects_decoded,
            "affects_raw": obj.affects,
            "values": obj.values,
            "values_interpreted": values_interpreted,
            "extra_descriptions": obj.extra_descr,
            "carried_by": carriers,
            "area": obj.area_name,
            "area_file": obj.area_file
        })
    response.headers["X-Total-Count"] = str(total)
    return result


@app.get("/api/rooms/{vnum}")
async def get_room(vnum: int) -> Dict[str, Any]:
    room = parser.rooms.get(vnum)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Resolve mobs
    mobs_in_room = []
    for mob_vnum in room.mobs:
        mob = parser.mobiles.get(mob_vnum)
        if mob:
            mobs_in_room.append({
                "vnum": mob.vnum,
                "name": mob.short_desc,
                "level": mob.level,
                "race": mob.race
            })

    # Resolve objects
    objects_in_room = []
    for obj_vnum in room.objects:
        obj = parser.objects.get(obj_vnum)
        if obj:
            objects_in_room.append({
                "vnum": obj.vnum,
                "name": obj.short_desc,
                "level": obj.level,
                "item_type": ITEM_TYPES.get(int(obj.item_type) if obj.item_type.isdigit() else 0, obj.item_type)
            })

    # Resolve exits
    exits_data = []
    for ex in room.exits:
        to_room_name = "Unknown"
        to_room = parser.rooms.get(ex.to_room)
        if to_room:
            to_room_name = to_room.name
            
        exits_data.append({
            "direction": parser.DIRECTIONS[ex.direction] if 0 <= ex.direction < len(parser.DIRECTIONS) else str(ex.direction),
            "to_room": ex.to_room,
            "to_room_name": to_room_name,
            "keyword": ex.keyword,
            "locks": ex.locks,
            "key_vnum": ex.key_vnum
        })

    # Decode room flags
    decoded_flags = decode_flags(room.room_flags, ROOM_FLAGS)
    
    # Decode sector type
    sector_num = int(room.sector_type) if room.sector_type.isdigit() else 0
    decoded_sector = SECTOR_TYPES.get(sector_num, room.sector_type)

    return {
        "vnum": room.vnum,
        "name": room.name,
        "description": room.description,
        "area": room.area_name,
        "area_file": room.area_file,
        "room_flags": decoded_flags,
        "room_flags_raw": room.room_flags,
        "sector_type": decoded_sector,
        "sector_type_raw": room.sector_type,
        "exits": exits_data,
        "extra_descr": room.extra_descr,
        "mobs": mobs_in_room,
        "objects": objects_in_room
    }


@app.get("/api/mobs/{vnum}")
async def get_mob(vnum: int) -> Dict[str, Any]:
    if vnum not in parser.mobiles:
        raise HTTPException(status_code=404, detail="Mobile not found")
    
    mob = parser.mobiles[vnum]
    
    # Interpret values
    values_interpreted = interpret_mob_values(mob)
    
    # Get drops
    drops = []
    for obj_vnum in mob.drops:
        if obj_vnum in parser.objects:
            obj = parser.objects[obj_vnum]
            drops.append({
                "vnum": obj.vnum,
                "name": obj.short_desc,
                "level": obj.level,
                "chance": 100,
                "item_type": ITEM_TYPES.get(int(obj.item_type) if obj.item_type.isdigit() else 0, obj.item_type)
            })
    
    # Get spawn rooms
    spawn_rooms = []
    for room_vnum in mob.spawn_rooms:
        if room_vnum in parser.rooms:
            room = parser.rooms[room_vnum]
            spawn_rooms.append({
                "vnum": room.vnum,
                "name": room.name,
                "area": room.area_name
            })
    
    # Decode flags
    act_decoded = decode_flags(mob.act_flags, ACT_FLAGS)
    off_decoded = decode_flags(mob.off_flags, OFF_FLAGS)
    imm_decoded = decode_flags(mob.imm_flags, IMM_FLAGS)
    res_decoded = decode_flags(mob.res_flags, RES_FLAGS)
    vuln_decoded = decode_flags(mob.vuln_flags, VULN_FLAGS)
    form_decoded = decode_flags(mob.form, FORM_FLAGS)
    parts_decoded = decode_flags(mob.parts, PART_FLAGS)
    affected_decoded = decode_flags(mob.affected_by, AFFECTED_FLAGS)

    return {
        "vnum": mob.vnum,
        "keywords": mob.keywords,
        "short_desc": mob.short_desc,
        "long_desc": mob.long_desc,
        "description": mob.description,
        "race": mob.race,
        "level": mob.level,
        "alignment": mob.alignment,
        "hitroll": mob.hitroll,
        "ac": mob.ac,
        "hitp_dice": mob.hitp_dice,
        "mana_dice": mob.mana_dice,
        "dam_dice": mob.dam_dice,
        "dam_type": mob.dam_type,
        "start_pos": mob.start_pos,
        "default_pos": mob.default_pos,
        "sex": mob.sex,
        "wealth": mob.wealth,
        "form": form_decoded,
        "parts": parts_decoded,
        "size": mob.size,
        "material": mob.material,
        "act_flags": act_decoded,
        "act_flags_raw": mob.act_flags,
        "affected_by": affected_decoded,
        "affected_by_raw": mob.affected_by,
        "off_flags": off_decoded,
        "off_flags_raw": mob.off_flags,
        "imm_flags": imm_decoded,
        "imm_flags_raw": mob.imm_flags,
        "res_flags": res_decoded,
        "res_flags_raw": mob.res_flags,
        "vuln_flags": vuln_decoded,
        "vuln_flags_raw": mob.vuln_flags,
        "form_flags": form_decoded,
        "parts_flags": parts_decoded,
        "values_interpreted": values_interpreted,
        "area": mob.area_name,
        "area_file": mob.area_file,
        "drops": drops,
        "spawn_rooms": spawn_rooms
    }


@app.get("/api/best_gear")
async def get_best_gear(
    class_name: str = Query(..., description="Class name (mage, cleric, thief, warrior, monk, necromancer)"),
    race_name: str = Query("human", description="Race name"),
    level: int = Query(50, description="Player level"),
    limit: int = Query(5, description="Items per slot")
):
    class_name = class_name.lower()
    race_name = race_name.lower()
    
    if class_name not in CLASS_WEIGHTS:
        raise HTTPException(status_code=400, detail=f"Unknown class: {class_name}")
    if race_name not in RACE_FLAGS:
        raise HTTPException(status_code=400, detail=f"Unknown race: {race_name}")
    if level < 1 or level > 70:
        raise HTTPException(status_code=400, detail="Level must be between 1 and 70")
    limit = max(1, min(limit, 50))
        
    weights = CLASS_WEIGHTS[class_name]
    race_flag = RACE_FLAGS.get(race_name)
    
    # Every slot the game equips, in the order it lists them, and an
    # entry for each even when nothing fits -- so a blank slot reads as
    # "nothing at this level" rather than as a slot the finder forgot.
    best_items: dict[str, list] = {key: [] for key, _label in GEAR_FINDER_SLOTS}

    for vnum, obj in parser.objects.items():
        # Obtainable only. A recommendation you cannot get is noise, so
        # skip anything no mobile carries or wears (carried_by is filled
        # from G and E resets). That drops uniques, quest-only pieces and
        # defined-but-never-reset orphans, leaving gear that actually
        # falls off a mob.
        if not getattr(obj, "carried_by", None):
            continue

        # Level check
        if obj.level > level:
            continue

        # Race check (exclude items restricted to OTHER races)
        flags2_decoded = decode_flags(obj.extra_flags2, ITEM_FLAGS2)
        restricted = False
        for flag in flags2_decoded:
            if flag.endswith("-only"):
                if race_flag and flag == race_flag:
                    pass # Allowed
                elif flag == "human-only" and race_name == "human":
                    pass
                else:
                    restricted = True # Restricted to another race
                    break

        if restricted:
            continue

        try:
            item_type_num = int(obj.item_type) if obj.item_type.isdigit() else 0
        except (TypeError, ValueError):
            item_type_num = 0

        # Where it can go. A light is worn as a light because of what it
        # is, not because of a wear flag (wear_obj tests the item type),
        # so lights were missing from the finder altogether. The
        # "two-hands" wear flag is read by nothing in the game.
        wear_decoded = decode_flags(obj.wear_flags, WEAR_FLAGS)
        slots = []
        if item_type_num == ITEM_TYPE_LIGHT:
            slots.append("light")
        for slot in wear_decoded:
            if slot not in best_items or slot == "light":
                continue
            # Only weapons are wielded, and a weapon goes nowhere else.
            if slot == "wield" and item_type_num != ITEM_TYPE_WEAPON:
                continue
            if item_type_num == ITEM_TYPE_WEAPON and slot != "wield":
                continue
            slots.append(slot)
        if not slots:
            continue

        # Calculate score
        score = 0.0
        breakdown = []
        affects_decoded = decode_applies(obj.affects)

        for aff in obj.affects:
            loc_id = aff.get('location', 0)
            val = aff.get('modifier', 0)
            loc_name = APPLY_LOCATIONS.get(loc_id, '').lower()

            if loc_name.startswith("save vs") and "save vs spell" in weights:
                # A save is better the lower it goes -- saves_spell()
                # subtracts saving_throw -- so a positive one is a penalty.
                # It was scored as a bonus, which put cursed kit on top.
                # All five saves move the one saving_throw in affect_modify,
                # so they share a weight.
                w = weights["save vs spell"]
                s = val * -w
                score += s
                breakdown.append(f"{loc_name.title()}: {val} x -{w} = {s:.1f}")
            elif loc_name in weights:
                w = weights[loc_name]
                s = val * w
                score += s
                breakdown.append(f"{loc_name.title()}: {val} x {w} = {s:.1f}")
            elif loc_name == 'armor class':
                # Negative AC is good in ROM, so multiply by -1 to make it a positive score
                s = val * -1.0
                score += s
                breakdown.append(f"AC: {val} x -1 = {s:.1f}")

        if item_type_num == ITEM_TYPE_WEAPON:
            # values[1] is dice count, values[2] is dice size
            try:
                d_num = int(obj.values[1])
                d_size = int(obj.values[2])
                avg_dam = d_num * (d_size + 1) / 2.0
                # Scale the weapon's own damage by how much this class fights in
                # melee (its damroll weight), so a weapon dominates a fighter's
                # score and barely moves a caster's. 0.5 keeps a warrior's
                # weapon weight at the old 2.0 (damroll 4.0 x 0.5).
                wdw = weights.get("damroll", 1.0) * 0.5
                s = avg_dam * wdw
                score += s
                breakdown.append(
                    f"Dmg: {d_num}d{d_size} (avg {avg_dam:.1f}) x {wdw:g} = {s:.1f}")
            except (IndexError, TypeError, ValueError):
                pass

        # An armour piece's own AC is values[0..3] -- pierce, bash, slash
        # and magic -- and it used to count for nothing, so plain armour
        # and most shields scored zero and were never listed.
        armour = 0.0
        if item_type_num == ITEM_TYPE_ARMOR:
            try:
                armour = sum(int(v) for v in obj.values[:4]) / 4.0
            except (TypeError, ValueError):
                armour = 0.0

        for slot in slots:
            slot_score = score
            slot_breakdown = list(breakdown)
            if armour:
                times = GEAR_AC_MULTIPLIER.get(slot, 1)
                s = armour * times
                slot_score += s
                slot_breakdown.append(
                    f"Armour: {armour:g} average x {times} on {slot} = {s:g}")
            if not slot_breakdown:
                slot_breakdown.append("No bonuses: it fills the slot and nothing more")

            best_items[slot].append({
                "score": round(slot_score, 2),
                "score_breakdown": slot_breakdown,
                "vnum": obj.vnum,
                "name": obj.short_desc,
                "level": obj.level,
                "affects": affects_decoded,
                "area": obj.area_name
            })

    # Sort and limit. Ties go to the higher-level item, then the vnum, so
    # the same question always gets the same answer.
    for items in best_items.values():
        items.sort(key=lambda x: (-x['score'], -x['level'], x['vnum']))

    result = {}
    taken: dict[str, int] = {}
    for key, label in GEAR_FINDER_SLOTS:
        items = best_items[key]
        if key in taken:
            # The second of a pair: whatever topped the first is already
            # worn there, so this one starts from the next best.
            items = [i for i in items if i["vnum"] != taken[key]]
        elif items:
            taken[key] = items[0]["vnum"]
        result[label] = items[:limit]

    return result


# --- Leveling advisor -------------------------------------------------
# The XP a kill is worth, straight from xp_compute() in src/fight.c: a
# table on level_range = mob_level - player_level + 3, flat +50 per level
# above the top of the table. Solo and neutral -- the group and alignment
# multipliers in the C only scale every mob the same way, so they do not
# change the ranking. Keep this in step with fight.c if that table moves.
_XP_BASE_TABLE = {-9: 1, -8: 2, -7: 5, -6: 10, -5: 15, -4: 25, -3: 35,
                  -2: 45, -1: 60, 0: 100, 1: 125, 2: 150, 3: 175, 4: 200}


def xp_for_kill(player_level: int, mob_level: int) -> int:
    rng = mob_level - player_level + 3
    if rng > 4:
        return 200 + 50 * (rng - 4)
    return _XP_BASE_TABLE.get(rng, 0)


def _dice_avg(spec: str) -> float:
    """Average of an 'XdY+Z' dice string, 0 on anything unparseable."""
    m = re.match(r"\s*(\d+)d(\d+)(?:\s*\+\s*(\d+))?", str(spec or ""))
    if not m:
        return 0.0
    n, size = int(m.group(1)), int(m.group(2))
    bonus = int(m.group(3)) if m.group(3) else 0
    return n * (size + 1) / 2.0 + bonus


# Town-service NPCs you grind only by mistake.
_LEVELING_SKIP_ACT = {"is-healer", "gain", "train", "practice"}
# Area resets are on a roughly uniform timer, so population -- how many of
# the mob stand in the world -- is the availability signal, not per-mob
# spawn speed. A quiet area refills a few times an hour.
_RESETS_PER_HOUR = 12


@app.get("/api/leveling")
async def get_leveling(
    level: int = Query(..., description="Player level to advise for"),
    limit: int = Query(20, description="How many mobs to return"),
):
    if level < 1 or level > 70:
        raise HTTPException(status_code=400, detail="Level must be between 1 and 70")
    limit = max(1, min(limit, 50))

    # DPS a player of this level is assumed to do. It is a modelled
    # estimate -- the game logs no combat damage and the dummy benchmark
    # board is the real source once it has runs -- and, being constant for
    # a fixed level, it only scales the xp/hour figure, never the order.
    player_dps = max(1.0, level * 3.0)
    player_hp = max(20.0, level * 20.0)

    # The same per-area routes the Directions tab shows, keyed by area so
    # each mob can carry the walk to its neighbourhood (from the Oak Tree
    # Square). Routes reach an area's entrance; the player finds the mob
    # from there.
    # Mob area names keep the builder field's padding ("Andi    The Astral
    # Plane") while the routes collapse it to single spaces, so match on a
    # whitespace-normalised key.
    def _area_key(name: str) -> str:
        return " ".join(str(name or "").split())

    directions = load_directions()
    routes_by_area: Dict[str, Dict[str, Any]] = {}
    for route in directions.get("routes", []):
        for key in (route.get("area"), route.get("area_display")):
            if key:
                routes_by_area.setdefault(_area_key(key), route)

    rows = []
    for vnum, mob in parser.mobiles.items():
        mob_level = int(mob.level or 0)
        if mob_level <= 0:
            continue
        # Killable band: you can punch above your weight, but a mob ten
        # levels up is a different game, and one far below is worth nothing.
        if mob_level > level + 8 or mob_level < level - 10:
            continue
        xp = xp_for_kill(level, mob_level)
        if xp <= 0:
            continue
        population = len(getattr(mob, "spawn_rooms", []) or [])
        if population <= 0:
            continue
        if _LEVELING_SKIP_ACT & set(decode_flags(mob.act_flags, ACT_FLAGS)):
            continue

        hp = _dice_avg(mob.hitp_dice) or (mob_level * 10.0)
        dmg = _dice_avg(mob.dam_dice)
        kill_time = max(1.0, hp / player_dps)                 # seconds
        solo_rate = 3600.0 / kill_time                        # kills/hour if always one up
        supply_rate = population * _RESETS_PER_HOUR           # kills/hour the world can refill
        kills_hr = min(solo_rate, supply_rate)
        # Brutal mobs for their level rank lower -- dying is the slowest
        # way to level.
        safety = 1.0 / (1.0 + dmg / (player_hp / 4.0))
        xp_hr = xp * kills_hr * safety

        route = routes_by_area.get(_area_key(mob.area_name))
        rows.append({
            "vnum": mob.vnum,
            "name": mob.short_desc,
            "level": mob_level,
            "area": mob.area_name,
            "count": population,
            "hp": round(hp),
            "damage": round(dmg, 1),
            "xp_per_kill": xp,
            "kill_seconds": round(kill_time, 1),
            "xp_per_hour": round(xp_hr),
            "aggressive": "aggressive" in decode_flags(mob.off_flags, OFF_FLAGS)
                          or "aggressive" in decode_flags(mob.act_flags, ACT_FLAGS),
            "directions": route["commands"] if route else "",
            "rooms_away": route.get("rooms_away") if route else None,
        })

    rows.sort(key=lambda r: r["xp_per_hour"], reverse=True)
    return {
        "level": level,
        "player_dps_estimate": round(player_dps),
        "note": "xp/hour is an estimate (modelled DPS); the ranking does "
                "not depend on it. xp/kill and the band come from fight.c.",
        "mobs": rows[:limit],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(MUD_HOST, MUD_PORT),
            timeout=5,
        )

        # Every web player reaches the game from 127.0.0.1, so without this
        # they are all recorded as "localhost" and all share one entry in the
        # login throttle, which skips loopback for exactly that reason.
        # A PROXY v1 header names the real client; the game accepts it only
        # over loopback, so a direct player cannot forge their address.
        peer = websocket.client.host if websocket.client else ""
        if peer and ":" not in peer:  # IPv4 only; PROXY TCP4 has no v6 form
            header = "PROXY TCP4 {} {} {} {}\r\n".format(
                peer, MUD_HOST, websocket.client.port or 0, MUD_PORT
            )
            writer.write(header.encode("latin-1"))
            await writer.drain()

        await websocket.send_text("\0TOC_CONNECTED")
        
        async def mud_to_ws() -> None:
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    negotiation = telnet_negotiation_responses(data)
                    if negotiation:
                        writer.write(negotiation)
                        await writer.drain()
                    await websocket.send_text(data.decode("latin-1", errors="replace"))
            except (ConnectionError, WebSocketDisconnect):
                pass

        async def ws_to_mud() -> None:
            try:
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        break
                    data = message.get("text")
                    if data is None:
                        await websocket.close(code=1003)
                        break
                    encoded = data.encode("latin-1", errors="replace")
                    if len(encoded) > MAX_GAME_FRAME_BYTES:
                        await websocket.close(code=1009)
                        break
                    writer.write(encoded)
                    await writer.drain()
            except (ConnectionError, WebSocketDisconnect):
                pass

        tasks = [asyncio.create_task(mud_to_ws()), asyncio.create_task(ws_to_mud())]
        _, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except (asyncio.TimeoutError, ConnectionError, OSError):
        try:
            await websocket.send_text("\0TOC_ERROR:Game server is unavailable.")
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
        try:
            await websocket.close()
        except RuntimeError:
            pass
    

if __name__ == "__main__":
    import uvicorn
    
    arg_parser = argparse.ArgumentParser(description="ToC Web Admin Server")
    arg_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    arg_parser.add_argument("--port", type=int, default=WEB_ADMIN_PORT, help="Port to bind to")
    arg_parser.add_argument("--mud-host", default=MUD_HOST, help="Game server host for health and console connections")
    arg_parser.add_argument("--mud-port", type=int, default=MUD_PORT, help="Game server port for health and console connections")
    arg_parser.add_argument("--queue", type=Path, default=QUEUE_PATH, help="Path to command queue file")
    arg_parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG, help="Path to log file")
    arg_parser.add_argument("--event-log-file", type=Path, default=EVENT_LOG, help="Path to server activity file")
    arg_parser.add_argument("--area-path", type=Path, default=AREA_PATH, help="Path to area files")
    arg_parser.add_argument("--backup-path", type=Path, default=BACKUP_PATH, help="Path to backup archive directory")
    arg_parser.add_argument("--player-path", type=Path, default=PLAYER_PATH, help="Path to player save files")
    
    args = arg_parser.parse_args()
    
    # Update globals
    QUEUE_PATH = args.queue
    DEFAULT_LOG = args.log_file
    EVENT_LOG = args.event_log_file
    AREA_PATH = args.area_path
    BACKUP_PATH = args.backup_path
    PLAYER_PATH = args.player_path
    MUD_HOST = args.mud_host
    MUD_PORT = args.mud_port
    WEB_ADMIN_PORT = args.port
    # The unlock gate has to know what was really bound, not what an
    # environment variable guessed.
    set_bind_address(args.host)

    uvicorn.run(app, host=args.host, port=args.port)
