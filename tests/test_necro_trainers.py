"""Every skill a necromancer can reach has somebody to teach it.

Cause serious (a necromancer's at 18) and scribe (at 30) sat in no group
and no necromancer trainer's list, so no necromancer could ever learn them
(owner, 2026-10-04). This reads the tables from src/const.c the way GAIN
does: a trainer's second list holds groups or single skills, and a group a
trainer sells brings its members with it.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NECRO = 5
LEVEL_IMMORTAL = 60

# Abilities no class has a trainer for, on purpose: phase is shadowmeld
# while you sleep (owner, 2026-10-04). Despair is taught by Rakar now.
NOBODY_TEACHES = {"phase"}


def tables() -> tuple[dict[str, int], dict[str, list[str]], set[str]]:
    src = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
    start = src.index("skill_table     [MAX_SKILL]")
    body = src[start:src.index("};", start)]
    skills = {}
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\}', body):
        levels = [int(x) for x in m.group(2).split(",") if x.strip()]
        if len(levels) == 6:
            skills[m.group(1)] = levels[NECRO]

    start = src.index("group_table")
    groups = {m.group(1): re.findall(r'"([^"]+)"', m.group(2))
              for m in re.finditer(r'\{\s*"([^"]+)",\s*\{[^}]*\},\s*\{(.*?)\}\s*\}',
                                   src[start:], re.S)}

    start = src.index("guildmaster_table")
    gm = src[start:src.index("};", start)]
    gained: set[str] = set()
    for m in re.finditer(r'\d+,\s*(\w+),\s*\w+,\s*\{(.*?)\},\s*\{(.*?)\}', gm, re.S):
        # Either list: psionics are granted and weapons come with the
        # class, and both are then practised rather than gained.
        if m.group(1) in ("CLASS_NECRO", "CLASS_ANY"):
            gained.update(re.findall(r'"([^"]+)"', m.group(2)))
            gained.update(re.findall(r'"([^"]+)"', m.group(3)))
    return skills, groups, gained


class NecroTrainerTests(unittest.TestCase):
    def test_every_necromancer_skill_has_a_trainer(self) -> None:
        skills, groups, gained = tables()
        reachable = set(gained)
        for name in list(gained) + ["necro basics", "necro default", "rom basics"]:
            reachable.update(groups.get(name, []))
        untaught = {name for name, level in skills.items()
                    if 0 <= level < LEVEL_IMMORTAL and name not in reachable}
        self.assertEqual(untaught, NOBODY_TEACHES)


SKIP = None
try:
    from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
    SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover
    SKIP = str(exc)

PW = "Znecrotr1"


@unittest.skipIf(SKIP is not None, SKIP or "")
class NecroTrainerLiveTests(unittest.TestCase):
    def test_necro_maladictions_brings_cause_serious(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Znecrogain", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Znecrogain", Cla=5, Gui=5, Levl=35,
                              Trai=40, Room=4721)
            with mud.connect(timeout=120) as client:
                login(client, "Znecrogain", PW)
                # GAIN sells a spell only inside a group.
                client.send("gain necro maladictions")
                client.drain(2)
                seen = client.transcript
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertIn("trains you in the art of necro maladictions", seen)
            text = (mud.player_dir / "Znecrogain").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Sk +1 'cause serious'$")

    def test_spirit_teaches_scribe(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Znecroscribe", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Znecroscribe", Cla=5, Gui=5, Levl=35,
                              Trai=40, Room=4720)
            with mud.connect(timeout=120) as client:
                login(client, "Znecroscribe", PW)
                client.send("gain scribe")
                client.drain(2)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            text = (mud.player_dir / "Znecroscribe").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Sk +1 'scribe'$")

    def test_no_remort_past_the_cap(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpastcap", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zpastcap", Levl=56, NumRemorts=0, Room=4207)
            with mud.connect(timeout=120) as client:
                login(client, "Zpastcap", PW)
                client.send(f"remort {PW} warrior none human")
                client.drain(3)
                seen = client.transcript
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertIn("past the level a remort is taken at", seen)
            text = (mud.player_dir / "Zpastcap").read_text(encoding="latin-1")
            self.assertRegex(text, r"(?m)^Levl 56$")


if __name__ == "__main__":
    unittest.main()
