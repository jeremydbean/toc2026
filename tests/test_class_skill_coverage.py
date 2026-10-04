"""What a class can learn, and the room rules travel spells keep.

Owner, 2026-10-04:

* Cross-class spells can be taught. ARCANE STUDIES, from Dawn the Wand
  Maker, holds the spells the class sheet gives a mage, thief or warrior a
  level for that no group of theirs held. The spells HELP keeps to one
  class -- the necromancer's, M/M's and C/C's own -- stay where they are.
* Despair is taught (Rakar); phase is not.
* Major globe will not form over armor, shield, stone skin or shroud, as
  HELP has always said.
* Earth travel and gate keep the rules walking in keeps.
* A remort keeps on what the new life can wear and stashes what it cannot,
  race included.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
CLASSES = ["mage", "cleric", "thief", "warrior", "monk", "necro"]

# Reachable on the class sheet and taught nowhere, each for a reason HELP
# gives: necromancers only, M/M only, C/C only, rope trick's own list,
# "not available to players", a remort gift, the thieves' guild, or phase.
EXPECTED_UNTAUGHT = {
    "mage": {"ventriloquate", "shadowmeld", "vampiric touch", "phase",
             "word of recall", "tentacles", "trap the soul"},
    "cleric": {"shadowmeld", "ventriloquate", "vampiric touch", "fire shield",
               "frost shield", "mass invis", "phase", "blizzard", "tentacles",
               "trap the soul"},
    "thief": {"ventriloquate", "shadowmeld", "phase", "mass invis",
              "vampiric touch", "word of recall", "rope trick"},
    "warrior": {"shadowmeld", "ventriloquate", "phase", "word of recall",
                "vampiric touch", "mass invis", "rope trick"},
    "monk": {"shadowmeld", "sleight of hand", "lore", "phase"},
    "necro": {"shadowmeld", "phase"},
}

CONST = {"CLASS_ANY": -1, "CLASS_OTHER": 6, "CLASS_MAGE": 0, "CLASS_CLERIC": 1,
         "CLASS_THIEF": 2, "CLASS_WARRIOR": 3, "CLASS_MONK": 4, "CLASS_NECRO": 5,
         "GUILD_MAGE": 0, "GUILD_CLERIC": 1, "GUILD_THIEF": 2, "GUILD_WARRIOR": 3,
         "GUILD_MONK": 4, "GUILD_NECRO": 5, "GUILD_ANY": 10, "GUILD_NONE": 11}
GUILDS = {0: [0, 1, 2, 3], 1: [0, 1, 2, 3], 2: [0, 1, 2, 3], 3: [0, 1, 2, 3],
          4: [4], 5: [5]}


def tables():
    src = re.sub(r"/\*.*?\*/", " ",
                 (SRC / "const.c").read_text(encoding="latin-1"), flags=re.S)
    start = src.index("skill_table     [MAX_SKILL]")
    body = src[start:src.index("\n};", start)]
    skills = {}
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\}', body):
        levels = [int(x) for x in m.group(2).split(",") if x.strip()]
        if len(levels) == 6:
            skills[m.group(1)] = levels
    start = src.index("group_table")
    groups, order = {}, []
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\},\s*\{(.*?)\}\s*\}',
                         src[start:], re.S):
        ratings = [int(x) for x in m.group(2).split(",") if x.strip()]
        if len(ratings) == 6:
            groups[m.group(1)] = (ratings, re.findall(r'"([^"]+)"', m.group(3)))
            order.append(m.group(1))
    start = src.index("guildmaster_table")
    gm = src[start:src.index("\n};", start)]
    trainers = []
    for m in re.finditer(r'(\d+),\s*(\w+),\s*(\w+),\s*\{(.*?)\},\s*\{(.*?)\}', gm, re.S):
        cls = CONST[m.group(2)] if m.group(2) in CONST else int(m.group(2))
        guild = CONST[m.group(3)] if m.group(3) in CONST else int(m.group(3))
        trainers.append((cls, guild, re.findall(r'"([^"]+)"', m.group(4)),
                         re.findall(r'"([^"]+)"', m.group(5))))
    return skills, groups, order, trainers


def serves(trainer, c, g):
    cls, guild = trainer[0], trainer[1]
    if cls == 6 and c == guild:
        return False
    if cls not in (-1, 6) and cls != c:
        return False
    return guild in (10, g)


class ClassSkillCoverageTests(unittest.TestCase):
    def test_only_what_help_restricts_is_untaught(self) -> None:
        skills, groups, order, trainers = tables()

        def expand(names):
            out, todo = set(), list(names)
            while todo:
                n = todo.pop()
                g = next((x for x in order if x.lower().startswith(n.lower())), None) \
                    if n not in skills else None
                if g and g not in out:
                    out.add(g)
                    todo.extend(groups[g][1])
                else:
                    out.add(n)
            return out

        for c, name in enumerate(CLASSES):
            have = set()
            for g in order:
                if groups[g][0][c] >= 0:
                    have |= expand([g])
            for t in trainers:
                if any(serves(t, c, g) for g in GUILDS[c]):
                    have |= expand(t[3]) | set(t[2])
            untaught = {n for n, lv in skills.items() if 0 <= lv[c] < 60 and n not in have}
            self.assertEqual(untaught, EXPECTED_UNTAUGHT[name], name)

    def test_major_globe_refuses_every_armor_spell(self) -> None:
        magic2 = (SRC / "magic2.c").read_text(encoding="latin-1")
        body = magic2[magic2.index("void spell_major_globe("):]
        body = body[:body.index("af.type")]
        for spell in ("shroud", "armor", "shield", "stone skin"):
            self.assertIn(f'skill_lookup("{spell}")', body, spell)

    def test_travel_spells_keep_room_rules(self) -> None:
        for path, spell in (("magic.c", "void spell_gate("),
                            ("magic2.c", "void spell_earth_travel(")):
            text = (SRC / path).read_text(encoding="latin-1")
            body = text[text.index(spell):]
            body = body[:body.index("\n}\n")]
            self.assertIn("travel_spell_refuses( ch, victim->in_room )", body, spell)
        move = (SRC / "act_move.c").read_text(encoding="latin-1")
        helper = move[move.index("bool travel_spell_refuses("):]
        helper = helper[:helper.index("\n}\n")]
        for rule in ("class_table[iClass].guild[iGuild]", "guild_closed_rooms",
                     "hyrule_gate_check"):
            self.assertIn(rule, helper)

    def test_remort_stashes_what_the_new_race_cannot_wear(self) -> None:
        info = (SRC / "act_info.c").read_text(encoding="latin-1")
        remort = info[info.index("void do_remort("):]
        remort = remort[:remort.index("\n}\n")]
        self.assertGreaterEqual(remort.count("gear_race_allowed"), 2)

    def test_walkto_pays_fares_and_respects_hyrule_order(self) -> None:
        walk = (SRC / "walkto.c").read_text(encoding="latin-1")
        self.assertIn("hyrule_gate_would_refuse( ch, room, pexit->u1.to_room )", walk)
        self.assertIn("has_enough_gold( ch, WALK_FARE_GOLD )", walk)


try:
    from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
    LIVE_SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover
    LIVE_SKIP = str(exc)

PW = "Zcoverage1"


@unittest.skipIf(LIVE_SKIP is not None, LIVE_SKIP or "")
class ClassSkillCoverageLiveTests(unittest.TestCase):
    def make(self, mud, name, **fields):
        with mud.connect(timeout=120) as client:
            create_character(client, name, PW)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, name, **fields)

    def test_gains_and_the_globe(self) -> None:
        with LiveMud() as mud:
            # A mage in the thieves' guild buys arcane studies from Dawn.
            self.make(mud, "Zarcane", Cla=0, Gui=2, Levl=30, Trai=40, Room=4329)
            # Anyone buys despair from Rakar.
            self.make(mud, "Zdespair", Cla=3, Gui=3, Levl=30, Trai=40, Room=2405)
            # A mage under armor cannot raise a globe over it.
            self.make(mud, "Zglobe", Cla=0, Gui=0, Levl=40, Room=4207,
                      HMV="500 500 2000 2000 500 500", HMVP="500 2000 500")
            for name, command in (("Zarcane", "gain arcane studies"),
                                  ("Zdespair", "gain despair")):
                with mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    client.send(command)
                    client.drain(2)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            with mud.connect(timeout=120) as client:
                login(client, "Zglobe", PW)
                client.send("cast armor")
                client.drain(2)
                client.send("cast 'major globe'")
                client.drain(2)
                globe = client.transcript
                client.send("quit")
                self.assertTrue(client.wait_closed())

            arcane = (mud.player_dir / "Zarcane").read_text(encoding="latin-1")
            for spell in ("earthquake", "plague", "harm"):
                self.assertRegex(arcane, rf"(?m)^Sk +1 '{spell}'$", spell)
            despair = (mud.player_dir / "Zdespair").read_text(encoding="latin-1")
            self.assertRegex(despair, r"(?m)^Sk +1 'despair'$")
            if "You feel someone protecting you." in globe:
                self.assertIn("will not form around other protective magic", globe)


if __name__ == "__main__":
    unittest.main()
