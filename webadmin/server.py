from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return """
    <html>
      <head>
        <title>ToC Web Admin</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 2rem; }
          form { margin-bottom: 1.5rem; }
          label { display: block; margin-bottom: 0.25rem; font-weight: bold; }
          textarea, input[type=text] { width: 100%; max-width: 720px; padding: 0.5rem; }
          button { padding: 0.5rem 1rem; }
          .card { border: 1px solid #ccc; padding: 1rem; border-radius: 6px; margin-bottom: 1.5rem; }
        </style>
      </head>
      <body>
        <h1>ToC Web Administration</h1>
        <div class="card">
          <h2>WizInfo Broadcast</h2>
          <form method="post" action="/api/wizinfo" onsubmit="return submitForm(event, this);">
            <label for="message">Message</label>
            <textarea name="message" rows="3" required></textarea>
            <label for="level">Minimum Level (optional, defaults to 62)</label>
            <input type="text" name="level" placeholder="62" />
            <button type="submit">Send WizInfo</button>
          </form>
        </div>
        <div class="card">
          <h2>Run Immortal Command</h2>
          <form method="post" action="/api/command" onsubmit="return submitForm(event, this);">
            <label for="command">Command</label>
            <input type="text" name="command" placeholder="copyover" required />
            <button type="submit">Run Command</button>
          </form>
        </div>
        <div class="card">
          <h2>Backups &amp; Control</h2>
          <button onclick="simplePost('/api/backup')">Run Backup</button>
          <button onclick="simplePost('/api/shutdown')">Request Shutdown</button>
        </div>
        <div class="card">
          <h2>Latest Log</h2>
          <pre id="log" style="white-space: pre-wrap; background: #111; color: #0f0; padding: 1rem; max-height: 400px; overflow: auto;">Loading...</pre>
        </div>
        <script>
          async function submitForm(event, form) {
            event.preventDefault();
            const data = new FormData(form);
            const body = {};
            data.forEach((value, key) => {
              if (value !== '') { body[key] = value; }
            });
            const res = await fetch(form.action, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(body)
            });
            alert(await res.text());
            return false;
          }
          async function simplePost(url) {
            const res = await fetch(url, { method: 'POST' });
            alert(await res.text());
          }
          async function refreshLog() {
            const res = await fetch('/api/logs');
            if (res.ok) {
              document.getElementById('log').textContent = await res.text();
            }
          }
          refreshLog();
          setInterval(refreshLog, 15000);
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
