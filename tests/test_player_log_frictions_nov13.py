"""What the players' logs of 2026-10-23 to 11-13 showed them stumbling on.

- "The locked is closed." (32 times): a door is called by the noun among
  its keywords, not the first word (door_noun in comm.c).
- GET X STASH, PUT X STASH and LOOK IN STASH answered "That's not a
  container." from the altar's decorative chest; they mean the stash now,
  and STASH GET ALL takes everything out.
- DROP POT PIE read "pot" alone and dropped potions; the whole phrase names
  the object for DROP, EAT and QUAFF (here DROP POT DISH, potatoes beside a
  potion).
- Five players stopped one room short of the questmaster: from the top of
  the oak he says one more climb up.
- PULL LEVER 5 in the riddle room (29217) is PULL 5.
- STASH BUY takes a count; AQUEST GAMBLE NEVER always collects.
- Words players typed and the game did not know get a hint; CROSS is ENTER.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zfricpw1"
TEMPLE = 4207
ALTAR = 4208
OAK_TOP = 2414
LEVER_ROOM = 29217
HYRULE_DOOR_ROOM = 30401      # its north door resets locked: "locked dungeon door"
POTATOES = 15008              # a dish of lyonnaise potatoes ("dish lyonnaise potatoes")
POTION = 6309                 # a blue potion ("potion blue")
SWORD = 3702                  # a sub issue sword


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


def carried(vnum: int) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % vnum


class FrictionSourceTests(unittest.TestCase):
    def test_cross_is_enter_and_last_in_the_table(self) -> None:
        interp = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
        table = interp[re.search(r"cmd_table\s*\[\]", interp).start():]
        table = table[:table.index("/* End of list. */")]
        self.assertIn('{ "cross",          do_enter,', table)
        # Last, so no shorter word that meant something moves.
        self.assertGreater(table.index('"cross"'), table.index('"maps"'))

    def test_a_boat_says_flight_works_too(self) -> None:
        move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        self.assertIn("You need a boat to go there, or to fly.", move)


@unittest.skipIf(SKIP is not None, SKIP or "")
class FrictionLiveTests(unittest.TestCase):
    def test_the_frictions(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zfricstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zfrichero", carried(POTATOES) + carried(POTION) + carried(SWORD),
                 Levl=30, Room=TEMPLE, NewPlat=5000000)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zfricstaff", PW)
                login(hero, "Zfrichero", PW)
                for client in (staff, hero):
                    client.sync("scroll 0")

                # A door is called a door.
                staff.must(f"goto {HYRULE_DOOR_ROOM}", "")
                closed = staff.sync("close north")
                staff.sync("lock north")
                staff.sync("north")
                bumped = staff.sync("north")
                staff.must(f"goto {TEMPLE}", "")

                # DROP POT DISH drops the potatoes, not the potion.
                dropped = hero.sync("drop pot dish")
                pack = hero.sync("inventory")
                floor = hero.sync("look")

                # The stash as a container, and STASH GET ALL.
                staff.must(f"transfer zfrichero {ALTAR}", "")
                put = hero.sync("put sword stash")
                looked = hero.sync("look in stash")
                got = hero.sync("get sword stash")
                hero.sync("stash put sword")
                hero.sync("stash put potion")
                all_out = hero.sync("stash get all")
                bought = hero.sync("stash buy 2")

                # One climb short of the questmaster.
                staff.must(f"transfer zfrichero {OAK_TOP}", "")
                short = hero.sync("aquest complete")
                staff.must(f"transfer zfrichero {TEMPLE}", "")

                # PULL LEVER 5 is PULL 5.
                staff.must(f"goto {LEVER_ROOM}", "")
                lever = staff.sync("pull lever 5")
                looked_lever = staff.sync("look lever")
                staff.must(f"goto {TEMPLE}", "")

                # The gamble setting, and a hint.
                never = hero.sync("aquest gamble never")
                ask = hero.sync("aquest gamble ask")
                hinted = hero.sync("changelog")
                for client in (staff, hero):
                    client.send("quit")
                    client.wait_closed()

        self.assertNotIn("The locked is closed", bumped, closed + bumped)
        self.assertIn("The door is closed", bumped, closed + bumped)
        self.assertIn("potatoes", dropped, dropped)
        self.assertNotIn("potion", dropped.lower(), dropped)
        self.assertIn("potion", pack, pack)
        self.assertIn("potatoes", floor, floor)
        self.assertIn("away for safe keeping", put, put)
        self.assertIn("stash", looked.lower(), looked)
        self.assertNotIn("not a container", looked + put + got)
        self.assertIn("out of your stash", got, got)
        self.assertRegex(all_out, r"You take 2 things out of your stash", all_out)
        self.assertIn("Your stash now holds 100", bought, bought)
        self.assertIn("one more climb UP", short, short)
        self.assertIn("You pull", lever, lever)
        self.assertIn("Ten levers", looked_lever, looked_lever)
        self.assertIn("collected at once", never, never)
        self.assertIn("offer double-or-nothing again", ask, ask)
        self.assertIn("CHANGES lists what has changed lately", hinted, hinted)


if __name__ == "__main__":
    unittest.main()
