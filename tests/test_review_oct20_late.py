"""What a second review of 2026-10-20's work found, pinned in the source.

Each test names the scenario that went wrong; the behaviour is played
live in the feature's own module where a live test is cheap.
"""
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


class UseAndFollow(unittest.TestCase):
    def test_use_portal_is_not_a_free_flee(self) -> None:
        use = body("src/act_obj.c", "void do_use(")
        portal = use[use.index("ITEM_PORTAL"):]
        self.assertLess(portal.index("ch->fighting != NULL"), portal.index("do_enter( ch, arg )"))
        self.assertLess(portal.index("POS_STANDING"), portal.index("do_enter( ch, arg )"))

    def test_use_bomb_bag_is_the_bag(self) -> None:
        use = body("src/act_obj.c", "void do_use(")
        self.assertIn("( obj = get_obj_carry( ch, argument ) ) != NULL", use)

    def test_nobody_follows_the_goblin_or_the_dealer(self) -> None:
        follow = body("src/act_comm.c", "void do_follow(")
        self.assertLess(follow.index("is_unfindable_mob( victim )"), follow.index("add_follower( ch, victim )"))


class TheGoblin(unittest.TestCase):
    def test_a_heal_between_blows_is_undone(self) -> None:
        blow = body("src/goblin.c", "int treasure_goblin_blow(")
        self.assertIn("gob->hit > gob_hp", blow)
        struck = body("src/goblin.c", "void treasure_goblin_struck(")
        self.assertIn("gob_hp = UMIN( gob_hp, gob->hit )", struck)

    def test_a_farslayer_is_one_hard_blow(self) -> None:
        cheat = body("src/goblin.c", "bool treasure_goblin_cheats_death(")
        self.assertLess(cheat.index("gob->hit = gob_hp"), cheat.index("gob->hit -="))

    def test_nothing_holds_him_any_more(self) -> None:
        """Superseded 2026-10-21 (owner): no stun holds him; every landed
        blow sends him running (tests/test_treasure_goblin.py)."""
        dmg = body("src/fight.c", "bool damage(")
        self.assertNotIn("goblin_held", dmg)
        self.assertIn("treasure_goblin_struck( ch, victim );", dmg)

    def test_never_where_a_room_carries_him_or_another_keeper_trades(self) -> None:
        ok = body("src/blackmarket.c", "static bool bm_room_ok(")
        for term in ("ROOM_TELEPORT", "ROOM_RIVER", "pShop != NULL"):
            self.assertIn(term, ok)


class ThePublishedLog(unittest.TestCase):
    """log/ reaches a public repository every five minutes: where the
    dealer or the goblin is now must never be in it."""

    def test_arrivals_and_vanishings_name_no_destination(self) -> None:
        bm = (ROOT / "src" / "blackmarket.c").read_text(encoding="latin-1")
        gob = (ROOT / "src" / "goblin.c").read_text(encoding="latin-1")
        self.assertNotIn('vanished from %s "\n              "to %s', bm)
        self.assertNotIn("vanished from %s to %s", gob)
        self.assertNotIn("called the black market dealer to room", bm)
        self.assertNotIn("called a treasure goblin to room", gob)
        arrive = body("src/blackmarket.c", "bool black_market_arrive(")
        logged = arrive[:arrive.index("log_string( line );")]
        self.assertNotIn("appeared in %s", logged[logged.rindex("snprintf"):])
        spawn = body("src/goblin.c", "bool treasure_goblin_spawn(")
        self.assertIn('log_string( "Treasure goblin: appeared." );', spawn)


class TheDealersGoods(unittest.TestCase):
    def test_seen_in_the_dark(self) -> None:
        see = body("src/handler.c", "bool can_see_obj(")
        self.assertLess(see.index("if ( black_market_holds( obj ) )\n\treturn true;"),
                        see.index("room_is_dark"))

    def test_a_busy_dealer_says_so_before_the_price(self) -> None:
        buy = body("src/act_obj.c", "static bool buy_one( CHAR_DATA *ch, CHAR_DATA *keeper, char *argument )\n{")
        self.assertLess(buy.index("black_market_buy_refuses"), buy.index("has_enough_copper"))


class RestAndDailies(unittest.TestCase):
    def test_a_remort_cannot_carry_a_heros_pool(self) -> None:
        rested = (ROOT / "src" / "rested.c").read_text(encoding="latin-1")
        self.assertIn("rest_xp_clamp( ch );", body("src/rested.c", "int rest_xp_bonus("))
        self.assertIn("rest_xp_clamp( ch );", body("src/rested.c", "void rest_xp_on_login("))
        self.assertNotIn("\"You slept rough", rested, "a crash or an old file is not a choice")

    def test_a_failed_daily_request_leaves_the_cooldown_alone(self) -> None:
        req = body("src/quest.c", "static void quest_daily_request(")
        self.assertIn("ch->nextquest = nextquest;", req)
        self.assertIn("daily_wait_until", req)

    def test_daily_wait_saved_under_d(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        reader = save[save.index("void fread_char("):save.index("void fread_pet(")]
        case_d = reader[reader.index("\tcase 'D':"):reader.index("\tcase 'E':")]
        self.assertIn('"DailyWait"', case_d)

    def test_the_quest_room_is_for_staff_only_over_gmcp(self) -> None:
        gmcp = body("src/gmcp.c", "void gmcp_send_quest(")
        self.assertLess(gmcp.index("IS_TRUSTED( ch, LEVEL_IMMORTAL )"), gmcp.index('\\"num\\"'))


class ThisMorningsChanges(unittest.TestCase):
    def test_hide_refuses_a_fight_before_the_roll(self) -> None:
        hide = body("src/act_move.c", "void do_hide(")
        self.assertLess(hide.index("ch->fighting != NULL"), hide.index("number_percent"))

    def test_practice_gains_at_least_a_point(self) -> None:
        self.assertIn("UMAX( 1, int_app[get_curr_stat(ch,STAT_INT)].learn /",
                      (ROOT / "src" / "act_info.c").read_text(encoding="latin-1"))

    def test_only_the_prayer_names_your_recall_point(self) -> None:
        travel = body("src/act_move.c", "static void recall_travel(")
        self.assertIn("own_prayer\n                  ? \"You are already standing at your recall point", travel)
        self.assertLess(travel.index("ch->in_room == location"), travel.index("do_dismount"))

    def test_bowl_tells_the_bowled(self) -> None:
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertNotIn('"%s picks you up and hurls you into the sky!"', wiz)
        self.assertEqual(wiz.count('"$n picks you up and hurls you into the sky!",ch,NULL,victim,TO_VICT'), 2)

    def test_a_wizinvis_victim_is_not_named_to_the_room(self) -> None:
        act = body("src/comm.c", "void act_new(")
        self.assertIn("type == TO_NOTVICT && vch != NULL && wizinvis_hides( vch, to )", act)

    def test_a_tell_is_capitalised(self) -> None:
        tell = body("src/act_comm.c", "void do_tell(")
        self.assertIn("teller[0] = UPPER( teller[0] );", tell)

    def test_the_keeper_blames_what_it_cannot_see_through(self) -> None:
        keeper = body("src/act_obj.c", "CHAR_DATA *find_keeper(")
        self.assertLess(keeper.index("too dark"), keeper.index("You are invisible"))
        self.assertIn("!IS_AFFECTED(keeper, AFF_DETECT_INVIS)", keeper)


if __name__ == "__main__":
    unittest.main()
