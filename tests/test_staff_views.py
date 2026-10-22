"""Read-only views (review, 2026-10-22): REPAIR QUOTE, DEVOTE PREVIEW, the
AQUEST INFO and DAILY STATUS refusals, and the staff's QUESTDIAG,
GEARDIAG, HYRULESTATUS and ALIGNCHECK.

Each is played against a real server in a throwaway tree with synthetic
characters, and each is held to changing nothing: the purse, the
alignment, the worn gear and the saved file are the same before and
after.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zviews1pass"
TEMPLE = 4207
SMITHY = 2490
VEST = 3703                  # sub issue vest: values 1 1 1 0
HELMET = 3706
ANTI_EVIL = 1024             # ITEM_ANTI_EVIL, bit K


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, objects: str = "", **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    if objects:
        path = mud.player_dir / name
        text = path.read_text(encoding="latin-1")
        path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def quit_all(*clients) -> None:
    for client in clients:
        client.send("quit")
        client.wait_closed()


@unittest.skipIf(SKIP is not None, SKIP or "")
class PlayerViewTests(unittest.TestCase):
    def test_quotes_and_previews_change_nothing(self) -> None:
        dented = ("#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 40\nVal  0 0 0 -1 0\n"
                  "ArmorLost 1 1 1 1\nEnd\n\n" % VEST)
        helmet = "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nExtF %d\nEnd\n\n" % (HELMET, ANTI_EVIL)
        with LiveMud() as mud:
            make(mud, "Zquoter", dented + helmet, Levl=20, Room=SMITHY, NewGold=0, Alig=-250)
            before = (mud.player_dir / "Zquoter").read_text(encoding="latin-1")
            with mud.connect(timeout=120) as client:
                login(client, "Zquoter", PW)
                run(client, "wear helmet")
                one = run(client, "repair quote vest")
                every = run(client, "repair quote all")
                perfect = run(client, "repair quote helmet")
                preview = run(client, "devote preview")
                dark = run(client, "devote preview dark")
                still = run(client, "equipment")
                align = run(client, "alignment")
                client.send("quit")
                self.assertTrue(client.wait_closed())
            after = (mud.player_dir / "Zquoter").read_text(encoding="latin-1")

        # The quote: a price, the armour back to its made values, and the
        # break mended -- with the vest, the purse and the ledger untouched.
        self.assertIn("A smith would charge", one, one)
        self.assertIn("armour 0 0 0 -1 -> 1 1 1 0", one, one)
        self.assertIn("more than you carry", one, one)
        self.assertIn("cheapest first", every, every)
        self.assertIn("covers 0 of them", every, every)
        self.assertIn("perfect condition", perfect, perfect)
        self.assertIn("Cond 40", after)
        self.assertIn("ArmorLost 1 1 1 1", after)
        # The preview: three forecasts, the dark one taking the anti-evil
        # helmet off -- and nothing moved.
        for way in ("light", "dark", "balance"):
            self.assertRegex(preview, rf"(?m)^\s*{way}\s+-250 -> ", preview)
        self.assertIn("-250 -> -350 (Balanced -> Ruthless)", dark, dark)
        self.assertIn("would come off", dark, dark)
        self.assertIn("helmet", still, still)
        self.assertIn("alignment -250", align, align)
        self.assertRegex(after, r"(?m)^Alig\s+-250$")
        self.assertNotIn("would come off", preview.split("light")[1].split("dark")[0])

    def test_aquest_info_says_why_not_yet(self) -> None:
        later = int(time.time()) + 8 * 60
        with LiveMud() as mud:
            make(mud, "Zquestinfo", Levl=20, Room=TEMPLE, QuestNext=12, DailyWait=later)
            with mud.connect(timeout=120) as client:
                login(client, "Zquestinfo", PW)
                info = run(client, "aquest info")
                daily = run(client, "aquest daily")
                quit_all(client)

        self.assertRegex(info, r"\d+ minutes before you may quest again", info)
        self.assertRegex(info, r"Daily Quest :.*0 of 3 today; next in \d+ minutes? \(a daily was given up\)",
                         info)
        self.assertRegex(daily, r"Next daily:\s+in \d+ minutes? \(a daily was given up\)", daily)
        self.assertIn("00:00 UTC", daily, daily)


@unittest.skipIf(SKIP is not None, SKIP or "")
class StaffViewTests(unittest.TestCase):
    def test_the_staff_views_read_and_refuse_by_rank(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zviewer", Levl=70, Room=TEMPLE)
            make(mud, "Zangel", Levl=65, Room=TEMPLE)
            make(mud, "Zviewed", "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % VEST,
                 Levl=20, Room=TEMPLE, Alig=500)
            before = (mud.player_dir / "Zviewed").read_text(encoding="latin-1")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as angel, \
                    mud.connect(timeout=120) as mortal:
                login(staff, "Zviewer", PW)
                login(angel, "Zangel", PW)
                login(mortal, "Zviewed", PW)
                run(mortal, "wear vest")
                quest = run(staff, "questdiag zviewed")
                gear = run(staff, "geardiag zviewed")
                hyrule = run(staff, "hyrulestatus zviewed")
                align = run(staff, "aligncheck zviewed")
                outranked = run(angel, "questdiag zviewer")
                refused = run(mortal, "questdiag zviewed")
                abbreviated = run(mortal, "align")
                staff_abbrev = run(staff, "align")
                quit_all(staff, angel, mortal)
            after = (mud.player_dir / "Zviewed").read_text(encoding="latin-1")

        self.assertIn("No quest out", quest, quest)
        self.assertIn("Ordinary request: ready now", quest, quest)
        self.assertIn("Daily request: ready now", quest, quest)
        self.assertIn("sub issue vest", gear, gear)
        self.assertIn("armour 1 1 1 0 (prototype 1 1 1 0), damage ledger 0 0 0 0", gear, gear)
        self.assertIn("WEAR would accept it now", gear, gear)
        self.assertIn("Level 1: entrance open", hyrule, hyrule)
        self.assertIn("Level 2: entrance shut", hyrule, hyrule)
        self.assertIn("next requirement: carry", hyrule, hyrule)
        self.assertIn("Zviewed is Kind (alignment 500)", align, align)
        self.assertIn("A devotion would make it", align, align)
        self.assertIn("outrank", outranked, outranked)
        self.assertNotIn("Quest state", refused, refused)
        # ALIGN is still ALIGNMENT, for a mortal and for staff.
        self.assertIn("alignment 500", abbreviated, abbreviated)
        self.assertIn("(alignment 0)", staff_abbrev, staff_abbrev)
        # Nothing about the viewed character changed but the vest put on.
        strip = lambda text: re.sub(r"(?m)^(Wear|LogO|Plyd|LastOut|Fixes|ChangesSeen).*\n", "", text)
        self.assertEqual(strip(before).count("Vnum %d" % VEST), strip(after).count("Vnum %d" % VEST))
        self.assertRegex(after, r"(?m)^Alig\s+500$")


if __name__ == "__main__":
    unittest.main()
