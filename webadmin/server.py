from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import asyncio

try:
    from webadmin.area_parser import AreaParser
    from webadmin.area_parser import decode_applies, decode_flags, ITEM_FLAGS, WEAR_FLAGS, ITEM_TYPES, interpret_values
except ImportError:
    from area_parser import AreaParser
    from area_parser import decode_applies, decode_flags, ITEM_FLAGS, WEAR_FLAGS, ITEM_TYPES, interpret_values

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

# Initialize parser and load area files
print(f"Loading areas from {AREA_PATH}...")
parser = AreaParser(AREA_PATH)
try:
    parser.parse_all()
    print(f"Loaded: {len(parser.mobiles)} mobs, {len(parser.objects)} objects, {len(parser.rooms)} rooms, {len(parser.areas)} areas")
except Exception as e:
    print(f"Warning: Failed to parse areas: {e}")


def read_process_health() -> dict[str, bool]:
    merc_running = subprocess.run(
        ["sh", "-c", "pgrep -f 'merc' >/dev/null"],
        check=False,
    ).returncode
    webadmin_running = subprocess.run(
        ["sh", "-c", "pgrep -f 'uvicorn .*webadmin.server' >/dev/null"],
        check=False,
    ).returncode
    return {
        "merc": merc_running == 0,
        "webadmin": webadmin_running == 0,
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
                                <div class="bg-black p-4 rounded border border-gray-800 h-[600px] font-mono text-sm overflow-y-auto relative flex flex-col" id="terminal-container">
                                    <div class="flex-grow overflow-y-auto mb-2" id="terminal-output">
                                        <div class="text-green-500 space-y-1">
                                            <p>Initializing Web Client...</p>
                                            <p>Connecting to WebSocket Bridge...</p>
                                        </div>
                                    </div>
                                    <div class="flex gap-2 border-t border-gray-800 pt-2">
                                        <span class="text-green-500">></span>
                                        <input type="text" id="terminal-input" class="bg-transparent border-none outline-none text-gray-200 flex-grow font-mono" autocomplete="off" autofocus>
                                    </div>
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
                    
                    <div class="flex gap-4 mb-8">
                        <button onclick="loadDb('mobs')" class="px-4 py-2 rounded bg-red-900/20 text-red-400 hover:bg-red-900/40 border border-red-900/50 transition-colors">Mobiles</button>
                        <button onclick="loadDb('objects')" class="px-4 py-2 rounded bg-blue-900/20 text-blue-400 hover:bg-blue-900/40 border border-blue-900/50 transition-colors">Objects</button>
                        <button onclick="loadDb('areas')" class="px-4 py-2 rounded bg-yellow-900/20 text-yellow-400 hover:bg-yellow-900/40 border border-yellow-900/50 transition-colors">Areas</button>
                    </div>

                    <div class="mb-6">
                        <input type="text" id="db-search" placeholder="Search database..." class="w-full bg-[#151515] border border-gray-800 rounded px-4 py-3 text-white focus:border-red-700 outline-none" onkeyup="filterDb()">
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
        function showSection(id) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.getElementById(id + '-section').classList.add('active');
            
            // Close mobile menu if open
            document.getElementById('mobile-menu').classList.add('hidden');

            if(id === 'play') initTerminal();
            if(id === 'admin') refreshLogs();
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
        let termInitialized = false;

        function initTerminal() {
            if(termInitialized) return;
            termInitialized = true;

            const output = document.getElementById('terminal-output');
            const input = document.getElementById('terminal-input');
            const status = document.getElementById('connection-status');

            function connect() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                ws = new WebSocket(protocol + '//' + window.location.host + '/ws');

                ws.onopen = () => {
                    status.textContent = 'Connected';
                    status.className = 'text-green-500';
                    writeToTerm('Connected to server.');
                };

                ws.onmessage = (event) => {
                    writeToTerm(event.data);
                };

                ws.onclose = () => {
                    status.textContent = 'Disconnected';
                    status.className = 'text-red-500';
                    writeToTerm('Connection lost. Reconnecting in 3s...');
                    setTimeout(connect, 3000);
                };

                ws.onerror = (err) => {
                    console.error('WebSocket error:', err);
                    ws.close();
                };
            }

            function writeToTerm(text) {
                // Convert ANSI color codes to HTML
                // Replace ESC[...m sequences with span tags
                let html = text
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/\x1b\[0m/g, '</span>')
                    .replace(/\x1b\[1;30m/g, '<span style="color: #555">')
                    .replace(/\x1b\[1;31m/g, '<span style="color: #ff5555">')
                    .replace(/\x1b\[1;32m/g, '<span style="color: #55ff55">')
                    .replace(/\x1b\[1;33m/g, '<span style="color: #ffff55">')
                    .replace(/\x1b\[1;34m/g, '<span style="color: #5555ff">')
                    .replace(/\x1b\[1;35m/g, '<span style="color: #ff55ff">')
                    .replace(/\x1b\[1;36m/g, '<span style="color: #55ffff">')
                    .replace(/\x1b\[1;37m/g, '<span style="color: #ffffff">')
                    .replace(/\x1b\[0;30m/g, '<span style="color: #333">')
                    .replace(/\x1b\[0;31m/g, '<span style="color: #aa0000">')
                    .replace(/\x1b\[0;32m/g, '<span style="color: #00aa00">')
                    .replace(/\x1b\[0;33m/g, '<span style="color: #aaaa00">')
                    .replace(/\x1b\[0;34m/g, '<span style="color: #0000aa">')
                    .replace(/\x1b\[0;35m/g, '<span style="color: #aa00aa">')
                    .replace(/\x1b\[0;36m/g, '<span style="color: #00aaaa">')
                    .replace(/\x1b\[0;37m/g, '<span style="color: #aaaaaa">')
                    .replace(/\x1b\[([0-9;]+)m/g, '');
                
                const line = document.createElement('div');
                line.innerHTML = html;
                line.style.whiteSpace = 'pre-wrap';
                output.appendChild(line);
                output.scrollTop = output.scrollHeight;
            }

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    const cmd = input.value;
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(cmd + '\r\n');
                    }
                    input.value = '';
                }
            });

            connect();
        }

        // ============ DATABASE ============
        let currentDb = 'mobs';
        let dbData = { mobs: [], objects: [], areas: [] };

        async function loadDb(type) {
            currentDb = type;
            const content = document.getElementById('db-content');
            const headers = document.getElementById('db-headers');
            
            content.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-gray-500">Loading...</td></tr>';

            try {
                if(dbData[type].length === 0) {
                    const res = await fetch('/api/' + type + (type === 'areas' ? '' : '?limit=1000'));
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
                    if(o.flags && o.flags.length > 0) {
                        flagsHtml = '<div class="mt-1"><strong class="text-purple-400">Flags:</strong> ' + 
                            o.flags.map(f => `<span class="text-purple-300">${f}</span>`).join(', ') + '</div>';
                    }
                    
                    // Build wear locations
                    let wearHtml = '';
                    if(o.wear_locations && o.wear_locations.length > 0) {
                        wearHtml = '<div class="mt-1"><strong class="text-blue-400">Wear:</strong> ' + 
                            o.wear_locations.map(w => `<span class="text-blue-300">${w}</span>`).join(', ') + '</div>';
                    }
                    
                    // Build weapon/armor details
                    let statsHtml = '';
                    if(o.values_interpreted) {
                        if(o.values_interpreted.damage_text) {
                            statsHtml += `<div class="mt-1"><strong class="text-red-400">Damage:</strong> <span class="text-red-300">${o.values_interpreted.damage_text}</span>`;
                            if(o.values_interpreted.damage_type) {
                                statsHtml += ` <span class="text-gray-400">(${o.values_interpreted.damage_type})</span>`;
                            }
                            if(o.values_interpreted.weapon_class) {
                                statsHtml += ` <span class="text-gray-400">[${o.values_interpreted.weapon_class}]</span>`;
                            }
                            statsHtml += '</div>';
                        }
                        if(o.values_interpreted.ac_summary) {
                            statsHtml += `<div class="mt-1"><strong class="text-cyan-400">AC:</strong> <span class="text-cyan-300">${o.values_interpreted.ac_summary}</span></div>`;
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
    log_path = DEFAULT_LOG
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")
    log_lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
    return HTMLResponse("\n".join(log_lines))


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
    decoded_item_type = ITEM_TYPES.get(int(obj.item_type) if obj.item_type.isdigit() else 0, obj.item_type)
    decoded_extra_flags = decode_flags(obj.extra_flags, ITEM_FLAGS)
    decoded_wear_flags = decode_flags(obj.wear_flags, WEAR_FLAGS)
    
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
        "extra_flags_raw": obj.extra_flags,
        "extra_flags2_raw": obj.extra_flags2,
        "wear_flags": decoded_wear_flags,
        "wear_flags_raw": obj.wear_flags,
        "values": obj.values,
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
    for area in parser.areas:
        result.append({
            "name": area.name,
            "filename": area.filename,
            "builders": area.builders,
            "vnums": f"{area.vnum_low} - {area.vnum_high}"
        })
    return result


@app.get("/api/objects")
async def get_objects(limit: int = 500) -> list:
    result = []
    for i, (vnum, obj) in enumerate(parser.objects.items()):
        if i >= limit:
            break
        
        # Get item type number and name
        try:
            item_type_num = int(obj.item_type) if obj.item_type.isdigit() else 0
        except (ValueError, TypeError):
            item_type_num = 0
        item_type_name = ITEM_TYPES.get(item_type_num, obj.item_type)
        
        # Decode flags
        flags_decoded = decode_flags(obj.extra_flags, ITEM_FLAGS)
        wear_decoded = decode_flags(obj.wear_flags, WEAR_FLAGS)
        
        # Decode affects
        affects_decoded = decode_applies(obj.affects)
        
        # Interpret values based on item type
        values_interpreted = interpret_values(item_type_num, obj.values)
        
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
    return result


# ============ WebSocket Bridge ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    writer = None
    try:
        # Connect to the MUD server
        reader, writer = await asyncio.open_connection('localhost', 9000)
        
        async def receive_from_mud():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    try:
                        text = data.decode('latin-1', errors='ignore')
                        await websocket.send_text(text)
                    except Exception:
                        break
            except Exception:
                pass

        async def send_to_mud():
            try:
                while True:
                    data = await websocket.receive_text()
                    writer.write(data.encode('latin-1'))
                    await writer.drain()
            except Exception:
                pass

        # Run both tasks
        receive_task = asyncio.create_task(receive_from_mud())
        send_task = asyncio.create_task(send_to_mud())
        
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        
        for task in pending:
            task.cancel()
            
    except Exception as e:
        print(f"WebSocket Error: {e}")
        await websocket.close()
    finally:
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass


def main() -> None:
    global queue_writer, QUEUE_PATH, DEFAULT_LOG

    parser = argparse.ArgumentParser(description="Run ToC web admin server")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()
    QUEUE_PATH = Path(args.queue)
    DEFAULT_LOG = Path(args.log_file)
    queue_writer = QueueWriter(QUEUE_PATH)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, reload=False)
if __name__ == "__main__":
    main()
