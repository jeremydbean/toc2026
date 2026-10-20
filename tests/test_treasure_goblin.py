"""The treasure goblin: always somewhere, never fights, runs from every blow.

Owner's design (2026-10-20), after Diablo's: a goblin with a sack of coin
who is always somewhere in the world and hidden from afar like the black
market dealer. He never strikes back; every landed blow spills platinum
and sends him through a random exit, and a stun holds him. Each blow
takes the same share of his health whoever lands it, so anyone patient
kills him, and never in fewer than twelve flights. A tick without a blow
and he opens a portal and is gone. Dead, he leaves a great deal of
platinum and often a piece of gear for the killer's level. Appearances
and kills go to WIZINFO and the log with the room.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zgoblin1pass"
START = 4202           # east of the Temple: not safe, and he can run from it


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class TreasureGoblinSourceTests(unittest.TestCase):
    def test_every_blow_counts_the_same_and_he_runs_from_it(self) -> None:
        dmg = body("src/fight.c", "bool damage(")
        self.assertIn("ch == victim && is_treasure_goblin( victim )", dmg)
        self.assertLess(dmg.index("treasure_goblin_blow( victim, dam )"),
                        dmg.index("dam_message( ch, victim, dam, dt, immune );"),
                        "the share is taken before the message")
        self.assertIn("treasure_goblin_struck( ch, victim, goblin_held );", dmg)
        source = (ROOT / "src" / "goblin.c").read_text(encoding="latin-1")
        self.assertIn("#define GOBLIN_BLOWS_MIN    13", source, "twelve flights at least")
        self.assertIn("#define GOBLIN_BLOWS_MAX    18", source)
        self.assertIn("black_market_kill_value(", body("src/goblin.c", "void treasure_goblin_slain("))
        self.assertIn("black_market_kill_value(", body("src/goblin.c", "void treasure_goblin_struck("))

    def test_he_never_strikes_back_and_his_hoard_is_in_the_corpse(self) -> None:
        self.assertIn("is_treasure_goblin( ch )", body("src/fight.c", "void multi_hit("))
        kill = body("src/fight.c", "static void raw_kill_internal(")
        self.assertLess(kill.index("treasure_goblin_slain( ch, victim );"),
                        kill.index("make_corpse( victim );"))

    def test_hidden_like_the_dealer(self) -> None:
        see = body("src/handler.c", "bool can_see(")
        self.assertIn("is_unfindable_mob( victim ) && !black_market_sees( ch, victim )", see)
        self.assertIn("is_unfindable_mob( rch ) && counter > 1", body("src/act_info.c", "void do_scan("))
        self.assertIn("is_unfindable_mob( vch )", body("src/oracle.c", "static bool oracle_can_see_char("))
        self.assertIn("treasure_goblin_forget( ch );", body("src/handler.c", "void extract_char("))

    def test_never_where_he_cannot_be_struck(self) -> None:
        ok = body("src/goblin.c", "static bool gob_room_ok(")
        for term in ("black_market_room_ok( room )", "ROOM_SAFE", "ROOM_VNUM_TEMPLE", "ROOM_VNUM_ALTAR"):
            self.assertIn(term, ok)

    def test_a_chase_not_kept_up_ends_in_a_portal(self) -> None:
        update = body("src/goblin.c", "void treasure_goblin_update(")
        self.assertIn("current_time - gob_last_hit >= GOBLIN_ALONE", update)
        self.assertIn("gob_teleport(", update)
        struck = body("src/goblin.c", "void treasure_goblin_struck(")
        self.assertIn("portal collapses", struck)

    def test_too_long_in_one_area_and_he_crosses_the_world(self) -> None:
        source = (ROOT / "src" / "goblin.c").read_text(encoding="latin-1")
        self.assertIn("#define GOBLIN_AREA_MAX     ( 10 * 60 )", source)
        update = body("src/goblin.c", "void treasure_goblin_update(")
        self.assertIn('gob_teleport( gob, gob_area, "too long in one area" )', update)
        self.assertLess(update.index("if ( gob_chased )"), update.index("GOBLIN_AREA_MAX"),
                        "a chase is the portal's business, not this")

    def test_an_instant_kill_is_only_a_hard_blow(self) -> None:
        kill = body("src/fight.c", "static void raw_kill_internal(")
        self.assertLess(kill.index("treasure_goblin_cheats_death( ch, victim )"),
                        kill.index("make_corpse( victim );"))
        cheat = body("src/goblin.c", "bool treasure_goblin_cheats_death(")
        self.assertIn("gob->position == POS_DEAD", cheat, "a death damage() decided stands")
        self.assertIn("treasure_goblin_struck( killer, gob, false );", cheat)
        self.assertIn("is_unfindable_mob( victim )", body("src/fight.c", "void do_backstab("))

    def test_nothing_pins_him_for_long(self) -> None:
        update = body("src/goblin.c", "void treasure_goblin_update(")
        for term in ("AFF2_STUNNED", "AFF_SLEEP", "POS_FIGHTING", "gob->move = gob->max_move"):
            self.assertIn(term, update)
        struck = body("src/goblin.c", "void treasure_goblin_struck(")
        self.assertIn("if ( gob == treasure_goblin )", struck,
                      "a hand-loaded copy does not move the real one's clocks")

    def test_test_worlds_start_without_one(self) -> None:
        live = (ROOT / "tests" / "live_mud.py").read_text(encoding="utf-8")
        self.assertIn('env.setdefault("TOC_NO_GOBLIN", "1")', live)


@unittest.skipIf(SKIP is not None, SKIP or "")
class TreasureGoblinLiveTests(unittest.TestCase):
    def test_chased_down_blow_by_blow(self) -> None:
        with LiveMud(extra_env={"TOC_GOBLIN_STILL": "1"}) as mud:
            for name in ("Zchaser", "Zkeeper"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zchaser", Levl=30, Room=4207)
            patch_player_file(mud, "Zkeeper", Levl=70, Room=START)

            with mud.connect(timeout=120) as chaser, mud.connect(timeout=120) as keeper:
                login(chaser, "Zchaser", PASSWORD)
                login(keeper, "Zkeeper", PASSWORD)
                run(chaser, "scroll 0", 1.0)
                run(keeper, "scroll 0", 1.0)

                self.assertIn("in room %d" % START, run(keeper, "goblin here", 2.0))
                self.assertIn("[WIZINFO] Treasure goblin: appeared in room %d" % START,
                              keeper.transcript)

                # From the Temple next door: SCAN sees him, nothing else does.
                self.assertIn("treasure goblin", run(chaser, "scan", 1.8))
                for cmd in ("where goblin", "consider goblin"):
                    self.assertNotIn("treasure goblin", run(chaser, cmd, 1.6), cmd)

                run(chaser, "east", 1.6)
                self.assertIn("(Rare) A treasure goblin", run(chaser, "look", 1.6))

                # Chase him down: strike, see where he ran, follow.
                fled = 0
                for _ in range(60):
                    status = run(keeper, "goblin", 1.0)
                    if "There is no treasure goblin" in status:
                        break
                    room = int(re.search(r"is in room (\d+)", status).group(1))
                    run(keeper, "transfer zchaser %d" % room, 1.0)
                    reply = run(chaser, "kill goblin", 4.0)
                    fled += reply.count("scurries off") + reply.count("dives through it")
                else:
                    self.fail("the goblin outlived sixty rounds")

                self.assertGreaterEqual(fled, 12, "he ran from every blow but the last")
                self.assertIn("spills from a hole", chaser.transcript)
                keeper.drain(1.0)
                self.assertRegex(keeper.transcript,
                                 r"\[WIZINFO\] Treasure goblin: slain by Zchaser in room \d+")
                # The sack bursts (a new character's autoloot or autosacrifice
                # may already have emptied the corpse).
                self.assertIn("a river of coin pours out", chaser.transcript)

            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("Treasure goblin: slain by Zchaser", log)
