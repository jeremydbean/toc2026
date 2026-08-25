from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import threading
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Shared-secret authentication for operational endpoints. An unset token
# disables those endpoints instead of exposing immortal commands anonymously.
_WEB_ADMIN_TOKEN: str = os.environ.get("WEB_ADMIN_TOKEN", "")
_WEB_ADMIN_BIND: str = os.environ.get("WEB_ADMIN_BIND", "127.0.0.1").strip().lower()
_LOCAL_ADMIN_UNLOCK: bool = (
    os.environ.get("WEB_ADMIN_LOCAL_UNLOCK", "0").strip().lower()
    in {"1", "true", "yes", "on"}
    and _WEB_ADMIN_BIND in {"127.0.0.1", "localhost", "::1"}
)
LOCAL_ADMIN_COOKIE = "toc_admin_session"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def local_admin_session_value() -> str:
    if not _WEB_ADMIN_TOKEN:
        return ""
    return hmac.new(
        _WEB_ADMIN_TOKEN.encode("utf-8"),
        b"toc-local-admin-session-v1",
        hashlib.sha256,
    ).hexdigest()


def loopback_hostname(hostname: Optional[str]) -> bool:
    return bool(hostname and hostname.rstrip(".").lower() in LOOPBACK_HOSTS)


def local_admin_request_allowed(request: Request) -> bool:
    return bool(_WEB_ADMIN_TOKEN) and _LOCAL_ADMIN_UNLOCK and loopback_hostname(request.url.hostname)


def local_admin_websocket_authenticated(websocket: WebSocket) -> bool:
    if not _LOCAL_ADMIN_UNLOCK or not loopback_hostname(websocket.url.hostname):
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
except ImportError:
    from area_health import build_area_health
    from area_parser import AreaParser, APPLY_LOCATIONS
    from area_parser import decode_applies, decode_flags, ITEM_FLAGS, ITEM_FLAGS2, WEAR_FLAGS, ITEM_TYPES, interpret_values, interpret_mob_values, SECTOR_TYPES
    from area_parser import ACT_FLAGS, OFF_FLAGS, IMM_FLAGS, RES_FLAGS, VULN_FLAGS, FORM_FLAGS, PART_FLAGS, AFFECTED_FLAGS, ROOM_FLAGS

# Default paths
QUEUE_PATH: Path = Path(os.getenv("QUEUE_PATH", "area/webadmin.queue"))
DEFAULT_LOG: Path = Path(os.getenv("LOG_FILE", "log/toc.log"))
AREA_PATH: Path = Path(os.getenv("AREA_PATH", "area"))
BACKUP_PATH: Path = Path(os.getenv("BACKUP_PATH", "backups"))
PLAYER_PATH: Path = Path(os.getenv("PLAYER_PATH", "player"))
STATIC_PATH = Path(__file__).resolve().parent / "static"

MUD_HOST = os.getenv("MUD_HOST", "127.0.0.1")
MUD_PORT = int(os.getenv("MUD_PORT", 9000))
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global AREA_HEALTH_CACHE, parser, queue_writer
    queue_writer = QueueWriter(QUEUE_PATH)
    parser = await asyncio.to_thread(load_area_parser, AREA_PATH)
    AREA_MAP_CACHE.clear()
    AREA_HEALTH_CACHE = None
    try:
        yield
    finally:
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


# Class stat weights for gear optimization
# Class-specific stat weights for Best Gear scoring
# Based on code analysis:
# - Hitroll: improves chance to hit (thac0), critical for melee DPS
# - Damroll: adds directly to damage output, critical for melee DPS  
# - STR: gives bonus hit/dam via str_app table (+6 hit, +9 dam at 25 str)
# - DEX: affects thief skills, dodge/parry, AC
# - CON: affects max HP
# - INT: affects mana for mages, learning rate
# - WIS: affects cleric spells, mana
# - HP: raw survivability, important for melee tanks
# - Mana: casting resource, critical for casters

CLASS_WEIGHTS = {
    "mage": {
        # Pure caster: INT and mana are king, some survivability
        "intelligence": 3.0,      # Prime stat, affects spell damage/learning
        "mana": 1.5,              # Casting resource
        "save vs spell": 1.0,     # Resist enemy spells
        "hit points": 0.8,        # Survivability
        "constitution": 0.8,      # More HP
        "wisdom": 0.5,            # Some mana benefit
        "dexterity": 0.3,         # Minimal AC benefit
        "hitroll": 0.2,           # Rarely melee
        "damroll": 0.2,           # Rarely melee
        "strength": 0.1,          # Carry capacity only
    },
    "cleric": {
        # Healer/buffer with some melee capability
        "wisdom": 3.0,            # Prime stat for cleric spells
        "mana": 1.5,              # Casting resource
        "hit points": 1.2,        # Frontline healer needs HP
        "constitution": 1.0,      # Survivability
        "save vs spell": 1.0,     # Resist debuffs
        "hitroll": 1.0,           # Can melee with mace
        "damroll": 1.0,           # Can melee with mace
        "strength": 0.8,          # Bonus to hit/dam
        "intelligence": 0.3,      # Minor mana benefit
        "dexterity": 0.3,         # AC benefit
    },
    "thief": {
        # Melee DPS with DEX focus for backstab/skills
        "dexterity": 3.0,         # Prime stat, affects skills/dodge
        "hitroll": 3.5,           # Critical for backstab to land
        "damroll": 3.5,           # Multiplied by backstab
        "hit points": 1.2,        # Need to survive
        "strength": 1.5,          # Bonus hit/dam
        "constitution": 1.0,      # HP
        "save vs spell": 0.5,     # Some spell resist
        "intelligence": 0.2,      # Minor
        "wisdom": 0.2,            # Minor
        "mana": 0.1,              # Thieves don't cast
    },
    "warrior": {
        # Tank/melee DPS, all about hit/dam and survivability
        "hitroll": 4.0,           # Must hit to deal damage
        "damroll": 4.0,           # Direct damage boost
        "strength": 2.5,          # Bonus hit/dam via str_app
        "hit points": 2.0,        # Tank survivability
        "constitution": 2.0,      # More HP
        "dexterity": 1.0,         # AC, parry
        "save vs spell": 0.5,     # Some magic resist
        "wisdom": 0.1,            # Useless
        "intelligence": 0.1,      # Useless
        "mana": 0.0,              # Warriors don't cast
    },
    "monk": {
        # Unarmed fighter, CON-based, needs survivability
        "constitution": 3.0,      # Prime stat
        "hitroll": 3.5,           # Need to hit
        "damroll": 3.5,           # Unarmed damage
        "hit points": 2.0,        # Survivability
        "strength": 1.5,          # Bonus hit/dam
        "dexterity": 1.5,         # Dodge/AC
        "save vs spell": 0.5,     # Magic resist
        "wisdom": 0.3,            # Minor
        "intelligence": 0.2,      # Minor
        "mana": 0.1,              # Some monk abilities use mana
    },
    "necromancer": {
        # Dark caster with some survivability focus
        "intelligence": 3.0,      # Prime stat
        "mana": 1.5,              # Casting resource
        "hit points": 1.0,        # Survivability (vampiric touch, etc.)
        "constitution": 1.0,      # HP
        "save vs spell": 1.0,     # Resist enemy magic
        "wisdom": 0.5,            # Some mana benefit
        "dexterity": 0.3,         # AC
        "strength": 0.2,          # Minor
        "hitroll": 0.2,           # Rarely melee
        "damroll": 0.2,           # Rarely melee
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


def read_process_health() -> dict[str, bool]:
    """Return runtime reachability without probing the dashboard itself."""
    try:
        with socket.create_connection((MUD_HOST, MUD_PORT), timeout=0.5):
            mud_online = True
    except OSError:
        mud_online = False
    return {
        "merc": mud_online,
        # Serving this request proves the web process is available. Probing a
        # separately configured port gave false negatives for --port launches.
        "webadmin": True,
    }


@app.get("/", response_class=FileResponse, include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_PATH / "index.html")


@app.get("/client", response_class=FileResponse, include_in_schema=False)
@app.get("/client/", response_class=FileResponse, include_in_schema=False)
async def game_client() -> FileResponse:
    return FileResponse(STATIC_PATH / "client.html")


@app.get("/api/health")
async def health() -> dict[str, bool | str]:
    status = await asyncio.to_thread(read_process_health)
    return {"status": "ok", **status}


@app.get("/api/config")
async def get_config(request: Request) -> Dict[str, Any]:
    return {
        "version": app.version,
        "admin_token_configured": bool(_WEB_ADMIN_TOKEN),
        "local_admin_unlock": local_admin_request_allowed(request),
        "mud_endpoint": f"{MUD_HOST}:{MUD_PORT}",
        "client_path": "/client",
        "game_websocket_auth": "same-origin",
        "player_data_protected": True,
        "log_websocket_auth": "cookie-or-first-message",
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


@app.get("/api/auth/check")
async def check_auth(_: None = Depends(verify_token)) -> Dict[str, bool]:
    return {"authenticated": True}


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


@app.get("/api/logs")
async def tail_logs(lines: int = 200, _: None = Depends(verify_token)) -> PlainTextResponse:
    lines = max(1, min(lines, 5000))
    if not DEFAULT_LOG.exists():
        return PlainTextResponse("Log file not found.", status_code=404)
    try:
        return PlainTextResponse(await asyncio.to_thread(tail_log_file, DEFAULT_LOG, lines))
    except OSError:
        return PlainTextResponse("Error reading log file.", status_code=500)


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket) -> None:
    if not websocket_origin_allowed(websocket):
        await websocket.close(code=1008)
        return
    local_session = local_admin_websocket_authenticated(websocket)
    await websocket.accept()
    if not local_session:
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
                return
        except (asyncio.TimeoutError, json.JSONDecodeError, WebSocketDisconnect):
            try:
                await websocket.close(code=4003)
            except RuntimeError:
                pass
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


@app.get("/api/backups")
async def list_backups(_: None = Depends(verify_token)) -> list[Dict[str, Any]]:
    if not BACKUP_PATH.is_dir():
        return []

    backups: list[Dict[str, Any]] = []
    for path in BACKUP_PATH.glob("*.tar.gz"):
        try:
            if not path.is_file():
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
    return backups[:100]


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
    
    # Group by wear location
    best_items = {} # location -> list of (score, item)
    
    for vnum, obj in parser.objects.items():
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
        
        # Calculate score
        score = 0.0
        breakdown = []
        affects_decoded = decode_applies(obj.affects)
        
        for aff in obj.affects:
            loc_id = aff.get('location', 0)
            val = aff.get('modifier', 0)
            loc_name = APPLY_LOCATIONS.get(loc_id, '').lower()
            
            if loc_name in weights:
                w = weights[loc_name]
                s = val * w
                score += s
                breakdown.append(f"{loc_name.title()}: {val} x {w} = {s:.1f}")
            elif loc_name == 'armor class':
                # Negative AC is good in ROM, so multiply by -1 to make it a positive score
                s = val * -1.0
                score += s
                breakdown.append(f"AC: {val} x -1 = {s:.1f}")
        
        # Also check values for weapons (avg damage)
        try:
            item_type_num = int(obj.item_type) if obj.item_type.isdigit() else 0
        except:
            item_type_num = 0
            
        if item_type_num == 5: # Weapon
            # values[1] is dice count, values[2] is dice size
            try:
                d_num = int(obj.values[1])
                d_size = int(obj.values[2])
                avg_dam = d_num * (d_size + 1) / 2.0
                s = avg_dam * 2.0
                score += s # Weight weapon damage highly
                breakdown.append(f"Dmg: {d_num}d{d_size} (avg {avg_dam:.1f}) x 2.0 = {s:.1f}")
            except:
                pass
        
        if score <= 0:
            continue
        
        # Add to best items per slot
        wear_decoded = decode_flags(obj.wear_flags, WEAR_FLAGS)
        for slot in wear_decoded:
            if slot == "take":
                continue
            
            # Filter: Only weapons in wield slot
            if slot == "wield" and item_type_num != 5:
                continue
                
            # Filter: No weapons in armor slots (head, body, etc)
            if item_type_num == 5 and slot not in ["wield", "two-hands"]:
                continue

            if slot not in best_items:
                best_items[slot] = []
            
            best_items[slot].append({
                "score": round(score, 2),
                "score_breakdown": breakdown,
                "vnum": obj.vnum,
                "name": obj.short_desc,
                "level": obj.level,
                "affects": affects_decoded,
                "area": obj.area_name
            })
    
    # Sort and limit
    result = {}
    for slot, items in best_items.items():
        items.sort(key=lambda x: x['score'], reverse=True)
        result[slot] = items[:limit]
        
    return result


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
    arg_parser.add_argument("--area-path", type=Path, default=AREA_PATH, help="Path to area files")
    arg_parser.add_argument("--backup-path", type=Path, default=BACKUP_PATH, help="Path to backup archive directory")
    arg_parser.add_argument("--player-path", type=Path, default=PLAYER_PATH, help="Path to player save files")
    
    args = arg_parser.parse_args()
    
    # Update globals
    QUEUE_PATH = args.queue
    DEFAULT_LOG = args.log_file
    AREA_PATH = args.area_path
    BACKUP_PATH = args.backup_path
    PLAYER_PATH = args.player_path
    MUD_HOST = args.mud_host
    MUD_PORT = args.mud_port
    WEB_ADMIN_PORT = args.port
    
    uvicorn.run(app, host=args.host, port=args.port)
