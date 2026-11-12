"""No pointer outlives what it points at (stale-pointer audit, 2026-11-11).

Characters, objects and descriptors are freed now (a pass after their
extraction), not recycled through ROM's pools, so a pointer left behind
reads freed memory. The audit found five; each is pinned here.

1. A hunting mobile kept pointing at a player who left the game: the
   extract_char sweep now stops any hunt or TRACK aimed at the one leaving.
2. A player's own TRACK target was never cleared: do_stop_hunting clears a
   pointer the hunter list does not hold.
3. A switched immortal's body could be idle-purged under the descriptor's
   `original`: the idle purge skips it, and extract_char clears `original`.
4. A bottled mobile and its bottle pointed at each other after either went:
   both sides are cleared, and a bottle leaving with nowhere to open takes
   its mobile with it.
5. A corpse staff retyped was never forgotten: corpse tracks match by
   pointer alone. The relic globals are cleared when their object goes.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_FLOOR, create_character, login,
                      patch_player_file, place_sparring_guard, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zstalepass11"


def body(path: str, start: str) -> str:
    text = (ROOT / path).read_text(encoding="latin-1")
    return text.split(start, 1)[1].split("\n}\n", 1)[0]


class StalePointerSourceTests(unittest.TestCase):
    def test_extract_char_sweeps_hunters_and_switched_descriptors(self) -> None:
        extract = body("src/handler.c", "void extract_char( CHAR_DATA *ch, bool fPull )")
        self.assertIn("if ( wch->hunting == ch )", extract)
        self.assertIn('do_stop_hunting( wch, "the prey is gone" );', extract)
        self.assertIn("if ( d->original == ch )", extract)
        self.assertIn("ch->in_object->trapped = NULL;", extract)

    def test_stop_hunting_clears_a_trackers_pointer(self) -> None:
        stop = body("src/hunt.c", "void do_stop_hunting( CHAR_DATA *ch, char *arg)")
        self.assertIn("ch->hunting = NULL;", stop)
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertNotIn("->hunting->name);", fight)

    def test_the_idle_purge_spares_a_switched_body(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        self.assertIn("!body_is_switched_from( ch )", update)

    def test_a_bottle_with_nowhere_to_open_takes_its_mobile(self) -> None:
        # Moved into captive_dispose (review, 2026-11-12), which every
        # extraction calls and char_from_obj falls back on.
        release = body("src/handler.c", "void char_from_obj( OBJ_DATA *obj )")
        self.assertIn("captive_dispose( obj );", release)
        dispose = body("src/handler.c", "void captive_dispose( OBJ_DATA *obj )")
        self.assertIn("extract_char( mob, true );", dispose)

    def test_corpse_tracks_and_relics(self) -> None:
        find = body("src/corpses.c", "static int track_find( const OBJ_DATA *corpse )")
        self.assertNotIn("ITEM_CORPSE_PC", find)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        self.assertEqual(handler.count("if ( obj == RELIC_1 ) RELIC_1 = NULL;"), 2)


@unittest.skipIf(SKIP is not None, SKIP or "")
class StalePointerLiveTests(unittest.TestCase):
    def test_a_tracker_forgets_a_mobile_that_is_gone(self) -> None:
        """TRACK leaves the tracker pointing at its prey; once the prey is
        extracted, TRACK alone must not name it (it read freed memory)."""
        with LiveMud(fixtures=True) as mud:
            for name, level, room in (("Zstalestaff", 70, SPARRING_FLOOR),
                                      ("Zstaleprey", 20, 32701)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=room)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hunter:
                login(staff, "Zstalestaff", PW)
                login(hunter, "Zstaleprey", PW)
                for client in (staff, hunter):
                    client.sync("scroll 0")
                staff.must("set skill zstaleprey track 100", "")
                place_sparring_guard(staff, "Zstalestaff", SPARRING_FLOOR)
                hunter.sync("track sparring", timeout=60)
                staff.sync("purge sparring", timeout=60)
                self.assertNotIn("sparring guard", staff.sync("look", timeout=60).lower())
                reply = hunter.sync("track", timeout=60)
                self.assertIn("Whom are you trying to track?", reply)
                self.assertNotIn("no longer tracking", reply)
                for client in (hunter, staff):
                    client.send("quit")
                    client.wait_closed()

if __name__ == "__main__":
    unittest.main()
