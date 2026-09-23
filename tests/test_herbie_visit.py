"""A summoned Herbie is the same Herbie.

The command used to spawn a throwaway copy at the victim's feet, print four
lines and assign the maximums. The real one flies in from his own room,
talks through a dozen lines and casts restore mana and refresh -- so a
player could tell instantly which one they had got, which is exactly what
giving saints the command was meant to avoid.

Both now go through herbie_visit(), so this checks the summoned visit has
the real one's dialogue, its spell messages, and that Herbie leaves his own
room to do it.
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

PASSWORD = "Zherbone1"

# Lines only the real sequence produces.
REAL_SEQUENCE = [
    "beating of mighty wings",
    "angelic figure with beautiful white wings",
    "bleeding all over the place",
    "A warm feeling fills your body",
    "pulse of energy surges through your body",
    "others to heal ya know",
    "disappears into the sky",
]


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
class HerbieVisitTests(unittest.TestCase):
    def test_a_summoned_visit_reads_like_a_real_one(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zherbimm", 70)
            with mud.connect(timeout=120) as client:
                create_character(client, "Zherbmort", PASSWORD)
                client.send("quit")
                client.wait_closed()

            with mud.connect(timeout=120) as victim:
                login(victim, "Zherbmort", PASSWORD)
                victim.drain(1.0)
                mark = len(victim.transcript)

                with mud.connect(timeout=120) as imm:
                    login(imm, "Zherbimm", PASSWORD)
                    sent = run(imm, "herbie Zherbmort", settle=6.0)
                    self.assertNotIn("not available", sent.lower(), sent)
                    victim.drain(3.0)

                seen = victim.transcript[mark:]

            for line in REAL_SEQUENCE:
                self.assertIn(line, seen,
                              f"a summoned visit is missing {line!r}:\n{seen}")

    def test_herbie_leaves_his_own_room_and_goes_back(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zherbtwo", 70)
            with mud.connect(timeout=120) as client:
                create_character(client, "Zherbthree", PASSWORD)
                client.send("quit")
                client.wait_closed()

            with mud.connect(timeout=120) as imm:
                login(imm, "Zherbtwo", PASSWORD)

                # Stand where Herbie lives and watch him go and come back.
                found = run(imm, "goto herbie", settle=4.0)
                self.assertNotIn("No place like that", found, found)

                with mud.connect(timeout=120) as victim:
                    login(victim, "Zherbthree", PASSWORD)
                    victim.drain(1.0)

                    watched = run(imm, "herbie Zherbthree", settle=6.0)

            self.assertIn("takes to the sky", watched,
                          f"Herbie should leave his room:\n{watched}")
            self.assertIn("Another mortal patched up", watched,
                          f"and come back to it:\n{watched}")


if __name__ == "__main__":
    unittest.main()
