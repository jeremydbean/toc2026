"""The lesser holes the Hyrule audits of 2026-11-10 found.

- A shutter into a guardian's chamber opened before the chamber's tool
  gate was asked, so a player turned away left it standing open.
- SHOOT through a doorway wounded a guardian from outside its chamber and
  broke the fight off, so it never answered.
- A fire or frost shield's reflection brought an unshrunk Digdogger to one
  hit point, and a poison tick finished it, with no Recorder: hit points
  that come off outside a blow now ask hyrule_shrugs_off.
- A reset's random door trap took PICKPROOF off a small-key door, and a
  teleport trap carried a player out of a no-recall dungeon: Hyrule's
  doors are never trapped at random.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zfollowpass1"
APPROACH = 30432        # Level 2: the shutter north into Dodongo's lair


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


class FollowupSourceTests(unittest.TestCase):
    def test_the_shutter_asks_the_gate_first(self) -> None:
        move = source("act_move.c")
        block = move.split("open_hyrule_shutter( in_room, pexit, door );", 1)[0][-1100:]
        self.assertIn("hyrule_gate_refuses( ch, in_room, pexit->u1.to_room )", block)

    def test_no_shot_through_a_doorway_at_a_hyrule_creature(self) -> None:
        fight = source("fight.c")
        shoot = fight.split("void do_shoot(", 1)[1].split("\nvoid ", 1)[0]
        refuse = shoot.index("hyrule_native( victim )")
        self.assertLess(shoot.index("You cannot shoot at players from another room"), refuse)
        self.assertLess(refuse, shoot.index("is_safe( ch, victim )"))

    def test_harm_outside_a_blow_asks_the_creature(self) -> None:
        hyrule = source("hyrule.c")
        shrugs = hyrule.split("bool hyrule_shrugs_off( CHAR_DATA *victim )", 1)[1].split("\n}\n", 1)[0]
        for rule in ("hyrule_enemy_is_invincible( victim )",
                     "hyrule_patra_eyes_left( victim ) > 0",
                     "victim->hyrule_state != HYRULE_DIGDOGGER_SHRUNK"):
            self.assertIn(rule, shrugs)
        fight = source("fight.c")
        reflect = fight.split("dam1 = apply_hyrule_relic_damage_reduction( ch, dam1, dam_type1 );", 1)[1][:200]
        self.assertIn("hyrule_shrugs_off( ch )", reflect)
        update = source("update.c")
        self.assertIn("if ( !hyrule_shrugs_off( ch ) )\n\t\tdamage( ch, ch, dam, gsn_plague,DAM_DISEASE);", update)
        self.assertIn("if ( !hyrule_shrugs_off( ch ) )\n\t            damage( ch, ch, dice(2,4), gsn_poison, DAM_POISON );", update)

    def test_a_digdogger_bounce_is_said_once_a_round(self) -> None:
        """Owner, 2026-11-10: a hasted Master Sword said the bounce and its
        hint nine times a round, with "bites deep" between."""
        hyrule = source("hyrule.c")
        turned = hyrule.split("bool hyrule_blow_turned_aside( CHAR_DATA *ch, CHAR_DATA *victim )", 1)[1]
        turned = turned.split("\n}\n", 1)[0]
        self.assertIn("now - ch->bounce_said_ms < HYRULE_BOUNCE_QUIET_MS", turned)
        self.assertIn("now - ch->bounce_hint_ms >= HYRULE_BOUNCE_HINT_MS", turned)
        self.assertIn("#define HYRULE_BOUNCE_QUIET_MS  2500L", hyrule)
        fight = source("fight.c")
        for stat in ("WEAPON_SHARP", "WEAPON_VORPAL"):
            block = fight.split(f"if ( IS_WEAPON_STAT(wield,{stat})", 1)[1][:120]
            self.assertIn("!hyrule_shrugs_off( victim )", block, stat)

    def test_hyrule_doors_are_never_trapped_at_random(self) -> None:
        db = source("db.c")
        traps = db.split("/* set some random traps */", 1)[1][:900]
        self.assertIn("!IS_HYRULE_ROOM_VNUM(pRoomIndex->vnum)", traps)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShutterLiveTests(unittest.TestCase):
    def test_a_player_turned_away_leaves_the_shutter_shut(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zfollowgod", 70), ("Zfollowhero", 30)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207, AfBy=512)
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as hero:
                login(god, "Zfollowgod", PW)
                login(hero, "Zfollowhero", PW)
                god.must(f"goto {APPROACH}", "")
                god.sync("purge")            # the room's foes: its shutters may open
                god.must("goto 4207", "")
                god.must(f"transfer zfollowhero {APPROACH}", "")
                unlock = hero.sync("unlock north", timeout=60)
                refused = hero.sync("north", timeout=60)
                after = god.sync(f"at {APPROACH} stat room", timeout=60)
                south = hero.sync("south", timeout=60)
                hero.send("quit")
                god.send("quit")
        # A shutter has no lock: UNLOCK says so rather than "You lack the key."
        # (2026-11-12: a player tried keys on this very shutter).
        self.assertIn("The shutter has no lock", unlock, unlock)
        self.assertNotIn("lack the key", unlock, unlock)
        self.assertIn("boomerang", refused.lower(), refused)
        self.assertNotIn("opens now that the chamber is clear", refused, refused)
        # Another shutter, with no gate behind it, still opens for a cleared room.
        self.assertIn("opens now that the chamber is clear", south, south)


if __name__ == "__main__":
    unittest.main()
