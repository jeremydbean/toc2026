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


NUMBERS = {"once": 1, "twice": 2, "two": 2, "three": 3, "four": 4, "five": 5}
QUESTMASTER_ROOM = 2497
SQUARE = 2401


def steps(said: str) -> tuple[str, str, int]:
    """The way the game says to go: WALKTO <place>, then <DIR> <n> times."""
    m = re.search(r"WALKTO (\w+), then ([A-Z]+) (\w+) times", said)
    assert m, said
    return m.group(1), m.group(2).lower(), NUMBERS[m.group(3)]


@unittest.skipIf(SKIP is not None, SKIP or "")
class LetterWalkTests(unittest.TestCase):
    """Melancholy's letter carried as the game tells a mortal to carry it:
    from the Oak Tree Square, on foot, with no staff to move anybody."""

    def test_the_stated_way_reaches_the_questmaster(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zerrwalker", Levl=8, Room=SQUARE, HMV="3000 3000 500 500 3000 3000")
            with mud.connect(timeout=120) as hero:
                login(hero, "Zerrwalker", PW)
                self.assertIn("Center of Oak Tree Square", hero.sync("look"))
                # ADVENTURE and the questmaster's refusal give the same way.
                self.assertIn("WALKTO SQUARE, UP four times", hero.sync("adventure", timeout=30))
                self.assertIn("go UP four times", hero.sync("aquest request"))

                said = hero.sync("errand take 2")
                self.assertIn("Letter: WALKTO MELANCHOLY", said, said)
                hero.send("walkto melancholy")
                hero.expect("You have arrived", timeout=120)
                given = hero.sync("errand")
                self.assertIn("sealed letter", given, given)
                place, way, count = steps(given)
                # ERRAND repeats the same way while the letter is carried.
                self.assertEqual(steps(hero.sync("errand")), (place, way, count))
                self.assertNotIn("climb", given.lower())

                hero.send("walkto " + place.lower())
                hero.expect("You have arrived", timeout=120)
                self.assertIn("Center of Oak Tree Square", hero.sync("look"))
                for _ in range(count):
                    hero.sync(way)
                self.assertIn("Questmaster's Globe", hero.sync("look"))
                done = hero.sync("errand")
                self.assertIn("Errand done: Melancholy's letter delivered", done, done)
                self.assertRegex(done, r"You gain \d+ experience and ")


def adventure_jobs(client) -> str:
    said = client.sync("adventure", timeout=30)
    assert "What you might do next" in said, said
    assert "Hit Return" not in said and "[Return" not in said, said
    for line in said.replace("\r", "").split("\n"):
        assert len(line) <= 79, line
    return said


@unittest.skipIf(SKIP is not None, SKIP or "")
class AdventureJobsTests(unittest.TestCase):
    """ADVENTURE names the jobs under way before the ones on offer."""

    def test_jobs_under_way_and_on_offer(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zerrgod", Levl=70, Room=TEMPLE)
            make(mud, "Zerrall", Levl=7, Room=TEMPLE)
            make(mud, "Zerrboth", Levl=7, Room=TEMPLE)
            make(mud, "Zerrexped", Levl=7, Room=TEMPLE)
            school = f"{area_id('school.are')} {KOBOLD} {GREMLIN} 0 0 0 0"
            # An expedition, the pests errand taken, the other two not.
            set_line(mud, "Zerrboth", "Errand", "0 1 0 0 0")
            set_line(mud, "Zerrboth", "Expedition", school)
            # An expedition and no errand taken.
            set_line(mud, "Zerrexped", "Expedition", school)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zerrgod", PW)
                login(hero, "Zerrall", PW)
                said = adventure_jobs(hero)
                self.assertIn("* Errands: small paid jobs", said, said)

                # All three taken: under way, nothing more on offer.
                hero.sync("errand take all")
                said = adventure_jobs(hero)
                self.assertIn("* Under way: 3 errands.  ERRAND shows all.", said, said)
                self.assertNotIn("* Errands:", said)

                # One finished: two left under way.
                staff.sync("transfer zerrall 2498")
                self.assertIn("sealed letter", hero.sync("errand"))
                staff.sync("transfer zerrall 2497")
                self.assertIn("Errand done", hero.sync("errand"))
                staff.sync(f"transfer zerrall {TEMPLE}")
                said = adventure_jobs(hero)
                self.assertIn("* Under way: 2 errands.  ERRAND shows all.", said, said)

                with mud.connect(timeout=120) as both, mud.connect(timeout=120) as exped:
                    login(both, "Zerrboth", PW)
                    login(exped, "Zerrexped", PW)
                    said = adventure_jobs(both)
                    self.assertIn("* Under way: your expedition and 1 errand; more on offer.", said, said)
                    self.assertNotIn("* Errands:", said)
                    said = adventure_jobs(exped)
                    self.assertIn("* Under way: your expedition; more on offer.", said, said)


class OakDirectionSourceTests(unittest.TestCase):
    def test_no_climb_for_the_oak(self) -> None:
        """CLIMB works an object; the oak is four UP exits (2401, 2410,
        2411, 2414, 2497), so no direction to the questmaster says climb."""
        for name in ("adventure.c", "errand.c", "tutorial.c"):
            text = (ROOT / "src" / name).read_text(encoding="latin-1")
            text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)     # comments aside
            self.assertNotRegex(text, r"(?i)climb\s+up", name)
        quest = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")
        self.assertNotIn("climb up from the Oak Tree Square", quest)
        commands = (ROOT / "area" / "commands.are").read_text(encoding="latin-1")
        errand_help = commands.split("ERRAND ERRANDS EXPEDITION EXPEDITIONS~", 1)[1].split("~", 1)[0]
        self.assertNotIn("climb", errand_help.lower())
        self.assertIn("UP four times", errand_help)


    def test_keys_are_read_under_e_and_last_in_the_table(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        case_e = save.split("case 'E':", 1)[1].split("case 'F':", 1)[0]
        self.assertIn('"Errand"', case_e)
        self.assertIn('"Expedition"', case_e)
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        table = interp.split("cmd_table	[] =", 1)[1].split("/* End of list. */", 1)[0]
        names = re.findall(r'\{\s*"([^"]+)"', table)
        self.assertEqual(names.index("errand"), names.index("hunting") + 1)


if __name__ == "__main__":
    unittest.main()
