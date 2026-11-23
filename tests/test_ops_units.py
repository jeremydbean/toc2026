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
      if [ -f "$SD/$u.failed" ]; then echo ActiveState=failed
      elif [ -f "$SD/$u.active" ]; then echo ActiveState=active; else echo ActiveState=inactive; fi
      if [ -f "$SD/$u.enabled" ]; then echo UnitFileState=enabled; else echo UnitFileState=disabled; fi
      if [ -f "$SD/$u.env" ]; then echo "Environment=$(cat "$SD/$u.env")"; else echo Environment=; fi
      exit 0 ;;
esac
exit 0
"""

UNITS = ["toc-state-sync.service", "toc-state-sync.timer", "toc-state-sync.path",
         "toc-state-sync-check.service",
         "toc-state-sync-check.timer", "toc-game-recovery.service", "toc-game-recovery.timer",
         "toc-auto-deploy.service", "toc-auto-deploy.timer", "toc-host-action.service",
         "toc-host-action.path",
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
        for timer in ("toc-state-sync.timer", "toc-state-sync.path", "toc-state-sync-check.timer",
                      "toc-game-recovery.timer", "toc-auto-deploy.timer",
                      "toc-heartbeat.timer", "toc-host-action.path"):
            self.assertIn(f"systemctl enable --now {timer}", calls)
        # No service is ever started or restarted here.
        self.assertFalse([c for c in calls if ".service" in c and
                          c.split()[1] in ("start", "restart", "enable")], calls)

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
        self.archive("Nov.23.tar.gz")
        self.sync, self.state = root / "sync", root / "lib-toc"
        for d in (self.sync, self.state):
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
                        TOC_SYNC_STATE_DIR=str(self.sync),
                        TOC_STATE_DIR=str(self.state), TOC_HEARTBEAT_ENV=str(root / "heartbeat.env"),
                        TOC_GAME_PROBE=str(probe), TOC_WEB_HEALTH_URL=f"{self.base}/api/health",
                        TOC_DISK_PATH=str(root), TOC_DISK_MIN_FREE_MB="1",
                        TOC_DISK_MIN_INODE_PCT="0")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()

    def archive(self, name: str, characters: dict[str, bytes] | None = None,
                cut: int | None = None) -> Path:
        """A synthetic game archive, laid out as backup_script's
        `tar cfz ... ../player`: never a real character."""
        import io
        import tarfile
        if characters is None:
            characters = {"Zarcha": b"#PLAYER\nName Zarcha~\nEnd\n#END\n"}
        path = self.live / "backups" / name
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for who, body in characters.items():
                info = tarfile.TarInfo(f"player/{who}")
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
            info = tarfile.TarInfo("player/recovery/ledger.tsv")
            info.size = 2
            tar.addfile(info, io.BytesIO(b"1\n"))
        data = buf.getvalue()
        path.write_bytes(data if cut is None else data[:cut])
        return path

    def mirror(self, configured: bool) -> None:
        env = self.host.sd / "toc-state-sync.service.env"
        if configured:
            env.write_text("TOC_SYNC_STATE_DIR=/x MIRROR_REMOTE=git@example:mirror.git")
        elif env.exists():
            env.unlink()

    def run_summary(self) -> tuple[subprocess.CompletedProcess, dict]:
        done = subprocess.run([sys.executable, str(SUMMARY)], env=self.env,
                              capture_output=True, text=True, timeout=60)
        out = json.loads((self.root / "ops-summary.json").read_text())
        return done, out

    def test_all_well_is_ok_and_the_heartbeat_goes(self) -> None:
        (self.root / "heartbeat.env").write_text(f'HEARTBEAT_URL="{self.base}/ping/host"\n')
        done, out = self.run_summary()
        self.assertEqual(done.returncode, 0, out["problems"])
        self.assertEqual(out["overall"], "ok")
        self.assertEqual(out["heartbeat"], {"heartbeat": "sent ok"})
        self.assertIn("/ping/host", self.server.seen)  # type: ignore[attr-defined]
        code, body = ops_status.ops_summary(self.root / "ops-summary.json")
        self.assertEqual(code, 200)
        self.assertEqual(body["overall"], "ok")

    def test_each_failure_is_named_and_the_heartbeat_says_fail(self) -> None:
        (self.root / "heartbeat.env").write_text(f"HEARTBEAT_URL={self.base}/ping/host\n")
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
                     "game_archives: newest is",
                     "recovery: last run exited 1", "toc-state-sync.timer inactive"):
            self.assertIn(word, joined)
        self.assertNotIn("203.0.113.7", (self.root / "ops-summary.json").read_text())
        self.assertIn("<address>", joined)
        self.assertEqual(out["heartbeat"], {"heartbeat": "sent fail"})
        self.assertIn("/ping/host/fail", self.server.seen)  # type: ignore[attr-defined]

    def test_a_refused_drop_is_a_problem_at_once(self) -> None:
        (self.sync / "last-attempt").write_text(
            f"time={int(time.time())}\nresult=failed\nreason=refused: the live tree shrank\n")
        done, out = self.run_summary()
        self.assertIn("public_sync: refused: the live tree shrank", out["problems"])

    def test_an_uninstalled_or_unreloaded_unit_is_named(self) -> None:
        (self.host.units / "toc-heartbeat.timer").unlink()
        (self.host.sd / "toc-state-sync.service.stale").write_text("")
        done, out = self.run_summary()
        joined = "\n".join(out["problems"])
        self.assertIn("toc-heartbeat.timer not installed", joined)
        self.assertIn("toc-state-sync.service changed on disk, not reloaded", joined)

    def test_the_mirror_is_off_until_it_runs_then_must_keep_up(self) -> None:
        """The private mirror (2026-11-23): never run is "off" and healthy;
        once it has a receipt, a failure or a stale one is a problem of its
        own, and never makes the public sync look broken."""
        done, out = self.run_summary()
        self.assertEqual((out["checks"]["mirror"]["ok"], out["checks"]["mirror"]["status"]),
                         (True, "off"))
        self.assertEqual(out["overall"], "ok", out["problems"])
        now = int(time.time())
        mirror = self.sync / "mirror"
        self.mirror(True)
        mirror.write_text(f"time={now}\nresult=ok\nreason=mirror holds abc\ncommit={'c' * 40}\n")
        done, out = self.run_summary()
        self.assertTrue(out["checks"]["mirror"]["ok"], out["problems"])
        mirror.write_text(f"time={now}\nresult=failed\nreason=rejected (fetch first)\ncommit={'c' * 40}\n")
        done, out = self.run_summary()
        self.assertFalse(out["checks"]["mirror"]["ok"])
        self.assertTrue(out["checks"]["public_sync"]["ok"], "the public copy is not blamed")
        self.assertIn("mirror: not updated (rejected (fetch first))", out["problems"])
        mirror.write_text(f"time={now - 3600}\nresult=ok\nreason=x\ncommit={'c' * 40}\n")
        done, out = self.run_summary()
        self.assertIn("mirror: last updated 60 min ago", out["problems"])
        only, error = ops_status.parse_only("mirror")
        self.assertIsNone(error, "mirror is a name ?only= accepts")

    def test_the_mirror_is_judged_by_configuration_too(self) -> None:
        """A missing receipt read "off" and healthy whatever the host was
        set to do (review, 2026-11-23)."""
        self.mirror(False)                                  # not wanted: off
        done, out = self.run_summary()
        self.assertEqual(out["checks"]["mirror"]["status"], "off")
        self.assertTrue(out["checks"]["mirror"]["ok"])
        self.mirror(True)                                   # wanted, sync has run, no receipt
        done, out = self.run_summary()
        self.assertEqual(out["checks"]["mirror"]["status"], "missing")
        self.assertFalse(out["checks"]["mirror"]["ok"])
        self.assertIn("mirror: configured, but it has never reported", "\n".join(out["problems"]))
        self.assertTrue(out["checks"]["public_sync"]["ok"], "the public copy is not blamed")
        (self.sync / "last-success").unlink()               # a fresh install: never synced
        done, out = self.run_summary()
        self.assertEqual(out["checks"]["mirror"]["status"], "pending")
        self.assertTrue(out["checks"]["mirror"]["ok"], "public_sync already names a sync that never ran")
        self.mirror(False)                                  # turned off with an old receipt left
        (self.sync / "mirror").write_text(f"time={int(time.time()) - 86400}\nresult=ok\n")
        done, out = self.run_summary()
        self.assertEqual(out["checks"]["mirror"]["status"], "off")

    def test_a_partial_success_is_not_a_whole_backup(self) -> None:
        """An hourly copy that failed, or unpushed commits kept aside, were a
        plain "ok" to monitoring (review, 2026-11-23)."""
        now = int(time.time())
        (self.sync / "last-success").write_text(
            f"time={now}\nkind=pushed\nremote_commit={'a' * 40}\npartial=hourly snapshots not copied\n")
        done, out = self.run_summary()
        self.assertFalse(out["checks"]["public_sync"]["ok"])
        self.assertIn("public_sync: pushed, but incomplete (hourly snapshots not copied)", out["problems"])
        (self.sync / "last-success").write_text(f"time={now}\nkind=pushed\npartial=\n")
        done, out = self.run_summary()
        self.assertTrue(out["checks"]["public_sync"]["ok"], out["problems"])

    def test_an_archive_is_judged_whole_not_by_its_age(self) -> None:
        """The newest archive counted by its mtime alone, so one damaged after
        it was made, or a well-formed archive of nothing, read healthy."""
        done, out = self.run_summary()
        self.assertTrue(out["checks"]["game_archives"]["verified"], out["problems"])
        self.assertEqual(out["checks"]["game_archives"]["characters"], 1)
        older = self.live / "backups" / "Nov.23.tar.gz"
        os.utime(older, (time.time() - 3600, time.time() - 3600))
        cases = {"truncated": dict(cut=60), "empty": dict(characters={}),
                 "not a character": dict(characters={"Zjunk": b"garbage\n"})}
        for label, how in cases.items():
            with self.subTest(label):
                self.archive("Nov.24.tar.gz", **how)
                done, out = self.run_summary()
                self.assertFalse(out["checks"]["game_archives"]["ok"], label)
                said = "\n".join(out["problems"])
                self.assertIn("game_archives: the newest (Nov.24.tar.gz)", said)
                self.assertIn("the last whole one is 1 h old", said, "how far back it goes")
        self.archive("Nov.24.tar.gz")                       # replaced by a whole one
        done, out = self.run_summary()
        self.assertTrue(out["checks"]["game_archives"]["ok"], out["problems"])

    def test_a_service_whose_last_run_failed_is_named(self) -> None:
        """A oneshot is "inactive" between runs, which is fine; "failed" is
        not. toc-state-sync-check failed every run for hours on 2026-11-23
        while the summary said units: ok."""
        done, out = self.run_summary()
        self.assertTrue(out["checks"]["units"]["ok"], out["problems"])
        (self.host.sd / "toc-state-sync-check.service.failed").write_text("")
        done, out = self.run_summary()
        self.assertFalse(out["checks"]["units"]["ok"])
        self.assertIn("toc-state-sync-check.service failed on its last run",
                      "\n".join(out["problems"]))

    def test_a_degraded_summary_recovers_though_its_own_unit_failed(self) -> None:
        """toc-ops-summary exits 1 whenever it is degraded, so systemd marks
        toc-heartbeat.service "failed". Judging that would keep the summary
        degraded for ever once anything slipped; it is never judged."""
        (self.host.sd / "toc-heartbeat.service.failed").write_text("")
        done, out = self.run_summary()
        self.assertEqual(out["overall"], "ok", out["problems"])
        self.assertEqual(done.returncode, 0)


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
        """One monitor per concern (2026-11-23): a check that is failing
        must not hold another concern's monitor red, and staleness always
        counts."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            now = time.time()
            path.write_text(json.dumps({
                "overall": "degraded", "generated": now,
                "checks": {"public_sync": {"ok": True}, "disk": {"ok": True},
                           "game_archives": {"ok": False, "status": "stale"}}}))
            only, error = ops_status.parse_only("public_sync, disk")
            self.assertIsNone(error)
            code, body = ops_status.ops_summary(path, now=now, only=only)
            self.assertEqual((code, body["verdict"], body["failing"]), (200, "ok", []))
            only, _ = ops_status.parse_only("game_archives")
            code, body = ops_status.ops_summary(path, now=now, only=only)
            self.assertEqual((code, body["failing"]), (503, ["game_archives"]))
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
        for route in ('@app.api_route("/api/ready", methods=["GET", "HEAD"])',
                      '@app.api_route("/api/ops-summary", methods=["GET", "HEAD"])'):
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
                                                       "game_archives": {"ok": False}}}))
                self.assertEqual(client.get("/api/ops-summary?only=disk").status_code, 200)
                self.assertEqual(client.get("/api/ops-summary?only=game_archives").status_code, 503)
                bad = client.get("/api/ops-summary?only=bogus")
                self.assertEqual(bad.status_code, 400)
                self.assertIn("unknown check", bad.json()["error"])

    def test_head_is_answered_for_the_monitored_routes(self) -> None:
        """UptimeRobot (and most uptime services) send HEAD. FastAPI does not
        answer HEAD on a GET route, so these read 405 -- an outage -- while
        the game was fine (2026-11-23)."""
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            path.write_text(json.dumps({"overall": "ok", "generated": time.time()}))
            with patch.object(web_server, "OPS_SUMMARY_PATH", path), \
                 patch.object(web_server, "probe_game", lambda timeout=1.5: (True, 0)):
                client = TestClient(web_server.app)
                for route in ("/api/health", "/api/ready", "/api/ops-summary"):
                    with self.subTest(route=route):
                        self.assertNotEqual(client.head(route).status_code, 405, route)


if __name__ == "__main__":
    unittest.main()
