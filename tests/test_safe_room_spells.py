"""A protected room refuses a hostile spell exactly as it refuses a blow.

Audit 2026-10-21: is_safe_spell had its ROOM_SAFE and Temple/altar tests
commented out, so in the Temple MURDER was refused ("Not in the temple my
dear") while CAST POISON landed, and the poison then ticked hit points
away. is_safe asks both rooms; is_safe_spell now asks the same.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zsafe1pass"
FIELD = 4202            # east of the Temple: not safe
TEMPLE = 4207
ALTAR = 4208
WORKER = 12002          # sentinel, not wimpy


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class SafeRoomSpellSourceTests(unittest.TestCase):
    def test_the_room_tests_are_live_code(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        body = fight[fight.index("bool is_safe_spell(CHAR_DATA *ch, CHAR_DATA *victim, bool area )"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("ch->in_room->vnum == ROOM_VNUM_TEMPLE", body)
        self.assertIn("IS_SET(victim->in_room->room_flags, ROOM_SAFE)", body)
        self.assertNotIn("/* no fighting in safe rooms", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SafeRoomSpellLiveTests(unittest.TestCase):
    def test_poison_is_refused_where_blows_are(self) -> None:
        with LiveMud() as mud:
            for name in ("Zwitch", "Zwarden"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwitch", Levl=50, Room=TEMPLE)
            patch_player_file(mud, "Zwarden", Levl=70, Room=TEMPLE)

            with mud.connect(timeout=120) as witch, mud.connect(timeout=120) as warden:
                login(witch, "Zwitch", PASSWORD)
                login(warden, "Zwarden", PASSWORD)
                run(warden, "set skill zwitch poison 100")
                run(warden, "set char zwitch mana 30000")

                def poisoned() -> bool:
                    return "Spell: 'poison'" in run(warden, "stat mob worker", 1.4)

                def try_poison(room: int) -> str:
                    run(warden, "goto %d" % room)
                    run(warden, "transfer zwitch %d" % room)
                    witch.drain(0.5)
                    run(warden, "load mob %d" % WORKER)
                    said = ""
                    # A save is a miss, not a refusal: try again. Landing is
                    # read from the caster's own screen ("looks very ill"),
                    # not from STAT afterwards -- a poisoned level 2 worker
                    # fights back and a level 50 kills it inside the drain
                    # window, which left nothing to STAT and failed CI.
                    for _ in range(8):
                        said += run(witch, "cast poison worker", 3.5)
                        if "I don't think so" in said or "looks very ill" in said:
                            break
                    return said

                for room in (TEMPLE, ALTAR):
                    said = try_poison(room)
                    self.assertIn("I don't think so", said, room)
                    self.assertFalse(poisoned(), room)
                    run(warden, "purge", 1.0)

                # An ordinary room flagged safe, and the same room unflagged
                # as the control: there the spell must still land.
                run(warden, "set room %d flags +safe" % FIELD)
                said = try_poison(FIELD)
                self.assertIn("I don't think so", said)
                self.assertFalse(poisoned())
                run(warden, "purge", 1.0)
                run(warden, "set room %d flags -safe" % FIELD)
                said = try_poison(FIELD)
                self.assertNotIn("I don't think so", said)
                self.assertIn("looks very ill", said)


if __name__ == "__main__":
    unittest.main()
