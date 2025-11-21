from pathlib import Path

content = r'''from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from webadmin.area_parser import AreaParser
from webadmin.area_parser import decode_applies, decode_flags, ITEM_FLAGS, WEAR_FLAGS, ITEM_TYPES

QUEUE_PATH: Path = Path("/app/area/webadmin.queue")
DEFAULT_LOG: Path = Path("/app/log/toc.log")

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


queue_writer: QueueWriter = QueueWriter(QUEUE_PATH)
parser = AreaParser()


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
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Times of Chaos | Admin</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
    <style>
        body { background-color: #0d1117; }
        .sidebar { background-color: #161b22; border-right: 1px solid #30363d; }
        .nav-link { color: #c9d1d9; }
        .nav-link:hover { color: #fff; background-color: #21262d; }
        .nav-link.active { background-color: #1f6feb !important; color: #fff !important; }
        .card { background-color: #161b22; border: 1px solid #30363d; }
        .card-header { border-bottom: 1px solid #30363d; background-color: #21262d; }
        .log-terminal { background-color: #0d1117; color: #7ee787; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; height: 600px; overflow-y: auto; padding: 1rem; border: 1px solid #30363d; border-radius: 6px; }
        .table { color: #c9d1d9; }
        .table-hover tbody tr:hover { color: #fff; background-color: #21262d; }
        .form-control, .form-select { background-color: #0d1117; border-color: #30363d; color: #c9d1d9; }
        .form-control:focus { background-color: #0d1117; color: #fff; border-color: #1f6feb; box-shadow: 0 0 0 0.25rem rgba(31, 111, 235, 0.25); }
        .vnum-badge { font-family: monospace; background-color: #238636; }
    </style>
</head>
<body>
    <div class="d-flex">
        <!-- Sidebar -->
        <div class="d-flex flex-column flex-shrink-0 p-3 sidebar" style="width: 260px; height: 100vh; position: fixed; z-index: 1000;">
            <a href="/" class="d-flex align-items-center mb-3 mb-md-0 me-md-auto text-white text-decoration-none">
                <i class="bi bi-fire fs-4 me-2 text-danger"></i>
                <span class="fs-4 fw-bold">ToC Admin</span>
            </a>
            <hr class="text-secondary">
            <ul class="nav nav-pills flex-column mb-auto">
                <li class="nav-item">
                    <a href="#" class="nav-link active" onclick="showView('dashboard', this)">
                        <i class="bi bi-speedometer2 me-2"></i> Dashboard
                    </a>
                </li>
                <li>
                    <a href="#" class="nav-link" onclick="showView('database', this)">
                        <i class="bi bi-database me-2"></i> Database
                    </a>
                </li>
                <li>
                    <a href="#" class="nav-link" onclick="showView('logs', this)">
                        <i class="bi bi-terminal me-2"></i> Server Logs
                    </a>
                </li>
            </ul>
            <hr class="text-secondary">
            <div class="dropdown">
                <a href="#" class="d-flex align-items-center text-white text-decoration-none dropdown-toggle" data-bs-toggle="dropdown">
                    <i class="bi bi-person-circle me-2"></i>
                    <strong>Administrator</strong>
                </a>
                <ul class="dropdown-menu dropdown-menu-dark text-small shadow">
                    <li><a class="dropdown-item" href="#" onclick="action('backup')"><i class="bi bi-save me-2"></i> Backup World</a></li>
                    <li><hr class="dropdown-divider"></li>
                    <li><a class="dropdown-item text-danger" href="#" onclick="action('shutdown')"><i class="bi bi-power me-2"></i> Shutdown</a></li>
                </ul>
            </div>
        </div>

        <!-- Main Content -->
        <div class="flex-grow-1 p-4" style="margin-left: 260px; min-height: 100vh;">
            
            <!-- Dashboard View -->
            <div id="view-dashboard" class="view-section">
                <h2 class="mb-4 border-bottom pb-2 border-secondary">Dashboard</h2>
                
                <!-- Stats Row -->
                <div class="row g-4 mb-4">
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body d-flex align-items-center">
                                <div class="bg-primary bg-opacity-10 p-3 rounded me-3">
                                    <i class="bi bi-people fs-3 text-primary"></i>
                                </div>
                                <div>
                                    <h6 class="card-subtitle mb-1 text-muted">Mobiles</h6>
                                    <h3 class="card-title mb-0" id="stat-mobs">-</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body d-flex align-items-center">
                                <div class="bg-success bg-opacity-10 p-3 rounded me-3">
                                    <i class="bi bi-box-seam fs-3 text-success"></i>
                                </div>
                                <div>
                                    <h6 class="card-subtitle mb-1 text-muted">Objects</h6>
                                    <h3 class="card-title mb-0" id="stat-objs">-</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body d-flex align-items-center">
                                <div class="bg-warning bg-opacity-10 p-3 rounded me-3">
                                    <i class="bi bi-geo-alt fs-3 text-warning"></i>
                                </div>
                                <div>
                                    <h6 class="card-subtitle mb-1 text-muted">Rooms</h6>
                                    <h3 class="card-title mb-0" id="stat-rooms">-</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body d-flex align-items-center">
                                <div class="bg-info bg-opacity-10 p-3 rounded me-3">
                                    <i class="bi bi-map fs-3 text-info"></i>
                                </div>
                                <div>
                                    <h6 class="card-subtitle mb-1 text-muted">Areas</h6>
                                    <h3 class="card-title mb-0" id="stat-areas">-</h3>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row g-4">
                    <!-- WizInfo -->
                    <div class="col-md-6">
                        <div class="card h-100">
                            <div class="card-header">
                                <i class="bi bi-broadcast me-2"></i> Broadcast WizInfo
                            </div>
                            <div class="card-body">
                                <form onsubmit="sendWizInfo(event)">
                                    <div class="mb-3">
                                        <label class="form-label">Message</label>
                                        <textarea class="form-control" id="wizinfo-msg" rows="3" required></textarea>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label">Min Level</label>
                                        <input type="number" class="form-control" id="wizinfo-level" value="62">
                                    </div>
                                    <button type="submit" class="btn btn-primary"><i class="bi bi-send me-2"></i> Send Broadcast</button>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Server Command -->
                    <div class="col-md-6">
                        <div class="card h-100">
                            <div class="card-header">
                                <i class="bi bi-terminal-fill me-2"></i> Server Command
                            </div>
                            <div class="card-body">
                                <form onsubmit="sendCommand(event)">
                                    <div class="mb-3">
                                        <label class="form-label">Command</label>
                                        <input type="text" class="form-control" id="server-cmd" placeholder="e.g. copyover" required>
                                    </div>
                                    <button type="submit" class="btn btn-danger"><i class="bi bi-lightning-charge me-2"></i> Execute</button>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Database View -->
            <div id="view-database" class="view-section d-none">
                <h2 class="mb-4 border-bottom pb-2 border-secondary">Database Browser</h2>
                
                <ul class="nav nav-tabs mb-4" id="dbTabs">
                    <li class="nav-item">
                        <button class="nav-link active" onclick="loadDb('mobs')">Mobiles</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" onclick="loadDb('objects')">Objects</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" onclick="loadDb('rooms')">Rooms</button>
                    </li>
                    <li class="nav-item">
                        <button class="nav-link" onclick="loadDb('areas')">Areas</button>
                    </li>
                </ul>

                <div class="card">
                    <div class="card-body">
                        <div class="input-group mb-3">
                            <span class="input-group-text bg-dark border-secondary text-secondary"><i class="bi bi-search"></i></span>
                            <input type="text" class="form-control" id="db-search" placeholder="Search..." onkeyup="filterDb()">
                        </div>
                        <div class="table-responsive" style="max-height: 600px;">
                            <table class="table table-hover table-dark mb-0">
                                <thead>
                                    <tr id="db-headers">
                                        <!-- Headers injected via JS -->
                                    </tr>
                                </thead>
                                <tbody id="db-content">
                                    <tr><td colspan="5" class="text-center text-muted py-4">Select a category to load data</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Logs View -->
            <div id="view-logs" class="view-section d-none">
                <div class="d-flex justify-content-between align-items-center mb-4 border-bottom pb-2 border-secondary">
                    <h2 class="mb-0">Server Logs</h2>
                    <button class="btn btn-outline-light btn-sm" onclick="refreshLogs()"><i class="bi bi-arrow-clockwise me-2"></i> Refresh</button>
                </div>
                <div id="log-terminal" class="log-terminal">
                    Loading logs...
                </div>
            </div>

        </div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <div id="liveToast" class="toast text-bg-primary" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <strong class="me-auto">Notification</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body" id="toast-msg"></div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // State
        let currentDb = 'mobs';
        let dbData = { mobs: [], objects: [], rooms: [], areas: [] };

        // Navigation
        function showView(viewId, linkEl) {
            document.querySelectorAll('.view-section').forEach(el => el.classList.add('d-none'));
            document.getElementById('view-' + viewId).classList.remove('d-none');
            
            if(linkEl) {
                document.querySelectorAll('.sidebar .nav-link').forEach(el => el.classList.remove('active'));
                linkEl.classList.add('active');
            }

            if(viewId === 'logs') refreshLogs();
            if(viewId === 'database' && dbData[currentDb].length === 0) loadDb(currentDb);
        }

        // Actions
        async function action(type) {
            if(!confirm('Are you sure?')) return;
            try {
                await fetch('/api/' + type, { method: 'POST' });
                showToast(type + ' queued successfully');
            } catch(e) { showToast('Error: ' + e, true); }
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
                showToast('Broadcast queued');
                e.target.reset();
            } catch(e) { showToast('Error: ' + e, true); }
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
                showToast('Command queued');
                e.target.reset();
            } catch(e) { showToast('Error: ' + e, true); }
        }

        // Logs
        async function refreshLogs() {
            const el = document.getElementById('log-terminal');
            try {
                const res = await fetch('/api/logs');
                el.textContent = await res.text();
                el.scrollTop = el.scrollHeight;
            } catch(e) { el.textContent = 'Error loading logs'; }
        }

        // Database
        async function loadDb(type) {
            currentDb = type;
            
            // Update tabs
            document.querySelectorAll('#dbTabs .nav-link').forEach(el => {
                el.classList.toggle('active', el.textContent.toLowerCase().includes(type === 'mobs' ? 'mobiles' : type));
            });

            const content = document.getElementById('db-content');
            content.innerHTML = '<tr><td colspan="5" class="text-center py-4"><div class="spinner-border text-primary"></div></td></tr>';

            try {
                if(dbData[type].length === 0) {
                    const res = await fetch('/api/' + type + (type === 'areas' ? '' : '?limit=1000'));
                    dbData[type] = await res.json();
                }
                renderDb(dbData[type]);
            } catch(e) {
                content.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-4">Error loading data: ${e}</td></tr>`;
            }
        }

        function renderDb(data) {
            const headers = document.getElementById('db-headers');
            const content = document.getElementById('db-content');
            
            let headerHtml = '';
            let rowsHtml = '';

            if(currentDb === 'mobs') {
                headerHtml = '<th>Vnum</th><th>Name</th><th>Level</th><th>Race</th><th>Area</th>';
                rowsHtml = data.map(m => `
                    <tr>
                        <td><span class="badge vnum-badge">#${m.vnum}</span></td>
                        <td>${m.short_desc || 'Unnamed'}</td>
                        <td>${m.level}</td>
                        <td>${m.race}</td>
                        <td>${m.area || '-'}</td>
                    </tr>
                `).join('');
            } else if(currentDb === 'objects') {
                headerHtml = '<th>Vnum</th><th>Name</th><th>Type</th><th>Level</th><th>Area</th>';
                rowsHtml = data.map(o => `
                    <tr>
                        <td><span class="badge vnum-badge">#${o.vnum}</span></td>
                        <td>${o.short_desc || 'Unnamed'}</td>
                        <td>${o.item_type}</td>
                        <td>${o.level}</td>
                        <td>${o.area || '-'}</td>
                    </tr>
                `).join('');
            } else if(currentDb === 'rooms') {
                headerHtml = '<th>Vnum</th><th>Name</th><th>Sector</th><th>Area</th>';
                rowsHtml = data.map(r => `
                    <tr>
                        <td><span class="badge vnum-badge">#${r.vnum}</span></td>
                        <td>${r.name || 'Unnamed'}</td>
                        <td>${r.sector_type}</td>
                        <td>${r.area || '-'}</td>
                    </tr>
                `).join('');
            } else if(currentDb === 'areas') {
                headerHtml = '<th>Name</th><th>Filename</th><th>Builders</th><th>Vnums</th>';
                rowsHtml = data.map(a => `
                    <tr>
                        <td>${a.name}</td>
                        <td><code>${a.filename}</code></td>
                        <td>${a.builders}</td>
                        <td>${a.vnums}</td>
                    </tr>
                `).join('');
            }

            headers.innerHTML = headerHtml;
            content.innerHTML = rowsHtml || '<tr><td colspan="5" class="text-center py-4">No results found</td></tr>';
        }

        function filterDb() {
            const q = document.getElementById('db-search').value.toLowerCase();
            const filtered = dbData[currentDb].filter(item => 
                JSON.stringify(item).toLowerCase().includes(q)
            );
            renderDb(filtered);
        }

        // Stats
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const s = await res.json();
                document.getElementById('stat-mobs').textContent = s.mobiles;
                document.getElementById('stat-objs').textContent = s.objects;
                document.getElementById('stat-rooms').textContent = s.rooms;
                document.getElementById('stat-areas').textContent = s.areas;
            } catch(e) { console.error(e); }
        }

        // Utils
        function showToast(msg, isError = false) {
            const el = document.getElementById('liveToast');
            const body = document.getElementById('toast-msg');
            el.classList.toggle('text-bg-danger', isError);
            el.classList.toggle('text-bg-primary', !isError);
            body.textContent = msg;
            const toast = new bootstrap.Toast(el);
            toast.show();
        }

        // Init
        loadStats();
        setInterval(refreshLogs, 5000);
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
        "extra_flags": decoded_extra_flags,
        "extra_flags_raw": obj.extra_flags,
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
'''

Path("webadmin/server.py").write_text(content, encoding="utf-8")
