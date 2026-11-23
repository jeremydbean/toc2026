"""Support units installed and proved, and the operations summary that
monitors and reviews read first (review, 2026-11-23).

- deploy/windows-vm/toc-install-units installs every support unit that
  changed, reloads once, keeps a disabled unit disabled, never restarts a
  service, leaves the encrypted backup's timer off until it is configured,
  and proves what systemd loaded.
- deploy/windows-vm/toc-ops-summary judges the sync, the encrypted backup,
  the game's archives, the disk, recovery and the units from what each
  recorded, writes a redacted verdict, and pings a heartbeat only when it is
  true. "not configured" is never healthy.
- webadmin/ops_status.py: /api/ready is 503 unless the game's loop answers,
  and /api/ops-summary is 503 unless the verdict is ok and fresh.

A stand-in systemctl keeps unit state in a directory: what is installed,
enabled and active, and whether a unit file changed since the last reload.
Nothing touches a real host path.
"""
from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VM = ROOT / "deploy" / "windows-vm"
INSTALL = VM / "toc-install-units"
SUMMARY = VM / "toc-ops-summary"
sys.path.insert(0, str(ROOT))
from webadmin import ops_status  # noqa: E402

FAKE_SYSTEMCTL = r"""#!/bin/sh
# Unit state in $SD: <unit>.enabled, <unit>.active, reloaded (a stamp).
echo "systemctl $*" >> "$SD/calls"
cmd=$1; shift
case "$cmd" in
daemon-reload) [ -f "$SD/reload-fails" ] && exit 1; date +%s%N > "$SD/reloaded"; exit 0 ;;
enable) now=0; [ "$1" = --now ] && { now=1; shift; }
        for u in "$@"; do touch "$SD/$u.enabled"; [ "$now" = 1 ] && touch "$SD/$u.active"; done; exit 0 ;;
restart|start) for u in "$@"; do touch "$SD/$u.active"; done; exit 0 ;;
is-enabled) if [ -f "$SD/$1.masked" ]; then echo masked; exit 1; fi
            if [ -f "$SD/$1.enabled" ]; then echo enabled; exit 0; fi; echo disabled; exit 1 ;;
show) u=$1
      if [ -f "$UD/$u" ] && [ ! -f "$SD/$u.unloadable" ]; then
          echo LoadState=loaded; echo "FragmentPath=$UD/$u"
          changed=$(stat -c %Y "$UD/$u")000000000; reloaded=$(cat "$SD/reloaded" 2>/dev/null || echo 0)
          if [ -f "$SD/$u.stale" ] || [ "$changed" -gt "$reloaded" ]; then echo NeedDaemonReload=yes; else echo NeedDaemonReload=no; fi
      else echo LoadState=not-found; echo FragmentPath=; echo NeedDaemonReload=no; fi
      if [ -f "$SD/$u.active" ]; then echo ActiveState=active; else echo ActiveState=inactive; fi
      if [ -f "$SD/$u.enabled" ]; then echo UnitFileState=enabled; else echo UnitFileState=disabled; fi
      exit 0 ;;
esac
exit 0
"""

UNITS = ["toc-state-sync.service", "toc-state-sync.timer", "toc-state-sync-check.service",
         "toc-state-sync-check.timer", "toc-game-recovery.service", "toc-game-recovery.timer",
         "toc-auto-deploy.service", "toc-auto-deploy.timer", "toc-host-action.service",
         "toc-host-action.path", "toc-player-backup.service", "toc-player-backup.timer",
         "toc-heartbeat.service", "toc-heartbeat.timer"]


class FakeHost:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.units = root / "etc-systemd"
        self.sd = root / "systemd-state"
        self.bin = root / "bin"
        for d in (self.units, self.sd, self.bin):
            d.mkdir(parents=True, exist_ok=True)
        (self.bin / "systemctl").write_text(FAKE_SYSTEMCTL)
        (self.bin / "systemctl").chmod(0o755)
        (self.sd / "reloaded").write_text("0\n")
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", SD=str(self.sd),
                        UD=str(self.units), TOC_UNIT_DIR=str(self.units),
                        TOC_BACKUP_ENV=str(root / "player-backup.env"),
                        TOC_UNITS_INTRODUCED=str(root / "units-introduced"))
        # The game's and dashboard's units, which toc-deploy installs itself.
        for unit in ("toc-game.service", "toc-web.service"):
            (self.units / unit).write_text((VM / unit).read_text())

    def calls(self) -> list[str]:
        path = self.sd / "calls"
        return path.read_text().splitlines() if path.exists() else []

    def install(self, src: Path = VM) -> subprocess.CompletedProcess:
        return subprocess.run(["sh", str(INSTALL), str(src)], env=self.env,
                              capture_output=True, text=True, timeout=60)


class InstallUnitsTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.host = FakeHost(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_a_bare_host_gets_every_unit_enabled_and_verified(self) -> None:
        done = self.host.install()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("support units verified", done.stdout)
        for unit in UNITS:
            self.assertTrue((self.host.units / unit).exists(), unit)
        calls = self.host.calls()
        self.assertEqual(calls.count("systemctl daemon-reload"), 1, "one reload")
        for timer in ("toc-state-sync.timer", "toc-state-sync-check.timer",
                      "toc-game-recovery.timer", "toc-auto-deploy.timer",
                      "toc-heartbeat.timer", "toc-host-action.path"):
            self.assertIn(f"systemctl enable --now {timer}", calls)
        # Not configured: installed and left off, and said so.
        self.assertNotIn("systemctl enable --now toc-player-backup.timer", calls)
        self.assertIn("the encrypted backup is not configured", done.stdout)
        # No service is ever started or restarted here.
        self.assertFalse([c for c in calls if ".service" in c and
                          c.split()[1] in ("start", "restart", "enable")], calls)

    def test_the_backup_timer_is_enabled_once_configured(self) -> None:
        (self.host.root / "player-backup.env").write_text("BACKUP_REMOTE=x\n")
        done = self.host.install()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("systemctl enable --now toc-player-backup.timer", self.host.calls())

    def test_a_changed_unit_is_reloaded_and_its_timer_restarted(self) -> None:
        self.assertEqual(self.host.install().returncode, 0)
        src = self.host.root / "src"
        src.mkdir()
        for unit in UNITS:
            (src / unit).write_text((VM / unit).read_text())
        (src / "toc-state-sync.timer").write_text(
            (VM / "toc-state-sync.timer").read_text() + "# changed\n")
        (src / "toc-state-sync.service").write_text(
            (VM / "toc-state-sync.service").read_text() + "# changed\n")
        (self.host.sd / "calls").unlink()
        time.sleep(1.1)
        done = self.host.install(src)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        calls = self.host.calls()
        self.assertIn("systemctl daemon-reload", calls)
        self.assertIn("systemctl restart toc-state-sync.timer", calls)
        self.assertNotIn("systemctl restart toc-state-sync.service", calls)
        self.assertEqual((self.host.units / "toc-state-sync.service").read_text(),
                         (src / "toc-state-sync.service").read_text())

    def test_a_disabled_unit_stays_disabled(self) -> None:
        self.assertEqual(self.host.install().returncode, 0)
        (self.host.sd / "toc-game-recovery.timer.enabled").unlink()
        (self.host.sd / "toc-game-recovery.timer.active").unlink()
        src = self.host.root / "src"
        src.mkdir()
        for unit in UNITS:
            (src / unit).write_text((VM / unit).read_text())
        (src / "toc-game-recovery.timer").write_text(
            (VM / "toc-game-recovery.timer").read_text() + "# changed\n")
        (self.host.sd / "calls").unlink()
        time.sleep(1.1)
        done = self.host.install(src)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("toc-game-recovery.timer left disabled", done.stdout)
        self.assertFalse([c for c in self.host.calls() if "toc-game-recovery.timer" in c
                          and c.split()[1] in ("enable", "restart", "start")])

    def test_the_backup_timer_is_enabled_by_the_first_run_that_finds_it_configured(self) -> None:
        self.assertEqual(self.host.install().returncode, 0)
        self.assertNotIn("systemctl enable --now toc-player-backup.timer", self.host.calls())
        (self.host.root / "player-backup.env").write_text("BACKUP_REMOTE=x\n")
        self.assertEqual(self.host.install().returncode, 0)
        self.assertIn("systemctl enable --now toc-player-backup.timer", self.host.calls())

    def test_units_a_person_set_up_before_are_theirs(self) -> None:
        """An existing host: units installed before this existed, one of them
        switched off on purpose. The installer never turns it back on."""
        for unit in UNITS:
            (self.host.units / unit).write_text((VM / unit).read_text())
        for unit in ("toc-state-sync.timer", "toc-heartbeat.timer"):
            (self.host.sd / f"{unit}.enabled").write_text("")
            (self.host.sd / f"{unit}.active").write_text("")
        done = self.host.install()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse([c for c in self.host.calls() if c.split()[1] in ("enable", "restart")],
                         self.host.calls())

    def test_unchanged_units_are_left_alone(self) -> None:
        self.assertEqual(self.host.install().returncode, 0)
        (self.host.sd / "calls").unlink()
        done = self.host.install()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse([c for c in self.host.calls() if c.split()[1] != "show"
                          and c.split()[1] != "is-enabled"], self.host.calls())

    def test_a_failed_reload_and_an_unloaded_unit_are_reported(self) -> None:
        (self.host.sd / "reload-fails").write_text("")
        done = self.host.install()
        self.assertEqual(done.returncode, 1)
        self.assertIn("daemon-reload failed", done.stderr)
        (self.host.sd / "reload-fails").unlink()
        # The next run reloads what the last could not, and enables the
        # timers it never got to.
        done = self.host.install()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("systemctl enable --now toc-heartbeat.timer", self.host.calls())
        (self.host.sd / "toc-state-sync.service.stale").write_text("")
        done = self.host.install()
        self.assertEqual(done.returncode, 2)
        self.assertIn("NOT VERIFIED toc-state-sync.service: changed on disk and not reloaded",
                      done.stderr)
        (self.host.sd / "toc-state-sync.service.stale").unlink()
        (self.host.sd / "toc-heartbeat.timer.active").unlink()
        done = self.host.install()
        self.assertEqual(done.returncode, 2)
        self.assertIn("NOT VERIFIED toc-heartbeat.timer: enabled but inactive", done.stderr)

    def test_the_deploy_and_restore_use_it(self) -> None:
        deploy = (VM / "toc-deploy").read_text()
        restore = (ROOT / "deploy" / "toc-restore").read_text()
        auto = (VM / "toc-auto-deploy").read_text()
        self.assertIn('sh "$BUILD/deploy/windows-vm/toc-install-units" "$BUILD/deploy/windows-vm"', deploy)
        self.assertIn('sh "$BUILD/deploy/windows-vm/toc-install-units" "$BUILD/deploy/windows-vm"', restore)
        self.assertIn("toc-install-units", auto)
        self.assertIn("toc-ops-summary", deploy)
        self.assertIn("/usr/local/sbin/toc-player-backup", deploy)
        # Every unit file the repository ships is on one list or the other.
        shipped = {p.name for p in VM.iterdir() if p.suffix in (".service", ".timer", ".path")}
        listed = set(UNITS) | {"toc-game.service", "toc-web.service"}
        self.assertEqual(shipped - listed, set(), "a unit nothing installs")


class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")
        self.server.seen.append(self.path)  # type: ignore[attr-defined]

    def log_message(self, *args) -> None:
        pass


class OpsSummaryTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self._tmp.name)
        self.host = FakeHost(root)
        self.assertEqual(self.host.install().returncode, 0)
        self.live = root / "live"
        for d in ("log", "backups", "area"):
            (self.live / d).mkdir(parents=True)
        (self.live / "area" / "webadmin.queue").write_text("")
        (self.live / "backups" / "Nov.23.tar.gz").write_bytes(b"x")
        self.sync, self.backup, self.state = root / "sync", root / "backup", root / "lib-toc"
        for d in (self.sync, self.backup, self.state):
            d.mkdir()
        now = int(time.time())
        (self.sync / "last-success").write_text(f"time={now}\nkind=pushed\nremote_commit={'a' * 40}\n")
        (self.sync / "last-attempt").write_text(f"time={now}\nresult=ok\nreason=pushed 3 files\n")
        (self.state / "recovery-last").write_text(f"time={now}\nexit=0\nsaid=healthy\n")
        probe = root / "probe"
        probe.write_text("#!/bin/sh\necho 2\n")
        probe.chmod(0o755)
        self.server = http.server.HTTPServer(("127.0.0.1", 0), Health)
        self.server.seen = []  # type: ignore[attr-defined]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{port}"
        self.env = dict(self.host.env, TOC_LIVE_ROOT=str(self.live),
                        TOC_OPS_SUMMARY=str(root / "ops-summary.json"),
                        TOC_SYNC_STATE_DIR=str(self.sync), TOC_BACKUP_STATE_DIR=str(self.backup),
                        TOC_BACKUP_ENV=str(root / "player-backup.env"),
                        TOC_STATE_DIR=str(self.state), TOC_HEARTBEAT_ENV=str(root / "heartbeat.env"),
                        TOC_GAME_PROBE=str(probe), TOC_WEB_HEALTH_URL=f"{self.base}/api/health",
                        TOC_DISK_PATH=str(root), TOC_DISK_MIN_FREE_MB="1",
                        TOC_DISK_MIN_INODE_PCT="0")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()

    def configure_backup(self, age_min: int = 10) -> None:
        (self.root / "player-backup.env").write_text("BACKUP_REMOTE=x\n")
        when = int(time.time()) - age_min * 60
        (self.backup / "status").write_text("ok\n")
        (self.backup / "last-success").write_text(
            f"time={when}\nremote_commit={'b' * 40}\ngenerations=5\narchive_bytes=1234\n")
        (self.backup / "last-attempt").write_text(f"time={when}\nresult=ok\nreason=pushed\n")
        (self.host.sd / "toc-player-backup.timer.enabled").write_text("")
        (self.host.sd / "toc-player-backup.timer.active").write_text("")

    def run_summary(self) -> tuple[subprocess.CompletedProcess, dict]:
        done = subprocess.run([sys.executable, str(SUMMARY)], env=self.env,
                              capture_output=True, text=True, timeout=60)
        out = json.loads((self.root / "ops-summary.json").read_text())
        return done, out

    def test_unconfigured_private_backup_is_never_ok(self) -> None:
        done, out = self.run_summary()
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertEqual(out["overall"], "degraded")
        self.assertEqual(out["checks"]["private_backup"]["status"], "not-configured")
        self.assertFalse(out["checks"]["private_backup"]["ok"])
        self.assertEqual(out["problems"], ["private_backup: not configured (no encrypted off-host copy)"])
        self.assertTrue(out["checks"]["public_sync"]["ok"])
        self.assertEqual(out["heartbeat"], {"heartbeat": "not-configured",
                                            "backup_heartbeat": "not-configured"})
        # The copy the state sync carries to GitHub.
        self.assertEqual(json.loads((self.live / "log" / "ops-summary.json").read_text())["overall"],
                         "degraded")

    def test_all_well_is_ok_and_both_heartbeats_go(self) -> None:
        self.configure_backup()
        (self.root / "heartbeat.env").write_text(
            f'HEARTBEAT_URL="{self.base}/ping/host"\nBACKUP_HEARTBEAT_URL={self.base}/ping/backup\n')
        done, out = self.run_summary()
        self.assertEqual(done.returncode, 0, out["problems"])
        self.assertEqual(out["overall"], "ok")
        self.assertEqual(out["heartbeat"], {"heartbeat": "sent ok", "backup_heartbeat": "sent ok"})
        self.assertIn("/ping/host", self.server.seen)  # type: ignore[attr-defined]
        self.assertIn("/ping/backup", self.server.seen)  # type: ignore[attr-defined]
        code, body = ops_status.ops_summary(self.root / "ops-summary.json")
        self.assertEqual(code, 200)
        self.assertEqual(body["overall"], "ok")

    def test_each_failure_is_named_and_the_heartbeat_says_fail(self) -> None:
        self.configure_backup(age_min=9 * 60)
        (self.root / "heartbeat.env").write_text(
            f"HEARTBEAT_URL={self.base}/ping/host\nBACKUP_HEARTBEAT_URL={self.base}/ping/backup\n")
        old = int(time.time()) - 3600
        (self.sync / "last-success").write_text(f"time={old}\nkind=pushed\n")
        (self.sync / "last-attempt").write_text(
            f"time={int(time.time())}\nresult=failed\nreason=push failed after 5 attempts from 203.0.113.7\n")
        (self.state / "recovery-failures").write_text("3\n")
        (self.state / "recovery-last").write_text(f"time={int(time.time())}\nexit=1\nsaid=fetch failed\n")
        os.utime(self.live / "backups" / "Nov.23.tar.gz", (old - 6 * 3600, old - 6 * 3600))
        (self.host.sd / "toc-state-sync.timer.active").unlink()
        probe = self.root / "probe"
        probe.write_text("#!/bin/sh\necho unknown\n")
        done, out = self.run_summary()
        self.assertEqual(done.returncode, 1)
        joined = "\n".join(out["problems"])
        for word in ("game: unknown", "public_sync: last verified sync 60 min ago",
                     "private_backup: last verified copy 9 h ago", "game_archives: newest is",
                     "recovery: last run exited 1", "toc-state-sync.timer inactive"):
            self.assertIn(word, joined)
        self.assertNotIn("203.0.113.7", (self.root / "ops-summary.json").read_text())
        self.assertIn("<address>", joined)
        self.assertEqual(out["heartbeat"], {"heartbeat": "sent fail", "backup_heartbeat": "sent fail"})
        self.assertIn("/ping/host/fail", self.server.seen)  # type: ignore[attr-defined]
        # Staff hear of the broken private backup, once an hour.
        queue = (self.live / "area" / "webadmin.queue").read_text()
        self.assertIn("wizinfo|60|The encrypted off-host player backup is not working", queue)
        self.run_summary()
        self.assertEqual((self.live / "area" / "webadmin.queue").read_text(), queue)

    def test_a_refused_drop_is_a_problem_at_once(self) -> None:
        self.configure_backup()
        (self.sync / "last-attempt").write_text(
            f"time={int(time.time())}\nresult=failed\nreason=refused: the live tree shrank\n")
        done, out = self.run_summary()
        self.assertIn("public_sync: refused: the live tree shrank", out["problems"])

    def test_an_uninstalled_or_unreloaded_unit_is_named(self) -> None:
        self.configure_backup()
        (self.host.units / "toc-heartbeat.timer").unlink()
        (self.host.sd / "toc-state-sync.service.stale").write_text("")
        done, out = self.run_summary()
        joined = "\n".join(out["problems"])
        self.assertIn("toc-heartbeat.timer not installed", joined)
        self.assertIn("toc-state-sync.service changed on disk, not reloaded", joined)


class ReadinessTests(unittest.TestCase):

    def test_ready_only_when_the_loop_answers(self) -> None:
        self.assertEqual(ops_status.readiness(lambda: (True, 0))[0], 200)
        code, body = ops_status.readiness(lambda: (True, None))
        self.assertEqual((code, body["game"]), (503, "not answering"))
        code, body = ops_status.readiness(lambda: (False, None))
        self.assertEqual((code, body["game"]), (503, "down"))

    def test_the_summary_route_judges_freshness_and_form(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            self.assertEqual(ops_status.ops_summary(path)[0], 503)
            path.write_text("not json")
            self.assertEqual(ops_status.ops_summary(path)[1]["overall"], "unknown")
            now = time.time()
            path.write_text(json.dumps({"overall": "ok", "generated": now - 60,
                                        "problems": [], "note": "from 198.51.100.4"}))
            code, body = ops_status.ops_summary(path, now=now)
            self.assertEqual(code, 200)
            self.assertEqual(body["note"], "from <address>")
            code, body = ops_status.ops_summary(path, now=now + 3600)
            self.assertEqual((code, body["overall"]), (503, "stale"))
            path.write_text(json.dumps({"overall": "degraded", "generated": now}))
            self.assertEqual(ops_status.ops_summary(path, now=now)[0], 503)

    def test_only_judges_the_checks_named(self) -> None:
        """One monitor per concern (2026-11-23): an encrypted backup not yet
        set up must not hold the sync's monitor red, and staleness always
        counts."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            now = time.time()
            path.write_text(json.dumps({
                "overall": "degraded", "generated": now,
                "checks": {"public_sync": {"ok": True}, "disk": {"ok": True},
                           "private_backup": {"ok": False, "status": "not-configured"}}}))
            only, error = ops_status.parse_only("public_sync, disk")
            self.assertIsNone(error)
            code, body = ops_status.ops_summary(path, now=now, only=only)
            self.assertEqual((code, body["verdict"], body["failing"]), (200, "ok", []))
            only, _ = ops_status.parse_only("private_backup")
            code, body = ops_status.ops_summary(path, now=now, only=only)
            self.assertEqual((code, body["failing"]), (503, ["private_backup"]))
            # A check the summary does not carry is not a pass.
            only, _ = ops_status.parse_only("recovery")
            self.assertEqual(ops_status.ops_summary(path, now=now, only=only)[0], 503)
            only, _ = ops_status.parse_only("public_sync")
            self.assertEqual(ops_status.ops_summary(path, now=now + 3600, only=only)[0], 503)
            self.assertEqual(ops_status.ops_summary(path, now=now)[0], 503, "whole verdict unchanged")
        self.assertIn("unknown check", ops_status.parse_only("public_sync,bogus")[1])
        self.assertEqual(ops_status.parse_only(""), (None, None))

    def test_the_routes_exist_and_need_no_token(self) -> None:
        server = (ROOT / "webadmin" / "server.py").read_text()
        for route in ('@app.get("/api/ready")', '@app.get("/api/ops-summary")'):
            at = server.index(route)
            self.assertNotIn("verify_token", server[at:server.index("\n\n\n", at)])


try:
    from fastapi.testclient import TestClient
    from webadmin import server as web_server
    ROUTE_SKIP = None
except Exception as error:  # noqa: BLE001
    ROUTE_SKIP = f"web test client unavailable ({type(error).__name__}: {error})"


@unittest.skipIf(ROUTE_SKIP is not None, ROUTE_SKIP or "")
class RouteTests(unittest.TestCase):
    """The routes through the real app, with the game probe and the summary
    file stood in for."""

    def test_ready_and_summary_routes(self) -> None:
        from unittest.mock import patch
        client = TestClient(web_server.app)
        with patch.object(web_server, "probe_game", lambda timeout=1.0: (True, 3)):
            reply = client.get("/api/ready")
        self.assertEqual((reply.status_code, reply.json()["ready"]), (200, True))
        self.assertEqual(reply.headers["cache-control"], "no-store")
        with patch.object(web_server, "probe_game", lambda timeout=1.0: (False, None)):
            self.assertEqual(client.get("/api/ready").status_code, 503)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ops.json"
            with patch.object(web_server, "OPS_SUMMARY_PATH", path):
                self.assertEqual(client.get("/api/ops-summary").status_code, 503)
                path.write_text(json.dumps({"overall": "ok", "generated": time.time()}))
                reply = client.get("/api/ops-summary")
                self.assertEqual((reply.status_code, reply.json()["overall"]), (200, "ok"))
                path.write_text(json.dumps({"overall": "degraded", "generated": time.time(),
                                            "checks": {"disk": {"ok": True},
                                                       "private_backup": {"ok": False}}}))
                self.assertEqual(client.get("/api/ops-summary?only=disk").status_code, 200)
                self.assertEqual(client.get("/api/ops-summary?only=private_backup").status_code, 503)
                bad = client.get("/api/ops-summary?only=bogus")
                self.assertEqual(bad.status_code, 400)
                self.assertIn("unknown check", bad.json()["error"])


if __name__ == "__main__":
    unittest.main()
