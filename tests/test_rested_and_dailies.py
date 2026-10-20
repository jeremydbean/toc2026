"""Rested experience and daily quests (owner's design, 2026-10-20, after
World of Warcraft's).

Rested: quitting somewhere a body could rest -- a safe or healing room,
the Temple, the pit's altar, your recall point -- banks five percent of a
level per hour away, up to a level and a half, and kills earn double
experience while it lasts. RESTED shows it.

Dailies: AQUEST DAILY REQUEST hands out three quests a day that pay daily
points, kept apart from quest points and spent with AQUEST DAILY BUY
PRACTICE or TRAIN. A daily never touches the streak or the cooldown.
"""
from __future__ import annotations

import pathlib
import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zrested1pass"
TEMPLE = 4207
QUESTMASTER = 2497
FIELD = 2401          # the Oak Tree Square: nobody's bed


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class RestedSourceTests(unittest.TestCase):
    def test_where_they_lie_down_is_judged_before_the_save(self) -> None:
        quit_ = body("src/act_comm.c", "void do_quit(")
        self.assertLess(quit_.index("rest_xp_on_quit( ch );"), quit_.index("save_char_obj( ch );"))
        self.assertIn("rest_xp_on_login( ch );", (ROOT / "src" / "comm.c").read_text(encoding="latin-1"))
        ok = body("src/rested.c", "bool rest_room_ok(")
        for term in ("ROOM_SAFE", "ROOM_HP_REGEN", "ROOM_MANA_REGEN", "ROOM_VNUM_TEMPLE",
                     "ROOM_VNUM_ALTAR", "recall_room( ch )", "ROOM_JAIL"):
            self.assertIn(term, ok)
        self.assertIn("was_in_room", body("src/rested.c", "void rest_xp_on_quit("),
                      "the idle are judged by the room the void took them from")

    def test_the_pool_cannot_overflow_and_a_relog_is_no_rest(self) -> None:
        login_ = body("src/rested.c", "void rest_xp_on_login(")
        self.assertIn("away >= REST_MIN_AWAY", login_)
        self.assertIn("60L * REST_CAP_PERCENT / REST_PERCENT_PER_HOUR", login_,
                      "minutes are capped before they multiply a level's span")
        span = body("src/rested.c", "static long rest_level_span(")
        self.assertIn("ch->level - LEVEL_HERO", span, "a hero's level, not the one after")

    def test_kills_draw_on_the_pool(self) -> None:
        source = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertIn("rest_xp_bonus( gch, xp )", source)
        self.assertIn("gain_exp( gch, xp + rested )", source)

    def test_saved_under_the_right_letters(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        reader = save[save.index("void fread_char("):save.index("void fread_pet(")]
        case_r = reader[reader.index("\tcase 'R':"):reader.index("\tcase 'S':")]
        case_d = reader[reader.index("\tcase 'D':"):reader.index("\tcase 'E':")]
        self.assertIn('"Rested"', case_r)
        self.assertIn('"Daily"', case_d)


class DailySourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.quest = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")

    def test_every_clear_of_a_contract_clears_the_daily_too(self) -> None:
        lines = self.quest.split("\n")
        for i, line in enumerate(lines):
            if "ch->questemergency = false" in line:
                self.assertIn("questdaily", lines[i + 1], "quest.c:%d" % (i + 1))

    def test_a_daily_keeps_its_clock_while_the_cooldown_runs(self) -> None:
        update = body("src/quest.c", "void quest_update(")
        self.assertNotIn("else if (IS_SET(ch->act,PLR_QUESTOR))", update)

    def test_a_lost_daily_costs_neither_streak_nor_cooldown(self) -> None:
        logout = body("src/quest.c", "void quest_handle_logout(")
        self.assertLess(logout.index("if ( daily )"), logout.index("ch->queststreak = 0"))
        self.assertIn("if (!daily)\n\t\tch->queststreak = 0;", self.quest)

    def test_a_perfect_month_buys_one_train(self) -> None:
        """Owner, 2026-10-20: every daily, every day, for a month is about
        a train. Thirty days of full sets from a standing start, with the
        streak bonus, against the price."""
        bonus = {int(m.group(1)): int(m.group(2)) for m in re.finditer(
            r"if \( streak >= (\d+) \)\s+return (\d+);", self.quest)}
        per = int(re.search(r"#define DAILY_POINTS_PER_QUEST\s+(\d+)", self.quest).group(1))
        setb = int(re.search(r"#define DAILY_SET_BONUS\s+(\d+)", self.quest).group(1))
        train = int(re.search(r"#define DAILY_TRAIN_COST\s+(\d+)", self.quest).group(1))
        month = sum(3 * per + setb + max([b for d, b in bonus.items() if day >= d] or [0])
                    for day in range(1, 31))
        self.assertGreaterEqual(month, train)
        self.assertLess(month, 2 * train, "about one train, not two")

    def test_a_daily_out_at_midnight_belongs_to_the_day_it_was_taken(self) -> None:
        roll = body("src/quest.c", "static void quest_daily_rollover(")
        self.assertLess(roll.index("if ( ch->questdaily )"), roll.index("daily_done = 0"))
        daily = body("src/quest.c", "static void complete_daily_quest(")
        self.assertIn("long set_day = ch->pcdata->daily_day;", daily)
        self.assertIn("daily_last_full = set_day;", daily)

    def test_no_quest_for_a_mobile_nobody_may_fight(self) -> None:
        pick = body("src/quest.c", "static bool automatic_quest_target_is_suitable(")
        for term in ("is_protected_npc(victim)", "ROOM_VNUM_TEMPLE", "ROOM_VNUM_ALTAR",
                     "MOB_VNUM_SPELLUP", "is_unfindable_mob(victim)"):
            self.assertIn(term, pick)

    def test_paid_in_daily_points_not_quest_points(self) -> None:
        daily = body("src/quest.c", "static void complete_daily_quest(")
        self.assertIn("daily_points += points", daily)
        self.assertNotIn("questgamble_pts", daily)
        self.assertNotIn("nextquest", daily)
        self.assertNotIn("queststreak", daily)


@unittest.skipIf(SKIP is not None, SKIP or "")
class RestedAndDailyLiveTests(unittest.TestCase):
    def test_rest_banked_shown_and_daily_points_spent(self) -> None:
        with LiveMud() as mud:
            for name in ("Zrester", "Zrough"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            ten_hours_ago = int(time.time()) - 10 * 3600
            # Quit at the Temple ten hours ago: rested. Quit in the square: not.
            patch_player_file(mud, "Zrester", Levl=20, Room=QUESTMASTER,
                              LastOut=ten_hours_ago, Rested="0 1", Daily="170 0 0 0 0")
            patch_player_file(mud, "Zrough", Levl=20, Room=FIELD,
                              LastOut=ten_hours_ago, Rested="0 0")

            with mud.connect(timeout=120) as client:
                greeting = login(client, "Zrester", PASSWORD) or ""
                client.drain(1.5)
                self.assertIn("You feel well rested", client.transcript)
                rested = run(client, "rested", 1.4)
                self.assertRegex(rested, r"You are rested: .* \(50% of a level\)")
                self.assertIn("would not let you rest", rested,
                              "the questmaster's room is no bed")

                # Daily quests: status, one taken, points spent.
                run(client, "scroll 0", 1.0)
                status = run(client, "aquest daily", 1.4)
                self.assertIn("Done today:", status)
                self.assertRegex(status, r"Daily points: \S*170")
                self.assertRegex(status, r"Daily streak: \S*0\S* days")
                self.assertIn("That costs 320 daily points, and you have 170.",
                              run(client, "aquest daily buy train 2", 1.4))
                self.assertIn("You trade 160 daily points for 1 train. 10 points left.",
                              run(client, "aquest daily buy train", 1.4))
                self.assertIn("Buy how many?", run(client, "aquest daily buy practice -3", 1.4))
                reply = run(client, "aquest daily request", 2.5)
                self.assertIn("daily task 1 of 3", reply)
                self.assertIn("Finish the quest you have first",
                              run(client, "aquest daily request", 2.0))
                # Abandoning a daily breaks no streak and sets no cooldown.
                run(client, "aquest abort", 2.0)
                self.assertNotIn("Return in", run(client, "aquest request", 2.5))
                client.send("quit")
                client.wait_closed()
            saved = (mud.player_dir / "Zrester").read_text(encoding="latin-1")
            self.assertRegex(saved, r"(?m)^Daily 10 \d+ 0 0 0$")
            self.assertIn("daily-train", saved, "Earned the Hard Way")
            self.assertIn("well-rested", saved)

            with mud.connect(timeout=120) as client:
                login(client, "Zrough", PASSWORD)
                client.drain(1.5)
                self.assertIn("slept rough", client.transcript)
                self.assertIn("You are not rested.", run(client, "rested", 1.4))


if __name__ == "__main__":
    unittest.main()
