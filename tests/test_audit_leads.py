"""Leads from the 2026-10-22 audit, confirmed and fixed afterwards.

Each test here failed on the code before its fix.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zlead1pass"
TEMPLE = 4207


def run(client, command: str, settle: float = 0.8) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.drain(1.0)
        client.send("quit")
        assert client.wait_closed()
    patch_player_file(mud, name, **fields)


def carried_count(inventory: str, what: str) -> int:
    total = 0
    for line in inventory.splitlines():
        if what in line:
            m = re.match(r"\s*\(\s*(\d+)\)", line)
            total += int(m.group(1)) if m else 1
    return total


@unittest.skipIf(SKIP is not None, SKIP or "")
class EnchantArmorTests(unittest.TestCase):
    def test_armour_that_fades_is_kept_damaged(self) -> None:
        """A failed ENCHANT ARMOR whose roll "destroyed" the piece took it
        out of the inventory and put it nowhere -- the player lost it and
        object_list kept an object with no owner. The message ("glows
        blue, then fades") and the damage flag say it was meant to stay.

        A vest with -9 AC of its own sets the failure chance at its 95%
        ceiling, so about a quarter of casts fade and a quarter explode;
        every vest is accounted for: carried, or exploded."""
        vest = "#O\nVnum 3703\nNest 0\nWear -1\nLev 1\nCond 100\nAffect -1 30 -1 -9 17 0 0\nEnd\n\n"
        with LiveMud() as mud:
            make(mud, "Zenchant", Levl=70, Room=TEMPLE)
            path = mud.player_dir / "Zenchant"
            text = path.read_text(encoding="latin-1")
            end = text.index("\nEnd\n")
            text = text[:end] + "\nSk 100 'enchant armor'" + text[end:]
            path.write_text(text.replace("#END", vest * 30 + "#END"), encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zenchant", PW)
                run(client, "scroll 0")
                run(client, "remove vest")
                before = carried_count(run(client, "inventory", 1.5), "sub issue vest")
                fades = explodes = 0
                for _ in range(40):
                    out = run(client, "cast 'enchant armor' vest")
                    fades += out.count("then fades")
                    explodes += out.count("explodes")
                    run(client, "restore self", 0.3)
                    if fades >= 2:
                        break
                after = carried_count(run(client, "inventory", 1.5), "sub issue vest")
                client.send("quit")
                self.assertTrue(client.wait_closed())

        self.assertGreaterEqual(fades, 1, "the 95% failure chance produced no fade")
        self.assertEqual(after, before - explodes,
                         f"{fades} faded and {explodes} exploded: a faded vest must stay carried")


@unittest.skipIf(SKIP is not None, SKIP or "")
class ResetPwdTests(unittest.TestCase):
    def test_a_path_or_a_login_in_progress_is_refused(self) -> None:
        """RESETPWD put the typed name into a file path unchecked, and
        asked get_char_world whether the target was online -- which a
        character at the password prompt is not, so their login then
        saved the old password back over the reset."""
        with LiveMud() as mud:
            make(mud, "Zresetter", Levl=70, Room=TEMPLE)
            make(mud, "Zresettee", Levl=10, Room=TEMPLE)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zresetter", PW)
                path = run(staff, "resetpwd ../gods/zresetter Zfreshpw1", 1.5)
                with mud.connect(timeout=60) as waiting:
                    waiting.expect("name", timeout=30)
                    waiting.send("Zresettee")
                    waiting.expect("assword", timeout=30)
                    pending = run(staff, "resetpwd zresettee Zfreshpw1", 1.5)
                staff.send("quit")
                staff.wait_closed()
            with mud.connect(timeout=120) as client:
                login(client, "Zresettee", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed(), "the refused reset changed the password")

        self.assertIn("No such character is saved", path)
        self.assertIn("logging in right now", pending)


@unittest.skipIf(SKIP is not None, SKIP or "")
class StashTimerTests(unittest.TestCase):
    def test_a_bag_holding_something_timed_is_refused(self) -> None:
        """STASH refused a timed object only at the top level, so one in
        a bag went in and rotted there unseen."""
        bag = "#O\nVnum 3032\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n"
        timed = "#O\nVnum 3032\nNest 1\nWear -1\nLev 1\nCond 100\nTime 40\nEnd\n\n"
        with LiveMud() as mud:
            make(mud, "Zstasher", Room=4208)
            path = mud.player_dir / "Zstasher"
            text = path.read_text(encoding="latin-1")
            path.write_text(text.replace("#END", bag + timed + "#END", 1), encoding="latin-1")
            with mud.connect(timeout=120) as client:
                login(client, "Zstasher", PW)
                one = run(client, "stash put bag", 1.2)
                every = run(client, "stash put all", 1.2)
                held = run(client, "inventory", 1.2)
                client.send("quit")
                self.assertTrue(client.wait_closed())

        self.assertIn("will not last long enough", one)
        self.assertIn("Nothing you are carrying can go in", every)
        self.assertIn("bag", held)


@unittest.skipIf(SKIP is not None, SKIP or "")
class OverlongLineTests(unittest.TestCase):
    def test_the_line_after_an_overlong_one_still_runs(self) -> None:
        """Cutting an overlong line short also cut the input buffer after
        it, so whatever arrived with it -- the next line typed, or the
        rest of an alias -- was silently lost."""
        with LiveMud() as mud:
            make(mud, "Zlongline", Room=TEMPLE)
            with mud.connect(timeout=120) as client:
                login(client, "Zlongline", PW)
                client.drain(0.5)
                mark = len(client.transcript)
                client.send_raw(b"say " + b"z" * 700 + b"\nsay zafterward\n")
                client.drain(3.0)
                out = client.transcript[mark:]
                client.send("quit")
                self.assertTrue(client.wait_closed())

        self.assertIn("the rest was not sent", out)
        self.assertIn("zafterward", out)


class LauncherParityTests(unittest.TestCase):
    def test_powershell_update_finishes_in_the_pulled_launcher(self) -> None:
        """toc.sh's update execs the newly pulled launcher to finish, so a
        fix to the launcher applies to the update that brings it; toc.ps1
        finished in the copy it had already loaded."""
        from pathlib import Path
        text = (Path(__file__).resolve().parent.parent / "toc.ps1").read_text(encoding="utf-8")
        update = text[text.index("    'update' {"):text.index("    '_finish-update' {")]
        pull = update.index("pull --ff-only")
        handoff = update.index("'toc.ps1') '_finish-update'")
        self.assertLess(pull, handoff)
        self.assertNotIn("Install-TocImage", update[pull:handoff])


if __name__ == "__main__":
    unittest.main()
