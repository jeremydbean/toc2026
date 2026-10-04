"""Rare-state bugs found in a sweep on 2026-10-04, and what keeps them fixed.

* STASH LINK sent the typed name straight into a file path: STASH LINK
  ../area/area.lst loaded that file as a character and saved a player
  file over it. Offline loads go through offline_player_load now, which
  takes only a legal player name.
* A stash TAKE from a linked partner who was online but unseen loaded a
  second copy from disk and duplicated the item; player_in_game finds a
  character by name whatever anyone can see.
* A saved pet was never put back in the world at login.
* A mobile corpse and a rot-death item inside it expiring on one tick were
  extracted twice.
* WEAR ALL went on equipping a dead character's corpse after an action
  item killed them.
* RIDE set ch->pet over a bought pet; any follower dying cleared the pet.
* An empty haven pocket expiring left a void return pointing at it.
"""
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def body(path: str, start: str) -> str:
    text = (SRC / path).read_text(encoding="latin-1")
    text = text[text.index(start):]
    return text[:text.index("\n}\n")]


class SourceTests(unittest.TestCase):
    def test_offline_loads_go_through_the_one_door(self) -> None:
        loader = body("save.c", "CHAR_DATA *offline_player_load(")
        self.assertIn("isalpha", loader)
        self.assertIn("player_in_game( proper, NULL )", loader)
        self.assertIn("free_char( d->character )", loader)
        for path in ("act_obj.c", "act_wiz.c"):
            text = (SRC / path).read_text(encoding="latin-1")
            self.assertNotIn("load_char_obj( &offline_desc", text, path)
            self.assertNotIn("load_char_obj(&d, arg", text, path)

    def test_a_pet_comes_back_and_a_phantom_mount_does_not(self) -> None:
        comm = (SRC / "comm.c").read_text(encoding="latin-1")
        self.assertIn("char_to_room( ch->pet, ch->in_room );", comm)
        self.assertIn("ch->pcdata->mounted = false;", comm)
        save = (SRC / "save.c").read_text(encoding="latin-1")
        self.assertIn("ch->pet->in_room == NULL", save)

    def test_queued_objects_leave_their_containers_first(self) -> None:
        update = body("update.c", "void obj_update(")
        self.assertIn("obj_from_obj( extract_list[i] )", update)
        self.assertIn("obj->timer = 1;", update)

    def test_wear_all_stops_when_the_pack_is_no_longer_yours(self) -> None:
        wear = body("act_obj.c", "void do_wear(")
        self.assertIn("obj_next->carried_by != ch", wear)

    def test_one_companion_and_only_the_pet_clears_the_pet(self) -> None:
        ride = body("act_move.c", "void do_ride(")
        self.assertIn("ch->pet != NULL && ch->pet != victim", ride)
        fight = (SRC / "fight.c").read_text(encoding="latin-1")
        self.assertIn("victim->master->pet == victim", fight)

    def test_the_void_return_is_repointed_before_a_pocket_is_freed(self) -> None:
        update = (SRC / "update.c").read_text(encoding="latin-1")
        start = update.index("ROOM_INDEX_DATA *expiring_room = raf->room;")
        chunk = update[start:start + 2500]
        self.assertLess(chunk.index("wch->was_in_room = way_out"),
                        chunk.index("extract_room(expiring_room)"))


class CombatAndMovementSourceTests(unittest.TestCase):
    def test_a_charmie_fights_a_player_only_where_its_master_could(self) -> None:
        safe = body("fight.c", "bool is_safe(CHAR_DATA *ch, CHAR_DATA *victim )")
        self.assertIn("is_safe( ch->master, victim )", safe)

    def test_one_book_for_player_kills(self) -> None:
        fight = (SRC / "fight.c").read_text(encoding="latin-1")
        self.assertEqual(fight.count("record_player_kill( ch, victim );"), 2)
        self.assertNotIn("ch->pcdata->pkills_given += 1;\n\t\tupdate_pkills(ch);", fight)

    def test_death_puts_back_race_and_gear_bits_and_frees_the_mount(self) -> None:
        fight = (SRC / "fight.c").read_text(encoding="latin-1")
        self.assertEqual(fight.count("reapply_innate_affects( victim );"), 4)
        self.assertGreaterEqual(fight.count("release_mount( victim );"), 3)

    def test_a_safe_room_ends_a_fight(self) -> None:
        violence = body("fight.c", "void violence_update(")
        self.assertIn("ROOM_SAFE", violence)

    def test_a_missing_mount_is_let_go_and_stasis_holds_a_rider(self) -> None:
        move = body("act_move.c", "void move_char(")
        self.assertLess(move.index("release_mount( ch )"), move.index("do_riding(ch,door"))
        self.assertLess(move.index("PLR_STASIS"), move.index("do_riding(ch,door"))

    def test_portals_and_random_rooms_keep_room_rules(self) -> None:
        enter = body("act_move.c", "void do_enter(")
        self.assertIn("travel_spell_refuses( ch, to_room )", enter)
        picker = body("act_move.c", "ROOM_INDEX_DATA *random_travel_room(")
        self.assertIn("random_scatter_room( NULL )", picker)
        self.assertIn("travel_spell_refuses( ch, room )", picker)
        update = (SRC / "update.c").read_text(encoding="latin-1")
        self.assertIn("random_travel_room( vch, true )", update)
        self.assertNotIn("pRoomTport = get_room_index( number_range", update)

    def test_followers_are_gathered_before_anyone_moves(self) -> None:
        move = body("act_move.c", "void move_char(")
        self.assertIn("followers[nfollow++] = fch;", move)


try:
    from live_mud import LiveMud, create_character, skip_reason
    LIVE_SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover
    LIVE_SKIP = str(exc)

PW = "Zedgecase1"


@unittest.skipIf(LIVE_SKIP is not None, LIVE_SKIP or "")
class LiveTests(unittest.TestCase):
    def test_stash_link_cannot_reach_outside_the_player_directory(self) -> None:
        with LiveMud() as mud:
            area_dir = mud.player_dir.parent / "area"
            target = area_dir / "area.lst"
            before = target.read_bytes()
            with mud.connect(timeout=120) as client:
                create_character(client, "Zlinker", PW)
                for name in ("../area/area.lst", "..", "Zl1nk", "a.b"):
                    client.send(f"stash link {name}")
                    client.drain(1.5)
                client.send("say still here")
                client.drain(1.5)
                seen = client.transcript
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertIn("still here", seen)
            self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
