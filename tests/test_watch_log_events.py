"""The watched-player log records kills, deaths and coin -- on every route.

Reading three weeks of the live log (2026-10-08) found 48,000 watched lines
and not one "killed", "died to" or coin line, though Alaric alone typed KILL
580 times. Both were wired, at the wrong address:

- death and kill were logged in raw_kill, and damage() -- every ordinary
  death in combat -- calls raw_kill_internal directly;
- coin was logged in gain_copper only, while picking coins up, looting,
  splitting, giving, paying and add_money's gold all go elsewhere.

The log exists to answer "where did that coin come from" and "what killed
them" after the fact, so both now live where every route passes.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PASSWORD = "Zwatchpw1"


def body(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start:source.index("\n}\n", start)]


class SourceTests(unittest.TestCase):
    def test_deaths_are_logged_where_every_death_passes(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        wrapper = body(fight, "void raw_kill( CHAR_DATA *ch, CHAR_DATA *victim )")
        self.assertNotIn("watch_log", wrapper)
        internal = body(fight, "static void raw_kill_internal( CHAR_DATA *ch, CHAR_DATA *victim,")
        self.assertIn('watch_log( victim, "died to %s"', internal)
        self.assertIn('watch_log( ch, "killed %s"', internal)
        # After the deaths that are not deaths.
        self.assertLess(internal.index("is_killuminati( victim ) )\n    {"),
                        internal.index('"died to %s"'))

    def test_every_purse_change_is_logged(self) -> None:
        obj = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        for signature, line in (
                ("bool adjust_coin_balance(CHAR_DATA *ch, long amount, int coin_type)",
                 'watch_log(ch, "coin %+ld %s"'),
                ("bool spend_copper( CHAR_DATA *ch, long copper )",
                 'watch_log( ch, "copper -%ld"'),
                ("bool gain_copper( CHAR_DATA *ch, long copper )",
                 'watch_log( ch, "copper %+ld"'),
                ("void add_money(CHAR_DATA *ch, long amount)",
                 'watch_log(ch, "gold %+ld"')):
            self.assertIn(line, body(obj, signature), signature)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_coin_dropped_and_picked_up_reaches_the_log(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zwatcher", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwatcher", Levl=40, Room=4207, NewCopp=50)

            with mud.connect(timeout=120) as player:
                login(player, "Zwatcher", PASSWORD)
                player.drain(1.0)
                # A coin gained and spent through the paths that were silent.
                player.send("drop 5 copper")
                player.drain(1.5)
                player.send("get coins")
                player.drain(1.5)
                player.send("quit")
                self.assertTrue(player.wait_closed())

            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1",
                                                          errors="replace")
        self.assertRegex(log, r"Log Zwatcher \[\d+\]: coin [+-]\d+ ",
                         "picking coins up or dropping them was not logged")


if __name__ == "__main__":
    unittest.main()
