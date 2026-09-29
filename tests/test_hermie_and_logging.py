"""Hermie, the healer's uncurse, and what LOG actually records.

All three came out of reading one watched player's session. The log
showed nine "say 22" in three seconds and nine "say 23" in two, every
one of them granted; three "heal uncurse jeans" five seconds apart
followed by the item being sacrificed; and 82 of its own 296 lines
empty.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Zhermie1"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.8) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class HermieTests(unittest.TestCase):
    def staffed(self, name: str = "Zbuffer") -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        with mud.connect(timeout=120) as client:
            create_character(client, name, PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        # SPELLUP is L4 (66) and LOG is L2 (68), so the fixture needs
        # the top of the tree, not merely immortal trust.
        patch_player_file(mud, name, Levl=60, Tru=70, Room=TEMPLE,
                          HpManaMove="500 2000 500 2000 500 2000")
        return mud

    def summon_hermie(self, client) -> None:
        said = run(client, "spellup", 2.0)
        self.assertNotIn("Huh?", said, said)

    def test_buff_asks_her_the_way_the_healer_is_asked(self) -> None:
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zbuffer", PASSWORD)
            self.summon_hermie(client)

            menu = run(client, "buff", 2.2)
            self.assertIn("sanctuary", menu, menu[-700:])

            said = run(client, "buff sanctuary", 2.2)
            self.assertNotIn("Huh?", said, said)
            self.assertIn("sanctuary", run(client, "affect", 2.0).lower())

    def test_she_is_free(self) -> None:
        """The healer at the pit charges; she is the free one."""
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zbuffer", PASSWORD)
            self.summon_hermie(client)
            before = run(client, "worth", 1.8)
            run(client, "buff armor", 2.0)
            self.assertEqual(before, run(client, "worth", 1.8))

    def test_a_full_restore_rather_than_nine_requests(self) -> None:
        """A player topping up said the same number nine times in three
        seconds, and every one of them worked."""
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zbuffer", PASSWORD)
            self.summon_hermie(client)

            # Spend some movement and mana to have something to restore.
            for _ in range(6):
                run(client, "north", 0.5)
                run(client, "south", 0.5)

            run(client, "buff vitals", 2.2)
            score = run(client, "score", 2.0)
            self.assertNotIn("Huh?", score, score)

            # Asking again with nothing wanting should say so rather than
            # silently doing nothing.
            again = run(client, "buff vitals", 2.0)
            self.assertIn("Nothing wanting", again, again)

    def test_a_group_hands_out_several_at_once(self) -> None:
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zbuffer", PASSWORD)
            self.summon_hermie(client)

            run(client, "buff detects", 3.0)
            affects = run(client, "affect", 2.0).lower()
            for piece in ("detect invis", "detect magic"):
                with self.subTest(piece=piece):
                    self.assertIn(piece, affects, affects)

    def test_heal_reaches_her_and_costs_nothing(self) -> None:
        """The healer at the pit is the interface players know, so hers
        is the same one. She is deliberately not ACT_IS_HEALER: that
        flag routes through the code that charges."""
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zbuffer", PASSWORD)
            self.summon_hermie(client)

            menu = run(client, "heal", 2.2)
            self.assertIn("free", menu, menu[-600:])
            self.assertIn("I offer the following", menu, menu[-600:])

            before = run(client, "worth", 1.8)
            run(client, "heal armor", 2.2)
            self.assertIn("armor", run(client, "affect", 2.0).lower())
            self.assertEqual(before, run(client, "worth", 1.8))

    def test_she_no_longer_listens_to_the_room(self) -> None:
        """Speech was how she worked and is not how she works now."""
        mud = self.staffed()
        with mud.connect(timeout=120) as client:
            login(client, "Zbuffer", PASSWORD)
            self.summon_hermie(client)
            run(client, "say armor", 2.2)
            self.assertNotIn("armor", run(client, "affect", 2.0).lower())


@unittest.skipIf(SKIP is not None, SKIP or "")
class WatchedPlayerLogTests(unittest.TestCase):
    def test_movement_and_refusals_are_recorded_with_the_room(self) -> None:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)

        with mud.connect(timeout=120) as client:
            create_character(client, "Zwatched", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zwatched", Levl=45, Tru=70, Room=TEMPLE)

        with mud.connect(timeout=120) as client:
            login(client, "Zwatched", PASSWORD)
            run(client, "log Zwatched", 1.8)
            run(client, "north", 1.2)
            run(client, "zzzznosuchcommand", 1.2)
            run(client, "look", 1.2)
            client.drain(1.5)

        log = (mud.root / "log").glob("*")
        text = ""
        for path in log:
            if path.is_file():
                text += path.read_text(encoding="latin-1", errors="replace")
        if not text:
            self.skipTest("this harness does not capture the game log")

        self.assertIn("Log Zwatched", text)
        # Movement is recorded rather than blanked.
        self.assertIn("north", text)
        # A refused command is recorded too.
        self.assertIn("refused", text)
        # And where they ended up, which no command shows for a portal,
        # a teleport or a recall ring.
        self.assertIn("moved to", text)


class LoggingSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        cls.magic = (ROOT / "src" / "magic.c").read_text(encoding="utf-8")
        cls.wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")

    def test_a_watched_player_never_gets_an_empty_line(self) -> None:
        """82 of the first 296 lines anyone captured were empty."""
        self.assertIn('logline[0] != \'\\0\'', self.interp)

    def test_a_social_is_not_logged_as_a_refusal(self) -> None:
        """The log has to be worth trusting, and it was not.

        The watched line was written from the command-table lookup, and
        socials are looked up after that, so every NOD, GRIN and BOW a
        watched character used was recorded as "(refused)". Four of
        them read back that way in the first session anyone checked. A
        log that reports working commands as failures is worse than no
        log at all.
        """
        body = self.interp.split("if ( !found )")[1]
        body = body.split("Character not in position")[0]

        self.assertIn("bool social = check_social( ch, command, argument );",
                      body)
        self.assertIn('social ? "social" : "refused"', body)
        self.assertLess(
            body.index("check_social"), body.index('"refused"'),
            "the lookup has to happen before the line is written",
        )

    def test_hermie_says_when_she_ignores_a_named_item(self) -> None:
        """Eight tries at 'heal uncurse shieldb' with no word back.

        Remove curse cannot be aimed -- it frees whichever cursed item
        fails its save first -- and she was dropping the name in
        silence, so the player had no way to know. The healer at the
        pit already said so.
        """
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        body = wiz.split("void do_buff(")[1].split(chr(10) + "}")[0]
        self.assertIn("I lift what I can reach, not what you name.", body)
        self.assertIn('!str_prefix( arg, "uncurse" )', body)

    def test_a_password_is_still_never_written(self) -> None:
        """The whole reason LOG_NEVER blanks the line. Watching a player
        must not defeat it: the command is named, the arguments are not."""
        self.assertIn("arguments withheld", self.interp)
        block = self.interp.split("watched = ( !IS_NPC(ch)", 1)[1][:2000]
        self.assertIn("secret ? cmd_table[cmd].name : logline", block)
        self.assertIn("logline[0] = '\\0'", block)

    def test_the_room_is_recorded(self) -> None:
        self.assertIn('"Log %s [%d]: %s%s"', self.interp)

    def test_a_curse_that_resists_says_so(self) -> None:
        """250 gold and complete silence was the old behaviour."""
        body = self.magic.split("void spell_remove_curse(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("The curse holds fast", body)
        self.assertIn("Nothing you are carrying is cursed", body)

    def test_hermie_fills_the_pool_rather_than_topping_it(self) -> None:
        body = self.wiz.split("static bool spellup_grant(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("SPELLUP_RESTORE", body)
        self.assertIn("victim->hit = victim->max_hit", body)
        self.assertIn("victim->move = victim->max_move", body)


if __name__ == "__main__":
    unittest.main()
