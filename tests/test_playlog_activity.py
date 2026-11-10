"""The play journal writes down everything a player gains and where they
go (owner, 2026-11-10: "log everything ... so this doesn't have to happen
again" -- a coin jump in the logs took hours to trace back to one mob's
over-generous purse, because no row said where a lump of coin came from).

New rows in log/play.tsv, each with the common columns (epoch, kind,
name, level, room, area):

  coin      every purse change: amount, source, command, from where, and
            wealth (purse and bank) after it; bank interest too
  got       every object reaching a player: vnum, name, type, level,
            cost, command, from where
  level     every level gained: from, to, class, remorts, experience,
            seconds the level took, how
  area      every move into another area, with the time spent in the last
  achieved  every achievement: key, points, total
  skill     every skill gain: skill, before, after, success or mistake
  quest     every quest handed out: kind, target, level, area, minutes

Wizinvis staff write none of them, and a wizinvis giver is "someone".
"""

from __future__ import annotations

import time
import unittest
from pathlib import Path

from live_mud import (MIND_ARENA, LiveMud, create_character, login,
                      patch_player_file, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zactpass11"
DAGGER = 3701
BAG = 3032


def rows(mud: LiveMud, name: str) -> list[list[str]]:
    text = (mud.root / "log" / "play.tsv").read_text(encoding="latin-1")
    return [line.split("\t") for line in text.splitlines()
            if line.count("\t") >= 6 and line.split("\t")[2] == name]


class ActivitySourceTests(unittest.TestCase):
    def test_every_hook_is_wired(self) -> None:
        def src(name):
            return (ROOT / "src" / name).read_text(encoding="latin-1")
        self.assertIn("playlog_got(ch, obj);", src("handler.c"))
        self.assertIn("playlog_moved( ch );", src("handler.c"))
        self.assertIn('playlog_bank( ch, gain, "interest" );', src("update.c"))
        self.assertIn("playlog_level( ch, ch->level - 1, is_advance );", src("update.c"))
        self.assertIn("playlog_achieved(ch, definition->key", src("achievements.c"))
        self.assertEqual(src("skills.c").count("playlog_skill( ch, sn,"), 2)
        self.assertEqual(src("quest.c").count("playlog_quest( ch, kind,"), 2)
        act_obj = src("act_obj.c")
        self.assertIn("playlog_from( keeper->short_descr );", act_obj)
        self.assertIn('playlog_from( container != NULL ? container->short_descr : "the floor" );',
                      act_obj)
        playlog = src("playlog.c")
        coin = playlog.split("void playlog_coin( CHAR_DATA *ch, long amount, long unit, bool pile )",
                             1)[1].split("\n}\n", 1)[0]
        self.assertIn('journal_write( "coin", ch, fields );', coin)
        self.assertIn("play_wealth( ch )", coin)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ActivityLiveTests(unittest.TestCase):
    def test_gains_levels_and_moves_are_written_down(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name, level in (("Zactstaff", 70), ("Zactplay", 10), ("Zacthidden", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207, NewGold=100)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player, \
                    mud.connect(timeout=120) as hidden:
                login(staff, "Zactstaff", PW)
                login(player, "Zactplay", PW)
                login(hidden, "Zacthidden", PW)
                hidden.sync("wizinvis")
                for client in (staff, player, hidden):
                    client.sync("scroll 0")
                staff.must(f"load obj {DAGGER}", "You create")
                staff.must("give dagger zactplay", "You give")
                hidden.must(f"load obj {DAGGER}", "You create")
                hidden.must("give dagger zactplay", "You give")
                player.sync("flee")                      # Brave Sir Robin
                staff.must("advance zactplay 12", "")
                # Into the fixture area: an area row, and a floor to drop on
                # (the Temple's takes what is dropped there).
                staff.must(f"goto {MIND_ARENA}", "")
                staff.must(f"transfer zactplay {MIND_ARENA}", "")
                # Starter gear burns as it hits the ground: a bag.
                staff.must(f"load obj {BAG}", "You create")
                staff.must("drop bag", "You drop")
                player.must("get bag", "You get")
                # A pile of coin off the floor: a coin row.
                staff.must("drop 5 gold", "OK")
                picked = player.must("get coins", "You get")
                time.sleep(1)
                for client in (player, staff, hidden):
                    client.send("quit")
                    client.wait_closed()
            mine = rows(mud, "Zactplay")
            hidden_rows = rows(mud, "Zacthidden")

        kinds = {r[1] for r in mine}
        coin = [r for r in mine if r[1] == "coin"]
        self.assertTrue(coin, kinds)
        self.assertTrue(coin[0][6].startswith("+"), coin[0])
        self.assertEqual(coin[0][7], "loot", coin[0])
        self.assertEqual(coin[0][8], "get", coin[0])
        self.assertEqual(coin[0][9], "the floor", coin[0])
        self.assertGreaterEqual(int(coin[0][10]), int(coin[0][6]), "wealth after")
        got = [r for r in mine if r[1] == "got"]
        froms = [r[12] for r in got if r[6] == str(DAGGER)]
        self.assertIn("Zactstaff", froms, got)
        self.assertIn("someone", froms, "a wizinvis giver is never named")
        self.assertIn("the floor", [r[12] for r in got if r[6] == str(BAG)], got)
        self.assertNotIn("Zacthidden", " ".join("\t".join(r) for r in mine))
        # Creation writes the usual rows; once wizinvis, nothing: not the
        # dagger loaded and given, not a command.
        self.assertFalse([r for r in hidden_rows if str(DAGGER) in r
                          or (r[1] == "cmd" and r[10] in ("wizinvis", "scroll", "load", "give"))],
                         "wizinvis staff write no rows")
        level = [r for r in mine if r[1] == "level"]
        self.assertTrue(level, kinds)
        self.assertEqual(level[-1][7], "12")
        self.assertEqual(level[-1][12], "advance")
        area = [r for r in mine if r[1] == "area"]
        self.assertTrue(any(r[7].endswith("ztestfix.are") for r in area), area)
        achieved = [r for r in mine if r[1] == "achieved"]
        self.assertTrue(achieved, kinds)


if __name__ == "__main__":
    unittest.main()
