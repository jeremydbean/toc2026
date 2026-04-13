from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
import asyncio

# Optional shared-secret authentication.
# Set WEB_ADMIN_TOKEN in the environment to require the X-Admin-Token header
# on mutating / sensitive endpoints.  Leave unset (or empty) to allow
# unauthenticated access (backward-compatible default).
_WEB_ADMIN_TOKEN: str = os.environ.get("WEB_ADMIN_TOKEN", "")


async def verify_token(x_admin_token: str = Header(default="")) -> None:
    """FastAPI dependency that enforces the WEB_ADMIN_TOKEN when configured."""
    if _WEB_ADMIN_TOKEN and x_admin_token != _WEB_ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

try:
    from webadmin.area_parser import AreaParser, APPLY_LOCATIONS
    from webadmin.area_parser import decode_applies, decode_flags, ITEM_FLAGS, ITEM_FLAGS2, WEAR_FLAGS, ITEM_TYPES, interpret_values, interpret_mob_values, SECTOR_TYPES
    from webadmin.area_parser import ACT_FLAGS, OFF_FLAGS, IMM_FLAGS, RES_FLAGS, VULN_FLAGS, FORM_FLAGS, PART_FLAGS, AFFECTED_FLAGS, ROOM_FLAGS
except ImportError:
    from area_parser import AreaParser, APPLY_LOCATIONS
    from area_parser import decode_applies, decode_flags, ITEM_FLAGS, ITEM_FLAGS2, WEAR_FLAGS, ITEM_TYPES, interpret_values, interpret_mob_values, SECTOR_TYPES
    from area_parser import ACT_FLAGS, OFF_FLAGS, IMM_FLAGS, RES_FLAGS, VULN_FLAGS, FORM_FLAGS, PART_FLAGS, AFFECTED_FLAGS, ROOM_FLAGS

# Default paths
QUEUE_PATH: Path = Path(os.getenv("QUEUE_PATH", "area/webadmin.queue"))
DEFAULT_LOG: Path = Path(os.getenv("LOG_FILE", "log/toc.log"))
AREA_PATH: Path = Path(os.getenv("AREA_PATH", "area"))

MUD_HOST = "127.0.0.1"
MUD_PORT = int(os.getenv("MUD_PORT", 9000))

# QueueWriter for inter-process communication with the MUD server
class QueueWriter:
    def __init__(self, queue_path: Path) -> None:
        self.queue_path = queue_path
        self.queue_path.touch(exist_ok=True)

    def append(self, line: str) -> None:
        with self.queue_path.open("a", encoding="utf-8") as queue_file:
            queue_file.write(line.rstrip("\n") + "\n")


queue_writer: Optional[QueueWriter] = None


def require_queue_writer() -> QueueWriter:
    if queue_writer is None:
        raise HTTPException(status_code=503, detail="Queue writer is not ready")
    return queue_writer


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global queue_writer
    queue_writer = QueueWriter(QUEUE_PATH)
    yield
    # Shutdown (nothing needed)


app = FastAPI(title="ToC Web Admin", version="1.0", lifespan=lifespan)


class CommandRequest(BaseModel):
    command: str


class WizinfoRequest(BaseModel):
    message: str
    level: Optional[int] = None


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

# Player file constants
PLAYER_PATH: Path = Path(os.getenv("PLAYER_PATH", "player"))

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


def parse_player_file(name: str) -> dict | None:
    """Parse a MUD player file and return a structured dict."""
    cname = name.capitalize()
    # Reject names with path-separator chars or dots to prevent traversal
    if "/" in cname or "\\" in cname or "." in cname:
        return None
    path = PLAYER_PATH / cname
    if not path.exists():
        return None

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


# Initialize parser and load area files
parser = AreaParser(AREA_PATH)
try:
    parser.parse_all()
except Exception as e:
    print(f"Warning: Failed to parse areas: {e}")

AREA_MAP_CACHE: Dict[str, Dict[str, Any]] = {}


def read_process_health() -> dict[str, bool]:
    # Check if services are reachable by probing their ports (works cross-platform)
    import socket

    def _port_open(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            return False

    return {
        "merc": _port_open(MUD_PORT),
        "webadmin": _port_open(int(os.getenv("WEB_ADMIN_PORT", 9001))),
    }


# ============ Frontend - Part 1 ============



@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Times of Chaos - MUD</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#x1F409;</text></svg>">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" />
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Roboto+Mono:wght@400;500&family=Lato:wght@400;700&display=swap');

        :root {
            --primary-color: #4a0404;
            --secondary-color: #1a1a1a;
            --accent-color: #d4af37;
            --text-color: #e0e0e0;
        }

        body {
            background-color: #0a0a0a;
            color: var(--text-color);
            font-family: 'Lato', sans-serif;
        }

        h1, h2, h3 {
            font-family: 'Cinzel', serif;
        }

        .terminal-font {
            font-family: 'Roboto Mono', monospace;
        }

        .hero-pattern {
            background-image: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.8)), url('https://images.unsplash.com/photo-1519074069444-1ba4fff66d16?ixlib=rb-1.2.1&auto=format&fit=crop&w=1920&q=80');
            background-size: cover;
            background-position: center;
        }

        .parchment {
            background-color: #1a1a1a;
            border: 1px solid #333;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }

        .btn-primary {
            background-color: var(--primary-color);
            color: white;
            transition: all 0.3s ease;
        }

        .btn-primary:hover {
            background-color: #6b0606;
            transform: translateY(-2px);
            box-shadow: 0 0 15px rgba(212, 175, 55, 0.3);
        }

        .stat-card {
            background: rgba(20, 20, 20, 0.9);
            border: 1px solid #333;
            transition: transform 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            border-color: var(--accent-color);
        }

        .blinking-cursor::after {
            content: '█';
            animation: blink 1s step-end infinite;
            color: var(--accent-color);
        }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #0f0f0f;
        }
        ::-webkit-scrollbar-thumb {
            background: #333;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #555;
        }
        
        @keyframes hero-blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        .hero-cursor {
            display: inline-block;
            animation: hero-blink 0.75s step-end infinite;
            color: #22c55e;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        .nav-link.active-nav { font-weight: bold; }
        
        /* Toast animation */
        #toast-container > div {
            opacity: 1;
            transform: translateX(0);
            transition: opacity 0.3s ease, transform 0.3s ease;
        }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Navigation -->
    <nav class="bg-black/90 border-b border-red-900/30 fixed w-full z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-20">
                <div class="flex items-center gap-3 cursor-pointer" onclick="showSection('home')">
                    <i class="fa-solid fa-dragon text-3xl text-red-700"></i>
                    <span class="text-2xl font-bold text-white tracking-wider font-cinzel">TIMES OF CHAOS</span>
                </div>
                <div class="hidden md:flex items-center gap-2 font-mono text-xs">
                    <span id="nav-dot" class="h-2 w-2 rounded-full bg-green-500 inline-block transition-colors duration-500"></span>
                    <span id="nav-dot-text" class="text-green-400 transition-colors duration-500">LIVE</span>
                </div>
                <div class="hidden md:block">
                    <div class="ml-10 flex items-baseline space-x-8">
                        <span data-nav="home" onclick="showSection('home')" class="nav-link text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Home</span>
                        <span data-nav="play" onclick="showSection('play')" class="nav-link text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Play Now</span>
                        <span data-nav="database" onclick="showSection('database')" class="nav-link text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Database</span>
                        <span data-nav="guide" onclick="showSection('guide')" class="nav-link text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">How to Play</span>
                        <span data-nav="players" onclick="showSection('players')" class="nav-link text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Players</span>
                        <span data-nav="admin" onclick="showSection('admin')" class="nav-link text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Admin</span>
                        <span data-nav="best-gear" onclick="showBestGear()" class="nav-link px-4 py-2 rounded hover:bg-gray-800 transition-colors text-yellow-500 hover:text-yellow-300 cursor-pointer"><i class="fas fa-khanda mr-2"></i>Best Gear</span>
                    </div>
                </div>
                <div class="md:hidden">
                    <button onclick="toggleMobileMenu()" class="text-gray-300 hover:text-white p-2">
                        <i class="fa-solid fa-bars text-2xl"></i>
                    </button>
                </div>
            </div>
        </div>
        <!-- Mobile Menu -->
        <div id="mobile-menu" class="hidden md:hidden bg-black border-b border-red-900/30">
            <div class="px-2 pt-2 pb-3 space-y-1 sm:px-3">
                <span data-nav="home" onclick="showSection('home')" class="nav-link text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Home</span>
                <span data-nav="play" onclick="showSection('play')" class="nav-link text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Play Now</span>
                <span data-nav="database" onclick="showSection('database')" class="nav-link text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Database</span>
                <span data-nav="guide" onclick="showSection('guide')" class="nav-link text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">How to Play</span>
                <span data-nav="players" onclick="showSection('players')" class="nav-link text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Players</span>
                <span data-nav="admin" onclick="showSection('admin')" class="nav-link text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Admin</span>
                <span data-nav="best-gear" onclick="showBestGear()" class="nav-link text-yellow-500 hover:text-yellow-300 block px-3 py-2 rounded-md text-base font-medium cursor-pointer"><i class="fas fa-khanda mr-2"></i>Best Gear</span>
            </div>
        </div>
    </nav>

    <!-- Main Content Container -->
    <div class="pt-20 flex-grow">
        
        <!-- HOME SECTION -->
        <div id="home-section" class="tab-content active">
            <!-- Hero Section - Terminal Login Aesthetic (art from original ROM greeting) -->
            <section class="hero-pattern relative min-h-screen flex items-center justify-center overflow-hidden">
                <!-- ASCII art filled by JS from #ascii-art-src -->
                <pre id="ascii-hero-art" class="absolute inset-0 text-red-900 select-none pointer-events-none overflow-hidden" style="opacity:0.08;font-size:0.54rem;line-height:1.2;font-family:'Roboto Mono',monospace;padding:7rem 2rem 2rem;z-index:0;white-space:pre;"></pre>
                <!-- CRT scanlines overlay -->
                <div class="absolute inset-0 pointer-events-none" style="background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,0.06) 3px,rgba(0,0,0,0.06) 6px);z-index:1;"></div>
                <div class="absolute inset-0 bg-gradient-to-b from-transparent via-black/40 to-[#0a0a0a]" style="z-index:1;"></div>
                <div class="relative text-center px-4 max-w-4xl mx-auto" style="z-index:2;">
                    <div class="mb-4 font-mono text-red-900/50 text-xs tracking-widest select-none">
                        =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
                    </div>
                    <h1 class="text-5xl md:text-7xl font-bold text-white mb-4 tracking-tight drop-shadow-2xl font-cinzel">
                        TIMES <span class="text-red-600">OF</span> CHAOS
                    </h1>
                    <div class="font-mono text-base mb-3">
                        <span class="text-gray-600">&gt;</span>&nbsp;<span class="text-green-400">By what name do you go by?</span>&nbsp;<span class="hero-cursor">_</span>
                    </div>
                    <p class="text-gray-600 font-mono text-sm mb-10 italic">
                        May your stay here be... Interesting...
                    </p>
                    <div class="flex flex-col sm:flex-row gap-4 justify-center mb-6">
                        <button onclick="showSection('play')" class="btn-primary px-8 py-4 rounded text-lg font-bold flex items-center justify-center gap-2 group font-mono">
                            <i class="fa-solid fa-terminal"></i> CONNECT NOW
                            <i class="fa-solid fa-arrow-right group-hover:translate-x-1 transition-transform"></i>
                        </button>
                        <a href="https://github.com/jeremydbean/toc2026" target="_blank" class="px-8 py-4 rounded border border-gray-700 hover:border-red-800 bg-transparent text-gray-400 hover:text-white text-lg font-bold flex items-center justify-center gap-2 transition-all hover:bg-red-900/10 font-mono">
                            <i class="fa-brands fa-github"></i> VIEW SOURCE
                        </a>
                    </div>
                    <div class="font-mono text-red-900/50 text-xs tracking-widest select-none">
                        =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
                    </div>
                </div>
            </section>
            <!-- ASCII Art data from original ROM login greeting (injected into #ascii-hero-art by JS) -->
            <script id="ascii-art-src" type="text/plain">
                            ==(W{==========-      /===-   _________
                              ||  (.--.)         /===-_---         ------____
                              | \\_,|**|,__      |===--___               __,-'
                 -==\\\\        ` ' `--'   ),    `//=\\\\   ----`---.___.--
             ______-==|        /`\\_.  .__/\\ \\    | |  \\\\           _--`
      ___----   ,-/-==\\\\      (   | .  |----|   | |   `\\        ,'
    _-        /'    |  \\\\     )__/==0==-\\<>/   / /      \\      /
  .'        /       |   \\\\      /-\\___/--\\/  /' /        \\   /'
 /  ____  /         |    \\`\\.__/---   \\  |_/'  /          \\/'
/-'-    --------__  |     --/-         ( )   /'       __---`
                  \\_|      /       __) | ;  ),   __---
                    '----_/      _- /- |/ \\   '- \\
 IMPs:              {\\__--_/}   _/ \\\\_>-|)<__\\     \\       TIMES
 Eclipse            /'   (_/ __-   | |__>--<__|     |        OF
 Gravestone        |  __/) )-      | |__>--<__|     |      CHAOS!
 Soulcrusher       / /  ,_/       / /__>---<__/     |
                 o-o _//        /--_>---<__--   _ /  May your stay here be...
                 (^(-          /-_>---<__-    /      Interesting...
               ( '))          |__>--<__|    /
            ' )) (            \\__>--<__\\    \\
        ,/,'//( (              --<__>--<--   \\
      ,( ( ((, ))               --_->--<_--_/
            </script>

            <!-- Features Grid -->
            <section class="py-16 bg-[#0f0f0f]">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="text-center mb-12">
                        <div class="font-mono text-red-900/40 text-xs mb-3 tracking-widest">=-=-=-=-=-=- FEATURES =-=-=-=-=-=-</div>
                        <h2 class="text-3xl md:text-4xl font-bold text-white mb-3 font-mono tracking-wider">A WORLD OF TEXT</h2>
                        <p class="text-gray-600 max-w-2xl mx-auto font-mono text-sm">ROM architecture &mdash; enhanced for the modern era.</p>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div class="stat-card p-6 rounded-lg">
                            <div class="font-mono text-gray-700 text-xs mb-3 tracking-widest">[ 01 / 03 ]</div>
                            <div class="flex items-center gap-3 mb-3">
                                <div class="w-10 h-10 bg-red-900/20 rounded border border-red-900/30 flex items-center justify-center text-red-500 shrink-0">
                                    <i class="fa-solid fa-skull-crossbones"></i>
                                </div>
                                <h3 class="text-sm font-bold text-white font-mono tracking-wider uppercase">Tactical Combat</h3>
                            </div>
                            <div class="font-mono text-red-900/30 text-xs mb-3">=====================================</div>
                            <p class="text-gray-500 text-xs leading-relaxed font-mono">
                                Real-time combat using THAC0 mechanics. Manage skills, spells, gear weight &mdash; survive legendary mobs.
                            </p>
                        </div>
                        <div class="stat-card p-6 rounded-lg">
                            <div class="font-mono text-gray-700 text-xs mb-3 tracking-widest">[ 02 / 03 ]</div>
                            <div class="flex items-center gap-3 mb-3">
                                <div class="w-10 h-10 bg-blue-900/20 rounded border border-blue-900/30 flex items-center justify-center text-blue-500 shrink-0">
                                    <i class="fa-solid fa-hat-wizard"></i>
                                </div>
                                <h3 class="text-sm font-bold text-white font-mono tracking-wider uppercase">Complex Magic</h3>
                            </div>
                            <div class="font-mono text-red-900/30 text-xs mb-3">=====================================</div>
                            <p class="text-gray-500 text-xs leading-relaxed font-mono">
                                Hundreds of spells across distinct magic schools. From simple heals to room-clearing chaos storms.
                            </p>
                        </div>
                        <div class="stat-card p-6 rounded-lg">
                            <div class="font-mono text-gray-700 text-xs mb-3 tracking-widest">[ 03 / 03 ]</div>
                            <div class="flex items-center gap-3 mb-3">
                                <div class="w-10 h-10 bg-yellow-900/20 rounded border border-yellow-900/30 flex items-center justify-center text-yellow-500 shrink-0">
                                    <i class="fa-solid fa-scroll"></i>
                                </div>
                                <h3 class="text-sm font-bold text-white font-mono tracking-wider uppercase"><span id="hero-area-count">100+</span> Areas</h3>
                            </div>
                            <div class="font-mono text-red-900/30 text-xs mb-3">=====================================</div>
                            <p class="text-gray-500 text-xs leading-relaxed font-mono">
                                Explore thousands of rooms across unique `.are` files. Midgaard, Moria, the Ashen Wastes, and beyond.
                            </p>
                        </div>
                    </div>
                </div>
            </section>
        </div>

        <!-- PLAY SECTION -->
        <div id="play-section" class="tab-content">
            <section class="py-10 bg-[#0a0a0a] min-h-screen">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                        
                        <!-- Terminal Window -->
                        <div class="lg:col-span-2">
                            <div class="parchment p-1 rounded-lg bg-[#111]">
                                <div class="bg-black p-4 rounded border border-gray-800 h-[600px] font-mono text-sm relative" id="terminal-container">
                                    <!-- xterm.js will be injected here -->
                                </div>
                            </div>
                            <div class="mt-4 flex justify-between text-gray-400 text-sm">
                                <div>Status: <span id="connection-status" class="text-gray-500">Not connected</span></div>
                                <div class="flex items-center gap-3">
                                    <span>Host: localhost:9000</span>
                                    <button onclick="if(ws) ws.close(); connectTerminal();" class="text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition-colors"><i class="fas fa-plug mr-1"></i>Reconnect</button>
                                    <button onclick="termFontSize(-1)" class="text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition-colors" title="Decrease font size"><i class="fas fa-minus"></i></button>
                                    <button onclick="termFontSize(1)" class="text-xs px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition-colors" title="Increase font size"><i class="fas fa-plus"></i></button>
                                </div>
                            </div>
                        </div>

                        <!-- Server Details -->
                        <div class="space-y-8">
                            <div>
                                <h2 class="text-3xl font-bold text-white mb-4">Live Server Status</h2>
                                <div class="flex items-center gap-3 mb-6">
                                    <span class="flex h-3 w-3 relative">
                                        <span id="status-ping" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                        <span id="status-dot" class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                    </span>
                                    <span id="status-text" class="text-green-400 font-mono">ONLINE</span>
                                </div>
                                <p class="text-gray-400 mb-6">
                                    Connect directly via Telnet if you prefer a dedicated client like Mudlet or Tintin++.
                                </p>
                            </div>

                            <div class="grid grid-cols-1 gap-4">
                                <div class="bg-[#151515] p-4 rounded border-l-2 border-red-700">
                                    <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Host</div>
                                    <div class="text-white font-mono text-xl">localhost</div>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border-l-2 border-red-700">
                                    <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Port</div>
                                    <div class="text-white font-mono text-xl flex items-center gap-2">
                                        9000 
                                        <button onclick="copyToClipboard('9000')" class="text-xs text-gray-600 hover:text-white"><i class="fa-regular fa-copy"></i></button>
                                    </div>
                                </div>
                            </div>
                        </div>

                    </div>
                </div>
            </section>
        </div>

        <!-- DATABASE SECTION -->
        <div id="database-section" class="tab-content">
            <section class="py-10 bg-[#0a0a0a] min-h-screen">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 class="text-3xl font-bold text-white mb-8 border-b border-gray-800 pb-4">World Database</h2>
                    
                    <!-- Stats Grid -->
                    <div id="db-stats" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        <div class="bg-[#151515] p-4 rounded border border-gray-800 text-center">
                            <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Mobiles</div>
                            <div id="stat-mobs" class="text-2xl font-bold text-red-500">-</div>
                        </div>
                        <div class="bg-[#151515] p-4 rounded border border-gray-800 text-center">
                            <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Objects</div>
                            <div id="stat-objs" class="text-2xl font-bold text-blue-500">-</div>
                        </div>
                        <div class="bg-[#151515] p-4 rounded border border-gray-800 text-center">
                            <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Rooms</div>
                            <div id="stat-rooms" class="text-2xl font-bold text-green-500">-</div>
                        </div>
                        <div class="bg-[#151515] p-4 rounded border border-gray-800 text-center">
                            <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Areas</div>
                            <div id="stat-areas" class="text-2xl font-bold text-yellow-500">-</div>
                        </div>
                    </div>
                    
                    <div class="flex gap-4 mb-8">
                        <button onclick="loadDb('mobs')" class="px-4 py-2 rounded bg-red-900/20 text-red-400 hover:bg-red-900/40 border border-red-900/50 transition-colors">Mobiles</button>
                        <button onclick="loadDb('objects')" class="px-4 py-2 rounded bg-blue-900/20 text-blue-400 hover:bg-blue-900/40 border border-blue-900/50 transition-colors">Objects</button>
                        <button onclick="loadDb('rooms')" class="px-4 py-2 rounded bg-green-900/20 text-green-400 hover:bg-green-900/40 border border-green-900/50 transition-colors">Rooms</button>
                        <button onclick="loadDb('areas')" class="px-4 py-2 rounded bg-yellow-900/20 text-yellow-400 hover:bg-yellow-900/40 border border-yellow-900/50 transition-colors">Areas</button>
                    </div>

                    <div class="flex gap-4 mb-2">
                        <input type="text" id="db-search" placeholder="Search loaded data..." class="flex-1 bg-[#151515] border border-gray-800 rounded px-4 py-3 text-white focus:border-red-700 outline-none" oninput="debouncedFilterDb()">
                        <button onclick="exportCsv()" class="shrink-0 px-4 py-2 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition-colors text-sm flex items-center gap-2" title="Export current results as CSV">
                            <i class="fas fa-download"></i><span class="hidden sm:inline">Export</span>
                        </button>
                    </div>
                    <div id="db-result-count" class="text-xs text-gray-600 font-mono mb-4"></div>

                    <!-- Advanced Filters (Objects Only) -->
                    <div id="obj-filter-container" class="hidden w-full mb-6">
                        <div class="flex justify-end mb-2">
                            <button onclick="toggleFilters(this)" class="px-4 py-2 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-600 transition-colors flex items-center gap-2">
                                <i class="fa-solid fa-filter"></i> Filters
                            </button>
                        </div>
                        
                        <div id="advanced-filters" class="hidden bg-[#151515] p-4 rounded border border-gray-800 grid grid-cols-1 md:grid-cols-3 gap-4">
                            <!-- Type -->
                            <div>
                                <label class="block text-xs text-gray-500 uppercase mb-1">Item Type</label>
                                <select id="filter-type" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-blue-500 outline-none">
                                    <option value="">Any</option>
                                    <option value="weapon">Weapon</option>
                                    <option value="armor">Armor</option>
                                    <option value="light">Light</option>
                                    <option value="container">Container</option>
                                    <option value="drink container">Drink Container</option>
                                    <option value="food">Food</option>
                                    <option value="potion">Potion</option>
                                    <option value="scroll">Scroll</option>
                                    <option value="wand">Wand</option>
                                    <option value="staff">Staff</option>
                                    <option value="pill">Pill</option>
                                    <option value="clothing">Clothing</option>
                                    <option value="money">Money</option>
                                    <option value="boat">Boat</option>
                                    <option value="fountain">Fountain</option>
                                    <option value="portal">Portal</option>
                                    <option value="key">Key</option>
                                    <option value="map">Map</option>
                                    <option value="treasure">Treasure</option>
                                </select>
                            </div>

                            <!-- Wear -->
                            <div>
                                <label class="block text-xs text-gray-500 uppercase mb-1">Wear Location</label>
                                <select id="filter-wear" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-blue-500 outline-none">
                                    <option value="">Any</option>
                                    <option value="take">Take</option>
                                    <option value="finger">Finger</option>
                                    <option value="neck">Neck</option>
                                    <option value="body">Body</option>
                                    <option value="head">Head</option>
                                    <option value="legs">Legs</option>
                                    <option value="feet">Feet</option>
                                    <option value="hands">Hands</option>
                                    <option value="arms">Arms</option>
                                    <option value="shield">Shield</option>
                                    <option value="about">About Body</option>
                                    <option value="waist">Waist</option>
                                    <option value="wrist">Wrist</option>
                                    <option value="wield">Wield</option>
                                    <option value="hold">Hold</option>
                                    <option value="two-hands">Two Hands</option>
                                </select>
                            </div>

                            <!-- Level -->
                            <div>
                                <label class="block text-xs text-gray-500 uppercase mb-1">Level Range</label>
                                <div class="flex gap-2">
                                    <input type="number" id="filter-min-level" placeholder="Min" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-blue-500 outline-none">
                                    <input type="number" id="filter-max-level" placeholder="Max" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-blue-500 outline-none">
                                </div>
                            </div>

                            <!-- Stat Filter -->
                            <div class="md:col-span-3">
                                <label class="block text-xs text-gray-500 uppercase mb-1">Stat Filter (e.g. hitroll>5)</label>
                                <input type="text" id="filter-stat" placeholder="hitroll>5" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-blue-500 outline-none">
                            </div>

                            <!-- Flags -->
                            <div class="md:col-span-3">
                                <label class="block text-xs text-gray-500 uppercase mb-2">Flags</label>
                                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="glow"> Glow
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="hum"> Hum
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="magic"> Magic
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="invis"> Invis
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="nodrop"> NoDrop
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="noremove"> NoRemove
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="anti-good"> Anti-Good
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="anti-evil"> Anti-Evil
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                                        <input type="checkbox" class="filter-flag" value="anti-neutral"> Anti-Neutral
                                    </label>
                                </div>
                            </div>

                            <!-- Apply Button -->
                            <div class="md:col-span-3 flex justify-end gap-2">
                                <button onclick="resetObjectFilters()" class="px-4 py-2 rounded bg-gray-700 text-gray-200 hover:bg-gray-600 font-bold transition-colors">
                                    Reset Filters
                                </button>
                                <button onclick="loadDb('objects', true)" class="px-6 py-2 rounded bg-blue-600 text-white hover:bg-blue-500 font-bold transition-colors">
                                    Apply Filters
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="bg-[#111] rounded border border-gray-800 overflow-hidden">
                        <div class="overflow-x-auto">
                            <table class="w-full text-left text-gray-400">
                                <thead class="bg-[#0a0a0a] text-gray-200 uppercase text-xs font-bold">
                                    <tr id="db-headers">
                                        <!-- Headers injected via JS -->
                                    </tr>
                                </thead>
                                <tbody id="db-content" class="divide-y divide-gray-800">
                                    <tr><td colspan="5" class="p-4 text-center">Select a category to load data</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </section>
        </div>

        <!-- GUIDE SECTION -->
        <div id="guide-section" class="tab-content">
            <section class="py-10 bg-[#0a0a0a] min-h-screen">
                <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 class="text-3xl font-bold text-white mb-8 border-b border-gray-800 pb-4">Adventurer's Guide</h2>
                    
                    <div class="space-y-12">
                        <!-- Introduction -->
                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Welcome to Times of Chaos</h3>
                            <div class="prose prose-invert max-w-none text-gray-300">
                                <p>Times of Chaos is a text-based Multiplayer Online Role-Playing Game (MUD) set in a fantasy world. You will explore vast realms, fight dangerous monsters, solve quests, and grow in power.</p>
                                <p>You can play directly from your browser using the "Play Now" tab, or connect using a dedicated MUD client (like Mudlet or Tintin++) to <strong>localhost:9000</strong>.</p>
                            </div>
                        </div>

                        <!-- Character Creation -->
                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Character Creation</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div>
                                    <h4 class="text-xl font-bold text-white mb-2">Races</h4>
                                    <ul class="space-y-2 text-gray-300">
                                        <li><strong class="text-yellow-500">Human:</strong> Versatile and balanced. No specific weaknesses.</li>
                                        <li><strong class="text-yellow-500">Elf:</strong> Agile and magical. Innate <em>Infrared</em> and <em>Sneak</em>.</li>
                                        <li><strong class="text-yellow-500">Dwarf:</strong> Tough and sturdy. Innate <em>Infrared</em> and <em>Bash</em>.</li>
                                        <li><strong class="text-yellow-500">Hobbit:</strong> Small and stealthy. Innate <em>Hide</em>.</li>
                                        <li><strong class="text-yellow-500">Saurian:</strong> Lizard-like humanoids. Innate <em>Infrared</em>.</li>
                                    </ul>
                                </div>
                                <div>
                                    <h4 class="text-xl font-bold text-white mb-2">Classes</h4>
                                    <ul class="space-y-2 text-gray-300">
                                        <li><strong class="text-blue-400">Warrior:</strong> Masters of weapons and combat. Primary Stat: <strong>Strength</strong>.</li>
                                        <li><strong class="text-blue-400">Mage:</strong> Wielders of arcane magic. Primary Stat: <strong>Intelligence</strong>.</li>
                                        <li><strong class="text-blue-400">Cleric:</strong> Healers and divine casters. Primary Stat: <strong>Wisdom</strong>.</li>
                                        <li><strong class="text-blue-400">Thief:</strong> Experts in stealth and trickery. Primary Stat: <strong>Dexterity</strong>.</li>
                                        <li><strong class="text-blue-400">Monk:</strong> Unarmed fighters and disciplinarians. Primary Stat: <strong>Constitution</strong>.</li>
                                        <li><strong class="text-blue-400">Necromancer:</strong> Masters of death and dark arts. Primary Stat: <strong>Intelligence</strong>.</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <!-- Web Features -->
                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Web Features</h3>
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <h4 class="text-lg font-bold text-white mb-2"><i class="fas fa-map text-green-500 mr-2"></i>Interactive Maps</h4>
                                    <p class="text-sm text-gray-400">In the <strong>Database</strong> section, click "Areas" and then the "Map" button next to any area to view a live, generated map of the zone. You can see room connections, mobs, and objects.</p>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <h4 class="text-lg font-bold text-white mb-2"><i class="fas fa-khanda text-yellow-500 mr-2"></i>Best Gear Finder</h4>
                                    <p class="text-sm text-gray-400">Use the <strong>Best Gear</strong> tool to automatically calculate the best equipment for your class and level. It analyzes item stats and suggests the optimal loadout.</p>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <h4 class="text-lg font-bold text-white mb-2"><i class="fas fa-database text-blue-500 mr-2"></i>Database</h4>
                                    <p class="text-sm text-gray-400">Search the entire game world for Mobs, Objects, and Rooms. Find out where items drop or where specific monsters spawn.</p>
                                </div>
                            </div>
                        </div>

                        <!-- Basic Commands -->
                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Essential Commands</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <h4 class="text-white font-bold mb-2">Movement & Looking</h4>
                                    <ul class="text-sm text-gray-400 space-y-1">
                                        <li><code class="text-yellow-500">north, south, east, west</code> - Move</li>
                                        <li><code class="text-yellow-500">up, down</code> - Change elevation</li>
                                        <li><code class="text-yellow-500">look</code> - See room description</li>
                                        <li><code class="text-yellow-500">exits</code> - See available exits</li>
                                    </ul>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <h4 class="text-white font-bold mb-2">Combat</h4>
                                    <ul class="text-sm text-gray-400 space-y-1">
                                        <li><code class="text-yellow-500">kill &lt;target&gt;</code> - Attack a monster</li>
                                        <li><code class="text-yellow-500">cast '&lt;spell&gt;' &lt;target&gt;</code> - Cast magic</li>
                                        <li><code class="text-yellow-500">flee</code> - Run away from combat</li>
                                        <li><code class="text-yellow-500">consider &lt;target&gt;</code> - Check difficulty</li>
                                    </ul>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <h4 class="text-white font-bold mb-2">Information</h4>
                                    <ul class="text-sm text-gray-400 space-y-1">
                                        <li><code class="text-yellow-500">score</code> - Check stats/exp/hp</li>
                                        <li><code class="text-yellow-500">inventory</code> - Check carried items</li>
                                        <li><code class="text-yellow-500">equipment</code> - Check worn items</li>
                                        <li><code class="text-yellow-500">who</code> - See online players</li>
                                    </ul>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <h4 class="text-white font-bold mb-2">Communication</h4>
                                    <ul class="text-sm text-gray-400 space-y-1">
                                        <li><code class="text-yellow-500">say &lt;message&gt;</code> - Talk to room</li>
                                        <li><code class="text-yellow-500">tell &lt;player&gt; &lt;msg&gt;</code> - Private message</li>
                                        <li><code class="text-yellow-500">gossip &lt;message&gt;</code> - Global chat</li>
                                        <li><code class="text-yellow-500">group</code> - Manage party</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Tips -->
                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Survival Tips</h3>
                            <ul class="list-disc list-inside text-gray-300 space-y-2">
                                <li><strong>Resting:</strong> Type <code class="text-yellow-500">sleep</code> to regenerate Health and Mana faster. Type <code class="text-yellow-500">wake</code> to stand up.</li>
                                <li><strong>Leveling:</strong> Gain experience by killing monsters. When you have enough, find your Guildmaster to <code class="text-yellow-500">train</code> stats and <code class="text-yellow-500">practice</code> skills.</li>
                                <li><strong>Light:</strong> Some areas are dark. Make sure to carry a light source or you won't be able to see!</li>
                                <li><strong>Food & Drink:</strong> Your character gets hungry and thirsty. Buy food at the inn or find a water source.</li>
                            </ul>
                        </div>

                    </div>
                </div>
            </section>
        </div>

        <!-- ADMIN SECTION -->
        <div id="admin-section" class="tab-content">
            <section class="py-10 bg-[#0a0a0a] min-h-screen">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 class="text-3xl font-bold text-white mb-8 border-b border-gray-800 pb-4">Server Administration</h2>

                    <!-- Auth Token -->
                    <div class="bg-[#151515] p-4 rounded border border-yellow-900/20 mb-8 flex items-center gap-4">
                        <i class="fas fa-key text-yellow-700 text-lg shrink-0"></i>
                        <div class="flex-1">
                            <label class="block text-xs text-gray-500 uppercase tracking-wider mb-1">API Token <span class="normal-case text-gray-600">(required if WEB_ADMIN_TOKEN is set)</span></label>
                            <input type="password" id="admin-token" placeholder="Leave blank if not configured"
                                   class="w-full bg-black border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:border-yellow-500 outline-none"
                                oninput="setAdminToken(this.value)">
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                        <!-- WizInfo -->
                        <div class="bg-[#151515] p-6 rounded border border-gray-800">
                            <h3 class="text-xl font-bold text-white mb-4"><i class="fa-solid fa-bullhorn text-red-500 mr-2"></i> Broadcast WizInfo</h3>
                            <form onsubmit="sendWizInfo(event)" class="space-y-4">
                                <div>
                                    <label class="block text-sm text-gray-400 mb-1">Message</label>
                                    <textarea id="wizinfo-msg" rows="3" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-red-500 outline-none" required></textarea>
                                </div>
                                <div>
                                    <label class="block text-sm text-gray-400 mb-1">Min Level</label>
                                    <input type="number" id="wizinfo-level" value="62" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-red-500 outline-none">
                                </div>
                                <button type="submit" class="btn-primary px-4 py-2 rounded font-bold w-full">Send Broadcast</button>
                            </form>
                        </div>

                        <!-- Server Command -->
                        <div class="bg-[#151515] p-6 rounded border border-gray-800">
                            <h3 class="text-xl font-bold text-white mb-4"><i class="fa-solid fa-terminal text-red-500 mr-2"></i> Server Command</h3>
                            <form onsubmit="sendCommand(event)" class="space-y-4">
                                <div>
                                    <label class="block text-sm text-gray-400 mb-1">Command</label>
                                    <input type="text" id="server-cmd" placeholder="e.g. copyover" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-red-500 outline-none" required>
                                </div>
                                <button type="submit" class="px-4 py-2 rounded font-bold w-full bg-red-900 hover:bg-red-800 text-white transition-colors">Execute Command</button>
                            </form>
                            
                            <div class="mt-8 pt-8 border-t border-gray-800">
                                <h4 class="text-white font-bold mb-4">Quick Actions</h4>
                                <div class="flex gap-4 flex-wrap">
                                    <button onclick="action('backup', this)" class="flex-1 px-4 py-2 rounded bg-blue-900/30 text-blue-400 hover:bg-blue-900/50 border border-blue-900 transition-colors">
                                        <i class="fa-solid fa-save mr-2"></i> Backup
                                    </button>
                                    <button onclick="action('reload', this)" class="flex-1 px-4 py-2 rounded bg-green-900/30 text-green-400 hover:bg-green-900/50 border border-green-900 transition-colors">
                                        <i class="fa-solid fa-rotate mr-2"></i> Reload Areas
                                    </button>
                                    <button onclick="action('shutdown', this)" class="flex-1 px-4 py-2 rounded bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-900 transition-colors">
                                        <i class="fa-solid fa-power-off mr-2"></i> Shutdown
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Logs -->
                    <div class="bg-[#151515] rounded border border-gray-800">
                        <div class="p-4 border-b border-gray-800 flex justify-between items-center">
                            <h3 class="text-xl font-bold text-white">Server Logs</h3>
                            <button onclick="refreshLogs()" class="text-sm text-gray-400 hover:text-white"><i class="fa-solid fa-sync mr-1"></i> Refresh</button>
                        </div>
                        <div id="log-terminal" class="bg-black p-4 font-mono text-xs text-green-500 h-96 overflow-y-auto whitespace-pre-wrap">Loading logs...</div>
                    </div>
                </div>
            </section>
        </div>

        <!-- Players Section -->
        <div id="players-section" class="tab-content">
            <section class="py-10 bg-[#0a0a0a] min-h-screen">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 class="text-3xl font-bold text-white mb-8 border-b border-gray-800 pb-4">Player Lookup</h2>

                    <!-- Search bar -->
                    <div class="bg-[#151515] p-6 rounded border border-gray-800 mb-8">
                        <div class="flex gap-3 items-end">
                            <div class="flex-1">
                                <label class="block text-sm text-gray-400 mb-1">Player Name</label>
                                <input id="pl-search" type="text" list="pl-datalist"
                                    placeholder="Type a name..."
                                    class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-red-500 outline-none font-mono"
                                    onkeydown="if(event.key==='Enter') lookupPlayer()">
                                <datalist id="pl-datalist"></datalist>
                            </div>
                            <button id="pl-lookup-btn" onclick="lookupPlayer()" class="px-6 py-2 rounded bg-red-700 hover:bg-red-600 text-white font-bold transition-colors whitespace-nowrap">
                                Look Up
                            </button>
                            <button id="pl-gear-btn" onclick="playerToGear()" class="hidden px-4 py-2 rounded bg-yellow-700 hover:bg-yellow-600 text-black font-bold transition-colors whitespace-nowrap">
                                <i class="fas fa-khanda mr-1"></i>Find Best Gear
                            </button>
                        </div>
                        <div id="pl-error" class="hidden mt-3 text-red-400 text-sm"></div>
                    </div>

                    <!-- Profile display -->
                    <div id="pl-profile" class="hidden">
                        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                            <!-- Left: Score -->
                            <div class="space-y-6">
                                <div class="bg-[#111] rounded border border-gray-800 overflow-hidden">
                                    <div class="bg-[#1a1a1a] px-4 py-2 border-b border-gray-800 font-bold text-red-400 uppercase text-xs tracking-wider font-mono">Score</div>
                                    <div class="p-4 font-mono text-sm space-y-1" id="pl-score-body"></div>
                                </div>
                                <div class="bg-[#111] rounded border border-gray-800 overflow-hidden">
                                    <div class="bg-[#1a1a1a] px-4 py-2 border-b border-gray-800 font-bold text-red-400 uppercase text-xs tracking-wider font-mono">Stats</div>
                                    <div class="p-4 font-mono text-sm" id="pl-stats-body"></div>
                                </div>
                                <div class="bg-[#111] rounded border border-gray-800 overflow-hidden" id="pl-affects-card">
                                    <div class="bg-[#1a1a1a] px-4 py-2 border-b border-gray-800 font-bold text-red-400 uppercase text-xs tracking-wider font-mono">Active Affects</div>
                                    <div class="p-4 font-mono text-sm" id="pl-affects-body"></div>
                                </div>
                            </div>
                            <!-- Right: Look / Equipment -->
                            <div class="space-y-6">
                                <div class="bg-[#111] rounded border border-gray-800 overflow-hidden">
                                    <div class="bg-[#1a1a1a] px-4 py-2 border-b border-gray-800 font-bold text-blue-400 uppercase text-xs tracking-wider font-mono">Look</div>
                                    <div class="p-4 text-gray-300 text-sm italic whitespace-pre-wrap font-serif" id="pl-look-body"></div>
                                </div>
                                <div class="bg-[#111] rounded border border-gray-800 overflow-hidden">
                                    <div class="bg-[#1a1a1a] px-4 py-2 border-b border-gray-800 font-bold text-blue-400 uppercase text-xs tracking-wider font-mono">Equipment</div>
                                    <div class="divide-y divide-gray-800" id="pl-equip-body"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>

        <!-- Best Gear Section -->
        <div id="best-gear-section" class="tab-content">
            <section class="py-10 bg-[#0a0a0a] min-h-screen">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 class="text-3xl font-bold text-white mb-8 border-b border-gray-800 pb-4">Best Gear Finder</h2>

                    <!-- Load from Player row -->
                    <div class="bg-[#151515] p-4 rounded border border-gray-800 mb-4 flex gap-3 items-end">
                        <div class="flex-1">
                            <label class="block text-xs text-gray-500 mb-1">Load settings from player</label>
                            <input id="bg-player-name" type="text" list="bg-player-datalist"
                                placeholder="Type player name..."
                                class="w-full bg-black border border-gray-700 rounded p-2 text-sm text-white focus:border-yellow-500 outline-none font-mono"
                                onkeydown="if(event.key==='Enter') bgLoadFromPlayer()">
                            <datalist id="bg-player-datalist"></datalist>
                        </div>
                        <button id="bg-load-player-btn" onclick="bgLoadFromPlayer()" class="px-4 py-2 rounded bg-gray-700 hover:bg-gray-600 text-white text-sm font-bold transition-colors whitespace-nowrap">
                            Load Player
                        </button>
                        <div id="bg-player-msg" class="text-xs text-gray-500 self-center"></div>
                    </div>
                    
                    <div class="bg-[#151515] p-6 rounded border border-gray-800 mb-8">
                        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                            <div>
                                <label class="block text-sm text-gray-400 mb-1">Class</label>
                                <select id="bg-class" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-yellow-500 outline-none">
                                    <option value="mage">Mage</option>
                                    <option value="cleric">Cleric</option>
                                    <option value="thief">Thief</option>
                                    <option value="warrior">Warrior</option>
                                    <option value="monk">Monk</option>
                                    <option value="necromancer">Necromancer</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm text-gray-400 mb-1">Race</label>
                                <select id="bg-race" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-yellow-500 outline-none">
                                    <option value="human">Human</option>
                                    <option value="elf">Elf</option>
                                    <option value="dwarf">Dwarf</option>
                                    <option value="hobbit">Hobbit</option>
                                    <option value="saurian">Saurian</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm text-gray-400 mb-1">Max Level</label>
                                <input type="number" id="bg-level" value="50" class="w-full bg-black border border-gray-700 rounded p-2 text-white focus:border-yellow-500 outline-none" onkeydown="if(event.key==='Enter') loadBestGear()">
                            </div>
                            <button id="bg-load-gear-btn" onclick="loadBestGear()" class="px-4 py-2 rounded bg-yellow-600 hover:bg-yellow-500 text-black font-bold transition-colors">
                                Find Gear
                            </button>
                        </div>
                    </div>

                    <div id="bg-results" class="space-y-8">
                        <div class="text-center text-gray-500 py-12">Select options and click Find Gear</div>
                    </div>
                </div>
            </section>
        </div>

        <!-- Room Detail Modal -->
        <div id="room-modal" class="fixed inset-0 bg-black/80 hidden z-50 flex items-center justify-center p-4">
            <div class="bg-[#1a1a1a] border border-gray-700 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
                <div class="p-6">
                    <div class="flex justify-between items-start mb-6 border-b border-gray-800 pb-4">
                        <div>
                            <h3 id="room-modal-title" class="text-2xl font-bold text-white font-cinzel">Room Name</h3>
                            <div class="text-gray-500 font-mono text-sm mt-1 flex items-center gap-2">Vnum: <span id="room-modal-vnum" class="text-gray-300">#1234</span><button onclick="copyToClipboard(document.getElementById('room-modal-vnum').textContent.replace('#',''))" class="text-gray-600 hover:text-white transition-colors" title="Copy vnum"><i class="fa-regular fa-copy text-xs"></i></button></div>
                        </div>
                        <button onclick="closeRoomModal()" class="text-gray-400 hover:text-white">
                            <i class="fa-solid fa-times text-xl"></i>
                        </button>
                    </div>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <!-- Main Info -->
                        <div class="lg:col-span-2 space-y-6">
                            <div>
                                <h4 class="text-red-400 font-bold mb-2 uppercase text-xs tracking-wider">Description</h4>
                                <p id="room-modal-desc" class="text-gray-300 leading-relaxed whitespace-pre-wrap font-serif"></p>
                            </div>
                            
                            <div>
                                <h4 class="text-red-400 font-bold mb-2 uppercase text-xs tracking-wider">Exits</h4>
                                <div id="room-modal-exits" class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                                    <!-- Exits injected here -->
                                </div>
                            </div>

                            <div>
                                <h4 class="text-red-400 font-bold mb-2 uppercase text-xs tracking-wider">Extra Descriptions</h4>
                                <div id="room-modal-extras" class="space-y-2">
                                    <!-- Extras injected here -->
                                </div>
                            </div>
                        </div>
                        
                        <!-- Sidebar -->
                        <div class="space-y-6">
                            <div class="bg-[#111] p-4 rounded border border-gray-800">
                                <h4 class="text-blue-400 font-bold mb-3 uppercase text-xs tracking-wider">Contents</h4>
                                
                                <div class="mb-4">
                                    <div class="text-xs text-gray-500 mb-1">Mobiles</div>
                                    <ul id="room-modal-mobs" class="space-y-1 text-sm">
                                        <!-- Mobs injected here -->
                                    </ul>
                                </div>
                                
                                <div>
                                    <div class="text-xs text-gray-500 mb-1">Objects</div>
                                    <ul id="room-modal-objects" class="space-y-1 text-sm">
                                        <!-- Objects injected here -->
                                    </ul>
                                </div>
                            </div>

                            <div class="bg-[#111] p-4 rounded border border-gray-800">
                                <h4 class="text-yellow-400 font-bold mb-3 uppercase text-xs tracking-wider">Details</h4>
                                <div class="space-y-2 text-sm">
                                    <div class="flex justify-between">
                                        <span class="text-gray-500">Area:</span>
                                        <span id="room-modal-area" class="text-gray-300 text-right"></span>
                                    </div>
                                    <div class="flex justify-between">
                                        <span class="text-gray-500">Sector:</span>
                                        <span id="room-modal-sector" class="text-gray-300 text-right"></span>
                                    </div>
                                    <div class="flex justify-between">
                                        <span class="text-gray-500">Flags:</span>
                                        <span id="room-modal-flags" class="text-gray-300 text-right"></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Mob Detail Modal -->
        <div id="mob-modal" class="fixed inset-0 bg-black/80 hidden z-50 flex items-center justify-center p-4">
            <div class="bg-[#1a1a1a] border border-gray-700 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
                <div class="p-6">
                    <div class="flex justify-between items-start mb-6 border-b border-gray-800 pb-4">
                        <div>
                            <h3 id="mob-modal-title" class="text-2xl font-bold text-white font-cinzel">Mob Name</h3>
                            <div class="text-gray-500 font-mono text-sm mt-1 flex items-center gap-2">Vnum: <span id="mob-modal-vnum" class="text-gray-300">#1234</span><button onclick="copyToClipboard(document.getElementById('mob-modal-vnum').textContent.replace('#',''))" class="text-gray-600 hover:text-white transition-colors" title="Copy vnum"><i class="fa-regular fa-copy text-xs"></i></button></div>
                        </div>
                        <button onclick="closeMobModal()" class="text-gray-400 hover:text-white">
                            <i class="fa-solid fa-times text-xl"></i>
                        </button>
                    </div>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <!-- Main Info -->
                        <div class="lg:col-span-2 space-y-6">
                            <div>
                                <h4 class="text-red-400 font-bold mb-2 uppercase text-xs tracking-wider">Description</h4>
                                <p id="mob-modal-desc" class="text-gray-300 leading-relaxed whitespace-pre-wrap font-serif"></p>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <h4 class="text-red-400 font-bold mb-2 uppercase text-xs tracking-wider">Combat</h4>
                                    <div class="bg-[#111] p-3 rounded border border-gray-800 text-sm space-y-1">
                                        <div class="flex justify-between"><span class="text-gray-500">Level:</span> <span id="mob-modal-level" class="text-yellow-400"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Hitroll:</span> <span id="mob-modal-hitroll" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Hit Dice:</span> <span id="mob-modal-hitdice" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Mana Dice:</span> <span id="mob-modal-manadice" class="text-blue-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Dam Dice:</span> <span id="mob-modal-damdice" class="text-red-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Dam Type:</span> <span id="mob-modal-damtype" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">AC:</span> <span id="mob-modal-ac" class="text-cyan-300"></span></div>
                                    </div>
                                </div>
                                <div>
                                    <h4 class="text-red-400 font-bold mb-2 uppercase text-xs tracking-wider">Details</h4>
                                    <div class="bg-[#111] p-3 rounded border border-gray-800 text-sm space-y-1">
                                        <div class="flex justify-between"><span class="text-gray-500">Race:</span> <span id="mob-modal-race" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Sex:</span> <span id="mob-modal-sex" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Size:</span> <span id="mob-modal-size" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Align:</span> <span id="mob-modal-align" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Wealth:</span> <span id="mob-modal-wealth" class="text-yellow-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Material:</span> <span id="mob-modal-material" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Start Pos:</span> <span id="mob-modal-startpos" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Def Pos:</span> <span id="mob-modal-defpos" class="text-gray-300"></span></div>
                                    </div>
                                </div>
                            </div>

                            <div>
                                <h4 class="text-red-400 font-bold mb-2 uppercase text-xs tracking-wider">Flags</h4>
                                <div class="space-y-2 text-sm">
                                    <div id="mob-modal-act" class="text-gray-400"><span class="text-purple-400 font-bold">ACT:</span> <span></span></div>
                                    <div id="mob-modal-off" class="text-gray-400"><span class="text-red-400 font-bold">OFF:</span> <span></span></div>
                                    <div id="mob-modal-aff" class="text-gray-400"><span class="text-green-400 font-bold">AFF:</span> <span></span></div>
                                    <div id="mob-modal-imm" class="text-gray-400"><span class="text-blue-400 font-bold">IMM:</span> <span></span></div>
                                    <div id="mob-modal-res" class="text-gray-400"><span class="text-cyan-400 font-bold">RES:</span> <span></span></div>
                                    <div id="mob-modal-vuln" class="text-gray-400"><span class="text-orange-400 font-bold">VULN:</span> <span></span></div>
                                    <div id="mob-modal-form" class="text-gray-400"><span class="text-gray-400 font-bold">FORM:</span> <span></span></div>
                                    <div id="mob-modal-parts" class="text-gray-400"><span class="text-gray-400 font-bold">PARTS:</span> <span></span></div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Sidebar -->
                        <div class="space-y-6">
                            <div class="bg-[#111] p-4 rounded border border-gray-800">
                                <h4 class="text-yellow-400 font-bold mb-3 uppercase text-xs tracking-wider">Drops</h4>
                                <ul id="mob-modal-drops" class="space-y-2 text-sm">
                                    <!-- Drops injected here -->
                                </ul>
                            </div>

                            <div class="bg-[#111] p-4 rounded border border-gray-800">
                                <h4 class="text-blue-400 font-bold mb-3 uppercase text-xs tracking-wider">Spawn Locations</h4>
                                <div class="text-xs text-gray-500 mb-2">Rooms where this mob loads:</div>
                                <ul id="mob-modal-spawns" class="space-y-1 text-sm max-h-60 overflow-y-auto">
                                    <!-- Spawns injected here -->
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Object Detail Modal -->
        <div id="obj-modal" class="fixed inset-0 bg-black/80 hidden z-50 flex items-center justify-center p-4">
            <div class="bg-[#1a1a1a] border border-gray-700 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
                <div class="p-6">
                    <div class="flex justify-between items-start mb-6 border-b border-gray-800 pb-4">
                        <div>
                            <h3 id="obj-modal-title" class="text-2xl font-bold text-white font-cinzel">Object Name</h3>
                            <div class="text-gray-500 font-mono text-sm mt-1 flex items-center gap-2">Vnum: <span id="obj-modal-vnum" class="text-gray-300">#1234</span><button onclick="copyToClipboard(document.getElementById('obj-modal-vnum').textContent.replace('#',''))" class="text-gray-600 hover:text-white transition-colors" title="Copy vnum"><i class="fa-regular fa-copy text-xs"></i></button></div>
                        </div>
                        <button onclick="closeObjModal()" class="text-gray-400 hover:text-white">
                            <i class="fa-solid fa-times text-xl"></i>
                        </button>
                    </div>
                    
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <!-- Main Info -->
                        <div class="lg:col-span-2 space-y-6">
                            <div>
                                <h4 class="text-blue-400 font-bold mb-2 uppercase text-xs tracking-wider">Description</h4>
                                <p id="obj-modal-desc" class="text-gray-300 leading-relaxed whitespace-pre-wrap font-serif"></p>
                            </div>
                            
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <h4 class="text-blue-400 font-bold mb-2 uppercase text-xs tracking-wider">Stats</h4>
                                    <div class="bg-[#111] p-3 rounded border border-gray-800 text-sm space-y-1">
                                        <div class="flex justify-between"><span class="text-gray-500">Type:</span> <span id="obj-modal-type" class="text-blue-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Level:</span> <span id="obj-modal-level" class="text-yellow-400"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Weight:</span> <span id="obj-modal-weight" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Cost:</span> <span id="obj-modal-cost" class="text-yellow-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Material:</span> <span id="obj-modal-material" class="text-gray-300"></span></div>
                                        <div class="flex justify-between"><span class="text-gray-500">Condition:</span> <span id="obj-modal-condition" class="text-gray-300"></span></div>
                                    </div>
                                </div>
                                <div>
                                    <h4 class="text-blue-400 font-bold mb-2 uppercase text-xs tracking-wider">Affects</h4>
                                    <ul id="obj-modal-affects" class="bg-[#111] p-3 rounded border border-gray-800 text-sm space-y-1 min-h-[100px]">
                                        <!-- Affects injected here -->
                                    </ul>
                                </div>
                            </div>

                            <div>
                                <h4 class="text-blue-400 font-bold mb-2 uppercase text-xs tracking-wider">Flags</h4>
                                <div class="space-y-2 text-sm">
                                    <div id="obj-modal-extra" class="text-gray-400"><span class="text-purple-400 font-bold">EXTRA:</span> <span></span></div>
                                    <div id="obj-modal-wear" class="text-gray-400"><span class="text-blue-400 font-bold">WEAR:</span> <span></span></div>
                                </div>
                            </div>
                            
                            <div>
                                <h4 class="text-blue-400 font-bold mb-2 uppercase text-xs tracking-wider">Values</h4>
                                <div id="obj-modal-values" class="bg-[#111] p-3 rounded border border-gray-800 text-sm">
                                    <!-- Values injected here -->
                                </div>
                            </div>
                        </div>
                        
                        <!-- Sidebar -->
                        <div class="space-y-6">
                            <div class="bg-[#111] p-4 rounded border border-gray-800">
                                <h4 class="text-yellow-400 font-bold mb-3 uppercase text-xs tracking-wider">Carried By</h4>
                                <div class="text-xs text-gray-500 mb-2">Mobs that load this item:</div>
                                <ul id="obj-modal-carried" class="space-y-2 text-sm max-h-60 overflow-y-auto">
                                    <!-- Carried by injected here -->
                                </ul>
                            </div>

                            <div class="bg-[#111] p-4 rounded border border-gray-800">
                                <h4 class="text-green-400 font-bold mb-3 uppercase text-xs tracking-wider">Extra Descriptions</h4>
                                <div id="obj-modal-extras" class="space-y-2 text-sm">
                                    <!-- Extras injected here -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Area Map Modal -->
        <div id="map-modal" class="fixed inset-0 bg-black/90 hidden z-50 flex items-center justify-center p-4">
            <div class="bg-[#0a0a0a] border border-gray-700 rounded-lg w-full h-full max-w-[95vw] max-h-[95vh] overflow-hidden shadow-2xl flex flex-col">
                <div class="p-4 border-b border-gray-800 flex justify-between items-center shrink-0">
                    <div>
                        <h3 id="map-modal-title" class="text-xl font-bold text-white font-cinzel">Area Map</h3>
                        <div class="text-gray-500 text-sm mt-1"><span id="map-modal-rooms">0</span> rooms</div>
                    </div>
                    <div class="flex items-center gap-4">
                        <div class="flex items-center gap-2 text-sm text-gray-400">
                            <span>Zoom:</span>
                            <button onclick="mapZoom(-0.2)" class="px-2 py-1 bg-gray-800 rounded hover:bg-gray-700">-</button>
                            <span id="map-zoom-level">100%</span>
                            <button onclick="mapZoom(0.2)" class="px-2 py-1 bg-gray-800 rounded hover:bg-gray-700">+</button>
                            <button onclick="mapZoom(0, true)" class="px-2 py-1 bg-gray-800 rounded hover:bg-gray-700 ml-2">Reset</button>
                        </div>
                        <button onclick="closeMapModal()" class="text-gray-400 hover:text-white">
                            <i class="fa-solid fa-times text-xl"></i>
                        </button>
                    </div>
                </div>
                
                <div id="map-container" class="flex-1 overflow-auto relative bg-[#050505]" style="cursor: grab;">
                    <svg id="map-svg" class="absolute" style="min-width: 100%; min-height: 100%;"></svg>
                </div>
                
                <!-- Legend -->
                <div class="p-2 border-t border-gray-800 flex flex-wrap gap-4 text-xs text-gray-400 shrink-0 bg-[#0a0a0a]">
                    <span class="font-bold text-gray-300">Legend:</span>
                    <span><span class="inline-block w-4 h-0.5 bg-gray-500 mr-1 align-middle"></span> N/S/E/W</span>
                    <span><span class="inline-block w-4 h-0.5 bg-[#4477aa] mr-1 align-middle" style="border-bottom: 2px dashed #4477aa; background: transparent;"></span> Up</span>
                    <span><span class="inline-block w-4 h-0.5 bg-[#aa5544] mr-1 align-middle" style="border-bottom: 2px dashed #aa5544; background: transparent;"></span> Down</span>
                    <span><span class="inline-block w-4 h-0.5 bg-[#7a7] mr-1 align-middle" style="border-bottom: 2px dashed #7a7; background: transparent;"></span> Special (climb, enter, etc)</span>
                    <span class="ml-4"><span class="inline-block w-3 h-3 bg-[#2a1a1a] border border-[#633] rounded mr-1 align-middle"></span> Has Mobs</span>
                    <span><span class="inline-block w-3 h-3 bg-[#1a1a2a] border border-[#336] rounded mr-1 align-middle"></span> Has Objects</span>
                    <span><span class="inline-block w-3 h-3 bg-[#2a1a2a] border border-[#636] rounded mr-1 align-middle"></span> Both</span>
                </div>
                
                <!-- Room tooltip -->
                <div id="map-tooltip" class="fixed hidden bg-[#1a1a1a] border border-gray-600 rounded-lg p-3 shadow-xl z-[60] max-w-xs pointer-events-none">
                    <div id="map-tooltip-name" class="font-bold text-white text-sm"></div>
                    <div id="map-tooltip-vnum" class="text-gray-500 text-xs font-mono mb-2"></div>
                    <div id="map-tooltip-desc" class="text-gray-400 text-xs line-clamp-3 mb-2"></div>
                    <div id="map-tooltip-exits" class="text-green-400 text-xs mb-1"></div>
                    <div id="map-tooltip-mobs" class="text-yellow-400 text-xs"></div>
                    <div id="map-tooltip-objects" class="text-blue-400 text-xs"></div>
                    <div class="text-gray-600 text-[10px] mt-2 italic">Click to view details</div>
                </div>
            </div>
        </div>

    </div>

    <!-- Footer -->
    <!-- Toast container -->
    <div id="toast-container" class="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 pointer-events-none"></div>

    <!-- Score Breakdown Modal -->
    <div id="score-modal" class="fixed inset-0 bg-black/80 hidden z-[150] flex items-center justify-center p-4">
        <div class="bg-[#1a1a1a] border border-gray-700 rounded-lg max-w-md w-full shadow-2xl">
            <div class="p-4 border-b border-gray-800 flex justify-between items-center">
                <h3 class="text-lg font-bold text-yellow-400 font-cinzel">Score Breakdown</h3>
                <button onclick="closeScoreModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-times text-xl"></i></button>
            </div>
            <div id="score-modal-content" class="p-4 font-mono text-sm text-gray-300 space-y-1 max-h-96 overflow-y-auto">
            </div>
        </div>
    </div>

    <footer class="bg-black border-t border-gray-900 py-12">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-6">
            <div class="text-gray-500 text-sm">
                &copy; 2026 Times of Chaos. Based on Merc/ROM Codebase.
            </div>
            <div class="flex gap-6">
                <a href="#" class="text-gray-500 hover:text-white"><i class="fa-brands fa-discord text-xl"></i></a>
                <a href="https://github.com/jeremydbean/toc2026" target="_blank" class="text-gray-500 hover:text-white"><i class="fa-brands fa-github text-xl"></i></a>
            </div>
        </div>
    </footer>

    <script>
        // ============ HELPERS ============
        function escHtml(str) {
            if (str == null) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function showToast(msg, type = 'info') {
            const colors = { success: 'bg-green-900 border-green-700', error: 'bg-red-900 border-red-700', info: 'bg-gray-800 border-gray-600', warning: 'bg-yellow-900 border-yellow-700' };
            const icons = { success: 'fa-check-circle text-green-400', error: 'fa-exclamation-circle text-red-400', info: 'fa-info-circle text-blue-400', warning: 'fa-exclamation-triangle text-yellow-400' };
            const toast = document.createElement('div');
            toast.className = `${colors[type] || colors.info} border text-white text-sm px-4 py-3 rounded shadow-2xl flex items-start gap-3 pointer-events-auto max-w-sm transition-all duration-300`;
            toast.innerHTML = `<i class="fas ${icons[type] || icons.info} mt-0.5 shrink-0"></i><span>${escHtml(msg)}</span>`;
            const container = document.getElementById('toast-container');
            container.appendChild(toast);
            // Animate in
            requestAnimationFrame(() => { toast.style.opacity = '1'; });
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }, 4500);
        }

        // ============ NAVIGATION ============
        
        // Global Escape key handler for modals
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                document.getElementById('room-modal').classList.add('hidden');
                document.getElementById('mob-modal').classList.add('hidden');
                document.getElementById('obj-modal').classList.add('hidden');
                document.getElementById('map-modal').classList.add('hidden');
                document.getElementById('score-modal').classList.add('hidden');
            }
        });

        function isTypingTarget(el) {
            if (!el) return false;
            const tag = (el.tagName || '').toLowerCase();
            return tag === 'input' || tag === 'textarea' || tag === 'select' || el.isContentEditable;
        }

        // Keyboard shortcuts:
        // - / focuses DB search
        // - Cmd/Ctrl+K also focuses DB search
        document.addEventListener('keydown', function(e) {
            if (isTypingTarget(e.target)) return;

            if (e.key === '/') {
                e.preventDefault();
                showSection('database');
                const dbSearch = document.getElementById('db-search');
                if (dbSearch) {
                    dbSearch.focus();
                    dbSearch.select();
                }
                return;
            }

            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                showSection('database');
                const dbSearch = document.getElementById('db-search');
                if (dbSearch) {
                    dbSearch.focus();
                    dbSearch.select();
                }
            }
        });
        
        function showSection(id, updateHash = true) {
            try {
                const validSections = ['home', 'play', 'database', 'guide', 'players', 'admin', 'best-gear'];
                if (!validSections.includes(id)) {
                    id = 'home';
                }

                if (id !== 'play') stopTerminal();
                if (id !== 'admin') stopLogs();

                document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                const targetSection = document.getElementById(id + '-section');
                if(targetSection) {
                    targetSection.classList.add('active');
                } else {
                    console.error("Section not found:", id + '-section');
                }
                
                // Update active nav link
                document.querySelectorAll('.nav-link[data-nav]').forEach(el => {
                    el.classList.remove('text-red-500', 'text-yellow-300');
                    el.style.fontWeight = 'normal';
                    if (el.dataset.nav === 'best-gear') {
                        el.classList.add('text-yellow-500');
                    } else {
                        el.classList.add('text-gray-300');
                    }
                });
                const activeLink = document.querySelector(`.nav-link[data-nav="${id}"]`);
                if (activeLink) {
                    activeLink.classList.remove('text-gray-300', 'text-yellow-500');
                    activeLink.classList.add(id === 'best-gear' ? 'text-yellow-300' : 'text-red-500');
                    activeLink.style.fontWeight = 'bold';
                }
                
                // Close mobile menu if open
                const mobileMenu = document.getElementById('mobile-menu');
                if(mobileMenu) {
                    mobileMenu.classList.add('hidden');
                }

                window.scrollTo(0, 0);
                if(id === 'play') initTerminal();
                if(id === 'database' && !dbData.mobs.length) loadDb('mobs');
                if(id === 'players') initPlayerList();
                if(id === 'best-gear') initPlayerList();
                if(id === 'admin') {
                    refreshLogs();
                    const tokenInput = document.getElementById('admin-token');
                    if(tokenInput) tokenInput.value = localStorage.getItem('toc_admin_token') || '';
                }

                localStorage.setItem('toc_last_section', id);
                if (updateHash) {
                    const targetHash = '#section/' + id;
                    if (location.hash !== targetHash) {
                        location.hash = targetHash;
                    }
                }
            } catch(e) {
                console.error("Error in showSection:", e);
            }
        }

        function toggleMobileMenu() {
            const menu = document.getElementById('mobile-menu');
            menu.classList.toggle('hidden');
        }

        function copyToClipboard(text) {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(() => {
                    showToast('Copied to clipboard!', 'success');
                }).catch(() => {
                    showToast('Copy failed — try manual copy.', 'error');
                });
            } else {
                // Fallback for non-HTTPS
                const el = document.createElement('textarea');
                el.value = text;
                el.style.position = 'fixed';
                el.style.opacity = '0';
                document.body.appendChild(el);
                el.select();
                try { document.execCommand('copy'); showToast('Copied to clipboard!', 'success'); }
                catch(e) { showToast('Copy failed — try manual copy.', 'error'); }
                document.body.removeChild(el);
            }
        }

        function getPreferredFontSize() {
            const raw = parseInt(localStorage.getItem('toc_term_font_size') || '12', 10);
            if (Number.isNaN(raw)) return 12;
            return Math.max(8, Math.min(24, raw));
        }

        let _adminTokenRefreshTimer = null;
        function setAdminToken(token) {
            localStorage.setItem('toc_admin_token', token || '');
            const adminActive = document.getElementById('admin-section')?.classList.contains('active');
            if (adminActive) {
                clearTimeout(_adminTokenRefreshTimer);
                _adminTokenRefreshTimer = setTimeout(() => refreshLogs(), 300);
            }
        }

        function setButtonLoading(btn, loading, loadingLabel) {
            if (!btn) return;
            if (loading) {
                if (!btn.dataset.origLabel) btn.dataset.origLabel = btn.innerHTML;
                btn.disabled = true;
                btn.classList.add('opacity-70', 'cursor-not-allowed');
                btn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i>${escHtml(loadingLabel || 'Loading...')}`;
            } else {
                btn.disabled = false;
                btn.classList.remove('opacity-70', 'cursor-not-allowed');
                if (btn.dataset.origLabel) btn.innerHTML = btn.dataset.origLabel;
            }
        }

        // ============ TERMINAL / WEBSOCKET ============
        let ws = null;
        let term = null;
        let fitAddon = null;
        let termInitialized = false;
        let termShouldReconnect = false;
        let localEcho = true;

        function stopTerminal() {
            termShouldReconnect = false;
            if (ws) {
                ws.onclose = null;
                ws.close();
                ws = null;
            }
            const status = document.getElementById('connection-status');
            if (status) {
                status.textContent = 'Disconnected';
                status.className = 'text-red-500';
            }
        }

        function connectTerminal() {
            if (!term || !termShouldReconnect) return;
            if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

            const status = document.getElementById('connection-status');
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(protocol + '//' + window.location.host + '/ws');

            ws.onopen = () => {
                if (status) {
                    status.textContent = 'Connected';
                    status.className = 'text-green-500';
                }
                term.writeln('\x1b[32mConnected to server.\x1b[0m');
            };

            ws.onmessage = (event) => {
                let data = event.data;
                const wasEcho = localEcho;

                // Telnet Negotiation for Echo - detect BEFORE stripping
                // IAC WILL ECHO (255 251 1) -> Server handles echo, turn local echo OFF
                const iacWillEcho = String.fromCharCode(255, 251, 1);
                if (data.includes(iacWillEcho)) localEcho = false;

                // IAC WONT ECHO (255 252 1) -> Server won't echo, turn local echo ON
                const iacWontEcho = String.fromCharCode(255, 252, 1);
                if (data.includes(iacWontEcho)) localEcho = true;

                // Strip all 3-byte telnet options (IAC+type+option), 2-byte commands,
                // and lone IAC bytes so control sequences never appear in the terminal.
                data = data.replace(/\xff[\xfb-\xfe]./gs, '');
                data = data.replace(/\xff[\xf0-\xfa]/g, '');
                data = data.replace(/\xff/g, '');

                // When entering password mode, ensure prompt is on its own line
                if (wasEcho && !localEcho) {
                    term.write('\\r\\n');
                }

                term.write(data);
            };

            ws.onclose = () => {
                ws = null;
                if (!termShouldReconnect) return;
                if (status) {
                    status.textContent = 'Disconnected';
                    status.className = 'text-red-500';
                }
                term.writeln('\x1b[31mConnection lost. Reconnecting in 3s...\x1b[0m');
                setTimeout(() => {
                    if (termShouldReconnect) connectTerminal();
                }, 3000);
            };

            ws.onerror = (err) => {
                console.error('WebSocket error:', err);
                if (ws) ws.close();
            };
        }

        function initTerminal() {
            termShouldReconnect = true;
            if(termInitialized) {
                connectTerminal();
                return;
            }
            termInitialized = true;

            const container = document.getElementById('terminal-container');
            const status = document.getElementById('connection-status');

            // Initialize xterm.js
            term = new Terminal({
                cursorBlink: true,
                fontFamily: '"Roboto Mono", monospace',
                fontSize: getPreferredFontSize(),
                theme: {
                    background: '#000000',
                    foreground: '#e0e0e0',
                    cursor: '#00ff00'
                },
                convertEol: false,
                lineHeight: 1.0
            });
            
            fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(container);
            fitAddon.fit();
            
            // Handle resize
            window.addEventListener('resize', () => fitAddon.fit());

            // Handle input
            term.onData(data => {
                // Normalize all line endings to \\n before sending to MUD
                let sendData = data.replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n');

                if (localEcho) {
                    // For Enter key (CR=\\r): echo CR+LF so the cursor advances to the next line.
                    // Without LF the cursor returns to column 0 on the SAME line, causing
                    // subsequent MUD output (like "Password: ") to overwrite the typed username.
                    term.write(data === '\\r' ? '\\r\\n' : data);
                }
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(sendData);
                } else {
                    console.error('WebSocket not ready:', ws ? ws.readyState : 'null');
                }
            });

            connectTerminal();
        }

        // ============ DATABASE ============
        let currentDb = 'mobs';
        let dbData = { mobs: [], objects: [], areas: [] };
        let _dbSortKey = null;
        let _dbSortAsc = true;

        function sortDb(key) {
            if (_dbSortKey === key) { _dbSortAsc = !_dbSortAsc; }
            else { _dbSortKey = key; _dbSortAsc = true; }
            renderDb(dbData[currentDb]);
        }

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('stat-mobs').textContent = data.mobiles;
                document.getElementById('stat-objs').textContent = data.objects;
                document.getElementById('stat-rooms').textContent = data.rooms;
                document.getElementById('stat-areas').textContent = data.areas;
                const heroCount = document.getElementById('hero-area-count');
                if (heroCount) heroCount.textContent = data.areas;
            } catch(e) {
                console.error("Error loading stats:", e);
            }
        }
        
        // Call on load
        loadStats();

        // Inject ASCII hero art from data script element
        (function() {
            const src = document.getElementById('ascii-art-src');
            const bg = document.getElementById('ascii-hero-art');
            if (src && bg) bg.textContent = src.textContent.trim();
        })();

        function toggleFilters(btnEl) {
            const el = document.getElementById('advanced-filters');
            const btn = btnEl || (typeof event !== 'undefined' ? event.currentTarget : null);
            if (!btn) return;
            const isHidden = el.classList.toggle('hidden');
            const icon = btn.querySelector('i');
            if (isHidden) {
                icon.className = 'fa-solid fa-filter';
                btn.classList.remove('bg-blue-900/30', 'border-blue-700');
            } else {
                icon.className = 'fa-solid fa-filter-circle-xmark';
                btn.classList.add('bg-blue-900/30', 'border-blue-700');
            }
        }

        async function loadDb(type, forceRefresh = false) {
            currentDb = type;
            // Reset sort when switching categories
            if (_dbSortKey) { _dbSortKey = null; _dbSortAsc = true; }
            const content = document.getElementById('db-content');
            const headers = document.getElementById('db-headers');
            const filterContainer = document.getElementById('obj-filter-container');
            
            // Toggle filter visibility
            if(type === 'objects') {
                filterContainer.classList.remove('hidden');
            } else {
                filterContainer.classList.add('hidden');
            }
            
            content.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-gray-500">Loading...</td></tr>';

            try {
                let url = '/api/' + type + (type === 'areas' ? '' : '?limit=10000');
                
                // Add filters for objects
                if(type === 'objects') {
                    const typeFilter = document.getElementById('filter-type').value;
                    const wearFilter = document.getElementById('filter-wear').value;
                    const minLevel = document.getElementById('filter-min-level').value;
                    const maxLevel = document.getElementById('filter-max-level').value;
                    const statFilter = document.getElementById('filter-stat').value;
                    
                    // Collect flags
                    const flags = Array.from(document.querySelectorAll('.filter-flag:checked')).map(cb => cb.value);
                    
                    if(typeFilter) url += '&item_type=' + encodeURIComponent(typeFilter);
                    if(wearFilter) url += '&wear_flag=' + encodeURIComponent(wearFilter);
                    if(minLevel) url += '&min_level=' + minLevel;
                    if(maxLevel) url += '&max_level=' + maxLevel;
                    if(statFilter) url += '&stat_filter=' + encodeURIComponent(statFilter);
                    if(flags.length > 0) url += '&extra_flags=' + encodeURIComponent(flags.join(','));
                    
                    if(typeFilter || wearFilter || minLevel || maxLevel || statFilter || flags.length > 0) {
                        forceRefresh = true;
                    }
                }

                if(forceRefresh || !dbData[type] || dbData[type].length === 0) {
                    const res = await fetch(url);
                    dbData[type] = await res.json();
                }
                renderDb(dbData[type]);
            } catch(e) {
                content.innerHTML = `<tr><td colspan="5" class="p-4 text-center text-red-500">Error loading data: ${escHtml(String(e))}</td></tr>`;
            }
        }

        function renderDb(data) {
            const headers = document.getElementById('db-headers');
            const content = document.getElementById('db-content');
            
            // Update stats card with loaded count
            if(currentDb === 'mobs') {
                const total = parseInt(document.getElementById('stat-mobs').textContent.split('/')[1] || document.getElementById('stat-mobs').textContent);
                const loaded = data.length;
                const el = document.getElementById('stat-mobs');
                el.textContent = `${loaded} / ${total}`;
                if(loaded < total) el.classList.add('text-orange-400');
                else el.classList.remove('text-orange-400');
            } else if(currentDb === 'objects') {
                const total = parseInt(document.getElementById('stat-objs').textContent.split('/')[1] || document.getElementById('stat-objs').textContent);
                const loaded = data.length;
                const el = document.getElementById('stat-objs');
                el.textContent = `${loaded} / ${total}`;
                if(loaded < total) el.classList.add('text-orange-400');
                else el.classList.remove('text-orange-400');
            } else if(currentDb === 'rooms') {
                const total = parseInt(document.getElementById('stat-rooms').textContent.split('/')[1] || document.getElementById('stat-rooms').textContent);
                const loaded = data.length;
                const el = document.getElementById('stat-rooms');
                el.textContent = `${loaded} / ${total}`;
                if(loaded < total) el.classList.add('text-orange-400');
                else el.classList.remove('text-orange-400');
            }

            let headerHtml = '';
            let rowsHtml = '';

            // Apply sort if active
            if (_dbSortKey && currentDb !== 'areas') {
                data = [...data].sort((a, b) => {
                    const av = a[_dbSortKey]; const bv = b[_dbSortKey];
                    const ai = isNaN(av) ? String(av||'').toLowerCase() : Number(av);
                    const bi = isNaN(bv) ? String(bv||'').toLowerCase() : Number(bv);
                    if (ai < bi) return _dbSortAsc ? -1 : 1;
                    if (ai > bi) return _dbSortAsc ? 1 : -1;
                    return 0;
                });
            }

            function sortHdr(label, key) {
                const arrow = _dbSortKey === key ? (_dbSortAsc ? ' &#9650;' : ' &#9660;') : ' <span class="text-gray-700">&#9650;</span>';
                return `<th class="p-4 cursor-pointer hover:text-white select-none" onclick="sortDb('${key}')">${label}${arrow}</th>`;
            }

            if(currentDb === 'mobs') {
                headerHtml = sortHdr('Vnum','vnum') + sortHdr('Name','short_desc') + sortHdr('Level','level') + sortHdr('Race','race') + sortHdr('Area','area') + '<th class="p-4">Actions</th>';
                rowsHtml = data.map(m => `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-mono text-sm text-gray-500">#${escHtml(m.vnum)}</td>
                        <td class="p-4 font-bold text-gray-300">${escHtml(m.short_desc || 'Unnamed')}</td>
                        <td class="p-4 text-yellow-500">${escHtml(m.level)}</td>
                        <td class="p-4 text-gray-400">${escHtml(m.race)}</td>
                        <td class="p-4 text-gray-500 text-sm">${escHtml(m.area || '-')}</td>
                        <td class="p-4">
                            <button onclick="showMobDetail(${m.vnum})" class="text-xs bg-gray-800 hover:bg-gray-700 text-white px-2 py-1 rounded border border-gray-600">View</button>
                        </td>
                    </tr>
                `).join('');
            } else if(currentDb === 'objects') {
                headerHtml = sortHdr('Vnum','vnum') + sortHdr('Name','short_desc') + sortHdr('Type','item_type') + sortHdr('Level','level') + '<th class="p-4">Details</th><th class="p-4">Actions</th>';
                rowsHtml = data.map(o => {
                    // Build affects display
                    let affectsHtml = '';
                    if(o.affects && o.affects.length > 0) {
                        affectsHtml = '<div class="mt-2"><strong class="text-green-400">Affects:</strong> ' + 
                            o.affects.map(a => `<span class="text-green-300">${escHtml(a)}</span>`).join(', ') + '</div>';
                    }
                    
                    // Build flags display
                    let flagsHtml = '';
                    if((o.flags && o.flags.length > 0) || (o.flags2 && o.flags2.length > 0)) {
                        let allFlags = [...(o.flags || []), ...(o.flags2 || [])];
                        flagsHtml = '<div class="mt-1"><strong class="text-purple-400">Flags:</strong> ' + 
                            allFlags.map(f => `<span class="text-purple-300">${escHtml(f)}</span>`).join(', ') + '</div>';
                    }
                    
                    // Build wear locations
                    let wearHtml = '';
                    if(o.wear_locations && o.wear_locations.length > 0) {
                        wearHtml = '<div class="mt-1"><strong class="text-blue-400">Wear:</strong> ' + 
                            o.wear_locations.map(w => `<span class="text-blue-300">${escHtml(w)}</span>`).join(', ') + '</div>';
                    }
                    
                    // Build detailed stats based on item type
                    let statsHtml = '';
                    if(o.values_interpreted) {
                        const v = o.values_interpreted;
                        
                        // Weapon
                        if(v.damage_text) {
                            statsHtml += `<div class="mt-1"><strong class="text-red-400">Damage:</strong> <span class="text-red-300">${v.damage_text}</span>`;
                            if(v.damage_type) statsHtml += ` <span class="text-gray-400">(${v.damage_type})</span>`;
                            if(v.weapon_class) statsHtml += ` <span class="text-gray-400">[${v.weapon_class}]</span>`;
                            if(v.weapon_flags && v.weapon_flags.length > 0) statsHtml += ` <span class="text-orange-400">{${v.weapon_flags.join(', ')}}</span>`;
                            statsHtml += '</div>';
                        }
                        
                        // Armor
                        if(v.ac_summary) {
                            statsHtml += `<div class="mt-1"><strong class="text-cyan-400">AC:</strong> <span class="text-cyan-300">${v.ac_summary}</span></div>`;
                        }
                        
                        // Container
                        if(v.capacity) {
                            statsHtml += `<div class="mt-1"><strong class="text-orange-400">Container:</strong> <span class="text-gray-300">Cap: ${v.weight_capacity || v.capacity}</span>`;
                            if(v.container_flags && v.container_flags.length > 0) statsHtml += ` <span class="text-orange-300">[${v.container_flags.join(', ')}]</span>`;
                            if(v.key_vnum && v.key_vnum !== '0') statsHtml += ` <span class="text-gray-500">Key: #${v.key_vnum}</span>`;
                            statsHtml += '</div>';
                        }
                        
                        // Drink Container
                        if(v.liquid_type) {
                            statsHtml += `<div class="mt-1"><strong class="text-blue-400">Drink:</strong> <span class="text-blue-300">${v.liquid_type}</span>`;
                            statsHtml += ` <span class="text-gray-400">(${v.current_quantity}/${v.capacity})</span>`;
                            if(v.poisoned) statsHtml += ` <span class="text-green-500 font-bold">[POISONED]</span>`;
                            statsHtml += '</div>';
                        }
                        
                        // Fountain
                        if(v.capacity_text) {
                            statsHtml += `<div class="mt-1"><strong class="text-blue-400">Fountain:</strong> <span class="text-blue-300">${v.capacity_text}</span></div>`;
                        }
                        
                        // Food
                        if(o.item_type === 'food' && v.hours_text) {
                            statsHtml += `<div class="mt-1"><strong class="text-green-400">Food:</strong> <span class="text-green-300">${v.hours_text}</span></div>`;
                        }

                        // Light
                        if(o.item_type === 'light' && v.hours_text) {
                            statsHtml += `<div class="mt-1"><strong class="text-yellow-200">Light:</strong> <span class="text-yellow-100">${v.hours_text}</span></div>`;
                        }
                        
                        // Money
                        if(v.gold_text) {
                            statsHtml += `<div class="mt-1"><strong class="text-yellow-400">Value:</strong> <span class="text-yellow-300">${v.gold_text}</span></div>`;
                        }
                        
                        // Manipulation
                        if(v.manip_type) {
                             statsHtml += `<div class="mt-1"><strong class="text-gray-400">Manip:</strong> <span class="text-gray-300">${v.manip_type}</span>`;
                             if(v.room_goes_to) statsHtml += ` -> Room #${v.room_goes_to}`;
                             statsHtml += '</div>';
                        }

                        // Action
                        if(v.action_type) {
                             statsHtml += `<div class="mt-1"><strong class="text-gray-400">Action:</strong> <span class="text-gray-300">${v.action_type}</span></div>`;
                        }
                        
                        // Spells (Scroll, Potion, Pill, Wand, Staff)
                        if(v.spell_level) {
                            statsHtml += `<div class="mt-1"><strong class="text-pink-400">Spells (Lvl ${v.spell_level}):</strong> `;
                            let spells = [];
                            if(v.spell1) spells.push(v.spell1);
                            if(v.spell2) spells.push(v.spell2);
                            if(v.spell3) spells.push(v.spell3);
                            if(v.spell_num) spells.push(v.spell_num);
                            statsHtml += `<span class="text-pink-300">${spells.join(', ')}</span>`;
                            
                            if(v.max_charges) {
                                statsHtml += ` <span class="text-gray-400">(${v.current_charges}/${v.max_charges} charges)</span>`;
                            }
                            statsHtml += '</div>';
                        }
                        
                        // Portal
                        if(v.portal_type) {
                            statsHtml += `<div class="mt-1"><strong class="text-indigo-400">Portal:</strong> <span class="text-indigo-300">${v.portal_type}</span>`;
                            if(v.to_room) statsHtml += ` <span class="text-gray-400">-> Room #${v.to_room}</span>`;
                            if(v.portal_flags && v.portal_flags.length > 0) statsHtml += ` <span class="text-indigo-300">[${v.portal_flags.join(', ')}]</span>`;
                            statsHtml += '</div>';
                        }
                    }
                    
                    // Build mob carriers list
                    let carriersHtml = '';
                    if(o.carried_by && o.carried_by.length > 0) {
                        carriersHtml = '<div class="mt-2"><strong class="text-yellow-400">Found on:</strong> ' + 
                            o.carried_by.slice(0, 3).map(m => `<span class="text-yellow-300 cursor-pointer hover:underline" onclick="showMobDetail(${m.vnum})">${escHtml(m.name)} (${escHtml(m.level)})</span>`).join(', ');
                        if(o.carried_by.length > 3) {
                            carriersHtml += ` <span class="text-gray-500">+${o.carried_by.length - 3} more</span>`;
                        }
                        carriersHtml += '</div>';
                    }
                    
                    return `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-mono text-sm text-gray-500 align-top">#${escHtml(o.vnum)}</td>
                        <td class="p-4 font-bold text-gray-300 align-top">
                            ${escHtml(o.short_desc || 'Unnamed')}
                            <div class="text-xs text-gray-500 mt-1">${escHtml(o.material || 'unknown')}</div>
                        </td>
                        <td class="p-4 text-blue-400 align-top">${escHtml(o.item_type)}</td>
                        <td class="p-4 text-yellow-500 align-top">
                            ${escHtml(o.level)}
                            <div class="text-xs text-gray-500 mt-1">
                                ${escHtml(o.weight)}lb / ${escHtml(o.cost)}g
                            </div>
                        </td>
                        <td class="p-4 text-sm align-top">
                            ${affectsHtml}
                            ${statsHtml}
                            ${flagsHtml}
                            ${wearHtml}
                            ${carriersHtml}
                            <div class="mt-1 text-xs text-gray-600">${escHtml(o.area || '-')}</div>
                        </td>
                        <td class="p-4 align-top">
                            <button onclick="showObjDetail(${o.vnum}); return false;" class="text-xs bg-gray-800 hover:bg-gray-700 text-white px-2 py-1 rounded border border-gray-600">View</button>
                        </td>
                    </tr>
                `;
                }).join('');
            } else if(currentDb === 'areas') {
                headerHtml = '<th class="p-4">Name</th><th class="p-4">Builder</th><th class="p-4">Filename</th><th class="p-4">Vnums</th><th class="p-4">Actions</th>';
                rowsHtml = data.map(a => `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-bold text-gray-300">${escHtml(a.name)}</td>
                        <td class="p-4 text-gray-400">${escHtml(a.builder || '-')}</td>
                        <td class="p-4 font-mono text-sm text-gray-500">${escHtml(a.filename)}</td>
                        <td class="p-4 text-gray-500 text-sm">${escHtml(a.vnums || '-')}</td>
                        <td class="p-4">
                            <button onclick="showAreaMap('${escHtml(a.filename)}')" class="text-xs bg-green-900/30 hover:bg-green-900/50 text-green-400 px-2 py-1 rounded border border-green-900/50"><i class="fas fa-map mr-1"></i>Map</button>
                        </td>
                    </tr>
                `).join('');
            } else if(currentDb === 'rooms') {
                headerHtml = sortHdr('Vnum','vnum') + sortHdr('Name','name') + sortHdr('Area','area') + sortHdr('Sector','sector_type') + '<th class="p-4">Flags</th><th class="p-4">Actions</th>';
                rowsHtml = data.map(r => `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-mono text-sm text-gray-500">#${escHtml(r.vnum)}</td>
                        <td class="p-4 font-bold text-gray-300">${escHtml(r.name)}</td>
                        <td class="p-4 text-gray-500 text-sm">${escHtml(r.area || '-')}</td>
                        <td class="p-4 text-gray-400 capitalize">${escHtml(r.sector_type)}</td>
                        <td class="p-4 text-gray-500 text-xs">${escHtml(r.room_flags || '-')}</td>
                        <td class="p-4">
                            <button onclick="showRoomDetail(${r.vnum})" class="text-xs bg-gray-800 hover:bg-gray-700 text-white px-2 py-1 rounded border border-gray-600">View</button>
                        </td>
                    </tr>
                `).join('');
            }

            headers.innerHTML = headerHtml;
            content.innerHTML = rowsHtml || '<tr><td colspan="6" class="p-4 text-center">No results found</td></tr>';

            const countEl = document.getElementById('db-result-count');
            if (countEl) countEl.textContent = data.length ? `Showing ${data.length.toLocaleString()} result${data.length !== 1 ? 's' : ''}` : '';
        }

        let _filterDbTimer = null;
        function debouncedFilterDb() {
            clearTimeout(_filterDbTimer);
            _filterDbTimer = setTimeout(filterDb, 300);
        }

        function resetObjectFilters() {
            const ids = ['filter-type', 'filter-wear', 'filter-min-level', 'filter-max-level', 'filter-stat'];
            ids.forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            document.querySelectorAll('.filter-flag').forEach(cb => {
                cb.checked = false;
            });
            loadDb('objects', true);
        }

        function filterDb() {
            const q = document.getElementById('db-search').value.toLowerCase().trim();
            if (!q) { renderDb(dbData[currentDb]); return; }
            const filtered = dbData[currentDb].filter(item => {
                const fields = [item.vnum, item.short_desc, item.name, item.area,
                    item.race, item.item_type, item.sector_type, item.builder,
                    item.filename, item.material, item.dam_type];
                return fields.some(f => f != null && String(f).toLowerCase().includes(q));
            });
            renderDb(filtered);
        }

        // ============ ADMIN ============
        function getAuthHeaders() {
            const token = localStorage.getItem('toc_admin_token') || '';
            return token ? { 'X-Admin-Token': token } : {};
        }

        function termFontSize(delta) {
            if (!term) return;
            const sz = Math.max(8, Math.min(24, (term.options.fontSize || 12) + delta));
            term.options.fontSize = sz;
            localStorage.setItem('toc_term_font_size', String(sz));
            if (fitAddon) fitAddon.fit();
            if (logTerm) {
                logTerm.options.fontSize = sz;
                if (logFitAddon) logFitAddon.fit();
            }
        }

        function exportCsv() {
            const data = dbData[currentDb];
            if (!data || data.length === 0) { showToast('No data loaded to export.', 'warning'); return; }
            const hdrs = currentDb === 'mobs' ? ['vnum','short_desc','level','race','area']
                : currentDb === 'objects' ? ['vnum','short_desc','item_type','level','area']
                : currentDb === 'rooms' ? ['vnum','name','area','sector_type','room_flags']
                : ['filename','name','builder'];
            const rows = [hdrs.join(',')];
            data.forEach(r => {
                rows.push(hdrs.map(h => {
                    const v = String(r[h] ?? '');
                    return (v.includes(',') || v.includes('"') || v.includes('\\n')) ? '"' + v.replace(/"/g, '""') + '"' : v;
                }).join(','));
            });
            const blob = new Blob([rows.join('\\n')], {type: 'text/csv'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `toc_${currentDb}_${new Date().toISOString().slice(0,10)}.csv`;
            a.click();
            URL.revokeObjectURL(a.href);
            showToast(`Exported ${data.length.toLocaleString()} rows as CSV.`, 'success');
        }

        let actionPendingTimers = {};
        async function action(type, btnEl) {
            const btn = btnEl || (typeof event !== 'undefined' ? event.currentTarget : null);
            if (!btn) return;
            if (btn.dataset.confirmPending === 'true') {
                // Second click
                clearTimeout(actionPendingTimers[type]);
                delete actionPendingTimers[type];
                btn.dataset.confirmPending = 'false';
                btn.innerHTML = btn.dataset.origHtml;
                btn.classList.remove('border-yellow-500', 'text-yellow-300');
                try {
                    const res = await fetch('/api/' + type, { method: 'POST', headers: getAuthHeaders() });
                    if (res.status === 403) { showToast('Forbidden — check your API token in Admin settings.', 'error'); return; }
                    showToast(type.charAt(0).toUpperCase() + type.slice(1) + ' queued successfully.', 'success');
                } catch(e) { showToast('Error: ' + e, 'error'); }
            } else {
                // First click - show confirm state
                btn.dataset.confirmPending = 'true';
                btn.dataset.origHtml = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-exclamation-triangle mr-1"></i> Click again to confirm';
                btn.classList.add('border-yellow-500', 'text-yellow-300');
                actionPendingTimers[type] = setTimeout(() => {
                    btn.dataset.confirmPending = 'false';
                    btn.innerHTML = btn.dataset.origHtml;
                    btn.classList.remove('border-yellow-500', 'text-yellow-300');
                }, 3000);
            }
        }

        async function sendWizInfo(e) {
            e.preventDefault();
            const msg = document.getElementById('wizinfo-msg').value;
            const level = document.getElementById('wizinfo-level').value;
            try {
                const res = await fetch('/api/wizinfo', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', ...getAuthHeaders()},
                    body: JSON.stringify({message: msg, level: parseInt(level)})
                });
                if (res.status === 403) { showToast('Forbidden — check your API token.', 'error'); return; }
                showToast('Broadcast queued.', 'success');
                e.target.reset();
            } catch(e) { showToast('Error: ' + e, 'error'); }
        }

        async function sendCommand(e) {
            e.preventDefault();
            const cmd = document.getElementById('server-cmd').value;
            try {
                const res = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', ...getAuthHeaders()},
                    body: JSON.stringify({command: cmd})
                });
                if (res.status === 403) { showToast('Forbidden — check your API token.', 'error'); return; }
                showToast('Command queued.', 'success');
                e.target.reset();
            } catch(e) { showToast('Error: ' + e, 'error'); }
        }

        let logWs = null;
        let logTerm = null;
        let logFitAddon = null;
        let logsShouldReconnect = false;

        function stopLogs() {
            logsShouldReconnect = false;
            if (logWs) {
                logWs.onclose = null;
                logWs.close();
                logWs = null;
            }
        }

        function initLogs() {
            logsShouldReconnect = true;
            const container = document.getElementById('log-terminal');
            if (!logTerm) {
                container.innerHTML = ''; // Clear "Loading logs..." text
                container.className = "bg-black p-1 h-96 overflow-hidden"; // Remove overflow-y-auto, let xterm handle it

                logTerm = new Terminal({
                    cursorBlink: false,
                    fontFamily: '"Roboto Mono", monospace',
                    fontSize: getPreferredFontSize(),
                    theme: {
                        background: '#000000',
                        foreground: '#00ff00',
                    },
                    disableStdin: true,
                    convertEol: true
                });
                
                logFitAddon = new FitAddon.FitAddon();
                logTerm.loadAddon(logFitAddon);
                logTerm.open(container);
                logFitAddon.fit();
                
                window.addEventListener('resize', () => logFitAddon.fit());
            }
            
            connectLogs();
        }

        function connectLogs() {
            if (!logsShouldReconnect) return;
            if (logWs) {
                logWs.onclose = null;
                logWs.close();
                logWs = null;
            }

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const token = localStorage.getItem('toc_admin_token') || '';
            const tokenQuery = token ? ('?x_admin_token=' + encodeURIComponent(token)) : '';
            logWs = new WebSocket(protocol + '//' + window.location.host + '/ws/logs' + tokenQuery);

            logWs.onopen = () => {
                logTerm.writeln('\x1b[32mConnected to log stream.\x1b[0m');
            };

            logWs.onmessage = (event) => {
                logTerm.write(event.data);
            };

            logWs.onclose = (event) => {
                logWs = null;
                if (!logsShouldReconnect) return;
                if (event.code === 4003) {
                    logsShouldReconnect = false;
                    logTerm.writeln('\x1b[31mLog stream forbidden. Set a valid Admin token to view logs.\x1b[0m');
                    return;
                }
                logTerm.writeln('\x1b[31mLog stream disconnected. Reconnecting...\x1b[0m');
                setTimeout(() => {
                    if (logsShouldReconnect) connectLogs();
                }, 3000);
            };

            logWs.onerror = () => {
                logTerm.writeln('\x1b[31mLog stream error.\x1b[0m');
            };
        }

        function refreshLogs() {
             initLogs();
        }

        // ============ STATUS ============
        async function checkStatus() {
            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                const statusPing = document.getElementById('status-ping');
                const statusDot = document.getElementById('status-dot');
                const statusText = document.getElementById('status-text');
                
                if (data.merc) {
                    statusDot.className = "relative inline-flex rounded-full h-3 w-3 bg-green-500";
                    statusPing.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75";
                    statusText.className = "text-green-400 font-mono";
                    statusText.textContent = "ONLINE";
                } else {
                    statusDot.className = "relative inline-flex rounded-full h-3 w-3 bg-red-500";
                    statusPing.className = "";
                    statusText.className = "text-red-400 font-mono";
                    statusText.textContent = "OFFLINE";
                }
                const navDot = document.getElementById('nav-dot');
                const navDotText = document.getElementById('nav-dot-text');
                if (navDot && navDotText) {
                    navDot.className = 'h-2 w-2 rounded-full inline-block transition-colors duration-500 ' + (data.merc ? 'bg-green-500' : 'bg-red-500');
                    navDotText.className = 'transition-colors duration-500 ' + (data.merc ? 'text-green-400' : 'text-red-400');
                    navDotText.textContent = data.merc ? 'LIVE' : 'OFFLINE';
                }
            } catch (e) {
                console.error("Status check failed", e);
            }
        }
        
        setInterval(checkStatus, 30000);
        checkStatus();

        // Room Modal Functions
        async function showRoomDetail(vnum) {
            // Show modal immediately with loading state
            document.getElementById('room-modal-title').textContent = 'Loading...';
            document.getElementById('room-modal-vnum').textContent = '';
            document.getElementById('room-modal-desc').textContent = '';
            document.getElementById('room-modal-exits').innerHTML = '<div class="col-span-full text-gray-500 text-sm"><i class="fas fa-spinner fa-spin mr-2"></i>Loading...</div>';
            document.getElementById('room-modal-mobs').innerHTML = '';
            document.getElementById('room-modal-objects').innerHTML = '';
            document.getElementById('room-modal-extras').innerHTML = '';
            document.getElementById('room-modal').classList.remove('hidden');
            try {
                const res = await fetch(`/api/rooms/${vnum}`);
                if(!res.ok) throw new Error('Failed to fetch room: ' + res.status);
                const room = await res.json();
                
                document.getElementById('room-modal-title').textContent = room.name;
                document.getElementById('room-modal-vnum').textContent = '#' + room.vnum;
                document.getElementById('room-modal-desc').textContent = room.description;
                document.getElementById('room-modal-area').textContent = room.area;
                document.getElementById('room-modal-sector').textContent = room.sector_type;
                document.getElementById('room-modal-flags').textContent = room.room_flags;
                
                // Exits
                const exitsContainer = document.getElementById('room-modal-exits');
                if(room.exits && room.exits.length > 0) {
                    exitsContainer.innerHTML = room.exits.map(ex => `
                        <div onclick="showRoomDetail(${ex.to_room})" class="bg-[#222] p-2 rounded border border-gray-700 text-center cursor-pointer hover:bg-[#333] transition-colors">
                            <div class="text-yellow-500 font-bold uppercase text-xs">${escHtml(ex.direction)}</div>
                            <div class="text-gray-400 text-xs truncate" title="${escHtml(ex.to_room_name)}">${escHtml(ex.to_room_name)}</div>
                            <div class="text-gray-600 text-[10px] font-mono">#${escHtml(ex.to_room)}</div>
                        </div>
                    `).join('');
                } else {
                    exitsContainer.innerHTML = '<div class="col-span-full text-gray-500 italic text-sm">No exits</div>';
                }
                
                // Mobs
                const mobsContainer = document.getElementById('room-modal-mobs');
                if(room.mobs && room.mobs.length > 0) {
                    mobsContainer.innerHTML = room.mobs.map(m => `
                        <li class="flex justify-between items-center">
                            <span class="text-red-300 truncate" title="${escHtml(m.name)}">${escHtml(m.name)}</span>
                            <span class="text-gray-600 text-xs font-mono">#${escHtml(m.vnum)}</span>
                        </li>
                    `).join('');
                } else {
                    mobsContainer.innerHTML = '<li class="text-gray-500 italic">None</li>';
                }
                
                // Objects
                const objsContainer = document.getElementById('room-modal-objects');
                if(room.objects && room.objects.length > 0) {
                    objsContainer.innerHTML = room.objects.map(o => `
                        <li class="flex justify-between items-center">
                            <span class="text-blue-300 truncate" title="${escHtml(o.name)}">${escHtml(o.name)}</span>
                            <span class="text-gray-600 text-xs font-mono">#${escHtml(o.vnum)}</span>
                        </li>
                    `).join('');
                } else {
                    objsContainer.innerHTML = '<li class="text-gray-500 italic">None</li>';
                }

                // Extras
                const extrasContainer = document.getElementById('room-modal-extras');
                if(room.extra_descr && room.extra_descr.length > 0) {
                    extrasContainer.innerHTML = room.extra_descr.map(ed => `
                        <div class="bg-[#151515] p-2 rounded border border-gray-800">
                            <span class="text-green-400 font-bold text-xs">${escHtml(ed.keyword)}:</span>
                            <span class="text-gray-400 text-xs">${escHtml(ed.description)}</span>
                        </div>
                    `).join('');
                } else {
                    extrasContainer.innerHTML = '<div class="text-gray-500 italic text-sm">None</div>';
                }
                
                document.getElementById('room-modal').classList.remove('hidden');
            } catch(e) {
                document.getElementById('room-modal').classList.add('hidden');
                showToast('Error loading room details: ' + e, 'error');
            }
        }
        
        function closeRoomModal() {
            document.getElementById('room-modal').classList.add('hidden');
        }

        // Mob Modal Functions
        async function showMobDetail(vnum) {
            // Show modal immediately with loading state
            document.getElementById('mob-modal-title').textContent = 'Loading...';
            document.getElementById('mob-modal-vnum').textContent = '';
            document.getElementById('mob-modal-desc').textContent = '';
            document.getElementById('mob-modal-drops').innerHTML = '<li class="text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading...</li>';
            document.getElementById('mob-modal-spawns').innerHTML = '';
            document.getElementById('mob-modal').classList.remove('hidden');
            try {
                const res = await fetch(`/api/mobs/${vnum}`);
                if(!res.ok) throw new Error('Failed to fetch mob: ' + res.status);
                const mob = await res.json();
                
                document.getElementById('mob-modal-title').textContent = mob.short_desc;
                document.getElementById('mob-modal-vnum').textContent = '#' + mob.vnum;
                document.getElementById('mob-modal-desc').textContent = mob.description;
                
                // Combat
                document.getElementById('mob-modal-level').textContent = mob.level;
                document.getElementById('mob-modal-hitroll').textContent = mob.hitroll;
                document.getElementById('mob-modal-hitdice').textContent = mob.hitp_dice;
                document.getElementById('mob-modal-manadice').textContent = mob.mana_dice;
                document.getElementById('mob-modal-damdice').textContent = mob.dam_dice;
                document.getElementById('mob-modal-damtype').textContent = mob.dam_type;
                document.getElementById('mob-modal-ac').textContent = mob.ac.join(' / ');
                
                // Details
                document.getElementById('mob-modal-race').textContent = mob.race;
                document.getElementById('mob-modal-sex').textContent = mob.sex;
                document.getElementById('mob-modal-size').textContent = mob.size;
                document.getElementById('mob-modal-align').textContent = mob.alignment;
                document.getElementById('mob-modal-wealth').textContent = mob.wealth;
                document.getElementById('mob-modal-material').textContent = mob.material;
                document.getElementById('mob-modal-startpos').textContent = mob.start_pos;
                document.getElementById('mob-modal-defpos').textContent = mob.default_pos;
                
                // Flags
                document.getElementById('mob-modal-act').querySelector('span:last-child').textContent = mob.act_flags.join(', ') || 'None';
                document.getElementById('mob-modal-off').querySelector('span:last-child').textContent = mob.off_flags.join(', ') || 'None';
                document.getElementById('mob-modal-aff').querySelector('span:last-child').textContent = mob.affected_by.join(', ') || 'None';
                document.getElementById('mob-modal-imm').querySelector('span:last-child').textContent = mob.imm_flags.join(', ') || 'None';
                document.getElementById('mob-modal-res').querySelector('span:last-child').textContent = mob.res_flags.join(', ') || 'None';
                document.getElementById('mob-modal-vuln').querySelector('span:last-child').textContent = mob.vuln_flags.join(', ') || 'None';
                document.getElementById('mob-modal-form').querySelector('span:last-child').textContent = mob.form.join(', ') || 'None';
                document.getElementById('mob-modal-parts').querySelector('span:last-child').textContent = mob.parts.join(', ') || 'None';
                
                // Drops
                const dropsContainer = document.getElementById('mob-modal-drops');
                if(mob.drops && mob.drops.length > 0) {
                    dropsContainer.innerHTML = mob.drops.map(d => `
                        <li class="flex justify-between items-center">
                            <span class="text-red-300 truncate" title="${escHtml(d.name)}">${escHtml(d.name)}</span>
                            <span class="text-gray-600 text-xs font-mono">#${escHtml(d.vnum)}</span>
                        </li>
                    `).join('');
                } else {
                    dropsContainer.innerHTML = '<li class="text-gray-500 italic">No drops</li>';
                }
                
                // Spawns
                const spawnsContainer = document.getElementById('mob-modal-spawns');
                if(mob.spawn_rooms && mob.spawn_rooms.length > 0) {
                    spawnsContainer.innerHTML = mob.spawn_rooms.map(r => `
                        <li onclick="closeMobModal(); showRoomDetail(${r.vnum})" class="flex justify-between items-center cursor-pointer hover:bg-[#222] p-1 rounded transition-colors">
                            <span class="text-gray-300 truncate text-xs">${escHtml(r.name)}</span>
                            <span class="text-gray-600 text-xs font-mono">#${escHtml(r.vnum)}</span>
                        </li>
                    `).join('');
                } else {
                    spawnsContainer.innerHTML = '<li class="text-gray-500 italic">No spawn locations found</li>';
                }
                
                document.getElementById('mob-modal').classList.remove('hidden');
            } catch(e) {
                document.getElementById('mob-modal').classList.add('hidden');
                showToast('Error loading mob details: ' + e, 'error');
            }
        }
        
        function closeMobModal() {
            document.getElementById('mob-modal').classList.add('hidden');
        }

        // Object Modal Functions
        async function showObjDetail(vnum) {
            if(vnum === undefined || vnum === null || vnum === 'undefined') {
                console.error('showObjDetail called with invalid vnum!');
                showToast('Error: Object vnum is undefined.', 'error');
                return;
            }
            // Show modal immediately with loading state
            document.getElementById('obj-modal-title').textContent = 'Loading...';
            document.getElementById('obj-modal-vnum').textContent = '';
            document.getElementById('obj-modal-desc').textContent = '';
            document.getElementById('obj-modal-affects').innerHTML = '<li class="text-gray-500"><i class="fas fa-spinner fa-spin mr-2"></i>Loading...</li>';
            document.getElementById('obj-modal-carried').innerHTML = '';
            document.getElementById('obj-modal-extras').innerHTML = '';
            document.getElementById('obj-modal').classList.remove('hidden');
            try {
                const res = await fetch(`/api/objects/${vnum}`);
                if(!res.ok) throw new Error('Failed to fetch object: ' + res.status);
                const obj = await res.json();
                
                document.getElementById('obj-modal-title').textContent = obj.short_desc;
                document.getElementById('obj-modal-vnum').textContent = '#' + obj.vnum;
                document.getElementById('obj-modal-desc').textContent = obj.long_desc;
                
                // Stats
                document.getElementById('obj-modal-type').textContent = obj.item_type;
                document.getElementById('obj-modal-level').textContent = obj.level;
                document.getElementById('obj-modal-weight').textContent = obj.weight;
                document.getElementById('obj-modal-cost').textContent = obj.cost;
                document.getElementById('obj-modal-material').textContent = obj.material;
                document.getElementById('obj-modal-condition').textContent = obj.condition;
                
                // Flags
                document.getElementById('obj-modal-extra').querySelector('span:last-child').textContent = obj.extra_flags.join(', ') || 'None';
                document.getElementById('obj-modal-wear').querySelector('span:last-child').textContent = obj.wear_flags.join(', ') || 'None';
                
                // Affects
                const affContainer = document.getElementById('obj-modal-affects');
                if(obj.affects && obj.affects.length > 0) {
                    affContainer.innerHTML = obj.affects.map(a => `
                        <li class="flex justify-between">
                            <span class="text-gray-400">${a}</span>
                        </li>
                    `).join('');
                } else {
                    affContainer.innerHTML = '<li class="text-gray-500 italic">None</li>';
                }
                
                // Values
                const valContainer = document.getElementById('obj-modal-values');
                let valHtml = '';
                const v = obj.values_interpreted;
                
                if(v.damage_text) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Damage:</span> <span class="text-red-300">${escHtml(v.damage_text)}</span></div>`;
                if(v.damage_type) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Type:</span> <span class="text-gray-300">${escHtml(v.damage_type)}</span></div>`;
                if(v.weapon_class) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Class:</span> <span class="text-gray-300">${escHtml(v.weapon_class)}</span></div>`;
                if(v.ac_summary) valHtml += `<div class="flex justify-between"><span class="text-gray-500">AC:</span> <span class="text-cyan-300">${escHtml(v.ac_summary)}</span></div>`;
                if(v.capacity) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Capacity:</span> <span class="text-gray-300">${escHtml(v.capacity)}</span></div>`;
                if(v.liquid_type) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Liquid:</span> <span class="text-blue-300">${escHtml(v.liquid_type)}</span></div>`;
                if(v.spell_level) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Spell Lvl:</span> <span class="text-pink-300">${escHtml(v.spell_level)}</span></div>`;
                if(v.spell1) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Spell 1:</span> <span class="text-pink-300">${escHtml(v.spell1)}</span></div>`;
                if(v.spell2) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Spell 2:</span> <span class="text-pink-300">${escHtml(v.spell2)}</span></div>`;
                if(v.spell3) valHtml += `<div class="flex justify-between"><span class="text-gray-500">Spell 3:</span> <span class="text-pink-300">${escHtml(v.spell3)}</span></div>`;
                
                valContainer.innerHTML = valHtml || '<div class="text-gray-500 italic">None</div>';
                
                // Carried By
                const carriedContainer = document.getElementById('obj-modal-carried');
                if(obj.carried_by && obj.carried_by.length > 0) {
                    carriedContainer.innerHTML = obj.carried_by.map(m => `
                        <li onclick="closeObjModal(); showMobDetail(${m.vnum})" class="flex justify-between items-center cursor-pointer hover:bg-[#222] p-1 rounded transition-colors">
                            <span class="text-yellow-300 truncate text-xs">${escHtml(m.name)}</span>
                            <span class="text-gray-600 text-xs font-mono">#${escHtml(m.vnum)}</span>
                        </li>
                    `).join('');
                } else {
                    carriedContainer.innerHTML = '<li class="text-gray-500 italic">Not found on any mobs</li>';
                }
                
                // Extras
                const extrasContainer = document.getElementById('obj-modal-extras');
                if(obj.extra_descr && obj.extra_descr.length > 0) {
                    extrasContainer.innerHTML = obj.extra_descr.map(ed => `
                        <div class="bg-[#151515] p-2 rounded border border-gray-800">
                            <span class="text-green-400 font-bold text-xs">${escHtml(ed.keyword)}:</span>
                            <span class="text-gray-400 text-xs">${escHtml(ed.description)}</span>
                        </div>
                    `).join('');
                } else {
                    extrasContainer.innerHTML = '<div class="text-gray-500 italic">None</div>';
                }
                
                document.getElementById('obj-modal').classList.remove('hidden');
            } catch(e) {
                document.getElementById('obj-modal').classList.add('hidden');
                showToast('Error loading object details: ' + e, 'error');
            }
        }
        
        function closeObjModal() {
            document.getElementById('obj-modal').classList.add('hidden');
        }

        // ============ PLAYER LOOKUP ============
        let _allPlayerNames = [];
        let _currentPlayer  = null;

        const WEAR_SLOT_NAMES = {
            0:"Light", 1:"Left Finger", 2:"Right Finger",
            3:"Neck (1st)", 4:"Neck (2nd)", 5:"Body",
            6:"Head", 7:"Legs", 8:"Feet",
            9:"Hands", 10:"Arms", 11:"Shield",
            12:"About Body", 13:"Waist", 14:"Left Wrist",
            15:"Right Wrist", 16:"Wielded", 17:"Held"
        };

        async function initPlayerList() {
            if (_allPlayerNames.length) return;
            try {
                const res = await fetch('/api/players');
                if (!res.ok) return;
                _allPlayerNames = await res.json();
                const dl = document.getElementById('pl-datalist');
                const bgDl = document.getElementById('bg-player-datalist');
                _allPlayerNames.forEach(n => {
                    [dl, bgDl].forEach(list => {
                        if (list) {
                            const opt = document.createElement('option');
                            opt.value = n;
                            list.appendChild(opt);
                        }
                    });
                });
            } catch(e) { /* silent */ }
        }

        async function lookupPlayer() {
            const name = document.getElementById('pl-search').value.trim();
            if (!name) return;
            const lookupBtn = document.getElementById('pl-lookup-btn');
            setButtonLoading(lookupBtn, true, 'Looking up...');
            const errEl = document.getElementById('pl-error');
            errEl.classList.add('hidden');
            document.getElementById('pl-profile').classList.add('hidden');
            document.getElementById('pl-gear-btn').classList.add('hidden');

            try {
                const res = await fetch('/api/player/' + encodeURIComponent(name));
                if (!res.ok) {
                    errEl.textContent = 'Player "' + escHtml(name) + '" not found.';
                    errEl.classList.remove('hidden');
                    return;
                }
                _currentPlayer = await res.json();
                renderPlayerProfile(_currentPlayer);
                document.getElementById('pl-profile').classList.remove('hidden');
                document.getElementById('pl-gear-btn').classList.remove('hidden');
            } catch(e) {
                errEl.textContent = 'Error: ' + e.message;
                errEl.classList.remove('hidden');
            } finally {
                setButtonLoading(lookupBtn, false);
            }
        }

        function alignStr(a) {
            if (a < -700) return 'Diabolic'; if (a < -350) return 'Evil';
            if (a < -100) return 'Mean';     if (a <  100) return 'Neutral';
            if (a <  350) return 'Kind';     if (a <  700) return 'Good';
            return 'Angelic';
        }

        function statBar(cur, max, cls) {
            const pct = max > 0 ? Math.min(100, Math.round(cur / max * 100)) : 0;
            return `<div class="flex items-center gap-2">
                <div class="flex-1 bg-gray-900 rounded-full h-2">
                    <div class="h-2 rounded-full ${cls}" style="width:${pct}%"></div>
                </div>
                <span class="text-xs text-gray-400 w-24 text-right">${cur}/${max}</span>
            </div>`;
        }

        function renderPlayerProfile(p) {
            const sexStr = p.sex === 1 ? 'Male' : p.sex === 2 ? 'Female' : 'Neutral';
            const remStr = p.num_remorts > 0 ? ` (${p.num_remorts}x remort)` : '';
            const titleFull = p.name + ' ' + (p.title || '');

            // ---- Score ----
            document.getElementById('pl-score-body').innerHTML = `
                <div class="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                    <div><span class="text-gray-500">Name:</span> <span class="text-white font-bold">${escHtml(titleFull)}</span></div>
                    <div><span class="text-gray-500">Race:</span> <span class="text-gray-300">${escHtml(p.race.charAt(0).toUpperCase()+p.race.slice(1))}</span></div>
                    <div><span class="text-gray-500">Class:</span> <span class="text-yellow-400">${escHtml(p.class_name.charAt(0).toUpperCase()+p.class_name.slice(1))}</span></div>
                    <div><span class="text-gray-500">Guild:</span> <span class="text-gray-300">${escHtml(p.guild_name)}</span></div>
                    <div><span class="text-gray-500">Level:</span> <span class="text-green-400 font-bold">${escHtml(p.level)}${remStr}</span></div>
                    <div><span class="text-gray-500">Sex:</span> <span class="text-gray-300">${sexStr}</span></div>
                    <div><span class="text-gray-500">Align:</span> <span class="text-gray-300">${alignStr(p.alignment)} (${p.alignment})</span></div>
                    <div><span class="text-gray-500">XP:</span> <span class="text-gray-300">${p.exp.toLocaleString()}</span></div>
                    <div><span class="text-gray-500">Gold:</span> <span class="text-yellow-300">${p.gold.toLocaleString()}</span></div>
                    <div><span class="text-gray-500">Platinum:</span> <span class="text-yellow-400">${p.platinum.toLocaleString()}</span></div>
                    <div><span class="text-gray-500">Practices:</span> <span class="text-gray-300">${p.practices}</span></div>
                    <div><span class="text-gray-500">Trains:</span> <span class="text-gray-300">${p.trains}</span></div>
                    <div><span class="text-gray-500">QP:</span> <span class="text-purple-400">${p.quest_points}</span></div>
                    <div><span class="text-gray-500">Hitroll:</span> <span class="text-orange-400">${p.hitroll}</span></div>
                    <div><span class="text-gray-500">Damroll:</span> <span class="text-orange-400">${p.damroll}</span></div>
                </div>
                <div class="mt-4 space-y-2">
                    <div><span class="text-gray-500 text-xs">HP</span>${statBar(p.hp_cur, p.hp_max, 'bg-red-600')}</div>
                    <div><span class="text-gray-500 text-xs">Mana</span>${statBar(p.mana_cur, p.mana_max, 'bg-blue-600')}</div>
                    <div><span class="text-gray-500 text-xs">Move</span>${statBar(p.mv_cur, p.mv_max, 'bg-green-700')}</div>
                </div>`;

            // ---- Stats ----
            const statRow = (name, base, mod) => {
                const total = base + mod;
                const modStr = mod !== 0 ? ` <span class="text-gray-600">(${base}${mod >= 0 ? '+' : ''}${mod})</span>` : '';
                const col = total >= 20 ? 'text-green-400' : total >= 16 ? 'text-yellow-400' : total >= 12 ? 'text-gray-300' : 'text-red-400';
                return `<tr><td class="pr-4 text-gray-500">${name}</td><td class="${col} font-bold">${total}</td><td>${modStr}</td></tr>`;
            };
            document.getElementById('pl-stats-body').innerHTML = `
                <table class="w-full"><tbody>
                    ${statRow('Strength', p.str_base, p.str_mod)}
                    ${statRow('Intelligence', p.int_base, p.int_mod)}
                    ${statRow('Wisdom', p.wis_base, p.wis_mod)}
                    ${statRow('Dexterity', p.dex_base, p.dex_mod)}
                    ${statRow('Constitution', p.con_base, p.con_mod)}
                </tbody></table>
                <div class="mt-3 border-t border-gray-800 pt-2 text-xs grid grid-cols-2 gap-1">
                    <div><span class="text-gray-500">AC Pierce:</span> <span class="text-cyan-400">${p.ac_pierce}</span></div>
                    <div><span class="text-gray-500">AC Slash:</span>  <span class="text-cyan-400">${p.ac_slash}</span></div>
                    <div><span class="text-gray-500">AC Bash:</span>   <span class="text-cyan-400">${p.ac_bash}</span></div>
                    <div><span class="text-gray-500">AC Exotic:</span> <span class="text-cyan-400">${p.ac_exotic}</span></div>
                </div>`;

            // ---- Affects ----
            const aff = p.affects || [];
            const affCard = document.getElementById('pl-affects-card');
            if (aff.length) {
                affCard.classList.remove('hidden');
                document.getElementById('pl-affects-body').innerHTML = aff.map(a => {
                    let extra = '';
                    if (a.location && a.modifier != null) extra = ` (${a.modifier >= 0 ? '+' : ''}${a.modifier} ${escHtml(String(a.location))})`;
                    return `<div class="py-0.5 text-purple-300">${escHtml(a.spell)}${extra}<span class="text-gray-600 ml-2 text-xs">${a.duration ? a.duration+'t' : ''}</span></div>`;
                }).join('');
            } else {
                affCard.classList.add('hidden');
            }

            // ---- Look ----
            document.getElementById('pl-look-body').textContent = p.description || '(no description)';

            // ---- Equipment ----
            const equip = p.equipment || [];
            const equipEl = document.getElementById('pl-equip-body');
            if (!equip.length) {
                equipEl.innerHTML = '<div class="p-4 text-gray-600 italic text-sm">Nothing worn.</div>';
            } else {
                // Sort by wear slot
                const sorted = [...equip].sort((a, b) => (a.wear||0) - (b.wear||0));
                equipEl.innerHTML = sorted.map(item => {
                    const slotName = WEAR_SLOT_NAMES[item.wear] || ('Slot '+item.wear);
                    const affStr = (item.affects||[]).slice(0,3).map(a =>
                        `<span class="text-xs text-gray-500">${escHtml(String(a))}</span>`
                    ).join(' ');
                    return `<div class="p-3 hover:bg-[#1a1a1a] transition-colors">
                        <div class="flex justify-between items-start">
                            <div class="flex-1 min-w-0">
                                <div class="text-xs text-gray-600 font-mono uppercase tracking-wider">${escHtml(slotName)}</div>
                                <div class="text-gray-200 cursor-pointer hover:text-white hover:underline mt-0.5" onclick="showObjDetail(${item.vnum})">${escHtml(item.name)}</div>
                                <div class="mt-0.5">${affStr}</div>
                            </div>
                            <div class="text-gray-700 text-xs font-mono ml-3 shrink-0">#${item.vnum}</div>
                        </div>
                    </div>`;
                }).join('');
            }
        }

        function playerToGear() {
            if (!_currentPlayer) return;
            document.getElementById('bg-class').value = _currentPlayer.class_name || 'warrior';
            document.getElementById('bg-race').value  = _currentPlayer.race || 'human';
            document.getElementById('bg-level').value = _currentPlayer.level || 50;
            showBestGear();
        }

        // Best Gear Functions
        function showBestGear() {
            showSection('best-gear');
        }

        const _bgBreakdownMap = new Map();

        async function bgLoadFromPlayer() {
            const name = document.getElementById('bg-player-name').value.trim();
            if (!name) return;
            const loadPlayerBtn = document.getElementById('bg-load-player-btn');
            setButtonLoading(loadPlayerBtn, true, 'Loading...');
            const msg = document.getElementById('bg-player-msg');
            msg.textContent = 'Loading...';
            try {
                const res = await fetch('/api/player/' + encodeURIComponent(name));
                if (!res.ok) { msg.textContent = 'Player not found'; return; }
                const p = await res.json();
                document.getElementById('bg-class').value = p.class_name || 'warrior';
                document.getElementById('bg-race').value  = p.race      || 'human';
                document.getElementById('bg-level').value = p.level     || 50;
                msg.textContent = `Loaded ${p.name} (${p.class_name} lv${p.level})`;
                loadBestGear();
            } catch(e) {
                msg.textContent = 'Error: ' + e.message;
            } finally {
                setButtonLoading(loadPlayerBtn, false);
            }
        }

        async function loadBestGear() {
            const loadGearBtn = document.getElementById('bg-load-gear-btn');
            setButtonLoading(loadGearBtn, true, 'Finding...');
            const cls = document.getElementById('bg-class').value;
            const race = document.getElementById('bg-race').value;
            const level = document.getElementById('bg-level').value;
            const container = document.getElementById('bg-results');
            
            container.innerHTML = '<div class="text-center text-gray-500 py-12">Finding best gear...</div>';
            _bgBreakdownMap.clear();
            
            try {
                const res = await fetch(`/api/best_gear?class_name=${cls}&race_name=${race}&level=${level}&limit=5`);
                if(!res.ok) throw new Error(await res.text());
                const data = await res.json();
                
                let html = '';
                
                // Order of slots to display
                const slots = ['light', 'finger', 'neck', 'body', 'head', 'legs', 'feet', 'hands', 'arms', 'shield', 'about', 'waist', 'wrist', 'wield', 'hold'];
                
                for(const slot of slots) {
                    if(!data[slot] || data[slot].length === 0) continue;
                    
                    html += `
                        <div class="bg-[#111] rounded border border-gray-800 overflow-hidden">
                            <div class="bg-[#1a1a1a] px-4 py-2 border-b border-gray-800 font-bold text-yellow-500 uppercase text-sm tracking-wider">
                                ${slot}
                            </div>
                            <div class="divide-y divide-gray-800">
                    `;
                    
                    for(const item of data[slot]) {
                        // Store breakdown in Map keyed by vnum — avoids fragile inline string escaping
                        _bgBreakdownMap.set(item.vnum, item.score_breakdown || []);
                        html += `
                            <div class="p-3 hover:bg-[#151515] transition-colors flex justify-between items-center group">
                                <div class="flex items-center gap-3 overflow-hidden">
                                    <div class="bg-gray-900 text-gray-500 text-xs font-mono px-2 py-1 rounded">#${escHtml(item.vnum)}</div>
                                    <div class="truncate">
                                        <div class="text-gray-300 font-bold group-hover:text-white cursor-pointer hover:underline" onclick="showObjDetail(${item.vnum})">${escHtml(item.name)}</div>
                                        <div class="text-xs text-gray-500">Lvl ${escHtml(item.level)} &bull; ${escHtml(item.area || 'Unknown Area')}</div>
                                    </div>
                                </div>
                                <div class="text-right pl-4 shrink-0 cursor-pointer" onclick="showScoreBreakdown(${item.vnum})">
                                    <div class="text-green-400 font-bold text-lg">${escHtml(item.score)}</div>
                                    <div class="text-[10px] text-gray-600 uppercase tracking-wider">Score</div>
                                </div>
                            </div>
                        `;
                    }
                    
                    html += `
                            </div>
                        </div>
                    `;
                }
                
                container.innerHTML = html || '<div class="text-center text-gray-500 py-12">No gear found matching criteria</div>';
                
            } catch(e) {
                const errMsg = (e && e.message) ? e.message : String(e);
                container.innerHTML = `<div class="text-center text-red-500 py-12">Error: ${escHtml(errMsg)}</div>`;
            } finally {
                setButtonLoading(loadGearBtn, false);
            }
        }

        function showScoreBreakdown(vnum) {
            const lines = (_bgBreakdownMap.get(vnum) || []).filter(l => String(l).trim());
            const content = document.getElementById('score-modal-content');
            content.innerHTML = lines.length
                ? lines.map(l => `<div class="py-0.5 border-b border-gray-800">${escHtml(l)}</div>`).join('')
                : '<div class="text-gray-500 italic">No breakdown available</div>';
            document.getElementById('score-modal').classList.remove('hidden');
        }

        function closeScoreModal() {
            document.getElementById('score-modal').classList.add('hidden');
        }

        // ============ AREA MAP ============
        let mapData = null;
        let mapScale = 1;
        let mapPan = { x: 0, y: 0 };
        let isDragging = false;
        let dragStart = { x: 0, y: 0 };
        
        async function showAreaMap(filename) {
            try {
                const res = await fetch('/api/areas/' + encodeURIComponent(filename) + '/map');
                if(!res.ok) throw new Error('Failed to fetch map data (HTTP ' + res.status + ')');
                
                const text = await res.text();
                if(!text || text.length === 0) {
                    throw new Error('Empty response from server - server may have crashed');
                }
                
                mapData = JSON.parse(text);
                
                if(!mapData || !mapData.rooms || !Array.isArray(mapData.rooms)) {
                    throw new Error('Invalid map data received - missing rooms array');
                }
                
                document.getElementById('map-modal-title').textContent = (mapData.area_name || 'Unknown') + ' Map';
                document.getElementById('map-modal-rooms').textContent = mapData.rooms.length;
                
                // Reset view
                mapScale = 1;
                mapPan = { x: 0, y: 0 };
                document.getElementById('map-zoom-level').textContent = '100%';
                
                renderMap();
                document.getElementById('map-modal').classList.remove('hidden');
                
                // Setup pan/drag
                setupMapDrag();
            } catch(e) {
                console.error('Map loading error:', e);
                showToast('Error loading map: ' + e.message, 'error');
            }
        }
        
        function closeMapModal() {
            document.getElementById('map-modal').classList.add('hidden');
            mapData = null;
        }
        
        function mapZoom(delta, reset = false) {
            if(reset) {
                mapScale = 1;
                mapPan = { x: 0, y: 0 };
            } else {
                mapScale = Math.max(0.3, Math.min(3, mapScale + delta));
            }
            document.getElementById('map-zoom-level').textContent = Math.round(mapScale * 100) + '%';
            renderMap();
        }
        
        function setupMapDrag() {
            const container = document.getElementById('map-container');
            
            container.onmousedown = (e) => {
                isDragging = true;
                dragStart = { x: e.clientX - mapPan.x, y: e.clientY - mapPan.y };
                container.style.cursor = 'grabbing';
            };
            
            container.onmousemove = (e) => {
                if(isDragging) {
                    mapPan.x = e.clientX - dragStart.x;
                    mapPan.y = e.clientY - dragStart.y;
                    renderMap();
                }
            };
            
            container.onmouseup = () => {
                isDragging = false;
                container.style.cursor = 'grab';
            };
            
            container.onmouseleave = () => {
                isDragging = false;
                container.style.cursor = 'grab';
            };
            
            // Scroll wheel zoom
            container.onwheel = (e) => {
                e.preventDefault();
                mapZoom(e.deltaY > 0 ? -0.1 : 0.1);
            };
        }
        
        function renderMap() {
            if(!mapData || !mapData.rooms || !Array.isArray(mapData.rooms)) {
                console.error('renderMap called with invalid mapData');
                return;
            }
            
            const svg = document.getElementById('map-svg');
            const container = document.getElementById('map-container');
            const tooltip = document.getElementById('map-tooltip');
            
            const CELL_SIZE = 80 * mapScale;
            const ROOM_SIZE = 60 * mapScale;
            const PADDING = 100;
            
            // Calculate bounds
            let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
            mapData.rooms.forEach(r => {
                minX = Math.min(minX, r.x);
                maxX = Math.max(maxX, r.x);
                minY = Math.min(minY, r.y);
                maxY = Math.max(maxY, r.y);
            });
            
            const width = (maxX - minX + 1) * CELL_SIZE + PADDING * 2;
            const height = (maxY - minY + 1) * CELL_SIZE + PADDING * 2;
            
            svg.setAttribute('width', width);
            svg.setAttribute('height', height);
            svg.style.transform = `translate(${mapPan.x}px, ${mapPan.y}px)`;
            
            let html = '';
            
            // Direction names for labels
            const DIR_NAMES = ['north', 'east', 'south', 'west', 'up', 'down'];
            
            // Draw grid
            html += '<defs><pattern id="grid" width="' + CELL_SIZE + '" height="' + CELL_SIZE + '" patternUnits="userSpaceOnUse">';
            html += '<path d="M ' + CELL_SIZE + ' 0 L 0 0 0 ' + CELL_SIZE + '" fill="none" stroke="#1a1a1a" stroke-width="1"/>';
            html += '</pattern></defs>';
            html += '<rect width="100%" height="100%" fill="url(#grid)"/>';
            
            // Draw connections first (so rooms appear on top)
            mapData.rooms.forEach(room => {
                const x1 = (room.x - minX) * CELL_SIZE + PADDING + CELL_SIZE/2;
                const y1 = (room.y - minY) * CELL_SIZE + PADDING + CELL_SIZE/2;
                
                const exits = room.exits || [];
                exits.forEach(ex => {
                    const targetRoom = mapData.rooms.find(r => r.vnum === ex.to_room);
                    if(targetRoom) {
                        const x2 = (targetRoom.x - minX) * CELL_SIZE + PADDING + CELL_SIZE/2;
                        const y2 = (targetRoom.y - minY) * CELL_SIZE + PADDING + CELL_SIZE/2;
                        
                        // Color and style based on direction
                        let color = '#444';
                        let dashArray = '';
                        let strokeWidth = 3 * mapScale;
                        
                        if(ex.direction === 4) { // up
                            color = '#4477aa';
                            dashArray = '5,3';
                        } else if(ex.direction === 5) { // down
                            color = '#aa5544';
                            dashArray = '5,3';
                        }
                        
                        // Check if this is a non-cardinal exit (has keyword like climb, enter, etc)
                        const hasKeyword = ex.keyword && ex.keyword.trim().length > 0;
                        if(hasKeyword) {
                            color = '#7a7';
                            dashArray = '3,3';
                        }
                        
                        html += '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" stroke="' + color + '" stroke-width="' + strokeWidth + '"' + (dashArray ? ' stroke-dasharray="' + dashArray + '"' : '') + '/>';
                        
                        // Add label for up/down/keyword exits at midpoint
                        if(ex.direction >= 4 || hasKeyword) {
                            const midX = (x1 + x2) / 2;
                            const midY = (y1 + y2) / 2;
                            let label = hasKeyword ? ex.keyword : (DIR_NAMES[ex.direction] || '?');
                            if(label && label.length > 8) label = label.substring(0, 6) + '..';
                            html += '<rect x="' + (midX - 20) + '" y="' + (midY - 8) + '" width="40" height="16" fill="#111" rx="3"/>';
                            html += '<text x="' + midX + '" y="' + (midY + 3) + '" text-anchor="middle" fill="' + color + '" font-size="' + (9 * mapScale) + '" font-family="monospace">' + (label || '?') + '</text>';
                        }
                    }
                });
            });
            
            // Draw rooms
            mapData.rooms.forEach(room => {
                const x = (room.x - minX) * CELL_SIZE + PADDING + (CELL_SIZE - ROOM_SIZE)/2;
                const y = (room.y - minY) * CELL_SIZE + PADDING + (CELL_SIZE - ROOM_SIZE)/2;
                
                // Room color based on content
                let fillColor = '#1a1a1a';
                let strokeColor = '#444';
                if(room.mob_count > 0) {
                    fillColor = '#2a1a1a';
                    strokeColor = '#633';
                }
                if(room.obj_count > 0) {
                    fillColor = '#1a1a2a';
                    strokeColor = '#336';
                }
                if(room.mob_count > 0 && room.obj_count > 0) {
                    fillColor = '#2a1a2a';
                    strokeColor = '#636';
                }
                
                html += '<g class="map-room" data-vnum="' + room.vnum + '" style="cursor:pointer">';
                html += '<rect x="' + x + '" y="' + y + '" width="' + ROOM_SIZE + '" height="' + ROOM_SIZE + '" fill="' + fillColor + '" stroke="' + strokeColor + '" stroke-width="2" rx="4"/>';
                
                // Room name (truncated)
                const fontSize = Math.max(8, 10 * mapScale);
                const maxChars = Math.floor(ROOM_SIZE / (fontSize * 0.6));
                let name = room.name.length > maxChars ? room.name.substring(0, maxChars-2) + '..' : room.name;
                html += '<text x="' + (x + ROOM_SIZE/2) + '" y="' + (y + ROOM_SIZE/2) + '" text-anchor="middle" dominant-baseline="middle" fill="#aaa" font-size="' + fontSize + '" font-family="sans-serif">' + name.split('&').join('&amp;').split('<').join('&lt;') + '</text>';
                
                // Vnum label
                html += '<text x="' + (x + ROOM_SIZE/2) + '" y="' + (y + ROOM_SIZE - 4) + '" text-anchor="middle" fill="#555" font-size="' + (fontSize * 0.7) + '" font-family="monospace">#' + room.vnum + '</text>';
                
                // Direction indicators for up/down
                const roomExits = room.exits || [];
                const hasUp = roomExits.some(e => e.direction === 4);
                const hasDown = roomExits.some(e => e.direction === 5);
                if(hasUp) {
                    html += '<text x="' + (x + ROOM_SIZE - 8) + '" y="' + (y + 12) + '" fill="#88f" font-size="' + (fontSize * 0.8) + '">↑</text>';
                }
                if(hasDown) {
                    html += '<text x="' + (x + ROOM_SIZE - 8) + '" y="' + (y + ROOM_SIZE - 4) + '" fill="#f88" font-size="' + (fontSize * 0.8) + '">↓</text>';
                }
                
                html += '</g>';
            });
            
            svg.innerHTML = html;
            
            // Setup room interactions
            document.querySelectorAll('.map-room').forEach(el => {
                el.onmouseenter = (e) => {
                    const vnum = parseInt(el.dataset.vnum);
                    const room = mapData.rooms.find(r => r.vnum === vnum);
                    if(room) {
                        document.getElementById('map-tooltip-name').textContent = room.name;
                        document.getElementById('map-tooltip-vnum').textContent = '#' + room.vnum;
                        document.getElementById('map-tooltip-desc').textContent = room.description.substring(0, 150) + (room.description.length > 150 ? '...' : '');
                        
                        // Format exits
                        const tooltipExits = room.exits || [];
                        const exitStr = tooltipExits.map(e => {
                            const dirName = DIR_NAMES[e.direction] || 'special';
                            const kw = e.keyword && e.keyword.trim() ? ' (' + e.keyword + ')' : '';
                            return dirName + kw;
                        }).join(', ');
                        document.getElementById('map-tooltip-exits').textContent = tooltipExits.length > 0 ? 'Exits: ' + exitStr : 'No exits';
                        
                        document.getElementById('map-tooltip-mobs').textContent = room.mob_count > 0 ? 'Mobs: ' + room.mob_names.join(', ') : '';
                        document.getElementById('map-tooltip-objects').textContent = room.obj_count > 0 ? 'Objects: ' + room.obj_names.join(', ') : '';
                        tooltip.classList.remove('hidden');
                    }
                };
                
                el.onmousemove = (e) => {
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                };
                
                el.onmouseleave = () => {
                    tooltip.classList.add('hidden');
                };
                
                el.onclick = () => {
                    const vnum = parseInt(el.dataset.vnum);
                    closeMapModal();
                    showRoomDetail(vnum);
                };
            });
        }

        // ============ HASH ROUTING ============
        function parseHash() {
            const m = location.hash.match(/^#(mob|room|obj|section)\\/(.+)/);
            if (!m) return;
            const [, type, val] = m;
            if (type === 'section') { showSection(val, false); return; }
            if (type === 'mob') showMobDetail(parseInt(val));
            else if (type === 'room') showRoomDetail(parseInt(val));
            else if (type === 'obj') showObjDetail(parseInt(val));
        }
        window.addEventListener('hashchange', parseHash);
        if (location.hash) {
            parseHash();
        } else {
            const savedSection = localStorage.getItem('toc_last_section') || 'home';
            showSection(savedSection, false);
        }
    </script>
</body>
</html>
    """


@app.get("/api/health")
async def health() -> dict[str, bool | str]:
    status = read_process_health()
    return {"status": "ok", **status}


@app.get("/api/logs")
async def tail_logs(lines: int = 200, _: None = Depends(verify_token)) -> PlainTextResponse:
    lines = max(1, min(lines, 5000))  # clamp to prevent resource exhaustion
    if not DEFAULT_LOG.exists():
        return PlainTextResponse("Log file not found.", status_code=404)
    
    try:
        # Use tail command for efficiency if available (Linux/Mac)
        if os.name == 'posix':
            proc = subprocess.run(
                ['tail', '-n', str(lines), str(DEFAULT_LOG)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if proc.returncode != 0:
                err = proc.stderr.decode('utf-8', errors='replace')
                return PlainTextResponse(f"Error reading log: {err}", status_code=500)
            return PlainTextResponse(proc.stdout.decode('utf-8', errors='replace'))
        else:
            # Fallback for Windows or if tail fails
            with open(DEFAULT_LOG, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                return PlainTextResponse("".join(all_lines[-lines:]))
    except Exception as e:
        return PlainTextResponse(f"Error reading log: {e}", status_code=500)

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket, x_admin_token: str = Query(default="")):
    if _WEB_ADMIN_TOKEN and x_admin_token != _WEB_ADMIN_TOKEN:
        await websocket.close(code=4003)
        return
    await websocket.accept()
    try:
        # Send last 200 lines first
        if DEFAULT_LOG.exists():
            # Use tail for initial load
            if os.name == 'posix':
                proc = subprocess.Popen(['tail', '-n', '200', str(DEFAULT_LOG)], stdout=subprocess.PIPE)
                output, _ = proc.communicate()
                await websocket.send_text(output.decode('utf-8', errors='replace'))
            else:
                with open(DEFAULT_LOG, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    await websocket.send_text("".join(lines[-200:]))
        
        # Tail the file
        last_pos = DEFAULT_LOG.stat().st_size if DEFAULT_LOG.exists() else 0
        
        while True:
            await asyncio.sleep(1);
            if DEFAULT_LOG.exists():
                current_pos = DEFAULT_LOG.stat().st_size
                if current_pos > last_pos:
                    with open(DEFAULT_LOG, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(last_pos)
                        new_data = f.read();
                        if new_data:
                            await websocket.send_text(new_data);
                    
                    last_pos = current_pos
                elif current_pos < last_pos:
                    # File truncated/rotated
                    last_pos = 0
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


@app.post("/api/wizinfo")
async def send_wizinfo(request: WizinfoRequest, _: None = Depends(verify_token)) -> str:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    level = request.level if request.level and request.level > 0 else 62
    require_queue_writer().append(f"wizinfo|{level}|{request.message.strip()}")
    return "queued"


@app.post("/api/command")
async def run_command(request: CommandRequest, _: None = Depends(verify_token)) -> str:
    if not request.command.strip():
        raise HTTPException(status_code=400, detail="Command required")
    require_queue_writer().append(f"command|{request.command.strip()}")
    return "queued"


@app.post("/api/backup")
async def run_backup(_: None = Depends(verify_token)) -> str:
    require_queue_writer().append("backup")
    return "queued"


@app.post("/api/shutdown")
async def run_shutdown(_: None = Depends(verify_token)) -> str:
    require_queue_writer().append("shutdown")
    return "queued"


@app.post("/api/reload")
async def reload_areas(_: None = Depends(verify_token)) -> Dict[str, Any]:
    """Reload all area files from disk without restarting the server."""
    try:
        new_parser = AreaParser(AREA_PATH)
        new_parser.parse_all()
        # Swap in new data atomically
        parser.areas = new_parser.areas
        parser.mobiles = new_parser.mobiles
        parser.objects = new_parser.objects
        parser.rooms = new_parser.rooms
        AREA_MAP_CACHE.clear()
        return {
            "status": "ok",
            "areas": len(parser.areas),
            "mobiles": len(parser.mobiles),
            "objects": len(parser.objects),
            "rooms": len(parser.rooms),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload failed: {e}")


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


# Validate player names: letters only, 1-20 chars (matches MUD naming rules)
import re as _re
_PLAYER_NAME_RE = _re.compile(r'^[A-Za-z]{1,20}$')


@app.get("/api/players")
async def list_players() -> list[str]:
    """Return sorted list of all player names (extension-less files only)."""
    try:
        return sorted(
            (
                p.name for p in PLAYER_PATH.iterdir()
                if p.is_file() and p.suffix == "" and not p.name.startswith(".")
            ),
            key=str.lower,
        )
    except Exception:
        return []


@app.get("/api/player/{name}")
async def get_player(name: str) -> Dict[str, Any]:
    """Return full parsed player profile."""
    if not _PLAYER_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid player name")
    data = parse_player_file(name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Player '{name}' not found")
    return data


@app.get("/api/mobs")
async def get_mobs(limit: int = 10000) -> list:
    limit = max(1, min(limit, 50000))
    result = []
    for i, (vnum, mob) in enumerate(sorted(parser.mobiles.items())):
        if i >= limit:
            break
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
async def get_rooms(limit: int = 10000) -> list:
    limit = max(1, min(limit, 50000))
    result = []
    for i, (vnum, room) in enumerate(sorted(parser.rooms.items())):
        if i >= limit:
            break
            
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
    limit: int = 10000,
    name: Optional[str] = None,
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    item_type: Optional[str] = None,
    wear_flag: Optional[str] = None,
    extra_flags: Optional[str] = None,
    stat_filter: Optional[str] = None
) -> list:
    limit = max(1, min(limit, 50000))
    result = []
    count = 0
    
    for vnum, obj in sorted(parser.objects.items()):
        if count >= limit:
            break
            
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
        
        # Decode affects
        affects_decoded = decode_applies(obj.affects)
        
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
        count += 1
    
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
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    writer = None
    try:
        # Connect to the C Game Server
        reader, writer = await asyncio.open_connection(MUD_HOST, MUD_PORT)
        
        async def mud_to_ws():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data: 
                        break
                    # Decode Latin-1 (standard for MUDs) to send to Browser (UTF-8 auto handled by websocket lib)
                    await websocket.send_text(data.decode('latin-1', errors='replace'))
            except Exception as e:
                print(f"mud_to_ws error: {e}")

        async def ws_to_mud():
            try:
                while True:
                    data = await websocket.receive_text()
                    writer.write(data.encode('latin-1', errors='replace'))
                    await writer.drain()
            except WebSocketDisconnect:
                pass
            except Exception as e:
                print(f"ws_to_mud error: {e}")

        # Run both tasks until one fails
        done, pending = await asyncio.wait(
            [asyncio.create_task(mud_to_ws()), asyncio.create_task(ws_to_mud())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            
    except Exception as e:
        print(f"Connection Error: {e}")
    finally:
        if writer:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
    

if __name__ == "__main__":
    import uvicorn
    
    arg_parser = argparse.ArgumentParser(description="ToC Web Admin Server")
    arg_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    arg_parser.add_argument("--port", type=int, default=9001, help="Port to bind to")
    arg_parser.add_argument("--queue", type=Path, default=QUEUE_PATH, help="Path to command queue file")
    arg_parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG, help="Path to log file")
    arg_parser.add_argument("--area-path", type=Path, default=AREA_PATH, help="Path to area files")
    
    args = arg_parser.parse_args()
    
    # Update globals
    QUEUE_PATH = args.queue
    DEFAULT_LOG = args.log_file
    AREA_PATH = args.area_path
    
    uvicorn.run(app, host=args.host, port=args.port)
