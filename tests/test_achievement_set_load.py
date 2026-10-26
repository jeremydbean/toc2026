"""AchSet lines are read strictly and boundedly (review, 2026-10-26).

The loader read each token with an unchecked strtol and expanded a range
with `for (; first <= last; first++)`, so "AchSet rooms
9223372036854775807 ~" made the increment after inserting LONG_MAX a
signed overflow (UBSan reported it; no production hang was shown). It
also took "12x" as 12, an out-of-range strtol as LONG_MAX, and stopped
reading after 20,000 tokens, leaving the rest of the line for fread_char.

Now a token is digits, or digits-digits, within the set's largest honest
id (an int for vnums and area ids, small for dailies and disciplines);
the range loop stops at its last value; at most twice the set's limit of
ids are tried per line; every token is read to the "~", so the keys
after a long or unknown set still load; and the writer never asks for
the id after LONG_MAX. Run against the sanitizer build too, where
LiveMud fails the test on any UBSan report.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zsetpass1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, lines: list) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=20, Room=TEMPLE)
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    at = text.index("\nEnd\n")
    path.write_text(text[:at] + "\n" + "\n".join(lines) + text[at:], encoding="latin-1")


def login_and_save(mud: LiveMud, name: str) -> tuple:
    started = time.monotonic()
    with mud.connect(timeout=120) as client:
        login(client, name, PW)
        took = time.monotonic() - started
        client.sync("save")
        client.send("quit")
        client.wait_closed()
    return (mud.player_dir / name).read_text(encoding="latin-1"), took


def saved_set(text: str, name: str) -> set:
    """The ids a saved "AchSet <name> ..." line holds."""
    match = re.search(r"^AchSet %s (.*) ~$" % re.escape(name), text, re.M)
    if not match:
        return set()
    ids = set()
    for token in match.group(1).split():
        if "-" in token:
            a, b = (int(x) for x in token.split("-"))
            assert b - a < 100000, token
            ids.update(range(a, b + 1))
        else:
            ids.add(int(token))
    return ids


@unittest.skipIf(SKIP is not None, SKIP or "")
class AchievementSetLoadTests(unittest.TestCase):
    def test_hostile_values_are_skipped_and_the_rest_loads(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zsetvalues", [
                # LONG_MAX, a value past it, and ranges ending at the top.
                "AchSet rooms 9223372036854775807 99999999999999999999 "
                "2147483646-2147483647 9223372036854775806-9223372036854775807 "
                # malformed: trailing letters, signs, a reversed range,
                # an empty end, a range ending past LONG_MAX
                "12x -3 +4 6-5 7- 8-99999999999999999999 "
                # honest ids and a run
                "100 200-202 ~",
                # Past their largest honest ids.
                "AchSet daily-kinds 1 63 64 ~",
                "AchSet psi-disciplines 0 15 16 ~",
                # A set from a newer build: read through, dropped.
                "AchSet zfuture 1 2 3 4-9 ~",
                # Keys after all of that still load.
                "AchCount goblins 7",
            ])
            text, _ = login_and_save(mud, "Zsetvalues")

        rooms = saved_set(text, "rooms")
        for kept in (100, 200, 201, 202, 2147483646, 2147483647):
            self.assertIn(kept, rooms, text)
        for dropped in (9223372036854775807, 12, 3, 4, 5, 6, 7, 8):
            self.assertNotIn(dropped, rooms, sorted(rooms))
        self.assertTrue(all(i <= 2147483647 for i in rooms), sorted(rooms))
        self.assertEqual(saved_set(text, "daily-kinds"), {1, 63})
        self.assertEqual(saved_set(text, "psi-disciplines"), {0, 15})
        self.assertNotIn("zfuture", text)
        self.assertRegex(text, r"(?m)^AchCount goblins 7$", "the key after the sets was lost")
        self.assertIn(" 2147483646-2147483647", text, "the top run is written as a run")

    def test_a_huge_line_is_bounded_and_read_to_its_end(self) -> None:
        tokens = " ".join(["0-2147483647"] * 30000)
        with LiveMud() as mud:
            make(mud, "Zsethuge", [
                f"AchSet rooms {tokens} ~",
                "AchSet areas 1-2147483647 ~",
                "AchCount goblins 3",
            ])
            text, took = login_and_save(mud, "Zsethuge")

        # The rooms set stops at its limit; the areas set at its own.
        self.assertEqual(len(saved_set(text, "rooms")), 16384)
        self.assertEqual(len(saved_set(text, "areas")), 1024)
        # Past 20,000 tokens the line is still read to its "~".
        self.assertRegex(text, r"(?m)^AchCount goblins 3$", "the key after a long set was lost")
        self.assertLess(took, 60, "loading a hostile set took too long")


if __name__ == "__main__":
    unittest.main()
