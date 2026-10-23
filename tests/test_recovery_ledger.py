"""The recovery ledger (src/recovery.c): what was restored, never rolled back.

A git restore request used to mark itself applied inside the player file
("restore:<id>" among the login fixes). A full PRESTORE to the copy taken
just before the request -- the obvious undo -- took the mark away with
everything else, and the next login applied the same request again. The
handoff review of 2026-10-23 reproduced it live; the first test here is
that probe: apply, roll back through the request's own safety copy, log
in again, and the request must not run a second time.

Also: a request that can never apply is rejected for good, one that cannot
apply yet waits; every player gets a uid that outlives their file; two
milestones of one kind in the same second get two names; and a history far
past the old 6,000-name scan is listed a page at a time.
"""
from __future__ import annotations

import os
import pathlib
import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zledgerpw1"


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def ledger(mud) -> list[list[str]]:
    path = mud.player_dir / "recovery" / "ledger.tsv"
    if not path.exists():
        return []
    return [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()
            if line and not line.startswith("#")]


def request_states(rows, request: str) -> list[str]:
    return [r[3] for r in rows if r[2] == "request" and r[6] == request]


def make(mud, name: str, level: int, room: int = 4202) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed()
    patch_player_file(mud, name, Levl=level, Room=room)


class LedgerSourceTests(unittest.TestCase):
    def test_receipts_live_in_the_ledger_not_only_the_player_file(self) -> None:
        restores = (ROOT / "src" / "restores.c").read_text(encoding="latin-1")
        login_fn = restores[restores.index("void restores_login"):]
        self.assertIn("recovery_request_state( e->id )", login_fn)
        self.assertIn('recovery_record( "request", "pending"', login_fn)
        # Pending is written before anything is given, committed after
        # the save, and the snapshot to undo it is taken before either.
        self.assertLess(login_fn.index('player_snapshot_milestone( ch, "gitrestore", true )'),
                        login_fn.index('recovery_record( "request", "pending"'))
        self.assertLess(login_fn.index('recovery_record( "request", "pending"'),
                        login_fn.index("obj_to_char( obj, ch )"))
        self.assertNotIn("RESTORES_MAX", restores)
        recovery = (ROOT / "src" / "recovery.c").read_text(encoding="latin-1")
        self.assertIn("fsync( fileno( fp ) )", recovery)
        self.assertIn('#define RECOVERY_DIR     "../player/recovery/"',
                      (ROOT / "src" / "merc.h").read_text(encoding="latin-1"))

    def test_the_death_penalty_has_a_copy_from_before_it(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        at = fight.index('player_snapshot_milestone( victim, "prepenalty", true );')
        self.assertLess(at, fight.index("gain_exp(victim, (int)UMIN(-1L * ((curr_exp - base_exp)/16),-1L));"))

    def test_no_fixed_scan_caps_remain(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        corpses = (ROOT / "src" / "corpses.c").read_text(encoding="latin-1")
        self.assertNotIn("SNAP_SCAN_MAX", save)
        self.assertNotIn("PRESTORE_SCAN_MAX", wiz)
        self.assertNotIn("CORPSE_REGISTRY_MAX", corpses)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LedgerLiveTests(unittest.TestCase):
    def test_an_applied_request_survives_a_rollback_and_never_runs_again(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zrkeeper", 70)
            make(mud, "Zrhistory", 20)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as victim:
                login(staff, "Zrkeeper", PW)
                login(victim, "Zrhistory", PW)
                run(staff, "slay zrhistory", 2.0)
                run(staff, "get all corpse", 1.5)
                for client in (victim, staff):
                    client.send("quit")
                    client.wait_closed()
            versions = mud.player_dir / "versions" / "Zrhistory"
            death = next(p.name for p in versions.iterdir() if p.name.endswith(".death"))
            death_stamp = death[len("Zrhistory."):]
            (mud.root / "area" / "restores.dat").write_text(
                f"zreceipt Zrhistory gear {death_stamp}\n"
                "zbogus Zrhistory gear 19990101_000000\n"
                "zwaits Zrhistory gear 20250101_000000 Zmissing.file\n", encoding="latin-1")
            mud.restart()

            with mud.connect(timeout=120) as victim:
                login(victim, "Zrhistory", PW)
                victim.drain(1.0)
                first_apply = "given back" in victim.transcript
                victim.send("quit")
                victim.wait_closed()
            receipt_in_file = "restore:zreceipt" in (mud.player_dir / "Zrhistory").read_text(encoding="latin-1")
            before = next(p.name for p in versions.iterdir() if p.name.endswith(".gitrestore"))

            # The obvious undo: the copy taken just before the request.
            with mud.connect(timeout=120) as staff:
                login(staff, "Zrkeeper", PW)
                rolled = run(staff, "prestore zrhistory " + before[len("Zrhistory."):], 2.0)
                staff.send("quit")
                staff.wait_closed()
            mark_after_rollback = "restore:zreceipt" in (mud.player_dir / "Zrhistory").read_text(encoding="latin-1")

            with mud.connect(timeout=120) as victim:
                login(victim, "Zrhistory", PW)
                victim.drain(1.0)
                second_apply = "given back" in victim.transcript
                victim.send("quit")
                victim.wait_closed()
            rows = ledger(mud)

        self.assertTrue(first_apply)
        self.assertTrue(receipt_in_file)
        self.assertIn("restored to:", rolled)
        # The file rolled back; the receipt in the ledger did not -- and
        # since the second review the file's mark is kept across a full
        # PRESTORE too, with the other things a rollback must not undo.
        self.assertTrue(mark_after_rollback)
        self.assertFalse(second_apply)
        self.assertEqual(request_states(rows, "zreceipt"), ["pending", "committed"])
        # A stamp that names nothing can never apply; a file not installed
        # yet may, and is only noted.
        self.assertEqual(request_states(rows, "zbogus"), ["rejected"])
        self.assertEqual(set(request_states(rows, "zwaits")), {"retry"})
        # The full PRESTORE left a receipt naming the copy that undoes it.
        prestores = [r for r in rows if r[2] == "prestore" and r[5] == "Zrhistory"]
        self.assertEqual([r[3] for r in prestores], ["pending", "committed"])
        self.assertIn("undo with Zrhistory.", prestores[-1][9])
        # Every character has a uid, and the receipts carry it.
        uids = {r[5]: r[4] for r in rows if r[2] == "uid" and r[3] == "assign"}
        self.assertRegex(uids.get("Zrhistory", ""), r"^P[0-9a-f]{16}$")
        self.assertTrue(all(r[4] == uids["Zrhistory"] for r in rows
                            if r[2] == "request" and r[5] == "Zrhistory"))

    def test_same_second_milestones_and_a_history_past_six_thousand(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zbigstaff", 70, room=4207)
            make(mud, "Zbighist", 20, room=4207)
            text = (mud.player_dir / "Zbighist").read_text(encoding="latin-1")
            versions = mud.player_dir / "versions" / "Zbighist"
            versions.mkdir(parents=True, exist_ok=True)
            now = time.time()
            planted = 6100
            for i in range(planted):
                s = time.strftime("%Y%m%d_%H%M%S", time.localtime(now - 3600 - i * 60))
                (versions / f"Zbighist.{s}.quest").write_text(text, encoding="latin-1")
            # An ADVANCE milestone already holds every second of the next
            # two minutes: the one ADVANCE below has to take a second name.
            taken = set()
            for i in range(-5, 120):
                s = time.strftime("%Y%m%d_%H%M%S", time.localtime(now + i))
                taken.add(f"Zbighist.{s}.advance")
                (versions / f"Zbighist.{s}.advance").write_text(text, encoding="latin-1")
            past = now - 3600
            for path in versions.iterdir():
                os.utime(path, (past, past))

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hist:
                login(staff, "Zbigstaff", PW)
                login(hist, "Zbighist", PW)
                run(staff, "scroll 0", 0.5)
                run(staff, "advance zbighist 21", 3.0)
                quests = run(staff, "prestore zbighist quests", 3.0)
                last = run(staff, "prestore zbighist quests 122", 3.0)
                for client in (hist, staff):
                    client.send("quit")
                    client.wait_closed()
            made = sorted(p.name for p in versions.iterdir()
                          if p.name.endswith(".advance") and p.name not in taken)
            quest_files = sum(1 for p in versions.iterdir() if p.name.endswith(".quest"))

        # Every quest milestone within ninety days is still there, and the
        # list says so, a page at a time.
        self.assertEqual(quest_files, planted)
        self.assertIn(f"Page 1 of 122 ({planted} in all)", quests)
        self.assertEqual(len(re.findall(r"\[\s*\d+\]", quests)), 50)
        self.assertIn(f"Page 122 of 122 ({planted} in all).", last)
        self.assertEqual(len(re.findall(r"\[\s*\d+\]", last)), 50)
        # A second name for the same second, never a skipped copy.
        self.assertEqual(len(made), 1, made)
        self.assertRegex(made[0], r"^Zbighist\.\d{8}_\d{6}_02\.advance$")

if __name__ == "__main__":
    unittest.main()
