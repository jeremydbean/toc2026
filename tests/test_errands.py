"""ERRAND: three starter errands and the expedition (2026-11-15).

Played in a disposable world with synthetic Z characters: the town walk
(four landmarks), Melancholy's letter to the questmaster, three of Mud
School's creatures, each paid once and saved; an expedition taken, given
up, and finished by a kill in its area; staff and levels past 10 refused.
Nothing under player/, gods/, heroes/, backups/ or log/ is touched.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zerrpass1"
TEMPLE = 4207
KOBOLD = 3704        # Mud School's starving kobold
KOBOLD_ROOM = 3713   # its cage
GREMLIN = 3702


def area_id(file_name: str) -> int:
    """achievement_area_id: FNV-1a of the lowercased file name, 31 bits."""
    h = 2166136261
    for c in file_name.lower().encode("latin-1"):
        h ^= c
        h = (h * 16777619) & 0xFFFFFFFF
    return h & 0x7FFFFFFF


def make(mud, name, **fields):
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    if fields:
        patch_player_file(mud, name, **fields)


def set_line(mud, name, key, value):
    path = mud.player_dir / name
    lines = [l for l in path.read_text(encoding="latin-1").split("\n")
             if not l.startswith(key + " ")]
    at = next(i for i, l in enumerate(lines) if l.startswith("Levl "))
    lines.insert(at, f"{key} {value}")
    path.write_text("\n".join(lines), encoding="latin-1")


def file_line(mud, name, key):
    for l in (mud.player_dir / name).read_text(encoding="latin-1").splitlines():
        if l.startswith(key + " "):
            return l
    return ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class ErrandTests(unittest.TestCase):
    def kill_kobold(self, staff, hero, *done: str) -> str:
        """One kobold alone in its cage, killed; returns what came of it,
        waiting for one of `done` (the errand's own line)."""
        staff.sync(f"goto {KOBOLD_ROOM}")
        staff.sync("purge")
        staff.must(f"load mob {KOBOLD}", "You create")
        staff.sync(f"transfer zerrand {KOBOLD_ROOM}")
        hero.sync("inventory")
        hero.buffer = ""
        mark = len(hero.transcript)
        hero.send("kill kobold")
        hero.expect(*done, timeout=120)
        hero.sync("inventory")
        staff.sync(f"transfer zerrand {TEMPLE}")
        return hero.transcript[mark:]

    def test_errands_and_expedition(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zerrgod", Levl=70, Room=TEMPLE)
            make(mud, "Zerrand", Levl=10, Room=TEMPLE, HMV="3000 3000 500 500 500 500")
            make(mud, "Zerrold", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zerrgod", PW)
                login(hero, "Zerrand", PW)
                self.assertIn("for players", staff.sync("errand"))

                said = hero.sync("adventure", timeout=30)
                self.assertIn("* Errands:", said, said)
                said = hero.sync("errand")
                for title in ("Pests", "A letter", "The town"):
                    self.assertIn(title, said, said)
                self.assertIn("ERRAND TAKE", said)
                # Nothing counts until taken.
                staff.sync("transfer zerrand 2401")
                mark = len(hero.transcript)
                hero.sync("look")
                self.assertNotIn("Errand:", hero.transcript[mark:])
                said = hero.sync("errand take all")
                self.assertIn("Town: still to see", said, said)

                # The town: four landmarks, the last pays.
                for room in (2401, 4208, 2419):
                    mark = len(hero.transcript)
                    staff.sync(f"transfer zerrand {room}")
                    hero.sync("look")
                    self.assertIn(" seen, ", hero.transcript[mark:], hero.transcript[mark:])
                mark = len(hero.transcript)
                staff.sync("transfer zerrand 4649")
                hero.sync("look")
                got = hero.transcript[mark:]
                self.assertIn("Errand done:", got, got)
                self.assertRegex(got, r"You gain \d+ experience and ")

                # The letter: Melancholy, then the questmaster.
                staff.sync("transfer zerrand 2497")
                self.assertNotIn("Errand done", hero.sync("errand"))      # no letter yet
                staff.sync("transfer zerrand 2498")
                self.assertIn("sealed letter", hero.sync("errand"))
                staff.sync("transfer zerrand 2497")
                self.assertIn("Errand done: Melancholy's letter delivered", hero.sync("errand"))

                # Pests: three of Mud School's creatures.
                self.assertIn("1 of 3", self.kill_kobold(staff, hero, "of 3 of Mud School"))
                self.assertIn("2 of 3", self.kill_kobold(staff, hero, "of 3 of Mud School"))
                self.assertIn("Errand done: three of Mud School", self.kill_kobold(staff, hero, "Errand done"))
                said = hero.sync("errand")
                self.assertEqual(len(re.findall(r"\[done\]", said)), 3, said)
                self.assertIn("Nothing to take", hero.sync("errand take all"))
                self.assertNotIn("* Errands:", hero.sync("adventure", timeout=30))

                # An expedition: taken, given up, refused for ten minutes.
                said = hero.sync("errand expedition", timeout=30)
                self.assertIn("Expedition: WALKTO ", said, said)
                walk = re.search(r"Expedition: WALKTO (.+?) and slay", said).group(1)
                self.assertIn("You set off for", hero.sync("walkto " + walk))
                hero.sync("walkto stop")
                self.assertIn("Given up", hero.sync("errand expedition abandon"))
                self.assertIn("a moment ago", hero.sync("errand expedition"))
                hero.must("save", "Saving")
                hero.send("quit")
                hero.wait_closed()

            self.assertTrue(file_line(mud, "Zerrand", "Errand").startswith("Errand 7 0 "),
                            file_line(mud, "Zerrand", "Errand"))
            # One in Mud School, its gremlin already slain: a kobold ends it.
            set_line(mud, "Zerrand", "Expedition",
                     f"{area_id('school.are')} {KOBOLD} {GREMLIN} 0 2 0 0")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero, \
                    mud.connect(timeout=120) as old:
                login(staff, "Zerrgod", PW)
                login(hero, "Zerrand", PW)
                said = hero.sync("errand")
                self.assertIn("[done] the gremlin", said, said)
                self.assertIn("the kobold", said, said)
                self.assertIn("Expedition done", self.kill_kobold(staff, hero, "Expedition done", "Expedition:"))
                self.assertIn("finished an expedition today", hero.sync("errand expedition"))

                # Past level 10 the errands are not offered.
                login(old, "Zerrold", PW)
                self.assertIn("levels 1 to 10", old.sync("errand take 1"))
                self.assertNotIn("* Errands:", old.sync("adventure", timeout=30))


class ErrandSourceTests(unittest.TestCase):
    def test_keys_are_read_under_e_and_last_in_the_table(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        case_e = save.split("case 'E':", 1)[1].split("case 'F':", 1)[0]
        self.assertIn('"Errand"', case_e)
        self.assertIn('"Expedition"', case_e)
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        table = interp.split("cmd_table	[] =", 1)[1].split("/* End of list. */", 1)[0]
        names = re.findall(r'\{\s*"([^"]+)"', table)
        self.assertEqual(names[-1], "errand")


if __name__ == "__main__":
    unittest.main()
