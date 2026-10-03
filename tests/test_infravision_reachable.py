"""Infravision can be learned by every class that has it, in any guild.

The spell sat only in "enhancement" (the Summoner: mage class, mage guild),
"guild enhancement" (the Gnome magician: mage guild, any other class) and
"necro enhancement" (Marilith, necromancers). A mage in the cleric, thief
or warrior guild reached level 8 with the spell on their class's list and
no trainer anywhere would sell it -- and the same was true of clerics,
thieves and warriors outside the mage guild at levels 10, 13 and 16.

The fix is a one-spell group, "night vision", sold and practised by the
class guildmasters in Dresden (mobs 51-54), who admit any guild. The test
walks the real tables the way do_gain and do_practice do, so a trainer
that turns somebody away at the door, or a group rated beyond them, does
not count as a way to learn it.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()

CLASS = {"CLASS_ANY": -1, "CLASS_MAGE": 0, "CLASS_CLERIC": 1, "CLASS_THIEF": 2,
         "CLASS_WARRIOR": 3, "CLASS_MONK": 4, "CLASS_NECRO": 5, "CLASS_OTHER": 6}
GUILD = {"GUILD_MAGE": 0, "GUILD_CLERIC": 1, "GUILD_THIEF": 2,
         "GUILD_WARRIOR": 3, "GUILD_MONK": 4, "GUILD_NECRO": 5,
         "GUILD_ANY": 10, "GUILD_NONE": 11}
CLASS_NAMES = ["mage", "cleric", "thief", "warrior", "monk", "necro"]
GUILD_GROUP = {0: "mage guild", 1: "cleric guild", 2: "thief guild",
               3: "warrior guild"}
# The highest level a mortal reaches.
MORTAL_TOP = 59


def _section(text: str, marker: str) -> str:
    start = text.index(marker)
    return text[start:text.index("\n};", start)]


def load_tables():
    text = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    skills = {}
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\},\s*\{([^}]*)\},\s*(\w+)',
                         _section(text, "skill_table")):
        levels = [int(x) for x in m.group(2).split(",") if x.strip()]
        ratings = [int(x) for x in m.group(3).split(",") if x.strip()]
        skills[m.group(1)] = (levels, ratings, m.group(4))

    groups = {}
    for m in re.finditer(r'"([^"]+)",\s*\{([^}]*)\},\s*\{([^}]*)\}',
                         _section(text, "group_table")):
        ratings = [int(x) for x in m.group(2).split(",") if x.strip()]
        groups[m.group(1)] = (ratings, re.findall(r'"([^"]+)"', m.group(3)))

    trainers = []
    for m in re.finditer(r'(\d+),\s*(CLASS_\w+),\s*(GUILD_\w+),\s*'
                         r'\{([^}]*)\},\s*\{([^}]*)\}',
                         _section(text, "guildmaster_table")):
        trainers.append((int(m.group(1)), CLASS[m.group(2)], GUILD[m.group(3)],
                         re.findall(r'"([^"]+)"', m.group(4)),
                         re.findall(r'"([^"]+)"', m.group(5))))
    return skills, groups, trainers


def admits(trainer, cls: int, guild: int) -> bool:
    """The three gates do_gain and do_practice both apply."""
    _, tclass, tguild, _, _ = trainer
    if tclass == CLASS["CLASS_OTHER"] and cls == tguild:
        return False
    if tclass not in (CLASS["CLASS_ANY"], CLASS["CLASS_OTHER"]) and cls != tclass:
        return False
    if tguild != GUILD["GUILD_ANY"] and guild != tguild:
        return False
    return True


def expand(groups, name: str, out: set) -> None:
    for item in groups[name][1]:
        if item in groups:
            expand(groups, item, out)
        else:
            out.add(item)


def combinations():
    """Every class and guild a character can hold past level 6."""
    for cls in range(4):
        for guild in range(4):
            yield cls, guild
    yield 4, GUILD["GUILD_MONK"]
    yield 5, GUILD["GUILD_NECRO"]


class InfravisionTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skills, cls.groups, cls.trainers = load_tables()

    def learnable(self, cls: int, guild: int, spell: str) -> bool:
        have: set = set()
        for name in ("rom basics", CLASS_NAMES[cls] + " basics",
                     CLASS_NAMES[cls] + " default"):
            expand(self.groups, name, have)
        if guild in GUILD_GROUP:
            expand(self.groups, GUILD_GROUP[guild], have)
        for trainer in self.trainers:
            if not admits(trainer, cls, guild):
                continue
            for name in trainer[4]:
                if name in self.groups and self.groups[name][0][cls] > 0:
                    expand(self.groups, name, have)
        return spell in have

    def practisable(self, cls: int, guild: int, spell: str) -> bool:
        return any(admits(t, cls, guild) and spell in t[3] for t in self.trainers)

    def test_every_class_with_infravision_can_gain_and_practise_it(self) -> None:
        levels, _, _ = self.skills["infravision"]
        missing = []
        for cls, guild in combinations():
            if levels[cls] > MORTAL_TOP:
                continue
            if not self.learnable(cls, guild, "infravision"):
                missing.append(f"{CLASS_NAMES[cls]}/guild {guild}: cannot gain")
            if not self.practisable(cls, guild, "infravision"):
                missing.append(f"{CLASS_NAMES[cls]}/guild {guild}: cannot practise")
        self.assertEqual([], missing)

    def test_which_classes_have_it_and_when_is_unchanged(self) -> None:
        levels, ratings, fun = self.skills["infravision"]
        self.assertEqual([8, 10, 13, 16, 62, 9], levels)
        self.assertEqual([1, 1, 2, 2, 2, 2], ratings)
        self.assertEqual("spell_infravision", fun)

    def test_night_vision_holds_only_infravision(self) -> None:
        ratings, members = self.groups["night vision"]
        self.assertEqual(["infravision"], members)
        # The monk never has the spell; the necromancer keeps his own group.
        self.assertEqual([1, 1, 2, 2, -1, -1], ratings)

    def test_the_class_guildmasters_sell_it(self) -> None:
        sellers = {t[0] for t in self.trainers if "night vision" in t[4]}
        self.assertEqual({51, 52, 53, 54}, sellers)

    def test_max_group_has_room_for_the_table(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        max_group = int(re.search(r"#define MAX_GROUP\s+(\d+)", merc).group(1))
        self.assertGreaterEqual(max_group, len(self.groups))

    def test_the_help_says_where(self) -> None:
        toc = (ROOT / "area" / "toc.are").read_text(encoding="latin-1")
        self.assertIn("-1 'NIGHT VISION'~", toc)
        spells = (ROOT / "area" / "spells.are").read_text(encoding="latin-1")
        entry = spells[spells.index("0 INFRAVISION~"):]
        entry = entry[:entry.index("\n~")]
        self.assertIn("NIGHT VISION", entry)


PASSWORD = "Zinfrapw12"
MAGE_GM_ROOM = 2472          # Gioli, mob 54
CLASS_MAGE, GUILD_CLERIC = 0, 1


@unittest.skipIf(SKIP is not None, SKIP or "")
class InfravisionLiveTests(unittest.TestCase):
    def run_cmd(self, client, command: str, settle: float = 2.0) -> str:
        mark = len(client.transcript)
        client.send(command)
        client.drain(settle)
        return client.transcript[mark:]

    def test_a_mage_in_the_cleric_guild_gains_infravision_from_gioli(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zinframage", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zinframage", Levl=10, Cla=CLASS_MAGE,
                              Gui=GUILD_CLERIC, Trai=5, Room=MAGE_GM_ROOM)

            with mud.connect(timeout=120) as client:
                login(client, "Zinframage", PASSWORD)

                listing = self.run_cmd(client, "gain list", 2.5)
                self.assertIn("night vision", listing, listing)

                gained = self.run_cmd(client, "gain night vision", 2.5)
                self.assertIn("night vision", gained.lower(), gained)
                self.assertNotIn("do not know", gained, gained)

                practised = self.run_cmd(client, "practice", 3.0)
                self.assertRegex(practised, r"infravision\s+\d+%", practised)


if __name__ == "__main__":
    unittest.main()
