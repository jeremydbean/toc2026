"""Resurrection, and titanic and empower to carry (owner, 2026-10-25).

A member of the cleric guild casts RESURRECTION on a player's corpse; its
owner is asked, and only ACCEPT brings them back -- to the corpse, at one
hit point, with everything it held. DECLINE ends the call and the caster
hears so.

CONCOCT and SCRIBE make potions and scrolls of TITANIC and EMPOWER, the
two bundles Hermie gives free. Nobody casts either: their skill rows sit at
level 72 for every class, so only an object casts them.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zrisepass1"
TEMPLE = 4207
DEATH_ROOM = 4216
DAGGER = 3701


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.drain(1.0)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError("character did not leave the world")
    if fields:
        patch_player_file(mud, name, **fields)


def add_lines(mud: LiveMud, name: str, objects=(), player_lines=()) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if player_lines:
        at = text.index("\nEnd\n")
        text = text[:at] + "\n" + "\n".join(player_lines) + text[at:]
    text = text.replace("#END", "".join(objects) + "#END", 1)
    path.write_text(text, encoding="latin-1")


def obj(vnum: int, level: int = 1) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev %d\nCond 100\nEnd\n\n" % (vnum, level)


def skill_row(const: str, name: str) -> str:
    at = re.search(r'\n\s*"%s",\s*\n\s*\{' % re.escape(name), const).start()
    return const[at:at + 400]


class SourceTests(unittest.TestCase):
    def test_bundles_are_object_only_spells(self) -> None:
        const = source("const.c")
        for name in ("empower", "titanic"):
            row = skill_row(const, name)
            with self.subTest(name=name):
                self.assertIn("{ 72, 72, 72, 72, 72, 72 }", row)
                self.assertIn("spell_%s," % name, row)
                self.assertIn("TAR_CHAR_DEFENSIVE", row)
        wiz = source("act_wiz.c")
        # The staff commands, Hermie and the spells lay down one effect.
        self.assertEqual(wiz.count("empower_apply( victim,"), 2)
        self.assertEqual(wiz.count("titanic_apply( victim,"), 2)
        # A crafted one never outlasts Hermie's free one.
        self.assertIn("URANGE( 5, level / 2, SPELLUP_DURATION )", wiz)

    def test_recipes_make_both_bundles(self) -> None:
        magic2 = source("magic2.c")
        for line in ('{ CRAFT_CONCOCT, { 57, 72, 0 }, { "titanic"',
                     '{ CRAFT_CONCOCT, { 55, 63, 0 }, { "empower"',
                     '{ CRAFT_SCRIBE, { 85, 76, 88 }, { "titanic"',
                     '{ CRAFT_SCRIBE, { 78, 80, 83 }, { "empower"'):
            self.assertIn(line, magic2)

    def test_resurrection_is_the_cleric_guilds(self) -> None:
        const = source("const.c")
        row = skill_row(const, "resurrection")
        self.assertIn("spell_resurrection", row)
        guild = const[const.index('"cleric guild",\t\t  {'):]
        guild = guild[:guild.index("}\n    },")]
        self.assertIn('"resurrection"', guild)
        body = source("resurrect.c")
        self.assertIn("ch->pcdata->guild != GUILD_CLERIC", body)
        # The offer's corpse is looked for again before it is trusted.
        accept = body[body.index("void do_accept"):body.index("void do_decline")]
        self.assertLess(accept.index("resurrect_corpse_still( ch )"),
                        accept.index("char_from_room( ch )"))
        self.assertLess(accept.index("resurrect_refusal( ch, to )"),
                        accept.index("char_from_room( ch )"))
        self.assertIn("ch->hit = 1;", accept)
        self.assertIn("src/resurrect.c", (ROOT / "CMakeLists.txt").read_text())


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_resurrection_asks_and_brings_back_at_one_hit_point(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zrisestaff", Levl=70, Room=TEMPLE)
            make(mud, "Zrisecleric", Levl=45, Room=TEMPLE, Cla=1, Gui=1,
                 HMV="900 900 2000 2000 500 500", HMVP="900 2000 500")
            make(mud, "Zrisefallen", Levl=20, Room=TEMPLE,
                 HMV="300 300 300 300 300 300", HMVP="300 300 300")
            add_lines(mud, "Zrisecleric", player_lines=["Sk 100 'resurrection'"])
            add_lines(mud, "Zrisefallen", objects=[obj(DAGGER)])

            with mud.connect(timeout=120) as staff, \
                    mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                login(staff, "Zrisestaff", PW)
                login(cleric, "Zrisecleric", PW)
                login(fallen, "Zrisefallen", PW)
                for client in (staff, cleric, fallen):
                    run(client, "scroll 0", 0.8)

                run(staff, "slay zrisefallen", 2.0)
                fallen.drain(1.5)
                self.assertIn("corpse", run(cleric, "look", 1.4))

                # Nothing happens to the dead until they say so.
                offer = run(cleric, "cast resurrection corpse", 2.0)
                self.assertIn("call its soul home", offer, offer)
                fallen.drain(1.5)
                self.assertIn("Type ACCEPT", fallen.transcript)
                no = run(fallen, "decline", 1.4)
                self.assertIn("let the call fade", no)
                self.assertIn("fade unanswered", run(cleric, "look", 1.4))
                self.assertIn("Nobody is calling", run(fallen, "accept", 1.2))

                # Asked again, and taken.
                run(cleric, "cast resurrection corpse", 3.5)
                fallen.drain(1.5)
                rose = run(fallen, "accept", 2.0)
                self.assertIn("edge of life", rose, rose)
                self.assertIn("Before the Altar", rose)
                self.assertIn("dagger", run(fallen, "inventory", 1.2))
                # One hit point as they rise; the Temple heals fast after.
                self.assertIn("<1hp", rose, rose)
                self.assertIn("answers your call", run(cleric, "look", 1.4))
                self.assertNotIn("corpse", run(cleric, "look", 1.4))

    def test_titanic_and_empower_come_from_a_potion_and_a_scroll(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zbrewbig", Levl=30, Room=TEMPLE, Cla=1,
                 HMV="400 400 400 400 400 400", HMVP="400 400 400")
            add_lines(mud, "Zbrewbig",
                      objects=[obj(57), obj(72), obj(57), obj(72),
                               obj(78), obj(80), obj(83), obj(78), obj(80), obj(83)],
                      player_lines=["Sk 100 'concoct'", "Sk 100 'scribe'",
                                    "Sk 100 'scrolls'"])
            with mud.connect(timeout=120) as client:
                login(client, "Zbrewbig", PW)
                run(client, "scroll 0")
                # No class reaches the spell itself.
                self.assertIn("You don't know any spells", run(client, "cast titanic", 1.2))
                made = ""
                for _ in range(2):
                    made = run(client, "concoct troll minotaur", 4.5)
                    if "towering bronze" in made:
                        break
                self.assertIn("towering bronze potion", made, made)
                # The concoction's lag runs first, then the quaff.
                drunk = run(client, "quaff bronze", 5.5)
                self.assertIn("titanic power", drunk, drunk)
                self.assertIn("titanic", run(client, "affects", 1.5))

                scroll = ""
                for _ in range(2):
                    scroll = run(client, "scribe demon fairy venom", 4.5)
                    if "gilded" in scroll:
                        break
                self.assertIn("gilded scroll", scroll, scroll)
                read = run(client, "recite gilded", 5.5)
                self.assertIn("divine power", read, read)
                # RECITE's six seconds of lag run before AFFECTS answers.
                affects = run(client, "affects", 8.5)
                self.assertIn("empower", affects)
                self.assertIn("sanctuary", affects)


if __name__ == "__main__":
    unittest.main()
