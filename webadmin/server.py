from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

try:
    from webadmin.area_parser import AreaParser
    from webadmin.area_parser import decode_applies, decode_flags, ITEM_FLAGS, WEAR_FLAGS, ITEM_TYPES
except ImportError:
    from area_parser import AreaParser
    from area_parser import decode_applies, decode_flags, ITEM_FLAGS, WEAR_FLAGS, ITEM_TYPES

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
    <title>Tales of Chaos - MUD</title>
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
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Navigation -->
    <nav class="bg-black/90 border-b border-red-900/30 fixed w-full z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex items-center justify-between h-20">
                <div class="flex items-center gap-3">
                    <i class="fa-solid fa-dragon text-3xl text-red-700"></i>
                    <span class="text-2xl font-bold text-white tracking-wider font-cinzel">TALES OF CHAOS</span>
                </div>
                <div class="hidden md:block">
                    <div class="ml-10 flex items-baseline space-x-8">
                        <a href="#home" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors">Home</a>
                        <a href="#play" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors">Play Now</a>
                        <a href="#world" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors">The World</a>
                        <a href="#classes" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors">Classes</a>
                        <a href="#community" class="text-gray-300 hover:text-red-500 px-3 py-2 rounded-md text-sm font-medium transition-colors">Community</a>
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
                <a href="#home" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium">Home</a>
                <a href="#play" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium">Play Now</a>
                <a href="#world" class="text-gray-300 hover:text-red-500 block px-3 py-2 rounded-md text-base font-medium">The World</a>
            </div>
        </div>
    </nav>

    <!-- Hero Section -->
    <section id="home" class="hero-pattern relative h-screen flex items-center justify-center pt-16">
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
                <a href="#play" class="btn-primary px-8 py-4 rounded text-lg font-bold flex items-center justify-center gap-2 group">
                    <i class="fa-solid fa-terminal"></i> CONNECT NOW
                    <i class="fa-solid fa-arrow-right group-hover:translate-x-1 transition-transform"></i>
                </a>
                <a href="https://github.com/jeremydbean/tocgpt" target="_blank" class="px-8 py-4 rounded border border-gray-600 hover:border-white bg-transparent text-white text-lg font-bold flex items-center justify-center gap-2 transition-all hover:bg-white/5">
                    <i class="fa-brands fa-github"></i> VIEW SOURCE
                </a>
            </div>
        </div>
    </section>

    <!-- Status & Connection -->
    <section id="play" class="py-20 bg-[#0a0a0a] relative overflow-hidden">
        <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-red-900 to-transparent"></div>
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
                
                <!-- Terminal Simulation -->
                <div class="parchment p-1 rounded-lg bg-[#111]">
                    <div class="bg-black p-4 rounded border border-gray-800 h-80 font-mono text-sm overflow-y-auto relative" id="terminal-window">
                        <div class="flex gap-1.5 mb-4">
                            <div class="w-3 h-3 rounded-full bg-red-500"></div>
                            <div class="w-3 h-3 rounded-full bg-yellow-500"></div>
                            <div class="w-3 h-3 rounded-full bg-green-500"></div>
                        </div>
                        <div class="text-green-500 space-y-1">
                            <p>Connecting to tocGPT Server...</p>
                            <p>Host: toc.mudserver.com</p>
                            <p>Port: 4000</p>
                            <p>Connected.</p>
                            <br>
                            <pre class="text-red-600 font-bold leading-none">
  / _ \___ _/ /  ___ ___  / _/
 / // / _ `/ /__/ -_|_-< / _/ 
/____/\_,_/____/\__/___/___/  
      CHAOS MUD SYSTEM v2.0
                            </pre>
                            <br>
                            <p class="text-gray-300">Welcome to Tales of Chaos.</p>
                            <p class="text-gray-300">By what name do you wish to be known?</p>
                            <p class="blinking-cursor">></p>
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
                            Experience the thrill of pure imagination. No graphics card required.
                            Our server runs a modified ROM codebase inside a modern Docker container, ensuring stability and performance.
                        </p>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-[#151515] p-4 rounded border-l-2 border-red-700">
                            <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Port</div>
                            <div class="text-white font-mono text-xl flex items-center gap-2">
                                4000 
                                <button onclick="copyToClipboard('4000')" class="text-xs text-gray-600 hover:text-white"><i class="fa-regular fa-copy"></i></button>
                            </div>
                        </div>
                        <div class="bg-[#151515] p-4 rounded border-l-2 border-red-700">
                            <div class="text-gray-500 text-xs uppercase tracking-wider mb-1">Protocol</div>
                            <div class="text-white font-mono text-xl">Telnet</div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </section>

    <!-- Features Grid -->
    <section id="world" class="py-20 bg-[#0f0f0f]">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="text-center mb-16">
                <h2 class="text-3xl md:text-4xl font-bold text-white mb-4">A World of Text</h2>
                <p class="text-gray-400 max-w-2xl mx-auto">Features derived from the legendary ROM architecture, enhanced for the modern era.</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                <!-- Feature 1 -->
                <div class="stat-card p-8 rounded-lg text-center">
                    <div class="w-16 h-16 bg-red-900/20 rounded-full flex items-center justify-center mx-auto mb-6 text-red-500">
                        <i class="fa-solid fa-skull-crossbones text-2xl"></i>
                    </div>
                    <h3 class="text-xl font-bold text-white mb-3">Tactical Combat</h3>
                    <p class="text-gray-400 text-sm leading-relaxed">
                        Real-time text combat based on THAC0 mechanics. Manage your skills, spells, and equipment weight to survive against legendary mobs like the Red Dragon.
                    </p>
                </div>

                <!-- Feature 2 -->
                <div class="stat-card p-8 rounded-lg text-center">
                    <div class="w-16 h-16 bg-blue-900/20 rounded-full flex items-center justify-center mx-auto mb-6 text-blue-500">
                        <i class="fa-solid fa-hat-wizard text-2xl"></i>
                    </div>
                    <h3 class="text-xl font-bold text-white mb-3">Complex Magic</h3>
                    <p class="text-gray-400 text-sm leading-relaxed">
                        Hundreds of spells across distinct schools of magic. From simple heals to room-clearing chaos storms. Mana management is key.
                    </p>
                </div>

                <!-- Feature 3 -->
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

    <!-- Classes -->
    <section id="classes" class="py-20 bg-[#0a0a0a] relative">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex flex-col md:flex-row gap-12 items-start">
                <div class="w-full md:w-1/3 sticky top-24">
                    <h2 class="text-4xl font-bold text-white mb-6">Choose Your Path</h2>
                    <p class="text-gray-400 mb-8">
                        Your class defines your journey. Will you rely on brute strength, divine favor, arcane knowledge, or subtle strikes?
                    </p>
                    <div class="space-y-2">
                        <button onclick="showClass('warrior')" class="class-btn w-full text-left px-4 py-3 bg-red-900/20 hover:bg-red-900/40 border-l-4 border-red-600 text-white font-medium transition-all active">Warrior</button>
                        <button onclick="showClass('mage')" class="class-btn w-full text-left px-4 py-3 hover:bg-blue-900/20 border-l-4 border-transparent hover:border-blue-500 text-gray-400 hover:text-white transition-all">Mage</button>
                        <button onclick="showClass('cleric')" class="class-btn w-full text-left px-4 py-3 hover:bg-yellow-900/20 border-l-4 border-transparent hover:border-yellow-500 text-gray-400 hover:text-white transition-all">Cleric</button>
                        <button onclick="showClass('thief')" class="class-btn w-full text-left px-4 py-3 hover:bg-green-900/20 border-l-4 border-transparent hover:border-green-500 text-gray-400 hover:text-white transition-all">Thief</button>
                    </div>
                </div>
                
                <div class="w-full md:w-2/3 bg-[#111] border border-gray-800 rounded-lg p-8 min-h-[400px]" id="class-display">
                    <!-- Content injected via JS -->
                </div>
            </div>
        </div>
    </section>

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
        // Mobile Menu Toggle
        function toggleMobileMenu() {
            const menu = document.getElementById('mobile-menu');
            menu.classList.toggle('hidden');
        }

        // Copy to clipboard
        function copyToClipboard(text) {
            const el = document.createElement('textarea');
            el.value = text;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
            alert('Port copied to clipboard!');
        }

        // Class Data
        const classes = {
            warrior: {
                title: "The Warrior",
                icon: "fa-shield-halved",
                color: "text-red-500",
                desc: "Masters of weapons and combat tactics. Warriors have the highest health pools and can wear the heaviest armor.",
                stats: [
                    { label: "Strength", val: "95%" },
                    { label: "Magic", val: "10%" },
                    { label: "Defense", val: "90%" }
                ],
                skills: ["Kick", "Bash", "Rescue", "Parry", "Double Attack"]
            },
            mage: {
                title: "The Mage",
                icon: "fa-hat-wizard",
                color: "text-blue-500",
                desc: "Scholars of the arcane. Mages are physically weak but command devastating elemental spells that can destroy entire rooms of enemies.",
                stats: [
                    { label: "Strength", val: "20%" },
                    { label: "Magic", val: "100%" },
                    { label: "Defense", val: "30%" }
                ],
                skills: ["Fireball", "Lightning Bolt", "Teleport", "Invisibility", "Sleep"]
            },
            cleric: {
                title: "The Cleric",
                icon: "fa-cross",
                color: "text-yellow-500",
                desc: "Servants of the gods. Clerics keep the party alive with healing magic and protect them with powerful blessings.",
                stats: [
                    { label: "Strength", val: "60%" },
                    { label: "Magic", val: "85%" },
                    { label: "Defense", val: "60%" }
                ],
                skills: ["Heal", "Sanctuary", "Bless", "Curse", "Resurrection"]
            },
            thief: {
                title: "The Thief",
                icon: "fa-mask",
                color: "text-green-500",
                desc: "Masters of stealth and trickery. Thieves strike from the shadows and can pick locks or steal gold from enemies.",
                stats: [
                    { label: "Strength", val: "60%" },
                    { label: "Magic", val: "20%" },
                    { label: "Defense", val: "70%" }
                ],
                skills: ["Backstab", "Pick Lock", "Steal", "Hide", "Sneak"]
            }
        };

        // Initialize Class Display
        function renderClass(key) {
            const c = classes[key];
            const html = `
                <div class="animate-fade-in">
                    <div class="flex items-center gap-4 mb-6">
                        <i class="fa-solid ${c.icon} text-4xl ${c.color}"></i>
                        <h3 class="text-3xl font-cinzel font-bold text-white">${c.title}</h3>
                    </div>
                    <p class="text-gray-300 text-lg mb-8 leading-relaxed">${c.desc}</p>
                    
                    <div class="mb-8">
                        <h4 class="text-white font-bold mb-4 uppercase tracking-wide text-sm">Base Attributes</h4>
                        <div class="space-y-3">
                            ${c.stats.map(s => `
                                <div class="flex items-center gap-3">
                                    <div class="w-24 text-gray-500 text-sm">${s.label}</div>
                                    <div class="flex-1 bg-gray-800 rounded-full h-2">
                                        <div class="h-2 rounded-full ${c.color.replace('text-', 'bg-')}" style="width: ${s.val}"></div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <div>
                        <h4 class="text-white font-bold mb-4 uppercase tracking-wide text-sm">Key Abilities</h4>
                        <div class="flex flex-wrap gap-2">
                            ${c.skills.map(sk => `
                                <span class="px-3 py-1 rounded bg-gray-800 text-gray-300 text-sm border border-gray-700">${sk}</span>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `;
            document.getElementById('class-display').innerHTML = html;
        }

        function showClass(key) {
            // Update buttons
            document.querySelectorAll('.class-btn').forEach(btn => {
                btn.className = "class-btn w-full text-left px-4 py-3 hover:bg-gray-800 border-l-4 border-transparent text-gray-400 hover:text-white transition-all";
                if(btn.textContent.toLowerCase().includes(key)) {
                    const color = classes[key].color.replace('text-', ''); // Extract color name roughly
                    let borderColor = 'border-gray-500';
                    if(key === 'warrior') borderColor = 'border-red-600';
                    if(key === 'mage') borderColor = 'border-blue-600';
                    if(key === 'cleric') borderColor = 'border-yellow-600';
                    if(key === 'thief') borderColor = 'border-green-600';
                    
                    btn.className = `class-btn w-full text-left px-4 py-3 bg-gray-900 ${borderColor} text-white font-medium transition-all`;
                }
            });
            renderClass(key);
        }

        // Initial Render
        showClass('warrior');

        // Server Status Check
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
        item_type_name = ITEM_TYPES.get(int(obj.item_type) if obj.item_type.isdigit() else 0, obj.item_type)
        result.append({
            "vnum": obj.vnum,
            "short_desc": obj.short_desc,
            "long_desc": obj.long_desc,
            "description": obj.long_desc,
            "item_type": item_type_name,
            "level": obj.level,
            "area": obj.area_name,
            "area_file": obj.area_file
        })
    return result


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



    <link rel="stylesheet" href="https://code.getmdl.io/1.3.0/material.indigo-pink.min.css">
    <script defer src="https://code.getmdl.io/1.3.0/material.min.js"></script>
    <style>
        body { background-color: #f5f5f5; font-family: 'Roboto', sans-serif; }
        .mdl-layout__header { background-color: #673ab7; }
        .page-content { padding: 20px; max-width: 1400px; margin: 0 auto; }
        .stat-card { background: #fff; padding: 20px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 48px; font-weight: 700; color: #673ab7; }
        .stat-label { font-size: 14px; color: #757575; text-transform: uppercase; }
        .search-box { margin: 20px 0; }
        .item-card { background: #fff; padding: 15px; margin: 10px 0; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
        .item-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
        .item-vnum { display: inline-block; background: #673ab7; color: #fff; padding: 2px 8px; border-radius: 3px; font-family: monospace; font-size: 12px; }
        .item-name { font-size: 18px; font-weight: 500; margin: 5px 0; color: #212121; }
        .item-desc { font-size: 14px; color: #757575; }
        .item-meta { font-size: 12px; color: #9e9e9e; margin-top: 5px; }
        .chip { display: inline-block; padding: 2px 8px; margin: 2px; border-radius: 12px; font-size: 11px; background: #e0e0e0; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .loading { text-align: center; padding: 40px; color: #757575; }
    </style>
</head>
<body>
    <div class="mdl-layout mdl-js-layout mdl-layout--fixed-header">
        <header class="mdl-layout__header">
            <div class="mdl-layout__header-row">
                <span class="mdl-layout-title">Times of Chaos - Database</span>
                <div class="mdl-layout-spacer"></div>
                <nav class="mdl-navigation">
                    <a class="mdl-navigation__link" href="/">Admin</a>
                    <a class="mdl-navigation__link" href="/browse">Database</a>
                </nav>
            </div>
        </header>
        <main class="mdl-layout__content">
            <div class="page-content">
                <!-- Stats Overview -->
                <div class="mdl-grid" style="margin-bottom: 20px;">
                    <div class="mdl-cell mdl-cell--3-col">
                        <div class="stat-card">
                            <div class="stat-number" id="statMobiles">-</div>
                            <div class="stat-label">Mobiles</div>
                        </div>
                    </div>
                    <div class="mdl-cell mdl-cell--3-col">
                        <div class="stat-card">
                            <div class="stat-number" id="statObjects">-</div>
                            <div class="stat-label">Objects</div>
                        </div>
                    </div>
                    <div class="mdl-cell mdl-cell--3-col">
                        <div class="stat-card">
                            <div class="stat-number" id="statRooms">-</div>
                            <div class="stat-label">Rooms</div>
                        </div>
                    </div>
                    <div class="mdl-cell mdl-cell--3-col">
                        <div class="stat-card">
                            <div class="stat-number" id="statAreas">-</div>
                            <div class="stat-label">Areas</div>
                        </div>
                    </div>
                </div>

                <!-- Tabs -->
                <div class="mdl-grid">
                    <div class="mdl-cell mdl-cell--12-col">
                        <div style="background: #fff; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <div class="mdl-tabs mdl-js-tabs mdl-js-ripple-effect" style="padding: 0;">
                                <div class="mdl-tabs__tab-bar" style="background: #673ab7;">
                                    <a href="#mobiles" class="mdl-tabs__tab is-active" onclick="showTab('mobiles')" style="color: #fff;">Mobiles</a>
                                    <a href="#objects" class="mdl-tabs__tab" onclick="showTab('objects')" style="color: #fff;">Objects</a>
                                    <a href="#rooms" class="mdl-tabs__tab" onclick="showTab('rooms')" style="color: #fff;">Rooms</a>
                                    <a href="#areas" class="mdl-tabs__tab" onclick="showTab('areas')" style="color: #fff;">Areas</a>
                                </div>
                                
                                <div style="padding: 20px;">
                                    <!-- Mobiles Tab -->
                                    <div id="mobiles" class="tab-content active">
                                        <div class="search-box">
                                            <div class="mdl-textfield mdl-js-textfield mdl-textfield--floating-label" style="width: 100%;">
                                                <input class="mdl-textfield__input" type="text" id="mobSearch" oninput="filterMobs()">
                                                <label class="mdl-textfield__label" for="mobSearch">Search mobiles by name, keywords, or area...</label>
                                            </div>
                                        </div>
                                        <div id="mobsList" class="loading">Loading mobiles...</div>
                                    </div>

                                    <!-- Objects Tab -->
                                    <div id="objects" class="tab-content">
                                        <div class="search-box">
                                            <div class="mdl-textfield mdl-js-textfield mdl-textfield--floating-label" style="width: 100%;">
                                                <input class="mdl-textfield__input" type="text" id="objectSearch" oninput="filterObjects()">
                                                <label class="mdl-textfield__label" for="objectSearch">Search objects by name or type...</label>
                                            </div>
                                        </div>
                                        <div id="objectsList" class="loading">Loading objects...</div>
                                    </div>

                                    <!-- Rooms Tab -->
                                    <div id="rooms" class="tab-content">
                                        <div class="search-box">
                                            <div class="mdl-textfield mdl-js-textfield mdl-textfield--floating-label" style="width: 100%;">
                                                <input class="mdl-textfield__input" type="text" id="roomSearch" oninput="filterRooms()">
                                                <label class="mdl-textfield__label" for="roomSearch">Search rooms by name or area...</label>
                                            </div>
                                        </div>
                                        <div id="roomsList" class="loading">Loading rooms...</div>
                                    </div>

                                    <!-- Areas Tab -->
                                    <div id="areas" class="tab-content">
                                        <div id="areasList" class="loading">Loading areas...</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <script>
        let allMobs = [];
        let allObjects = [];
        let allRooms = [];
        let allAreas = [];

        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const stats = await res.json();
                document.getElementById('statMobiles').textContent = stats.mobiles;
                document.getElementById('statObjects').textContent = stats.objects;
                document.getElementById('statRooms').textContent = stats.rooms;
                document.getElementById('statAreas').textContent = stats.areas;
            } catch (e) {
                console.error('Failed to load stats:', e);
            }
        }

        async function loadMobs() {
            try {
                const res = await fetch('/api/mobs?limit=500');
                allMobs = await res.json();
                displayMobs(allMobs);
            } catch (e) {
                document.getElementById('mobsList').innerHTML = '<p style="color: red;">Error loading mobiles</p>';
            }
        }

        function displayMobs(mobs) {
            const container = document.getElementById('mobsList');
            if (!mobs || mobs.length === 0) {
                container.innerHTML = '<p>No mobiles found</p>';
                return;
            }
            container.innerHTML = mobs.map(mob => `
                <div class="item-card">
                    <span class="item-vnum">#${mob.vnum}</span>
                    <div class="item-name">${mob.short_desc || 'Unnamed'}</div>
                    <div class="item-desc">${mob.long_desc || ''}</div>
                    <div class="item-meta">
                        <span class="chip">Level ${mob.level || '?'}</span>
                        <span class="chip">${mob.race || 'unknown'}</span>
                        <span class="chip">${mob.area || 'unknown area'}</span>
                    </div>
                </div>
            `).join('');
        }

        function filterMobs() {
            const query = document.getElementById('mobSearch').value.toLowerCase();
            if (!query) {
                displayMobs(allMobs);
                return;
            }
            const filtered = allMobs.filter(mob => 
                (mob.short_desc && mob.short_desc.toLowerCase().includes(query)) ||
                (mob.keywords && mob.keywords.toLowerCase().includes(query)) ||
                (mob.area && mob.area.toLowerCase().includes(query))
            );
            displayMobs(filtered);
        }

        async function loadObjects() {
            try {
                const res = await fetch('/api/objects?limit=500');
                allObjects = await res.json();
                displayObjects(allObjects);
            } catch (e) {
                document.getElementById('objectsList').innerHTML = '<p style="color: red;">Error loading objects</p>';
            }
        }

        function displayObjects(objects) {
            const container = document.getElementById('objectsList');
            if (!objects || objects.length === 0) {
                container.innerHTML = '<p>No objects found</p>';
                return;
            }
            container.innerHTML = objects.map(obj => `
                <div class="item-card">
                    <span class="item-vnum">#${obj.vnum}</span>
                    <div class="item-name">${obj.short_desc || 'Unnamed'}</div>
                    <div class="item-desc">${obj.description || ''}</div>
                    <div class="item-meta">
                        <span class="chip">${obj.item_type || 'unknown'}</span>
                        <span class="chip">Level ${obj.level || '?'}</span>
                        <span class="chip">${obj.area || 'unknown area'}</span>
                    </div>
                </div>
            `).join('');
        }

        function filterObjects() {
            const query = document.getElementById('objectSearch').value.toLowerCase();
            if (!query) {
                displayObjects(allObjects);
                return;
            }
            const filtered = allObjects.filter(obj => 
                (obj.short_desc && obj.short_desc.toLowerCase().includes(query)) ||
                (obj.item_type && obj.item_type.toLowerCase().includes(query)) ||
                (obj.area && obj.area.toLowerCase().includes(query))
            );
            displayObjects(filtered);
        }

        async function loadRooms() {
            try {
                const res = await fetch('/api/rooms?limit=300');
                allRooms = await res.json();
                displayRooms(allRooms);
            } catch (e) {
                document.getElementById('roomsList').innerHTML = '<p style="color: red;">Error loading rooms</p>';
            }
        }

        function displayRooms(rooms) {
            const container = document.getElementById('roomsList');
            if (!rooms || rooms.length === 0) {
                container.innerHTML = '<p>No rooms found</p>';
                return;
            }
            container.innerHTML = rooms.map(room => `
                <div class="item-card">
                    <span class="item-vnum">#${room.vnum}</span>
                    <div class="item-name">${room.name || 'Unnamed Room'}</div>
                    <div class="item-desc">${room.description || ''}</div>
                    <div class="item-meta">
                        <span class="chip">${room.sector || 'unknown'}</span>
                        <span class="chip">${room.area || 'unknown area'}</span>
                    </div>
                </div>
            `).join('');
        }

        function filterRooms() {
            const query = document.getElementById('roomSearch').value.toLowerCase();
            if (!query) {
                displayRooms(allRooms);
                return;
            }
            const filtered = allRooms.filter(room => 
                (room.name && room.name.toLowerCase().includes(query)) ||
                (room.description && room.description.toLowerCase().includes(query)) ||
                (room.area && room.area.toLowerCase().includes(query))
            );
            displayRooms(filtered);
        }

        async function loadAreas() {
            try {
                const res = await fetch('/api/areas');
                allAreas = await res.json();
                displayAreas(allAreas);
            } catch (e) {
                document.getElementById('areasList').innerHTML = '<p style="color: red;">Error loading areas</p>';
            }
        }

        function displayAreas(areas) {
            const container = document.getElementById('areasList');
            if (!areas || areas.length === 0) {
                container.innerHTML = '<p>No areas found</p>';
                return;
            }
            container.innerHTML = areas.map(area => `
                <div class="item-card">
                    <div class="item-name">${area.name || area.filename}</div>
                    <div class="item-meta">
                        <span class="chip">${area.filename}</span>
                    </div>
                </div>
            `).join('');
        }

        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.getElementById(tabName).classList.add('active');
            
            // Load data when tab is shown
            if (tabName === 'mobiles' && allMobs.length === 0) loadMobs();
            if (tabName === 'objects' && allObjects.length === 0) loadObjects();
            if (tabName === 'rooms' && allRooms.length === 0) loadRooms();
            if (tabName === 'areas' && allAreas.length === 0) loadAreas();
        }

        // Load initial data
        loadStats();
        loadMobs();
    </script>
</body>
</html>
    """


if __name__ == "__main__":
    main()
