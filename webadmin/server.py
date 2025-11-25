from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio

try:
    from webadmin.area_parser import AreaParser, APPLY_LOCATIONS
    from webadmin.area_parser import decode_applies, decode_flags, ITEM_FLAGS, ITEM_FLAGS2, WEAR_FLAGS, ITEM_TYPES, interpret_values, interpret_mob_values
except ImportError:
    from area_parser import AreaParser, APPLY_LOCATIONS
    from area_parser import decode_applies, decode_flags, ITEM_FLAGS, ITEM_FLAGS2, WEAR_FLAGS, ITEM_TYPES, interpret_values, interpret_mob_values

# Default paths
QUEUE_PATH: Path = Path(os.getenv("QUEUE_PATH", "area/webadmin.queue"))
DEFAULT_LOG: Path = Path(os.getenv("LOG_FILE", "log/toc.log"))
AREA_PATH: Path = Path(os.getenv("AREA_PATH", "area"))

app = FastAPI(title="ToC Web Admin", version="1.0")


class CommandRequest(BaseModel):
    command: str


class WizinfoRequest(BaseModel):
    message: str
    level: Optional[int] = None


class QueueWriter:
    def __init__(self, queue_path: Path) -> None:
        self.queue_path = queue_path
        self.queue_path.touch(exist_ok=True)

    def append(self, line: str) -> None:
        with self.queue_path.open("a", encoding="utf-8") as queue_file:
            queue_file.write(line.rstrip("\n") + "\n")


queue_writer: Optional[QueueWriter] = None

# Class stat weights for gear optimization
CLASS_WEIGHTS = {
    "mage": {
        "intelligence": 2.0, "mana": 1.0, "save vs spell": 1.0, "hit points": 0.5,
        "constitution": 0.5, "dexterity": 0.5
    },
    "cleric": {
        "wisdom": 2.0, "mana": 1.0, "save vs spell": 1.0, "hit points": 0.8,
        "constitution": 0.5, "strength": 0.2
    },
    "thief": {
        "dexterity": 2.0, "hitroll": 1.5, "damroll": 1.5, "hit points": 0.8,
        "strength": 0.5, "constitution": 0.5
    },
    "warrior": {
        "strength": 1.5, "constitution": 1.5, "hitroll": 1.5, "damroll": 1.5, 
        "hit points": 1.0, "dexterity": 0.5
    },
    "monk": {
        "constitution": 2.0, "strength": 1.0, "hitroll": 1.5, "damroll": 1.5, 
        "hit points": 1.0, "dexterity": 0.8
    },
    "necromancer": {
        "intelligence": 2.0, "mana": 1.0, "save vs spell": 1.0, "hit points": 0.5,
        "constitution": 0.5, "dexterity": 0.5
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

# Initialize parser and load area files
print(f"DEBUG: AreaParser file: {AreaParser.__module__}")
try:
    print(f"DEBUG: AreaParser path: {AreaParser.__file__}") # This might fail if it's a class
except:
    import inspect
    print(f"DEBUG: AreaParser source: {inspect.getfile(AreaParser)}")

parser = AreaParser(AREA_PATH)
try:
    parser.parse_all()
    print(f"Loaded: {len(parser.mobiles)} mobs, {len(parser.objects)} objects, {len(parser.rooms)} rooms, {len(parser.areas)} areas")
except Exception as e:
    print(f"Warning: Failed to parse areas: {e}")


def read_process_health() -> dict[str, bool]:
    # Check if processes are running by looking at /proc filesystem
    merc_running = False
    webadmin_running = False
    
    try:
        # Check /proc for running processes
        result = subprocess.run(
            ["sh", "-c", r"cat /proc/*/cmdline 2>/dev/null | tr '\000' '\n'"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode == 0:
            output = result.stdout.lower()
            merc_running = "merc" in output
            webadmin_running = "webadmin.server" in output
    except Exception:
        pass
    
    return {
        "merc": merc_running,
        "webadmin": webadmin_running,
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
        
        .tab-content { display: none; }
        .tab-content.active { display: block; }
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
                <div class="hidden md:block">
                    <div class="ml-10 flex items-baseline space-x-8">
                        <span onclick="showSection('home')" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Home</span>
                        <span onclick="showSection('play')" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Play Now</span>
                        <span onclick="showSection('database')" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Database</span>
                        <span onclick="showSection('guide')" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">How to Play</span>
                        <span onclick="showSection('admin')" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer">Admin</span>
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
                <span onclick="showSection('home')" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Home</span>
                <span onclick="showSection('play')" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Play Now</span>
                <span onclick="showSection('database')" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Database</span>
                <span onclick="showSection('guide')" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">How to Play</span>
                <span onclick="showSection('admin')" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium cursor-pointer">Admin</span>
            </div>
        </div>
    </nav>

    <!-- Main Content Container -->
    <div class="pt-20 flex-grow">
        
        <!-- HOME SECTION -->
        <div id="home-section" class="tab-content active">
            <!-- Hero Section -->
            <section class="hero-pattern relative h-screen flex items-center justify-center">
                <div class="absolute inset-0 bg-gradient-to-b from-transparent via-black/50 to-[#0a0a0a]"></div>
                <div class="relative z-10 text-center px-4 max-w-4xl mx-auto">
                    <div class="mb-6 inline-block">
                        <span class="py-1 px-3 rounded-full bg-red-900/30 border border-red-800/50 text-red-400 text-xs font-bold tracking-widest uppercase">
                            Legacy MUD Engine Reborn
                        </span>
                    </div>
                    <h1 class="text-5xl md:text-7xl font-bold text-white mb-6 tracking-tight drop-shadow-2xl">
                        ENTER THE <span class="text-red-600">CHAOS</span>
                    </h1>
                    <p class="text-xl text-gray-300 mb-10 max-w-2xl mx-auto leading-relaxed">
                        A text-based MMORPG experience powered by the classic ROM codebase. 
                        Explore persistent realms, battle legendary monsters, and forge your legacy in pure text.
                    </p>
                    <div class="flex flex-col sm:flex-row gap-4 justify-center">
                        <button onclick="showSection('play')" class="btn-primary px-8 py-4 rounded text-lg font-bold flex items-center justify-center gap-2 group">
                            <i class="fa-solid fa-terminal"></i> CONNECT NOW
                            <i class="fa-solid fa-arrow-right group-hover:translate-x-1 transition-transform"></i>
                        </button>
                        <a href="https://github.com/jeremydbean/tocgpt" target="_blank" class="px-8 py-4 rounded border border-gray-600 hover:border-white bg-transparent text-white text-lg font-bold flex items-center justify-center gap-2 transition-all hover:bg-white/5">
                            <i class="fa-brands fa-github"></i> VIEW SOURCE
                        </a>
                    </div>
                </div>
            </section>

            <!-- Features Grid -->
            <section class="py-20 bg-[#0f0f0f]">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="text-center mb-16">
                        <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">A World of Text</h2>
                        <p class="text-gray-400 max-w-2xl mx-auto">Features derived from the legendary ROM architecture, enhanced for the modern era.</p>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                        <div class="stat-card p-8 rounded-lg text-center">
                            <div class="w-16 h-16 bg-red-900/20 rounded-full flex items-center justify-center mx-auto mb-6 text-red-500">
                                <i class="fa-solid fa-skull-crossbones text-2xl"></i>
                            </div>
                            <h3 class="text-xl font-bold text-white mb-3">Tactical Combat</h3>
                            <p class="text-gray-400 text-sm leading-relaxed">
                                Real-time text combat based on THAC0 mechanics. Manage your skills, spells, and equipment weight to survive against legendary mobs.
                            </p>
                        </div>
                        <div class="stat-card p-8 rounded-lg text-center">
                            <div class="w-16 h-16 bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-6 text-blue-500">
                                <i class="fa-solid fa-hat-wizard text-2xl"></i>
                            </div>
                            <h3 class="text-xl font-bold text-white mb-3">Complex Magic</h3>
                            <p class="text-gray-400 text-sm leading-relaxed">
                                Hundreds of spells across distinct schools of magic. From simple heals to room-clearing chaos storms. Mana management is key.
                            </p>
                        </div>
                        <div class="stat-card p-8 rounded-lg text-center">
                            <div class="w-16 h-16 bg-yellow-900/20 rounded-full flex items-center justify-center mx-auto mb-6 text-yellow-500">
                                <i class="fa-solid fa-scroll text-2xl"></i>
                            </div>
                            <h3 class="text-xl font-bold text-white mb-3">50+ Custom Areas</h3>
                            <p class="text-gray-400 text-sm leading-relaxed">
                                Explore thousands of unique rooms defined in our `.are` files. Visit Midgaard, Moria, or the dangerous realm of Thalos.
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
                                <div>Status: <span id="connection-status" class="text-yellow-500">Connecting...</span></div>
                                <div>Host: localhost:9000</div>
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

                    <div class="flex gap-4 mb-6">
                        <input type="text" id="db-search" placeholder="Search loaded data..." class="flex-1 bg-[#151515] border border-gray-800 rounded px-4 py-3 text-white focus:border-red-700 outline-none" onkeyup="filterDb()">
                    </div>

                    <!-- Advanced Filters (Objects Only) -->
                    <div id="obj-filter-container" class="hidden w-full mb-6">
                        <div class="flex justify-end mb-2">
                            <button onclick="toggleFilters()" class="px-4 py-2 rounded bg-gray-800 text-gray-300 hover:bg-gray-700 border border-gray-600 transition-colors flex items-center gap-2">
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
                            <div class="md:col-span-3 flex justify-end">
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
                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Getting Started</h3>
                            <div class="prose prose-invert max-w-none text-gray-300">
                                <p>Welcome to Times of Chaos. When you first connect, you will be asked to provide a name for your character. Choose wisely, as this is how you will be known throughout the realms.</p>
                                <p>After naming your character, you will select a race and a class. Each combination offers unique strengths and weaknesses.</p>
                            </div>
                        </div>

                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Basic Commands</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <code class="text-yellow-500 font-bold">look</code>
                                    <p class="text-sm text-gray-400 mt-1">Examine your current surroundings.</p>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <code class="text-yellow-500 font-bold">score</code>
                                    <p class="text-sm text-gray-400 mt-1">View your character's attributes and status.</p>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <code class="text-yellow-500 font-bold">inventory</code>
                                    <p class="text-sm text-gray-400 mt-1">See what you are carrying.</p>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <code class="text-yellow-500 font-bold">equipment</code>
                                    <p class="text-sm text-gray-400 mt-1">See what you are wearing.</p>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <code class="text-yellow-500 font-bold">north, south, east, west</code>
                                    <p class="text-sm text-gray-400 mt-1">Move in a direction.</p>
                                </div>
                                <div class="bg-[#151515] p-4 rounded border border-gray-800">
                                    <code class="text-yellow-500 font-bold">kill &lt;target&gt;</code>
                                    <p class="text-sm text-gray-400 mt-1">Initiate combat with a monster.</p>
                                </div>
                            </div>
                        </div>

                        <div>
                            <h3 class="text-2xl font-cinzel text-red-500 mb-4">Combat & Magic</h3>
                            <div class="prose prose-invert max-w-none text-gray-300">
                                <p>Combat is automatic once initiated. You will automatically attack every round. However, you can use special skills or cast spells during combat to turn the tide.</p>
                                <ul class="list-disc pl-5 space-y-2 mt-2">
                                    <li><strong class="text-white">Warriors</strong> should use <code class="text-red-400">kick</code> and <code class="text-red-400">bash</code> to disable opponents.</li>
                                    <li><strong class="text-white">Mages</strong> cast spells using <code class="text-blue-400">cast 'spell name' &lt;target&gt;</code>.</li>
                                    <li><strong class="text-white">Clerics</strong> can heal using <code class="text-yellow-400">cast 'heal' &lt;target&gt;</code>.</li>
                                    <li><strong class="text-white">Thieves</strong> can <code class="text-green-400">backstab</code> for massive opening damage.</li>
                                </ul>
                            </div>
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
                                <div class="flex gap-4">
                                    <button onclick="action('backup')" class="flex-1 px-4 py-2 rounded bg-blue-900/30 text-blue-400 hover:bg-blue-900/50 border border-blue-900 transition-colors">
                                        <i class="fa-solid fa-save mr-2"></i> Backup
                                    </button>
                                    <button onclick="action('shutdown')" class="flex-1 px-4 py-2 rounded bg-red-900/30 text-red-400 hover:bg-red-900/50 border border-red-900 transition-colors">
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

        <!-- Room Detail Modal -->
        <div id="room-modal" class="fixed inset-0 bg-black/80 hidden z-50 flex items-center justify-center p-4">
            <div class="bg-[#1a1a1a] border border-gray-700 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
                <div class="p-6">
                    <div class="flex justify-between items-start mb-6 border-b border-gray-800 pb-4">
                        <div>
                            <h3 id="room-modal-title" class="text-2xl font-bold text-white font-cinzel">Room Name</h3>
                            <div class="text-gray-500 font-mono text-sm mt-1">Vnum: <span id="room-modal-vnum" class="text-gray-300">#1234</span></div>
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

    </div>

    <!-- Footer -->
    <footer class="bg-black border-t border-gray-900 py-12">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row justify-between items-center gap-6">
            <div class="text-gray-500 text-sm">
                &copy; 2023 tocGPT Project. Based on Merc/ROM Codebase.
            </div>
            <div class="flex gap-6">
                <a href="#" class="text-gray-500 hover:text-white"><i class="fa-brands fa-discord text-xl"></i></a>
                <a href="#" class="text-gray-500 hover:text-white"><i class="fa-brands fa-twitter text-xl"></i></a>
                <a href="https://github.com/jeremydbean/tocgpt" class="text-gray-500 hover:text-white"><i class="fa-brands fa-github text-xl"></i></a>
            </div>
        </div>
    </footer>

    <script>
        // Navigation
        console.log("Script loading...");
        
        // Ensure DOM is ready
        document.addEventListener('DOMContentLoaded', function() {
            console.log("DOM Content Loaded");
        });
        
        function showSection(id) {
            console.log("showSection called with id:", id);
            try {
                document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                const targetSection = document.getElementById(id + '-section');
                console.log("Target section:", targetSection);
                if(targetSection) {
                    targetSection.classList.add('active');
                    console.log("Section activated successfully");
                } else {
                    console.error("Section not found:", id + '-section');
                }
                
                // Close mobile menu if open
                const mobileMenu = document.getElementById('mobile-menu');
                if(mobileMenu) {
                    mobileMenu.classList.add('hidden');
                }

                if(id === 'play') initTerminal();
                if(id === 'admin') refreshLogs();
            } catch(e) {
                console.error("Error in showSection:", e);
            }
        }

        function toggleMobileMenu() {
            const menu = document.getElementById('mobile-menu');
            menu.classList.toggle('hidden');
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('Port copied to clipboard!');
            });
        }

        // ============ TERMINAL / WEBSOCKET ============
        let ws = null;
        let term = null;
        let fitAddon = null;
        let termInitialized = false;

        function initTerminal() {
            if(termInitialized) return;
            termInitialized = true;

            const container = document.getElementById('terminal-container');
            const status = document.getElementById('connection-status');

            // Initialize xterm.js
            term = new Terminal({
                cursorBlink: true,
                fontFamily: '"Roboto Mono", monospace',
                fontSize: 12,
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

            function connect() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                ws = new WebSocket(protocol + '//' + window.location.host + '/ws');

                ws.onopen = () => {
                    status.textContent = 'Connected';
                    status.className = 'text-green-500';
                    term.writeln('\x1b[32mConnected to server.\x1b[0m');
                };

                ws.onmessage = (event) => {
                    term.write(event.data);
                };

                ws.onclose = () => {
                    status.textContent = 'Disconnected';
                    status.className = 'text-red-500';
                    term.writeln('\x1b[31mConnection lost. Reconnecting in 3s...\x1b[0m');
                    setTimeout(connect, 3000);
                };

                ws.onerror = (err) => {
                    console.error('WebSocket error:', err);
                    ws.close();
                };
            }

            // Handle input
            term.onData(data => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(data);
                }
            });

            connect();
        }

        // ============ DATABASE ============
        let currentDb = 'mobs';
        let dbData = { mobs: [], objects: [], areas: [] };

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('stat-mobs').textContent = data.mobiles;
                document.getElementById('stat-objs').textContent = data.objects;
                document.getElementById('stat-rooms').textContent = data.rooms;
                document.getElementById('stat-areas').textContent = data.areas;
            } catch(e) {
                console.error("Error loading stats:", e);
            }
        }
        
        // Call on load
        loadStats();

        function toggleFilters() {
            const el = document.getElementById('advanced-filters');
            el.classList.toggle('hidden');
        }

        async function loadDb(type, forceRefresh = false) {
            currentDb = type;
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
                let url = '/api/' + type + (type === 'areas' ? '' : '?limit=1000');
                
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
                content.innerHTML = `<tr><td colspan="5" class="p-4 text-center text-red-500">Error loading data: ${e}</td></tr>`;
            }
        }

        function renderDb(data) {
            const headers = document.getElementById('db-headers');
            const content = document.getElementById('db-content');
            
            let headerHtml = '';
            let rowsHtml = '';

            if(currentDb === 'mobs') {
                headerHtml = '<th class="p-4">Vnum</th><th class="p-4">Name</th><th class="p-4">Level</th><th class="p-4">Race</th><th class="p-4">Area</th>';
                rowsHtml = data.map(m => `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-mono text-sm text-gray-500">#${m.vnum}</td>
                        <td class="p-4 font-bold text-gray-300">${m.short_desc || 'Unnamed'}</td>
                        <td class="p-4 text-yellow-500">${m.level}</td>
                        <td class="p-4 text-gray-400">${m.race}</td>
                        <td class="p-4 text-gray-500 text-sm">${m.area || '-'}</td>
                    </tr>
                `).join('');
            } else if(currentDb === 'objects') {
                headerHtml = '<th class="p-4">Vnum</th><th class="p-4">Name</th><th class="p-4">Type</th><th class="p-4">Level</th><th class="p-4">Details</th>';
                rowsHtml = data.map(o => {
                    // Build affects display
                    let affectsHtml = '';
                    if(o.affects && o.affects.length > 0) {
                        affectsHtml = '<div class="mt-2"><strong class="text-green-400">Affects:</strong> ' + 
                            o.affects.map(a => `<span class="text-green-300">${a}</span>`).join(', ') + '</div>';
                    }
                    
                    // Build flags display
                    let flagsHtml = '';
                    if((o.flags && o.flags.length > 0) || (o.flags2 && o.flags2.length > 0)) {
                        let allFlags = [...(o.flags || []), ...(o.flags2 || [])];
                        flagsHtml = '<div class="mt-1"><strong class="text-purple-400">Flags:</strong> ' + 
                            allFlags.map(f => `<span class="text-purple-300">${f}</span>`).join(', ') + '</div>';
                    }
                    
                    // Build wear locations
                    let wearHtml = '';
                    if(o.wear_locations && o.wear_locations.length > 0) {
                        wearHtml = '<div class="mt-1"><strong class="text-blue-400">Wear:</strong> ' + 
                            o.wear_locations.map(w => `<span class="text-blue-300">${w}</span>`).join(', ') + '</div>';
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
                            o.carried_by.slice(0, 3).map(m => `<span class="text-yellow-300">${m.name} (${m.level})</span>`).join(', ');
                        if(o.carried_by.length > 3) {
                            carriersHtml += ` <span class="text-gray-500">+${o.carried_by.length - 3} more</span>`;
                        }
                        carriersHtml += '</div>';
                    }
                    
                    return `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-mono text-sm text-gray-500 align-top">#${o.vnum}</td>
                        <td class="p-4 font-bold text-gray-300 align-top">
                            ${o.short_desc || 'Unnamed'}
                            <div class="text-xs text-gray-500 mt-1">${o.material || 'unknown'}</div>
                        </td>
                        <td class="p-4 text-blue-400 align-top">${o.item_type}</td>
                        <td class="p-4 text-yellow-500 align-top">
                            ${o.level}
                            <div class="text-xs text-gray-500 mt-1">
                                ${o.weight}lb / ${o.cost}g
                            </div>
                        </td>
                        <td class="p-4 text-sm align-top">
                            ${affectsHtml}
                            ${statsHtml}
                            ${flagsHtml}
                            ${wearHtml}
                            ${carriersHtml}
                            <div class="mt-1 text-xs text-gray-600">${o.area || '-'}</div>
                        </td>
                    </tr>
                `;
                }).join('');
            } else if(currentDb === 'areas') {
                headerHtml = '<th class="p-4">Name</th><th class="p-4">Filename</th><th class="p-4">Builders</th><th class="p-4">Vnums</th>';
                rowsHtml = data.map(a => `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-bold text-gray-300">${a.name}</td>
                        <td class="p-4 font-mono text-sm text-gray-500">${a.filename}</td>
                        <td class="p-4 text-gray-400">${a.builders}</td>
                        <td class="p-4 text-gray-500 text-sm">${a.vnums}</td>
                    </tr>
                `).join('');
            } else if(currentDb === 'rooms') {
                headerHtml = '<th class="p-4">Vnum</th><th class="p-4">Name</th><th class="p-4">Area</th><th class="p-4">Sector</th><th class="p-4">Actions</th>';
                rowsHtml = data.map(r => `
                    <tr class="hover:bg-[#151515] transition-colors">
                        <td class="p-4 font-mono text-sm text-gray-500">#${r.vnum}</td>
                        <td class="p-4 font-bold text-gray-300">${r.name}</td>
                        <td class="p-4 text-gray-500 text-sm">${r.area || '-'}</td>
                        <td class="p-4 text-gray-400">${r.sector_type}</td>
                        <td class="p-4">
                            <button onclick="showRoomDetail(${r.vnum})" class="text-xs bg-gray-800 hover:bg-gray-700 text-white px-2 py-1 rounded border border-gray-600">View</button>
                        </td>
                    </tr>
                `).join('');
            }

            headers.innerHTML = headerHtml;
            content.innerHTML = rowsHtml || '<tr><td colspan="5" class="p-4 text-center">No results found</td></tr>';
        }

        function filterDb() {
            const q = document.getElementById('db-search').value.toLowerCase();
            const filtered = dbData[currentDb].filter(item => 
                JSON.stringify(item).toLowerCase().includes(q)
            );
            renderDb(filtered);
        }

        // ============ ADMIN ============
        async function action(type) {
            if(!confirm('Are you sure?')) return;
            try {
                await fetch('/api/' + type, { method: 'POST' });
                alert(type + ' queued successfully');
            } catch(e) { alert('Error: ' + e); }
        }

        async function sendWizInfo(e) {
            e.preventDefault();
            const msg = document.getElementById('wizinfo-msg').value;
            const level = document.getElementById('wizinfo-level').value;
            try {
                await fetch('/api/wizinfo', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg, level: parseInt(level)})
                });
                alert('Broadcast queued');
                e.target.reset();
            } catch(e) { alert('Error: ' + e); }
        }

        async function sendCommand(e) {
            e.preventDefault();
            const cmd = document.getElementById('server-cmd').value;
            try {
                await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({command: cmd})
                });
                alert('Command queued');
                e.target.reset();
            } catch(e) { alert('Error: ' + e); }
        }

        async function refreshLogs() {
            const el = document.getElementById('log-terminal');
            try {
                const res = await fetch('/api/logs');
                el.textContent = await res.text();
                el.scrollTop = el.scrollHeight;
            } catch(e) { el.textContent = 'Error loading logs'; }
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
            } catch (e) {
                console.error("Status check failed", e);
            }
        }
        
        setInterval(checkStatus, 30000);
        checkStatus();

        // Room Modal Functions
        async function showRoomDetail(vnum) {
            try {
                const res = await fetch(`/api/rooms/${vnum}`);
                if(!res.ok) throw new Error('Failed to fetch room');
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
                            <div class="text-yellow-500 font-bold uppercase text-xs">${ex.direction}</div>
                            <div class="text-gray-400 text-xs truncate" title="${ex.to_room_name}">${ex.to_room_name}</div>
                            <div class="text-gray-600 text-[10px] font-mono">#${ex.to_room}</div>
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
                            <span class="text-red-300 truncate" title="${m.name}">${m.name}</span>
                            <span class="text-gray-600 text-xs font-mono">#${m.vnum}</span>
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
                            <span class="text-blue-300 truncate" title="${o.name}">${o.name}</span>
                            <span class="text-gray-600 text-xs font-mono">#${o.vnum}</span>
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
                            <span class="text-green-400 font-bold text-xs">${ed.keyword}:</span>
                            <span class="text-gray-400 text-sm">${ed.description}</span>
                        </div>
                    `).join('');
                } else {
                    extrasContainer.innerHTML = '<div class="text-gray-500 italic text-sm">None</div>';
                }
                
                document.getElementById('room-modal').classList.remove('hidden');
            } catch(e) {
                alert('Error loading room details: ' + e);
            }
        }
        
        function closeRoomModal() {
            document.getElementById('room-modal').classList.add('hidden');
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
async def tail_logs(lines: int = 200) -> HTMLResponse:
    log_dir = Path("/app/log")
    
    # Try to read DEFAULT_LOG first (toc.log)
    if DEFAULT_LOG.exists():
        log_lines = DEFAULT_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
        return HTMLResponse("\n".join(log_lines))
    
    # Fall back to aggregating numbered log files
    if not log_dir.exists():
        raise HTTPException(status_code=404, detail="Log directory not found")
    
    # Get all numbered log files and sort by modification time
    log_files = sorted(
        [f for f in log_dir.glob("*.log") if f.name.replace(".log", "").isdigit()],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    
    if not log_files:
        raise HTTPException(status_code=404, detail="No log files found")
    
    # Aggregate lines from the most recent log files
    all_lines = []
    for log_file in log_files[:10]:  # Read up to 10 most recent logs
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            all_lines.extend(content.splitlines())
            if len(all_lines) >= lines:
                break
        except Exception:
            continue
    
    return HTMLResponse("\n".join(all_lines[-lines:]))


@app.post("/api/wizinfo")
async def send_wizinfo(request: WizinfoRequest) -> str:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    level = request.level if request.level and request.level > 0 else 62
    queue_writer.append(f"wizinfo|{level}|{request.message.strip()}")
    return "queued"


@app.post("/api/command")
async def run_command(request: CommandRequest) -> str:
    if not request.command.strip():
        raise HTTPException(status_code=400, detail="Command required")
    queue_writer.append(f"command|{request.command.strip()}")
    return "queued"


@app.post("/api/backup")
async def run_backup() -> str:
    queue_writer.append("backup")
    return "queued"


@app.post("/api/shutdown")
async def run_shutdown() -> str:
    queue_writer.append("shutdown")
    return "queued"


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
    decoded_extra_flags = decode_flags(obj.extraFlags, ITEM_FLAGS)
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
        "extra_flags": decoded_extra_flags,
        "extra_flags_raw": obj.extraFlags,
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


@app.get("/api/mobs")
async def get_mobs(limit: int = 500) -> list:
    result = []
    for i, (vnum, mob) in enumerate(parser.mobiles.items()):
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
async def get_rooms(limit: int = 300) -> list:
    result = []
    for i, (vnum, room) in enumerate(parser.rooms.items()):
        if i >= limit:
            break
        result.append({
            "vnum": room.vnum,
            "name": room.name,
            "description": room.description,
            "sector_type": room.sector_type,
            "area": room.area_name,
            "area_file": room.area_file
        })
    return result


@app.get("/api/areas")
async def get_areas() -> list:
    result = []
    try:
        for area in parser.areas.values():
            result.append({
                "name": area.name,
                "filename": area.filename,
                "builders": area.builders,
                "vnums": getattr(area, "vnums", "")
            })
    except Exception as e:
        print(f"Error in get_areas: {e}")
        # Return partial result or empty list instead of 500
        return result
    return result


@app.get("/api/objects")
async def get_objects(
    limit: int = 500,
    name: Optional[str] = None,
    min_level: Optional[int] = None,
    max_level: Optional[int] = None,
    item_type: Optional[str] = None,
    wear_flag: Optional[str] = None,
    extra_flags: Optional[str] = None,
    stat_filter: Optional[str] = None
) -> list:
    result = []
    count = 0
    
    for vnum, obj in parser.objects.items():
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
        except (ValueError, TypeError):
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
                    for aff in affects_decoded:
                        if s_name.lower() in aff['location'].lower() and aff['modifier'] > s_val:
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
            to_room_name = to_room.name;
            
        exits_data.append({
            "direction": parser.DIRECTIONS[ex.direction] if 0 <= ex.direction < len(parser.DIRECTIONS) else str(ex.direction),
            "to_room": ex.to_room,
            "to_room_name": to_room_name,
            "keyword": ex.keyword,
            "locks": ex.locks,
            "key_vnum": ex.key_vnum
        })

    return {
        "vnum": room.vnum,
        "name": room.name,
        "description": room.description,
        "area": room.area_name,
        "area_file": room.area_file,
        "room_flags": room.room_flags,
        "sector_type": room.sector_type,
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
                "short_desc": obj.short_desc
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
        "form": mob.form,
        "parts": mob.parts,
        "size": mob.size,
        "material": mob.material,
        "act_flags_raw": mob.act_flags,
        "affected_by_raw": mob.affected_by,
        "off_flags_raw": mob.off_flags,
        "imm_flags_raw": mob.imm_flags,
        "res_flags_raw": mob.res_flags,
        "vuln_flags_raw": mob.vuln_flags,
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
        affects_decoded = decode_applies(obj.affects)
        
        for aff in obj.affects:
            loc_id = aff.get('location', 0)
            val = aff.get('modifier', 0)
            loc_name = APPLY_LOCATIONS.get(loc_id, '').lower()
            
            if loc_name in weights:
                score += val * weights[loc_name]
            elif loc_name == 'armor class':
                # Negative AC is good in ROM, so multiply by -1 to make it a positive score
                score += (val * -1.0)
                
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
                score += avg_dam * 2.0 # Weight weapon damage highly
            except:
                pass
                
        if score <= 0:
            continue
        
        # Add to best items per slot
        wear_decoded = decode_flags(obj.wear_flags, WEAR_FLAGS)
        for slot in wear_decoded:
            if slot == "take": continue
            
            if slot not in best_items:
                best_items[slot] = []
            
            best_items[slot].append({
                "score": round(score, 2),
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
    
    # Initialize parser
    print(f"DEBUG: AreaParser file: {AreaParser.__module__}")
    print(f"DEBUG: AreaParser source: {AreaParser.__init__.__code__.co_filename}")
    parser = AreaParser(AREA_PATH)
    parser.parse_all()
    print(f"Loaded: {len(parser.mobiles)} mobs, {len(parser.objects)} objects, {len(parser.rooms)} rooms, {len(parser.areas)} areas")
    
    uvicorn.run(app, host=args.host, port=args.port)
