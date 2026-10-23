"""A player's corpse outlasts a restart, as it actually is (src/corpses.c).

Owner, 2026-10-23: Alaric died AFK, his corpse rotted in half an hour and
the morning's deploy took the gear. A player's corpse now lasts a week and
is written down -- ../corpse/live/<id>.corpse -- at the death and within a
second of every change, with every object in it at any depth. At boot each
is made again in its room with exactly what it held.

The first version rebuilt only untouched corpses, from the death snapshot,
and forgot a corpse for good the moment anything came out of it, so a
corpse half looted lost the other half at the next restart (handoff review,
2026-10-23). This module plays that: die, take one thing out, restart --
the rest is still there. A corpse that ends (purged here) goes to the
owner's history, PRESTORE <player> CORPSES lists it, and CORPSE <id> GEAR
gives what it held back once, refusing a second time without FORCE.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zkeeppass1"
ROOM = 4202
KIT = "sub issue sword"


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def corpse_lines(text: str) -> list[str]:
    """The objects LOOK IN CORPSE lists, one per line."""
    body = text.split("holds:", 1)[-1] if "holds:" in text else text
    return sorted(line.strip() for line in body.splitlines()
                  if line.strip() and not line.strip().startswith("<")
                  and "corpse" not in line.lower())


class CorpseKeeperSourceTests(unittest.TestCase):
    def test_a_player_corpse_lasts_a_week_and_every_change_is_written(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        corpse = fight[fight.index("void make_corpse( CHAR_DATA *ch )"):]
        corpse = corpse[:corpse.index("\n}\n")]
        self.assertIn("corpse->timer   = (sh_int) PC_CORPSE_TICKS;", corpse)
        self.assertIn("corpse_registry_died( ch, corpse, player_snapshot_last_milestone() );", corpse)
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("#define PC_CORPSE_TICKS  10080", merc)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        for hook in ('corpse_registry_touched( obj, "it is gone" );',
                     "corpse_note_change( obj_from, obj, false );",
                     "corpse_note_change( obj_to, obj, true );",
                     "corpse_registry_moved( obj );"):
            self.assertIn(hook, handler)
        # Taking something out marks it to be written, never forgets it.
        self.assertNotIn('"something was taken out"', handler)
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        self.assertIn('corpse_registry_touched( obj, "it rotted away" );', update)
        self.assertIn("corpse_registry_update( );", update)
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        self.assertIn("corpse_registry_flush_all( );", comm)
        # Nothing is left out of a corpse file: keys and blank maps too.
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertIn("fwrite_obj_everything = true;", save)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseKeeperLiveTests(unittest.TestCase):
    def test_a_looted_corpse_keeps_the_rest_and_an_ended_one_is_restorable(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zkeepstaff", 70), ("Zkeepdead", 20)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=ROOM)

            live = mud.root / "corpse" / "live"
            history = mud.root / "corpse" / "history" / "Zkeepdead"
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as dead:
                login(staff, "Zkeepstaff", PW)
                login(dead, "Zkeepdead", PW)
                run(staff, "scroll 0", 0.5)
                run(staff, "slay zkeepdead", 2.0)
                self.assertIn("corpse of Zkeepdead", run(staff, "look", 1.0))
                whole = corpse_lines(run(staff, "look in corpse", 1.5))
                for client in (staff, dead):
                    client.send("quit")
                    client.wait_closed()
            self.assertIn(KIT, " ".join(whole))
            self.assertGreaterEqual(len(whole), 2, whole)
            files = list(live.glob("*.corpse"))
            self.assertEqual(len(files), 1, files)
            corpse_id = files[0].name[:-len(".corpse")]
            self.assertTrue((history / f"{corpse_id}.death.corpse").exists())

            # A restart: the corpse comes back whole. One thing taken out.
            mud.restart()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zkeepstaff", PW)
                run(staff, "scroll 0", 0.5)
                self.assertEqual(corpse_lines(run(staff, "look in corpse", 1.5)), whole)
                run(staff, "get sword corpse", 2.5)       # written within a second
                rest = corpse_lines(run(staff, "look in corpse", 1.5))
                staff.send("quit")
                staff.wait_closed()
            self.assertNotIn(KIT, " ".join(rest))
            self.assertEqual(len(rest), len(whole) - 1, (whole, rest))

            # Another restart: the rest is still there -- the bug was that
            # it was forgotten once anything came out.
            mud.restart()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zkeepstaff", PW)
                run(staff, "scroll 0", 0.5)
                after = corpse_lines(run(staff, "look in corpse", 1.5))
                # It ends: picked up. Its last state goes to history.
                run(staff, "get corpse", 2.5)
                run(staff, "drop corpse", 2.5)          # kept again, as a new record
                run(staff, "get corpse", 2.5)
                listed = run(staff, "prestore zkeepdead corpses", 2.0)
                shown = run(staff, f"prestore zkeepdead corpse {corpse_id} show", 2.0)
                given = run(staff, f"prestore zkeepdead corpse {corpse_id} gear", 2.5)
                again = run(staff, f"prestore zkeepdead corpse {corpse_id} gear", 2.0)
                staff.send("quit")
                staff.wait_closed()
            log_lines = (history / f"{corpse_id}.log").read_text(encoding="latin-1")
            ledger = (mud.player_dir / "recovery" / "ledger.tsv").read_text(encoding="latin-1")
            saved = (mud.player_dir / "Zkeepdead").read_text(encoding="latin-1")
            toc = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")

        self.assertEqual(after, rest)
        self.assertFalse(list(live.glob("*.corpse")) if live.exists() else [])
        self.assertIn(corpse_id, listed)
        self.assertIn("ended carried: picked up by Zkeepstaff", listed)
        self.assertIn("Nothing was changed", shown)
        restored = re.search(r"Restored (\d+) object", given)
        self.assertIsNotNone(restored, given)
        self.assertEqual(int(restored.group(1)), len(rest))
        self.assertIn("already given back once", again)
        # Who took what, by command; what was made, kept and ended.
        self.assertRegex(log_lines, r"Zkeepstaff: get\ttook out a sub issue sword")
        self.assertIn("ended (carried)", log_lines)
        self.assertRegex(ledger, rf"\tcorpse\tcreated\t[^\t]+\tZkeepdead\t{corpse_id}\t")
        self.assertRegex(ledger, rf"\trequest\tcommitted\t[^\t]+\tZkeepdead\tcorpse:{corpse_id}\t")
        # The restored things are in the dead player's file, the sword not.
        self.assertNotIn("Corpse keeper", saved)
        self.assertIn(f"Zkeepdead's corpse {corpse_id} made again in room {ROOM}", toc)


if __name__ == "__main__":
    unittest.main()
