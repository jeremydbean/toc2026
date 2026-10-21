"""Nobody is stuck at either end of alignment.

From 2026-10-20 every kill moved the slayer away from the victim's
alignment. At -1000 every mobile is more good than you, so every kill
pushed you down and nothing could raise you; 112 characters sat at -1000
and 217 at 1000 when the player-file audit first ran (2026-10-21). A
victim within 500 of you now pulls you toward neutral, Merc's rule, and a
file saved at 1005 by the older unclamped branch loads at 1000.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zalign1pass"
FIELD = 4202            # east of the Temple: not safe
RABBIT = 309


def run(client, command: str, settle: float = 1.6) -> str:
    start = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[start:]


def saved_alignment(mud, name: str) -> int:
    text = (mud.root / "player" / name).read_text(encoding="latin-1")
    return int(re.search(r"(?m)^Alig\s+(-?\d+)", text).group(1))


class AlignmentSourceTests(unittest.TestCase):
    def test_own_kind_pulls_toward_neutral(self) -> None:
        source = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        block = source[source.index("/* do alignment computations */"):
                       source.index("/* calculate exp multiplier */")]
        self.assertIn("change = gch->alignment / 100;", block)
        self.assertIn("if ( align > 500 || align < -500 )", block)

    def test_loader_clamps(self) -> None:
        source = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertIn("ch->alignment = (sh_int) URANGE( -1000, align, 1000 );", source)
        self.assertNotIn('KEY( "Alig",\tch->alignment', source)


@unittest.skipIf(SKIP is not None, SKIP or "")
class AlignmentLiveTests(unittest.TestCase):
    def test_both_ends_have_a_way_back(self) -> None:
        with LiveMud() as mud:
            for name in ("Zslayer", "Zwarden"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zslayer", Levl=50, Room=FIELD, Alig=-1000)
            patch_player_file(mud, "Zwarden", Levl=70, Room=FIELD)

            with mud.connect(timeout=120) as slayer, mud.connect(timeout=120) as warden:
                login(slayer, "Zslayer", PASSWORD)
                login(warden, "Zwarden", PASSWORD)
                run(slayer, "damagenumbers", 1.0)

                # At -1000, an evil rabbit within 500 of you raises you.
                run(warden, "load mob %d" % RABBIT, 1.0)
                run(warden, "set mob rabbit level 1", 1.0)
                run(warden, "set mob rabbit align -800", 1.0)
                reply = run(slayer, "kill rabbit", 6.0)
                self.assertIn("Your alignment has risen by 10.", reply)

                # At 1000, a saintly rabbit lowers you.
                run(warden, "set char zslayer align 1000", 1.0)
                run(warden, "load mob %d" % RABBIT, 1.0)
                run(warden, "set mob rabbit level 1", 1.0)
                run(warden, "set mob rabbit align 800", 1.0)
                reply = run(slayer, "kill rabbit", 6.0)
                self.assertIn("Your alignment has lowered by 10.", reply)

                # The far side still pushes you out, and still stops at the end.
                run(warden, "load mob %d" % RABBIT, 1.0)
                run(warden, "set mob rabbit level 1", 1.0)
                run(warden, "set mob rabbit align -1000", 1.0)
                reply = run(slayer, "kill rabbit", 6.0)
                self.assertIn("Your alignment has risen by 10.", reply)

                slayer.send("quit")
                self.assertTrue(slayer.wait_closed())
            self.assertEqual(saved_alignment(mud, "Zslayer"), 1000)

            # A file left at 1005 by the old branch loads clamped.
            patch_player_file(mud, "Zslayer", Alig=1005)
            with mud.connect(timeout=120) as slayer:
                login(slayer, "Zslayer", PASSWORD)
                slayer.drain(1.0)
                slayer.send("quit")
                self.assertTrue(slayer.wait_closed())
            self.assertEqual(saved_alignment(mud, "Zslayer"), 1000)


if __name__ == "__main__":
    unittest.main()
