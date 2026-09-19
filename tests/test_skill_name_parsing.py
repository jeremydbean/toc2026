"""A skill name with a quote in it must not corrupt the player file.

Skills are saved as `Sk 75 'shield block'` and were read back with
fread_word, which treats the opening quote as a delimiter and stops at the
next one. A skill named "hero's grip" therefore wrote a line the reader
could not read: it came back as `hero`, left `s grip'` in the stream as the
next key, and every field after that parsed against the wrong offset until
the load segfaulted. A live character was left unable to log in.

The reader now takes the rest of the line, so no name can desync it, and a
line naming a skill that no longer exists is skipped rather than fatal.
"""
from __future__ import annotations

import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zparseone1"


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class SkillNameParsingTests(unittest.TestCase):
    def test_a_quoted_apostrophe_in_a_saved_skill_does_not_break_the_load(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zparser", PASSWORD)
                before = run(client, "practice", settle=4.0)
                client.send("quit")
                client.wait_closed()

            path = mud.player_dir / "Zparser"
            saved = path.read_text(encoding="latin-1")

            # Exactly what the old build wrote into a live character.
            lines = saved.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("Sk "):
                    lines.insert(i, "Sk 1 'hero's grip'")
                    break
            else:
                self.fail("no skill lines in the saved character")
            path.write_text("\n".join(lines), encoding="latin-1", newline="")

            with mud.connect(timeout=120) as client:
                login(client, "Zparser", PASSWORD)
                sheet = run(client, "score", settle=4.0)
                # The bad line was put first, so every real skill after it
                # is one the old reader would have lost.
                after = run(client, "practice", settle=4.0)

            self.assertIn("Zparser", sheet,
                          f"the character should still load:\n{sheet}")

            kept = [s for s in ("sword", "recall", "shield block",
                                "hand to hand", "parry", "dodge")
                    if s in before]
            self.assertTrue(kept, f"no skills to check against:\n{before}")
            for skill in kept:
                self.assertIn(skill, after,
                              f"{skill} was lost after the bad line:\n{after}")

    def test_ordinary_two_word_skills_still_round_trip(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zparsetwo", PASSWORD)
                before = run(client, "skills", settle=4.0)
                client.send("quit")
                client.wait_closed()

            with mud.connect(timeout=120) as client:
                login(client, "Zparsetwo", PASSWORD)
                after = run(client, "skills", settle=4.0)

            for skill in ("shield block", "hand to hand"):
                if skill in before:
                    self.assertIn(skill, after,
                                  f"{skill} was lost across a save:\n{after}")


if __name__ == "__main__":
    unittest.main()
