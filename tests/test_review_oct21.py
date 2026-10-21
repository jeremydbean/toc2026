"""What the review of 2026-10-21 and that day's player logs found.

- The goblin and the dealer were sent to rooms no walker can follow into:
  a cloud, the Dragon Sea, a whirlpool, under the sea.
- The quest cooldown counted down only while you were logged in.
- REPAIR took one item; Trentlin mended ten one at a time.
- The healer charged for an uncurse with nothing to lift, and REMOVE
  CURSE stripped NODROP from a Triforce piece, which is bound on purpose.
- A staff-loaded goblin's flight reset the real goblin's chase clocks;
  a DailyWait from a bad clock was not capped; the shopkeeper blamed the
  dark for a shadowmeld; USE BOMB BAG could find the bombs.
"""
from __future__ import annotations

import pathlib
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zreview1pass"


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class ReviewSourceTests(unittest.TestCase):
    def test_no_room_a_walker_cannot_follow_into(self) -> None:
        ok = body("src/blackmarket.c", "static bool bm_room_ok(")
        for sector in ("SECT_AIR", "SECT_WATER_NOSWIM", "SECT_UNDER_WATER"):
            self.assertIn(sector, ok)

    def test_the_cooldown_runs_while_away(self) -> None:
        self.assertIn("quest_login_cooldown( ch );", (ROOT / "src" / "comm.c").read_text(encoding="latin-1"))
        fn = body("src/quest.c", "void quest_login_cooldown(")
        self.assertIn("last_logout", fn)

    def test_repair_all_charges_once_an_item(self) -> None:
        source = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        mend = body("src/act_obj.c", "static void repair_mend(")
        self.assertEqual(mend.count("spend_copper("), 1)
        every = body("src/act_obj.c", "static void repair_all(")
        self.assertNotIn("spend_copper(", every, "repair_mend charges")
        self.assertIn('!str_cmp( argument, "all" )', body("src/act_obj.c", "void do_repair("))
        self.assertIn("repair all", (ROOT / "area" / "commands.are").read_text(encoding="latin-1"))
        self.assertTrue(source)

    def test_bound_hyrule_items_are_not_cursed(self) -> None:
        curse = body("src/magic.c", "void spell_remove_curse(")
        self.assertEqual(curse.count("hyrule_bound_object( obj )"), 2)
        heal = (ROOT / "src" / "misc.c").read_text(encoding="latin-1")
        self.assertIn("remove_curse_has_work( ch )", heal)

    def test_smaller_ones(self) -> None:
        teleport = body("src/goblin.c", "static void gob_teleport(")
        self.assertLess(teleport.index("if ( gob == treasure_goblin )"), teleport.index("gob_chased = false"))
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertIn("UMIN( until, (long) current_time + DAILY_GIVE_UP_WAIT )", save)
        keeper = body("src/act_obj.c", "CHAR_DATA *find_keeper(")
        self.assertLess(keeper.index("AFF2_SHADOWMELD"), keeper.index("too dark"))
        use = body("src/act_obj.c", "void do_use(")
        self.assertIn("( obj = get_obj_carry( ch, argument ) ) != NULL", use)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ReviewLiveTests(unittest.TestCase):
    def test_cooldown_spent_offline_and_a_free_refusal_at_the_healer(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcooler", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            # Quit two hours ago with a 15 minute cooldown left.
            patch_player_file(mud, "Zcooler", Levl=20, Room=4208,
                              LastOut=int(time.time()) - 2 * 3600)
            path = mud.player_dir / "Zcooler"
            text = path.read_text(encoding="latin-1")
            text = text.replace("Exp  ", "QuestNext 15\nExp  ", 1)
            path.write_text(text, encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zcooler", PASSWORD)
                run(client, "scroll 0", 1.0)
                self.assertIn("Ready to quest!", run(client, "aquest time", 1.6))

                # The pit healer: nothing cursed, nothing charged.
                before = run(client, "worth", 1.2)
                reply = run(client, "heal uncurse", 2.0)
                self.assertIn("I see no curse on you", reply)
                self.assertEqual(before.split("\n")[1:2], run(client, "worth", 1.2).split("\n")[1:2])


if __name__ == "__main__":
    unittest.main()
