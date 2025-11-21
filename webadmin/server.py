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

    <!-- Object Detail Modal -->
    <div class="modal fade" id="objectModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content bg-dark border-secondary text-light">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title">Object Details</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="object-modal-body">
                    <!-- Content injected via JS -->
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
                    <tr style="cursor: pointer" data-vnum="${o.vnum}">
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

        let objectModal = null;

        async function showObject(vnum) {
            if (!objectModal) {
                objectModal = new bootstrap.Modal(document.getElementById('objectModal'));
            }
            
            const body = document.getElementById('object-modal-body');
            body.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div></div>';
            objectModal.show();

            try {
                const res = await fetch('/api/objects/' + vnum);
                const obj = await res.json();
                
                let affectsHtml = obj.affects.map(a => `<span class="badge bg-info me-1">${a}</span>`).join('');
                if (!affectsHtml) affectsHtml = '<span class="text-muted">None</span>';

                let extraFlagsHtml = obj.extra_flags.map(f => `<span class="badge bg-secondary me-1">${f}</span>`).join('');
                if (!extraFlagsHtml) extraFlagsHtml = '<span class="text-muted">None</span>';

                let wearFlagsHtml = obj.wear_flags.map(f => `<span class="badge bg-secondary me-1">${f}</span>`).join('');
                if (!wearFlagsHtml) wearFlagsHtml = '<span class="text-muted">None</span>';

                let valuesHtml = obj.values.map((v, i) => `<div><strong>Val ${i}:</strong> ${v}</div>`).join('');

                body.innerHTML = `
                    <div class="row mb-3">
                        <div class="col-md-8">
                            <h4>${obj.short_desc} <span class="badge vnum-badge">#${obj.vnum}</span></h4>
                            <p class="text-muted"><em>${obj.long_desc}</em></p>
                        </div>
                        <div class="col-md-4 text-end">
                            <span class="badge bg-primary">${obj.item_type}</span>
                            <div class="mt-2">Level: ${obj.level}</div>
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <div class="card bg-dark border-secondary mb-3">
                                <div class="card-header py-1">Properties</div>
                                <div class="card-body py-2">
                                    <div><strong>Material:</strong> ${obj.material}</div>
                                    <div><strong>Weight:</strong> ${obj.weight}</div>
                                    <div><strong>Cost:</strong> ${obj.cost}</div>
                                    <div><strong>Condition:</strong> ${obj.condition}</div>
                                    <div><strong>Area:</strong> ${obj.area} (${obj.area_file})</div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card bg-dark border-secondary mb-3">
                                <div class="card-header py-1">Values</div>
                                <div class="card-body py-2">
                                    ${valuesHtml}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="mb-3">
                        <strong>Extra Flags:</strong> ${extraFlagsHtml} <small class="text-muted">(${obj.extra_flags_raw})</small><br>
                        <strong>Extra Flags 2:</strong> <small class="text-muted">${obj.extra_flags2_raw}</small><br>
                        <strong>Wear Flags:</strong> ${wearFlagsHtml} <small class="text-muted">(${obj.wear_flags_raw})</small>
                    </div>

                    <div class="mb-3">
                        <strong>Affects:</strong><br>
                        ${affectsHtml}
                    </div>
                    
                    ${obj.extra_descr.length > 0 ? `
                    <div class="mb-3">
                        <strong>Extra Descriptions:</strong>
                        ${obj.extra_descr.map(ed => `
                            <div class="border-start border-secondary ps-2 mt-1">
                                <strong>${ed.keywords}:</strong> ${ed.description}
                            </div>
                        `).join('')}
                    </div>` : ''}
                `;
            } catch(e) {
                body.innerHTML = `<div class="alert alert-danger">Error loading object: ${e}</div>`;
            }
        }

        // Event delegation for table clicks
        document.getElementById('db-content').addEventListener('click', function(e) {
            const row = e.target.closest('tr');
            if (row && row.dataset.vnum && currentDb === 'objects') {
                showObject(row.dataset.vnum);
            }
        });

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
