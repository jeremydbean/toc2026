import asyncio
import os
import glob
import re
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- Configuration ---
MUD_HOST = "game"        # Docker service name defined in docker-compose
MUD_PORT = 4000          # Standard ROM port
AREA_DIR = "/app/area"   # Mapped volume in Docker
PLAYER_DIR = "/app/player" # Mapped volume in Docker

app = FastAPI(title="TOC Web Gateway")

# Enable CORS for the React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the background image mounted in docker-compose
# docker-compose maps ./ToCBG.png -> /app/static/background.jpg
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- In-Memory Database Cache ---
db_cache = {
    "mobs": [],
    "items": [],
    "rooms": [],
    "players": []
}

# --- Helper Functions ---

def clean_string(text: str) -> str:
    """Removes MUD-specific formatting (tildes and color codes)."""
    if not text: return ""
    # Remove the trailing tilde used in ROM strings
    text = text.replace('~', '')
    # Remove ROM color codes like {r, {x, etc.
    text = re.sub(r'\{[a-zA-Z0-9]', '', text)
    return text.strip()

def parse_area_files():
    """Scans all .are files to populate Mobs, Items, and Rooms."""
    mobs = []
    items = []
    rooms = []

    print(f"Scanning Area files in {AREA_DIR}...")
    if not os.path.exists(AREA_DIR):
        print("Area directory not found!")
        return

    files = glob.glob(f"{AREA_DIR}/*.are")
    
    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
                lines = f.readlines()

            section = None
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Detect Section Headers
                if line.startswith('#MOBILES'): section = 'MOBILES'; i+=1; continue
                elif line.startswith('#OBJECTS'): section = 'OBJECTS'; i+=1; continue
                elif line.startswith('#ROOMS'): section = 'ROOMS'; i+=1; continue
                elif line.startswith('#0'): section = None; i+=1; continue

                # Parse Mobiles
                if section == 'MOBILES' and line.startswith('#'):
                    # Format: #VNUM \n Name~ \n Short~
                    if i + 2 < len(lines):
                        vnum_match = re.match(r'#(\d+)', line)
                        if vnum_match:
                            mobs.append({
                                "id": vnum_match.group(1),
                                "name": clean_string(lines[i+1]),
                                "short": clean_string(lines[i+2]),
                                "source": filename
                            })
                
                # Parse Objects
                elif section == 'OBJECTS' and line.startswith('#'):
                    # Format: #VNUM \n Name~ \n Short~
                    if i + 2 < len(lines):
                        vnum_match = re.match(r'#(\d+)', line)
                        if vnum_match:
                            items.append({
                                "id": vnum_match.group(1),
                                "name": clean_string(lines[i+1]),
                                "short": clean_string(lines[i+2]),
                                "source": filename
                            })

                # Parse Rooms
                elif section == 'ROOMS' and line.startswith('#'):
                    # Format: #VNUM \n Name~
                    if i + 1 < len(lines):
                        vnum_match = re.match(r'#(\d+)', line)
                        if vnum_match:
                            rooms.append({
                                "id": vnum_match.group(1),
                                "name": clean_string(lines[i+1]),
                                "source": filename
                            })
                i += 1
        except Exception as e:
            print(f"Failed to parse {filename}: {e}")

    db_cache['mobs'] = mobs
    db_cache['items'] = items
    db_cache['rooms'] = rooms
    print(f"Loaded {len(mobs)} mobs, {len(items)} items, {len(rooms)} rooms.")

def parse_player_files():
    """Scans the player directory to build a roster."""
    players = []
    print(f"Scanning Player files in {PLAYER_DIR}...")
    
    if not os.path.exists(PLAYER_DIR):
        print("Player directory not found!")
        return

    # Iterate over all files in player dir
    # Note: ROM pfiles are usually just the player name capitalized
    files = [f for f in os.listdir(PLAYER_DIR) if os.path.isfile(os.path.join(PLAYER_DIR, f))]
    
    for filename in files:
        if filename.startswith('.'): continue # Skip hidden files
        
        filepath = os.path.join(PLAYER_DIR, filename)
        try:
            with open(filepath, 'r', encoding='latin-1', errors='replace') as f:
                content = f.read()
                
            # Heuristic regex parsing for Pfile fields
            level_match = re.search(r'^Levl\s+(\d+)', content, re.MULTILINE)
            race_match = re.search(r'^Race\s+(.*?)~', content, re.MULTILINE)
            class_match = re.search(r'^Clas\s+(.*?)~', content, re.MULTILINE) # Some ROMs use 'Clas', some 'Class'
            
            level = int(level_match.group(1)) if level_match else 0
            race = race_match.group(1) if race_match else "Unknown"
            
            players.append({
                "name": filename,
                "level": level,
                "race": race
            })
        except Exception:
            pass # Skip malformed files

    # Sort by level descending
    db_cache['players'] = sorted(players, key=lambda x: x['level'], reverse=True)
    print(f"Loaded {len(players)} players.")

# --- Startup Hook ---
@app.on_event("startup")
async def startup_event():
    # Load data once on startup
    parse_area_files()
    parse_player_files()

# --- API Routes ---

@app.get("/api/db/{category}")
async def get_data(category: str):
    if category not in db_cache:
        raise HTTPException(status_code=404, detail="Category not found")
    return db_cache[category]

# --- WebSocket Proxy ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # Connect to the C Game Server
        reader, writer = await asyncio.open_connection(MUD_HOST, MUD_PORT)
        
        async def mud_to_ws():
            while True:
                data = await reader.read(4096)
                if not data: break
                # Decode Latin-1 (standard for MUDs) to send to Browser (UTF-8 auto handled by websocket lib)
                await websocket.send_text(data.decode('latin-1', errors='replace'))

        async def ws_to_mud():
            try:
                while True:
                    data = await websocket.receive_text()
                    # Ensure command ends with newline
                    if not data.endswith('\n'):
                        data += '\n'
                    writer.write(data.encode('latin-1'))
                    await writer.drain()
            except WebSocketDisconnect:
                pass

        # Run both tasks until one fails
        await asyncio.wait(
            [asyncio.create_task(mud_to_ws()), asyncio.create_task(ws_to_mud())],
            return_when=asyncio.FIRST_COMPLETED
        )
    except Exception as e:
        print(f"Connection Error: {e}")
        await websocket.close()
