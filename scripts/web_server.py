import asyncio
import os
import glob
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# --- Configuration ---
MUD_HOST = os.getenv("MUD_HOST", "127.0.0.1") # 'game' if in docker-compose network
MUD_PORT = int(os.getenv("MUD_PORT", 4000))
WEB_PORT = int(os.getenv("WEB_ADMIN_PORT", 9001))

# Paths
AREA_DIR = Path("/app/area")
PLAYER_DIR = Path("/app/player")
QUEUE_PATH = AREA_DIR / "webadmin.queue"
LOG_PATH = Path("/app/log/toc.log")

app = FastAPI(title="ToC Unified Web Interface")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files (Frontend)
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Data Cache ---
db_cache = {
    "mobs": [],
    "items": [],
    "rooms": [],
    "players": []
}

# --- Models ---
class CommandRequest(BaseModel):
    command: str

class WizinfoRequest(BaseModel):
    message: str
    level: Optional[int] = 62

# --- Helper Functions ---
def clean_string(text: str) -> str:
    if not text: return ""
    text = text.replace('~', '')
    text = re.sub(r'\{[a-zA-Z0-9]', '', text)
    return text.strip()

def parse_area_files():
    print(f"Scanning Area files in {AREA_DIR}...")
    mobs, items, rooms = [], [], []
    if not AREA_DIR.exists(): return

    for filepath in glob.glob(f"{AREA_DIR}/*.are"):
        filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
                lines = f.readlines()
            
            section = None
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('#MOBILES'): section = 'MOBILES'; i+=1; continue
                elif line.startswith('#OBJECTS'): section = 'OBJECTS'; i+=1; continue
                elif line.startswith('#ROOMS'): section = 'ROOMS'; i+=1; continue
                elif line.startswith('#0'): section = None; i+=1; continue

                if section == 'MOBILES' and line.startswith('#') and i + 2 < len(lines):
                    vnum = re.match(r'#(\d+)', line)
                    if vnum:
                        mobs.append({
                            "vnum": vnum.group(1),
                            "name": clean_string(lines[i+1]),
                            "short": clean_string(lines[i+2]),
                            "area": filename
                        })
                elif section == 'OBJECTS' and line.startswith('#') and i + 2 < len(lines):
                    vnum = re.match(r'#(\d+)', line)
                    if vnum:
                        items.append({
                            "vnum": vnum.group(1),
                            "name": clean_string(lines[i+1]),
                            "short": clean_string(lines[i+2]),
                            "area": filename
                        })
                elif section == 'ROOMS' and line.startswith('#') and i + 1 < len(lines):
                    vnum = re.match(r'#(\d+)', line)
                    if vnum:
                        rooms.append({
                            "vnum": vnum.group(1),
                            "name": clean_string(lines[i+1]),
                            "area": filename
                        })
                i += 1
        except Exception: pass

    db_cache['mobs'] = mobs
    db_cache['items'] = items
    db_cache['rooms'] = rooms
    print(f"Loaded {len(mobs)} mobs, {len(items)} items, {len(rooms)} rooms.")

def parse_player_files():
    players = []
    if not PLAYER_DIR.exists(): return
    
    for filename in os.listdir(PLAYER_DIR):
        if filename.startswith('.'): continue
        try:
            with open(PLAYER_DIR / filename, 'r', encoding='latin-1', errors='replace') as f:
                content = f.read()
            
            lvl = re.search(r'^Levl\s+(\d+)', content, re.MULTILINE)
            race = re.search(r'^Race\s+(.*?)~', content, re.MULTILINE)
            cls = re.search(r'^Cla\w{1,2}\s+(.*?)~', content, re.MULTILINE)
            
            players.append({
                "name": filename,
                "level": int(lvl.group(1)) if lvl else 0,
                "race": race.group(1) if race else "Unknown",
                "class": cls.group(1) if cls else "Unknown"
            })
        except Exception: pass
    
    db_cache['players'] = sorted(players, key=lambda x: x['level'], reverse=True)

def queue_command(cmd_str: str):
    # Appends to the queue file for the C game loop to pick up
    try:
        with open(QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write(cmd_str + "\n")
    except Exception as e:
        print(f"Error writing to queue: {e}")

@app.on_event("startup")
async def startup():
    parse_area_files()
    parse_player_files()

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>ToC Game Interface</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #121212; color: #e0e0e0; }
            .console { background: #000; color: #0f0; font-family: monospace; height: 400px; overflow-y: scroll; padding: 10px; border: 1px solid #333; }
            .card { background: #1e1e1e; border-color: #333; margin-bottom: 20px; }
            input, textarea, select { background: #2d2d2d; color: #fff; border: 1px solid #444; }
            .nav-tabs .nav-link { color: #aaa; }
            .nav-tabs .nav-link.active { background: #1e1e1e; color: #fff; border-color: #333 #333 #1e1e1e; }
        </style>
    </head>
    <body>
    <div class="container-fluid p-4">
        <div class="row">
            <div class="col-md-7">
                <div class="card">
                    <div class="card-header">Game Console (Websocket)</div>
                    <div class="card-body">
                        <div id="console" class="console"></div>
                        <input type="text" id="cmdInput" class="form-control mt-2" placeholder="Type command..." onkeydown="if(event.key==='Enter') sendCmd()">
                        <button class="btn btn-success mt-2 btn-sm" onclick="connect()">Connect</button>
                        <button class="btn btn-danger mt-2 btn-sm" onclick="disconnect()">Disconnect</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">Admin Console (IMP Level 70)</div>
                    <div class="card-body">
                        <div class="input-group mb-3">
                            <span class="input-group-text">Command</span>
                            <input type="text" id="adminCmd" class="form-control" placeholder="e.g., load obj 3090">
                            <button class="btn btn-warning" onclick="postAdminCmd()">Execute</button>
                        </div>
                        <div class="input-group mb-3">
                            <span class="input-group-text">WizInfo</span>
                            <input type="text" id="wizMsg" class="form-control" placeholder="Broadcast message">
                            <button class="btn btn-info" onclick="postWizInfo()">Broadcast</button>
                        </div>
                        <button class="btn btn-danger" onclick="doAction('shutdown')">Shutdown Server</button>
                        <button class="btn btn-secondary" onclick="doAction('backup')">Force Backup</button>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">Server Logs (Last 200 lines) <button class="btn btn-sm btn-outline-light float-end" onclick="loadLogs()">Refresh</button></div>
                    <div class="card-body">
                        <pre id="serverLogs" style="height: 200px; overflow-y: scroll; font-size: 0.8em; color: #ccc;"></pre>
                    </div>
                </div>
            </div>

            <div class="col-md-5">
                <div class="card">
                    <div class="card-header">
                        <ul class="nav nav-tabs card-header-tabs" id="dbTabs">
                            <li class="nav-item"><a class="nav-link active" onclick="showTab('mobs')">Mobs</a></li>
                            <li class="nav-item"><a class="nav-link" onclick="showTab('items')">Items</a></li>
                            <li class="nav-item"><a class="nav-link" onclick="showTab('rooms')">Rooms</a></li>
                            <li class="nav-item"><a class="nav-link" onclick="showTab('players')">Players</a></li>
                        </ul>
                    </div>
                    <div class="card-body">
                        <input type="text" id="dbSearch" class="form-control mb-2" placeholder="Filter..." onkeyup="filterDb()">
                        <div id="dbContent" style="height: 600px; overflow-y: scroll;">Loading...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let currentData = [];

        async function loadDb(type) {
            const res = await fetch('/api/db/' + type);
            currentData = await res.json();
            renderDb(currentData);
        }

        function renderDb(data) {
            const html = data.map(item => {
                let text = "";
                if(item.vnum) text = `<b>[${item.vnum}]</b> ${item.name} <br><small>${item.short || ''}</small>`;
                else text = `<b>${item.name}</b> (Lvl ${item.level} ${item.race} ${item.class})`;
                return `<div class="db-item p-2 border-bottom">${text}</div>`;
            }).join('');
            document.getElementById('dbContent').innerHTML = html;
        }

        function filterDb() {
            const term = document.getElementById('dbSearch').value.toLowerCase();
            const filtered = currentData.filter(i => JSON.stringify(i).toLowerCase().includes(term));
            renderDb(filtered);
        }

        function showTab(type) {
            document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
            event.target.classList.add('active');
            loadDb(type);
        }

        // Websocket
        function connect() {
            ws = new WebSocket(((window.location.protocol === "https:") ? "wss://" : "ws://") + window.location.host + "/ws");
            ws.onmessage = (e) => {
                const d = document.getElementById('console');
                d.innerHTML += e.data.replace(/\\n/g, '<br>').replace(/\\r/g, ''); 
                d.scrollTop = d.scrollHeight;
            };
            ws.onopen = () => document.getElementById('console').innerHTML += "<br><em>Connected.</em><br>";
        }
        function disconnect() { if(ws) ws.close(); }
        function sendCmd() {
            const input = document.getElementById('cmdInput');
            if(ws) ws.send(input.value);
            input.value = '';
        }

        // Admin
        async function postAdminCmd() {
            const cmd = document.getElementById('adminCmd').value;
            await fetch('/api/command', {method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({command: cmd})});
            alert('Executed');
        }
        async function postWizInfo() {
            const msg = document.getElementById('wizMsg').value;
            await fetch('/api/wizinfo', {method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg})});
        }
        async function doAction(act) {
            await fetch('/api/' + act, {method: 'POST'});
            alert(act + ' queued.');
        }
        async function loadLogs() {
            const res = await fetch('/api/logs');
            document.getElementById('serverLogs').innerText = await res.text();
        }

        // Init
        loadDb('mobs');
        loadLogs();
    </script>
    </body>
    </html>
    """

@app.get("/api/db/{category}")
async def get_db(category: str):
    return db_cache.get(category, [])

@app.get("/api/logs")
async def get_logs():
    if LOG_PATH.exists():
        # Read last 200 lines
        try:
            # Reading binary to avoid encoding issues with raw log bytes, then decode
            with open(LOG_PATH, "rb") as f:
                lines = f.readlines()
            return b"".join(lines[-200:]).decode("latin-1", errors="replace")
        except Exception:
            return "Error reading log."
    return "Log file not found."

@app.post("/api/command")
async def run_admin_command(req: CommandRequest):
    queue_command(f"command|{req.command}")
    return {"status": "queued"}

@app.post("/api/wizinfo")
async def run_wizinfo(req: WizinfoRequest):
    queue_command(f"wizinfo|{req.level}|{req.message}")
    return {"status": "queued"}

@app.post("/api/backup")
async def trigger_backup():
    queue_command("backup")
    return {"status": "queued"}

@app.post("/api/shutdown")
async def trigger_shutdown():
    queue_command("shutdown")
    return {"status": "queued"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        reader, writer = await asyncio.open_connection(MUD_HOST, MUD_PORT)
        
        async def mud_to_client():
            while True:
                data = await reader.read(4096)
                if not data: break
                # Basic ANSI stripping for browser display could be added here
                text = data.decode('latin-1', errors='ignore')
                await websocket.send_text(text)

        async def client_to_mud():
            try:
                while True:
                    data = await websocket.receive_text()
                    writer.write((data + "\n").encode('latin-1'))
                    await writer.drain()
            except Exception: pass

        await asyncio.wait(
            [asyncio.create_task(mud_to_client()), asyncio.create_task(client_to_mud())],
            return_when=asyncio.FIRST_COMPLETED
        )
    except Exception as e:
        print(f"WS Error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)
