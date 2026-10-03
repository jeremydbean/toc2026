"""Old player bug reports that turned out to be live, and stay fixed.

Each test names the report it answers. Most are read from the source or
the area data, because the behaviour turns on one condition; the few that
are cheap to watch happen in a running game are in OldReportsLiveTests.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason  # noqa: E402
from webadmin.area_parser import AreaParser  # noqa: E402

SKIP = skip_reason()
PASSWORD = "Zreport1"


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1").replace("\r\n", "\n")


def function_body(source: str, signature: str) -> str:
    """The text of one C function, from its signature to its closing brace."""
    start = source.index(signature)
    end = source.index("\n}", start)
    return source[start:end]


def code(text: str) -> str:
    """Comments stripped, so a test cannot pass on a comment."""
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


class SourceTests(unittest.TestCase):
    def test_open_door_direction_picks_that_door(self) -> None:
        """[2550] OPEN DOOR EAST read only "door" and opened the first."""
        move = read("src", "act_move.c")
        body = code(function_body(move, "int find_door( CHAR_DATA *ch, char *argument )"))
        self.assertIn("one_argument( argument, dir_arg )", body)
        self.assertIn("door_direction_word( dir_arg )", body)
        # Every door command hands over the whole argument, not one word.
        self.assertNotIn("find_door( ch, arg )", move)
        self.assertGreaterEqual(move.count("find_door( ch, argument )"), 7)

    def test_teleport_can_be_cast_on_yourself(self) -> None:
        """[2401] TELEPORT is offensive, and offensive refused yourself."""
        body = code(function_body(read("src", "magic.c"), "void do_cast("))
        offensive = body.split("case TAR_CHAR_OFFENSIVE:", 1)[1].split("case TAR_CHAR_DEFENSIVE:", 1)[0]
        self.assertIn("ch == victim && skill_table[sn].spell_fun != spell_teleport", offensive)
        self.assertIn("victim = ch;", offensive)

    def test_a_wand_user_answers_for_the_attack(self) -> None:
        """[4208] Attacked, but the victim got the killer flag."""
        body = code(function_body(read("src", "magic.c"), "void obj_cast_spell("))
        # The check sits ahead of the fighting test now, so a target
        # already busy with something else still flags the user.
        retaliate = body.split("if ( victim == vch )", 1)[1]
        self.assertLess(retaliate.index("check_killer( ch, victim )"),
                        retaliate.index("victim->fighting == NULL"))
        self.assertLess(retaliate.index("check_killer( ch, victim )"),
                        retaliate.index("multi_hit( victim, ch"))

    def test_run_rejects_a_negative_distance_and_a_non_direction(self) -> None:
        """[9531] RUN EAST -1 counted down from -1 and never reached zero."""
        body = code(function_body(read("src", "act_move.c"), "void do_run( CHAR_DATA *ch, char *argument )"))
        self.assertIn("if (distance < 1)", body)
        self.assertIn("Run in which direction?", body)

    def test_running_past_a_wimpy_mobile_is_safe(self) -> None:
        """[4208] Fidos and bruisers -- both wimpy -- jumped runners."""
        move = code(read("src", "act_move.c"))
        block = move.split("if(runner == 1)", 1)[1].split("multi_hit( fch, ch", 1)[0]
        for guard in ("!IS_SET(fch->act, ACT_WIMPY)",
                      "!IS_SET(to_room->room_flags, ROOM_SAFE)",
                      "!IS_AFFECTED(fch, AFF_CALM)",
                      "!IS_AFFECTED(fch, AFF_CHARM)",
                      "IS_AWAKE(fch)"):
            self.assertIn(guard, block)

    def test_a_monk_is_not_handed_a_dagger(self) -> None:
        """[3720] OUTFIT wielded the class table's dagger for a monk."""
        body = code(function_body(read("src", "act_wiz.c"), "void do_outfit ("))
        self.assertIn("ch->class != CLASS_MONK", body)

    def test_quest_targets_skip_unbought_pets_and_closed_guild_halls(self) -> None:
        """[2427] A pet in storage; [2497]/[4206] a mobile inside a guild."""
        quest = code(read("src", "quest.c"))
        suitable = quest.split("static bool automatic_quest_target_is_suitable(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("IS_SET(victim->act, ACT_PET)", suitable)
        self.assertIn("closed[i] == room", suitable)
        self.assertIn("guild_closed_rooms( ch, closed", quest)
        special = code(read("src", "special.c"))
        self.assertIn("int guild_closed_rooms(", special)
        # One table for both: the guard and the quest master cannot disagree.
        self.assertEqual(special.count("gg_table[] ="), 1)

    def test_a_hunter_that_cannot_strike_waits_between_growls(self) -> None:
        """[4210] An imp hunting an invisible player growled every second."""
        body = code(function_body(read("src", "hunt.c"), "void hunt_victim(CHAR_DATA *ch, int ANNOY)"))
        gate = body.split("--ch->wait;", 1)[1].split("ch->wait = 0;", 1)[0]
        self.assertIn("!can_see(ch, ch->hunting)", gate)
        self.assertIn("ROOM_SAFE", gate)

    def test_setting_sex_lifts_change_sex_first(self) -> None:
        """[4209] Base sex flipped back after an immortal fixed it."""
        wiz = code(read("src", "act_wiz.c"))
        block = wiz.split('if ( !str_prefix( arg2, "sex" ) )', 1)[1].split("return;\n    }", 1)[0]
        self.assertLess(block.index('skill_lookup( "change sex" )'),
                        block.index("victim->sex = clamp_sh_int( value )"))
        modify = code(function_body(read("src", "handler.c"), "void affect_modify("))
        apply_sex = modify.split("case APPLY_SEX:", 1)[1].split("case APPLY_CLASS:", 1)[0]
        self.assertIn("ch->pcdata->true_sex", apply_sex)

    def test_flip_reaches_the_social(self) -> None:
        """[4206] The FLIP command shadowed the FLIP social completely."""
        body = code(function_body(read("src", "handler.c"), "void do_flip("))
        self.assertIn("check_social( ch, social, argument )", body)

    def test_pet_prices_name_their_coin(self) -> None:
        """[2562] The pet list printed a bare number of gold coins."""
        special = code(read("src", "special.c"))
        owner = special.split("bool spec_pet_shop_owner(", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("%8d", owner)
        self.assertGreaterEqual(owner.count("pet_price("), 2)

    def test_a_closed_exit_is_named_by_its_keyword(self) -> None:
        """Mud School's gate was listed as a "Closed door"."""
        info = code(read("src", "act_info.c"))
        exits = info.split("void do_exits( CHAR_DATA *ch, char *argument )", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn('"Closed door"', exits)
        self.assertEqual(exits.count("closed_exit_label( pexit"), 2)

    def test_a_tell_to_a_mobile_reads_no_player_data(self) -> None:
        """[4209] AFK and REPLY: PLR_AFK is a mobile's ACT_NOALIGN bit,
        every Mud School monster carries it, and TELL or REPLY to one read
        victim->pcdata -- which a mobile has none of."""
        comm = code(read("src", "act_comm.c"))
        self.assertNotIn("if (IS_SET(victim->act,PLR_AFK))", comm)
        self.assertEqual(comm.count("!IS_NPC(victim) && IS_SET(victim->act,PLR_AFK)"), 2)

    def test_the_caster_answers_even_when_the_target_is_busy(self) -> None:
        """[4208] "I was attacked, but I got the killer flag." check_killer
        sat behind victim->fighting == NULL in both casting paths."""
        magic = code(read("src", "magic.c"))
        self.assertNotIn("victim == vch && victim->fighting == NULL", magic)
        for signature in ("void do_cast(", "void obj_cast_spell("):
            body = code(function_body(magic, signature))
            loop = body.split("if ( victim == vch )", 1)[1]
            self.assertLess(loop.index("check_killer( ch, victim )"),
                            loop.index("victim->fighting == NULL"), signature)

    def test_flee_can_take_every_direction(self) -> None:
        """[4208] "wimpy doesn't work": number_door was & 7, so SE and SW
        were never drawn and a room whose only exits were those said
        PANIC every time."""
        body = code(function_body(read("src", "db.c"), "int number_door( void )"))
        self.assertIn("number_mm() & 15 ) > 9", body)

    def test_arrivals_say_above_and_below(self) -> None:
        """[4207] Arrival lines were "the" plus a direction: going up you
        arrived "from the down"."""
        for name in ("act_move.c", "const.c", "fight.c"):
            source = code(read("src", name))
            self.assertNotIn("from the $t", source, name)
            self.assertNotIn("from the $T", source, name)
        self.assertNotIn("'Ye shall DIE!\"", read("src", "hunt.c"))

    def test_balance_states_the_rate_interest_pays(self) -> None:
        self.assertIn("0.25% per real day", read("src", "act_obj.c"))
        self.assertIn("BANK_INTEREST_DIVISOR  400L", read("src", "update.c"))
        self.assertNotIn("1% interest", read("area", "commands.are"))


class AreaDataTests(unittest.TestCase):
    parser: AreaParser

    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def resets(self, filename: str):
        return self.parser.resets[filename]

    def test_drow_mages_hold_their_wand(self) -> None:
        """[2402] A wand in the wield slot hit for its charges as 10d10."""
        slots = {r.arg3 for r in self.resets("mushroom.are")
                 if r.command == "E" and r.arg1 == 25219}
        self.assertEqual(slots, {17})

    def test_the_mercenary_axe_chops(self) -> None:
        """[25256] The duergar mercenary's axe used the "peck" noun."""
        self.assertEqual(self.parser.objects[25222].values[3], "25")

    def test_marilyn_stays_in_her_shop(self) -> None:
        """[13252] She had no SENTINEL and wandered out of the bird shop."""
        self.assertIn("B", self.parser.mobiles[13211].act_flags)

    def test_the_storage_jar_can_be_picked_up(self) -> None:
        """The room says to pick up a jar; it had no TAKE flag."""
        self.assertIn("A", self.parser.objects[3733].wear_flags)

    def test_keywords_answer_to_what_the_short_description_says(self) -> None:
        robe = self.parser.objects[3742].keywords.split()
        self.assertTrue({"robe", "robes", "newbie"} <= set(robe))
        bracer = self.parser.objects[25109].keywords.split()
        self.assertTrue({"bracer", "bracers", "dark", "metal"} <= set(bracer))
        for name in ("limbo.are", "limbo_halloween.are", "limbo_xmas.are"):
            text = read("area", name)
            record = text.split("\n#57\n", 1)[1].replace("\r", "")
            self.assertTrue(record.startswith("salir "), name)

    def test_the_chess_door_is_locked_from_both_sides(self) -> None:
        """[24301] The mahogany door locked on the inside only, so from the
        hall the vase's silver key was never needed."""
        for room, direction in ((24300, 0), (24301, 2)):
            exit_data = [e for e in self.parser.rooms[room].exits
                         if e.direction == direction][0]
            self.assertEqual(exit_data.key_vnum, 24301, room)
        locks = {(r.arg1, r.arg2, r.arg3) for r in self.resets("chess.are")
                 if r.command == "D"}
        self.assertIn((24300, 0, 2), locks)
        self.assertIn((24301, 2, 2), locks)

    def test_the_halloween_vampires_are_evil(self) -> None:
        """[2436] "The vampires are of good alignment": the elite guards
        4444-4451 were left neutral when the rest turned evil."""
        text = read("area", "limbo_halloween.are")
        mobs = text.split("#MOBILES", 1)[1].split("#OBJECTS", 1)[0]
        for vnum in range(4444, 4452):
            record = mobs.split("\n#%d\n" % vnum, 1)[1].split("\n#", 1)[0]
            self.assertIn("ACGTV DFN -800 M", record, vnum)

    def test_the_mud_school_gate_answers_to_door(self) -> None:
        north = [e for e in self.parser.rooms[3721].exits if e.direction == 0][0]
        self.assertEqual(north.keyword.split(), ["gate", "door"])


@unittest.skipIf(SKIP is not None, SKIP or "")
class OldReportsLiveTests(unittest.TestCase):
    def run_command(self, client, command: str, settle: float = 1.2) -> str:
        mark = len(client.transcript)
        client.send(command)
        client.drain(settle)
        return client.transcript[mark:]

    def test_doors_gates_flip_and_run(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zdoorman", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed(), "character did not leave")
            # An immortal, so Mud School and the two-door hall are both
            # reachable with GOTO and nothing aggressive takes notice.
            patch_player_file(mud, "Zdoorman", Levl=70, Room=4207)

            with mud.connect(timeout=120) as client:
                login(client, "Zdoorman", PASSWORD)

                flip = self.run_command(client, "flip")
                self.assertIn("You flip head over heels", flip, flip)

                self.assertIn("Run in which direction",
                              self.run_command(client, "run sideways"))
                self.assertIn("from 1 to 30",
                              self.run_command(client, "run east -1"))

                # Impy Way (632): a door east and a door west, both "door".
                self.run_command(client, "goto 632")
                self.run_command(client, "close east")
                self.run_command(client, "close west")
                self.run_command(client, "open door west")
                exits = self.run_command(client, "exits")
                self.assertRegex(exits, r"East\s+- \[\d+\] Closed door", exits)
                self.assertNotRegex(exits, r"West\s+- \[\d+\] Closed", exits)

                # TELL to a Mud School monster: they carry the bit PLR_AFK
                # shares, and the AFK branch read a mobile's pcdata.
                self.run_command(client, "goto 3716")
                self.run_command(client, "tell gremlin hello")
                self.assertIn("You have", self.run_command(client, "worth"),
                              "the game survived a tell to a mobile")

                # Mud School's gate is called a gate, and answers to door.
                self.run_command(client, "goto 3721")
                self.run_command(client, "close gate")
                gate = self.run_command(client, "exits")
                self.assertIn("Closed gate", gate, gate)
                opened = self.run_command(client, "open door")
                self.assertNotIn("I see no", opened, opened)

                # A quest request walks every guild hall this character
                # is shut out of before choosing; the game must answer.
                self.run_command(client, "goto 2497")
                asked = self.run_command(client, "aquest request", 2.0)
                self.assertRegex(asked, r"(?i)quest", asked)
                self.assertIn("You have", self.run_command(client, "worth"))


if __name__ == "__main__":
    unittest.main()
