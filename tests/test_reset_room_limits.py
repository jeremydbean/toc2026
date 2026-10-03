"""A room must not hoard mobiles that other rooms lost.

ROM's 'M' reset limit caps a mobile vnum across the whole world, not within a
room, and reset_area never clears survivors before repopulating. At boot the
world sits at exactly that cap, so nothing can accumulate until mobiles start
dying. Once they do, the freed headroom is handed out in reset order, which is
room-vnum order: before fix_reset_room_limits the earliest rooms took the
refills whether or not they were already full, so they grew past what the
builder wrote while the rooms that actually lost mobiles stayed empty.

This reproduces that directly -- clear a late room, force a reset, and watch
an early room -- through the immortal GOTO/PURGE/REPOP commands. Every
character here is created by the test and discarded with the throwaway tree.
"""

from __future__ import annotations

import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)


SKIP = skip_reason()

# area/hyrule.are stocks these rooms with mobile 32353, the peahat built for
# the Level 4 band (scripts/build_hyrule_area.py generates one record per
# enemy kind per band, so every room drained here must sit in the same
# band as the watched one). Its world-wide cap equals the total the area
# asks for, so every freed slot is contested on the next reset.
WATCHED_ROOM = 30201          # earliest peahat room, asks for two
WATCHED_INTENT = 2
DRAINED_ROOMS = (30286, 30309, 30311)   # later rooms, six peahats between them
# The peahat's room line, from data/hyrule_mob_prose.json.
MOB_LONG_DESC = "A peahat whirls through the air on spinning petals."

IMMORTAL_LEVEL = 70
PASSWORD = "Ziprepoppw"
REPOPS = 3


@unittest.skipIf(SKIP is not None, SKIP or "")
class ResetRoomLimitTests(unittest.TestCase):
    def test_an_early_room_does_not_hoard_refills(self) -> None:
        name = "Ziprepop"

        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            # GOTO/PURGE/REPOP are immortal commands.
            patch_player_file(
                mud, name, Levl=IMMORTAL_LEVEL, Room=WATCHED_ROOM
            )

            with mud.connect(timeout=120) as client:
                login(client, name, PASSWORD)

                start = self.count_mobs(client)
                self.assertEqual(
                    start,
                    WATCHED_INTENT,
                    "the watched room did not start at its stocked count",
                )

                # Kill off peahats elsewhere so the world drops below its cap.
                for vnum in DRAINED_ROOMS:
                    client.send(f"goto {vnum}")
                    client.drain(0.8)
                    client.send("purge")
                    client.drain(0.8)

                client.send(f"goto {WATCHED_ROOM}")
                client.drain(0.8)

                for _ in range(REPOPS):
                    client.send("repop")
                    client.expect("has been repopulated", timeout=60)

                after = self.count_mobs(client)

        # Resets top a room up; they never stack it. Wandering can only lower
        # this count, so an over-count is unambiguous.
        self.assertLessEqual(
            after,
            WATCHED_INTENT,
            f"room {WATCHED_ROOM} hoarded {after} peahats after {REPOPS} "
            f"resets; the area asks for {WATCHED_INTENT}",
        )

    def count_mobs(self, client) -> int:
        mark = len(client.transcript)
        client.send("look")
        client.drain(1.2)
        return client.transcript[mark:].count(MOB_LONG_DESC)


if __name__ == "__main__":
    unittest.main()
