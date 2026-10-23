"""Recovery under failure (independent review of 3876e95, 2026-10-23).

The first recovery-hardening pass was tested on its happy paths. The
review broke it with real failures, and each case here is one of those,
played against a disposable world with synthetic Z-named characters:

- A corpse restore whose save failed reported success, committed its
  receipt, refused a retry and dropped the only copy of what it gave. Now
  a failed save gives nothing (offline) and leaves the receipt
  abandoned, a crash between the save and the receipt is settled at the
  next login by the mark in the file, and a retry works.
- A history write that failed still deleted the live copy of an ended
  corpse; the exact remainder after looting was gone. Now the end state
  waits beside the live copy and reaches history once it can.
- A torn ledger line swallowed the next record and a player got a second
  uid. Now a torn tail is set aside and cut off, at boot and at once
  after a failed write.
- A full PRESTORE went on when its undo copy failed, or the online
  target's save did. Now it changes nothing.
- Durability that was not confirmed was reported as done. Now it is not.

Failures are real where they can be (PLAYER_TEMP made a directory, a
history directory replaced by a file, a .partial that cannot be written)
and injected at named points otherwise (TOC_FAULT, TOC_FAULT_FILE in
src/recovery.c, set nowhere but here).
"""
from __future__ import annotations

import pathlib
import re
import shutil
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zfailpass1"
ROOM = 4202


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud, name: str, level: int, room: int = ROOM) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed()
    patch_player_file(mud, name, Levl=level, Room=room)


def fnv(text: str) -> int:
    h = 2166136261
    for b in text.encode("latin-1"):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


def ledger_rows(mud) -> list[list[str]]:
    """Every record, each checked whole: a newline and a good check."""
    path = mud.player_dir / "recovery" / "ledger.tsv"
    if not path.exists():
        return []
    data = path.read_text(encoding="latin-1")
    assert data == "" or data.endswith("\n"), "the ledger ends in a torn record"
    rows = []
    for line in data.splitlines():
        body, _, check = line.rpartition("\t")
        assert len(check) == 8 and int(check, 16) == fnv(body), f"bad record: {line!r}"
        rows.append(body.split("\t"))
    return rows


def states(rows, request: str) -> list[str]:
    return [r[3] for r in rows if r[2] in ("request", "prestore") and r[6].startswith(request)]


def fault(mud, point: str) -> None:
    (mud.root / "fault.once").write_text(point + "\n")


def kill_and_end_corpse(mud, staff_name: str, dead_name: str) -> str:
    """Slay the dead one, staff pick the corpse up (it ends, carried),
    the dead quit. Returns the corpse id."""
    with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as dead:
        login(staff, staff_name, PW)
        login(dead, dead_name, PW)
        run(staff, f"slay {dead_name.lower()}", 2.0)
        run(staff, "get corpse", 2.5)
        for client in (dead, staff):
            client.send("quit")
            client.wait_closed()
    ended = list((mud.root / "corpse" / "history" / dead_name).glob("*.carried.corpse"))
    assert len(ended) == 1, ended
    return ended[0].name.split(".", 1)[0]


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseRestoreFailureTests(unittest.TestCase):
    def test_a_failed_save_gives_nothing_and_a_retry_works(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            make(mud, "Zrevstaff", 70)
            make(mud, "Zrevdead", 20)
            cid = kill_and_end_corpse(mud, "Zrevstaff", "Zrevdead")
            pfile = mud.player_dir / "Zrevdead"
            temp = mud.player_dir / "temp"
            with mud.connect(timeout=120) as staff:
                login(staff, "Zrevstaff", PW)
                run(staff, "scroll 0", 0.5)
                # PLAYER_TEMP a directory: no save can land, so the copy
                # that would undo it cannot be taken; nothing is given.
                temp.mkdir()
                blocked = run(staff, f"prestore zrevdead corpse {cid} gear", 2.5)
                temp.rmdir()
                after_blocked = pfile.read_text(encoding="latin-1")
                # The save after the pending receipt fails: offline, the
                # copy holding the gift goes unsaved, so it is abandoned.
                fault(mud, "save 2")
                failed = run(staff, f"prestore zrevdead corpse {cid} gear", 2.5)
                after_failed = pfile.read_text(encoding="latin-1")
                # Nothing in the way: given, and given once.
                given = run(staff, f"prestore zrevdead corpse {cid} gear", 2.5)
                again = run(staff, f"prestore zrevdead corpse {cid} gear", 2.0)
                staff.send("quit")
                staff.wait_closed()
            after_given = pfile.read_text(encoding="latin-1")
            rows = ledger_rows(mud)

        self.assertIn("Nothing was given", blocked)
        self.assertNotIn("Restored", blocked)
        self.assertNotIn(f"restore:corpse:{cid}", after_blocked)
        self.assertIn("Nothing was given", failed)
        self.assertIn("could not be saved", failed)
        self.assertNotIn(f"restore:corpse:{cid}", after_failed)
        self.assertRegex(given, r"Restored \d+ object")
        self.assertIn(f"restore:corpse:{cid}", after_given)
        self.assertGreater(after_given.count("#O\n"), after_failed.count("#O\n"))
        self.assertIn("already given back once", again)
        self.assertEqual(states(rows, f"corpse:{cid}"), ["pending", "abandoned", "pending", "committed"])

    def test_a_crash_between_the_save_and_the_receipt_is_settled_at_login(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            make(mud, "Zcrstaff", 70)
            make(mud, "Zcrdead", 20)
            cid = kill_and_end_corpse(mud, "Zcrstaff", "Zcrdead")
            with mud.connect(timeout=120) as staff:
                login(staff, "Zcrstaff", PW)
                fault(mud, "crash-before-commit")
                staff.send(f"prestore zcrdead corpse {cid} gear")
                self.assertTrue(staff.wait_closed(), "the game should have stopped")
            pending = states(ledger_rows(mud), f"corpse:{cid}")
            saved = (mud.player_dir / "Zcrdead").read_text(encoding="latin-1")
            mud.restart()
            with mud.connect(timeout=120) as dead:
                login(dead, "Zcrdead", PW)
                run(dead, "scroll 0", 0.5)
                inventory = run(dead, "inventory", 1.5)
                dead.send("quit")
                dead.wait_closed()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zcrstaff", PW)
                again = run(staff, f"prestore zcrdead corpse {cid} gear", 2.0)
                staff.send("quit")
                staff.wait_closed()
            rows = ledger_rows(mud)

        self.assertEqual(pending, ["pending"])
        self.assertIn(f"restore:corpse:{cid}", saved)
        self.assertEqual(inventory.count("sub issue sword"), 1, inventory)
        self.assertEqual(states(rows, f"corpse:{cid}"), ["pending", "committed"])
        self.assertTrue(any(r[2] == "request" and r[3] == "committed" and r[8] == "login"
                            for r in rows))
        self.assertIn("already given back once", again)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseArchiveFailureTests(unittest.TestCase):
    def test_an_end_state_that_cannot_reach_history_is_kept_exactly(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zarstaff", 70)
            make(mud, "Zardead", 20)
            live = mud.root / "corpse" / "live"
            hist = mud.root / "corpse" / "history" / "Zardead"
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as dead:
                login(staff, "Zarstaff", PW)
                login(dead, "Zardead", PW)
                run(staff, "scroll 0", 0.5)
                run(staff, "slay zardead", 2.0)
                dead.send("quit")
                dead.wait_closed()
                cid = next(live.glob("*.corpse")).name[:-len(".corpse")]
                # Looted part way. (Nothing can be added to a player's
                # corpse in play: PUT answers that it is not a container.)
                run(staff, "get sword corpse", 2.5)
                run(staff, "get banner corpse", 2.5)
                # History cannot be written: its directory is a file now.
                hist.rename(hist.with_name("Zardead.aside"))
                hist.write_text("in the way\n")
                run(staff, "get corpse", 2.5)
                staff.send("quit")
                staff.wait_closed()
            live_after = sorted(p.name for p in live.iterdir())
            mud.restart()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zarstaff", PW)
                run(staff, "scroll 0", 0.5)
                room = run(staff, f"goto {ROOM}", 1.5) + run(staff, "look", 1.0)
                listed = run(staff, "prestore zardead corpses", 2.0)
                shown = run(staff, f"prestore zardead corpse {cid} show", 2.0)
                staff.send("quit")
                staff.wait_closed()
            # Mended, and a restart moves the end state into history.
            hist.unlink()
            hist.with_name("Zardead.aside").rename(hist)
            mud.restart()
            history = sorted(p.name for p in hist.iterdir())
            live_final = sorted(p.name for p in live.iterdir())
            rows = ledger_rows(mud)

        self.assertIn(f"{cid}.ending.corpse", live_after)
        self.assertNotIn(f"{cid}.corpse", live_after)
        self.assertNotIn("corpse of Zardead", room)       # ended: not made again
        self.assertIn("NOT yet in history", listed)
        # Exactly what was left: the shield and the vest, not what was taken.
        self.assertIn("sub issue shield", shown)
        self.assertIn("sub issue vest", shown)
        self.assertNotIn("sub issue sword", shown)
        self.assertNotIn("war banner", shown)
        self.assertIn(f"{cid}.carried.corpse", history)
        self.assertNotIn(f"{cid}.ending.corpse", live_final)
        outcomes = [r[3] for r in rows if r[2] == "corpse" and r[6] == cid]
        self.assertEqual(outcomes, ["created", "pending-archive", "archived"])


@unittest.skipIf(SKIP is not None, SKIP or "")
class LedgerFramingTests(unittest.TestCase):
    def test_a_torn_tail_is_set_aside_and_a_failed_write_is_cut_back(self) -> None:
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            recovery = mud.player_dir / "recovery"
            recovery.mkdir(parents=True, exist_ok=True)
            torn = "999\t0\trequest\tcommitted\t"
            (recovery / "ledger.tsv").write_text(torn, encoding="latin-1")
            mud.restart()
            make(mud, "Ztailcase", 20)
            # The same process: a write fails half way and is cut back.
            fault(mud, "ledger")
            make(mud, "Zledgfail", 20)
            mud.restart()
            for name in ("Ztailcase", "Zledgfail"):
                with mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.send("quit")
                    client.wait_closed()
            rows = ledger_rows(mud)
            quarantined = [p.read_text(encoding="latin-1") for p in recovery.glob("ledger.torn.*")]

        assigns = lambda n: [r for r in rows if r[2] == "uid" and r[3] == "assign" and r[5] == n]  # noqa: E731
        self.assertEqual(len(assigns("Ztailcase")), 1, rows)
        self.assertEqual(len(assigns("Zledgfail")), 1, rows)
        self.assertEqual(quarantined, [torn])


@unittest.skipIf(SKIP is not None, SKIP or "")
class FullRestoreAbortTests(unittest.TestCase):
    def test_no_undo_copy_or_no_save_means_nothing_changes(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zfullstaff", 70)
            make(mud, "Zfulltgt", 20)
            versions = mud.player_dir / "versions" / "Zfulltgt"
            versions.mkdir(parents=True, exist_ok=True)
            current = mud.player_dir / "Zfulltgt"
            text = current.read_text(encoding="latin-1")
            old = re.sub(r"(?m)^Levl \d+$", "Levl 12", text)
            old = re.sub(r"(?m)^Pass .*~$", "Pass Zoldhashxxxxx~", old)
            (versions / "Zfulltgt.20261001_120000").write_text(old, encoding="latin-1")
            patch_player_file(mud, "Zfulltgt", Levl=30, HyruleSecrets=5)
            pass_now = re.search(r"(?m)^Pass .*~$", current.read_text(encoding="latin-1")).group(0)
            partial = versions / ".partial"

            with mud.connect(timeout=120) as staff:
                login(staff, "Zfullstaff", PW)
                run(staff, "scroll 0", 0.5)
                # Offline, the undo copy cannot be written.
                partial.mkdir()
                offline = run(staff, "prestore zfulltgt 20261001_120000", 2.5)
                level_offline = re.search(r"(?m)^Levl (\d+)$", current.read_text(encoding="latin-1")).group(1)
                with mud.connect(timeout=120) as target:
                    login(target, "Zfulltgt", PW)
                    # Online, the same: they stay in the game.
                    online = run(staff, "prestore zfulltgt 20261001_120000", 2.5)
                    still_there = run(target, "score", 1.5)
                    partial.rmdir()
                    # Online, their save fails: nothing changes either.
                    (mud.player_dir / "temp").mkdir()
                    unsaved = run(staff, "prestore zfulltgt 20261001_120000", 2.5)
                    (mud.player_dir / "temp").rmdir()
                    still_there2 = run(target, "score", 1.5)
                    target.send("quit")
                    target.wait_closed()
                done = run(staff, "prestore zfulltgt 20261001_120000", 2.5)
                staff.send("quit")
                staff.wait_closed()
            restored = current.read_text(encoding="latin-1")
            rows = ledger_rows(mud)

        self.assertIn("Nothing was changed", offline)
        self.assertEqual(level_offline, "30")
        self.assertIn("Nothing was changed", online)
        self.assertIn("Zfulltgt", still_there)
        self.assertIn("Nothing was changed", unsaved)
        self.assertIn("could not be saved", unsaved)
        self.assertIn("Zfulltgt", still_there2)
        self.assertIn("restored to", done)
        self.assertRegex(restored, r"(?m)^Levl 12$")
        # Not rolled back: the password, the one-time claims, and the
        # restore's own mark rides on the fixes.
        self.assertIn(pass_now, restored)
        self.assertNotIn("Zoldhash", restored)
        self.assertRegex(restored, r"(?m)^HyruleSecrets 5$")
        self.assertRegex(restored, r"(?m)^Fixes .*restore:full:\d+")
        self.assertEqual([r[3] for r in rows if r[2] == "prestore"], ["pending", "committed"])


@unittest.skipIf(SKIP is not None, SKIP or "")
class DurabilityTests(unittest.TestCase):
    def test_unconfirmed_durability_is_never_acknowledged(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zdurstaff", 70)
            make(mud, "Zdurdead", 20)
            cid = kill_and_end_corpse(mud, "Zdurstaff", "Zdurdead")
            # Every directory flush fails, then every file flush: nothing
            # can be confirmed, so nothing is given or acknowledged.
            refused = {}
            for point in ("dirsync", "fsync"):
                mud.extra_env["TOC_FAULT"] = point
                mud.restart()
                with mud.connect(timeout=120) as staff:
                    login(staff, "Zdurstaff", PW)
                    refused[point] = run(staff, f"prestore zdurdead corpse {cid} gear", 2.5)
                    staff.send("quit")
                    staff.wait_closed()
            before = states(ledger_rows(mud), f"corpse:{cid}")
            mud.extra_env.pop("TOC_FAULT")
            mud.restart()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zdurstaff", PW)
                given = run(staff, f"prestore zdurdead corpse {cid} gear", 2.5)
                staff.send("quit")
                staff.wait_closed()
            rows = ledger_rows(mud)

        for point, said in refused.items():
            self.assertIn("Nothing was given", said, point)
        self.assertNotIn("committed", before)
        self.assertRegex(given, r"Restored \d+ object")
        self.assertEqual(states(rows, f"corpse:{cid}")[-1], "committed")


class FailureSourceTests(unittest.TestCase):
    def test_every_restore_goes_through_the_checked_path(self) -> None:
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        give = wiz[wiz.index("static void prestore_give("):wiz.index("static void prestore_op(")]
        order = [give.index('player_snapshot_milestone( victim, undo_tag, true )'),
                 give.index('recovery_record( "request", "pending"'),
                 give.index("player_fix_record( victim, mark )"),
                 give.index("save_char_obj( victim )"),
                 give.index('recovery_record( "request", "committed", capname, op, kind, ch->name, detail )')]
        self.assertEqual(order, sorted(order))
        for caller in ("static void prestore_stash(", "static void prestore_gear(",
                       "static void prestore_corpse("):
            body = wiz[wiz.index(caller):]
            body = body[:body.index("\n}\n")]
            self.assertIn("prestore_give(", body, caller)
        corpses = (ROOT / "src" / "corpses.c").read_text(encoding="latin-1")
        archive = corpses[corpses.index("static void track_archive("):]
        archive = archive[:archive.index("\n}\n")]
        self.assertLess(archive.index("track_history( t, state ) == DURABLE_OK"),
                        archive.index("remove( path )"))


if __name__ == "__main__":
    unittest.main()
