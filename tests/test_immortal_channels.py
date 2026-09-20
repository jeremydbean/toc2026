"""The immortal channels carry messages.

IMMTALK, GODTALK, HERO, INFO, LEVELING, CASTLE and CGOS all sat in the
command table with help entries describing them and a COMM_ flag reserved
for each, and every one answered "That command is not available." The
IMMTALK help said so itself in its last paragraph.
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

PASSWORD = "Zchanone1"


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def staff(mud: LiveMud, name: str, level: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=level)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ImmortalChannelTests(unittest.TestCase):
    def test_immtalk_reaches_another_immortal(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zchanone", 70)
            staff(mud, "Zchantwo", 65)

            with mud.connect(timeout=120) as listener:
                login(listener, "Zchantwo", PASSWORD)
                listener.drain(1.0)

                with mud.connect(timeout=120) as talker:
                    login(talker, "Zchanone", PASSWORD)
                    said = run(talker, "immtalk world still turning", settle=3.0)

                    self.assertNotIn("not available", said.lower(), said)
                    self.assertIn("world still turning", said,
                                  f"the sender should see their own line:\n{said}")

                    listener.drain(2.0)

                heard = listener.transcript

            self.assertIn("world still turning", heard,
                          f"another immortal should hear it:\n{heard[-600:]}")
            self.assertIn("Zchanone", heard,
                          "immtalk should name the sender")

    def test_a_mortal_does_not_hear_immtalk(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zchanimm", 70)
            with mud.connect(timeout=120) as client:
                create_character(client, "Zchanmort", PASSWORD)
                client.send("quit")
                client.wait_closed()

            with mud.connect(timeout=120) as mortal:
                login(mortal, "Zchanmort", PASSWORD)
                mortal.drain(1.0)
                mark = len(mortal.transcript)

                with mud.connect(timeout=120) as imm:
                    login(imm, "Zchanimm", PASSWORD)
                    run(imm, "immtalk staff only please", settle=3.0)
                    mortal.drain(2.0)

                self.assertNotIn("staff only please", mortal.transcript[mark:],
                                 "immtalk must not leak to mortals")

    def test_toggling_and_info(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zchanthree", 70)

            with mud.connect(timeout=120) as client:
                login(client, "Zchanthree", PASSWORD)

                off = run(client, "immtalk", settle=2.0)
                self.assertIn("OFF", off, f"bare immtalk should toggle:\n{off}")
                on = run(client, "immtalk", settle=2.0)
                self.assertIn("ON", on, f"and toggle back:\n{on}")

                # INFO carries announcements; there is nothing to say on it.
                said = run(client, "info hello", settle=2.0)
                self.assertIn("not conversation", said.lower(),
                              f"info should refuse a message:\n{said}")

                for channel in ("godtalk", "hero", "leveling", "castle",
                                "cgos", "roll 2d6", "qui"):
                    out = run(client, channel, settle=1.5)
                    self.assertNotIn("not available", out.lower(),
                                     f"{channel} is still a stub:\n{out}")


if __name__ == "__main__":
    unittest.main()
