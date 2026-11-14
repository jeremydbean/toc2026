"""A mortal given trust is a mortal everywhere but the command table.

Owner, 2026-11-12: "i think trusted characters should actually be logged
also. just not immortals", "no let trusted players act as mortals across
the board", "staff-only should ONLY apply to actual immortals level 60+".

One world, synthetic characters only:

- Ztrustee, level 20 trusted to 65. Trust is command authority, so GOTO
  and STAT work; everything staff-only treats them as the level 20 they
  are: INVULN is refused and a sparring guard's blows hurt, IMMTALK and
  WIZINFO do not reach them, CHANGES ALL holds no staff-only entry, a
  wizinvis immortal at 62 is not on their WHO, and they earn the
  achievements the login catch-up pays any mortal.
- Zimmy, level 65: an immortal by level, who has every one of those.
- Zgodly, level 70: sets things up and speaks on IMMTALK.

Logging is tests/test_trusted_logging.py's; the source sweep is
tests/test_staff_trust.py's.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import (
    LiveMud,
    SPARRING_GUARD,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Ztrustee1"
TEMPLE = 4207
ALTAR = 4208
FLOOR = 32703            # a fixture room joined to nothing
BIG = "20000 20000 1000 1000 1000 1000"


def make(mud: LiveMud, name: str, skills: bool = False, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    if skills:
        # What the login catch-up pays: Weapons Scholar I and Practice
        # Makes Permanent I (tests/test_achievement_staff.py).
        path = mud.player_dir / name
        text = path.read_text(encoding="latin-1")
        end = text.index("\nEnd\n")
        path.write_text(text[:end] + "\nSk 100 'sword'\nSk 100 'dagger'" + text[end:],
                        encoding="latin-1")


def hitpoints(client) -> int:
    client.drain(1.0)
    found = re.findall(r"<(-?\d+)hp", client.transcript[-600:])
    return int(found[-1]) if found else -1


def fight_until_hurt_or(client, rounds: int) -> tuple[int, str]:
    """Drain a fight a round at a time; the prompt's hit points at the end."""
    seen = ""
    start = hitpoints(client)
    for _ in range(rounds):
        mark = len(client.transcript)
        client.drain(2.5)
        seen += client.transcript[mark:]
        now = hitpoints(client)
        if 0 < now < start:
            return now, seen
    return hitpoints(client), seen


@unittest.skipIf(SKIP is not None, SKIP or "")
class TrustedMortalTests(unittest.TestCase):
    def test_trust_runs_commands_and_nothing_else(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zgodly", Levl=70, Room=TEMPLE)
            make(mud, "Zimmy", skills=True, Levl=65, Room=TEMPLE, HMV=BIG)
            make(mud, "Ztrustee", skills=True, Levl=20, Tru=65, Room=TEMPLE, HMV=BIG)
            make(mud, "Zpasser", Levl=10, Room=3700)   # elsewhere: only WIZINFO carries it

            with mud.connect(timeout=120) as god, \
                    mud.connect(timeout=120) as imm, \
                    mud.connect(timeout=120) as trustee:
                for client, name in ((god, "Zgodly"), (imm, "Zimmy"),
                                     (trustee, "Ztrustee")):
                    login(client, name, PW)
                    client.sync("scroll 0")

                # --- Command authority stays trust's: GOTO and STAT. ---
                trustee.sync(f"goto {ALTAR}")
                self.assertEqual(ALTAR, room_of(god, "ztrustee"))
                self.assertIn("Vnum:", trustee.sync("stat room"))
                trustee.sync(f"goto {TEMPLE}")

                # --- Wizinvis: a staff privilege, by level. ---
                god.must("wizinvis 62", "vanish")
                self.assertNotIn("Zgodly", trustee.sync("who"))
                self.assertIn("Zgodly", imm.sync("who"))
                god.must("wizinvis", "fade back")
                self.assertIn("Zgodly", trustee.sync("who"))

                # --- IMMTALK: heard by an immortal, not a trusted mortal. ---
                for client in (imm, trustee):
                    client.drain(0.5)
                marks = {id(c): len(c.transcript) for c in (imm, trustee)}
                god.sync("immtalk the staff word is quince")
                imm.drain(1.5)
                trustee.drain(1.5)
                self.assertIn("quince", imm.transcript[marks[id(imm)]:])
                self.assertNotIn("quince", trustee.transcript[marks[id(trustee)]:])
                # They may still speak on it: typing it is the command's.
                trustee.sync("immtalk the trusted mortal speaks")
                god.drain(1.5)
                self.assertIn("the trusted mortal speaks", god.transcript)

                # --- WIZINFO: a quit elsewhere reaches only staff. ---
                marks = {id(c): len(c.transcript) for c in (imm, trustee)}
                with mud.connect(timeout=120) as passer:
                    login(passer, "Zpasser", PW)
                    passer.send("quit")
                    self.assertTrue(passer.wait_closed())
                imm.drain(2.0)
                trustee.drain(2.0)
                self.assertIn("Zpasser has left the game",
                              imm.transcript[marks[id(imm)]:])
                self.assertNotIn("WIZINFO", trustee.transcript[marks[id(trustee)]:])
                self.assertNotIn("Zpasser has left", trustee.transcript[marks[id(trustee)]:])

                # --- CHANGES: staff-only entries for staff by level. ---
                self.assertIn("(staff only)", imm.sync("changes all", timeout=60))
                self.assertNotIn("(staff only)", trustee.sync("changes all", timeout=60))

                # --- Invulnerability: an immortal's. ---
                refused = trustee.sync("invuln damage")
                self.assertIn("an immortal's", refused)
                self.assertNotIn("Invulnerability on", refused)
                imm.must("invuln damage", "Invulnerability on")

                place_sparring_guard(god, "Zgodly", FLOOR)
                god.must("transfer ztrustee", "")
                self.assertEqual(FLOOR, room_of(god, "ztrustee"))

                # --- SWITCH: possession is an immortal's (2026-11-14). ---
                refused = trustee.sync("switch sparring")
                self.assertIn("immortal's power", refused)
                self.assertNotIn("Possessed", refused)
                self.assertIn("aren't switched", trustee.sync("return"))

                before = hitpoints(trustee)
                self.assertGreater(before, 0)
                trustee.send("kill sparring")
                after, fight = fight_until_hurt_or(trustee, 12)
                self.assertLess(after, before,
                                "a trusted mortal took no damage: " + fight[-500:])
                god.sync("peace")
                god.sync("purge sparring")
                god.must(f"transfer ztrustee {TEMPLE}", "")

                god.must(f"load mob {SPARRING_GUARD}", "You create a sparring guard")
                god.must("transfer zimmy", "")
                before = hitpoints(imm)
                self.assertGreater(before, 0)
                imm.send("kill sparring")
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    imm.drain(2.5)
                self.assertEqual(before, hitpoints(imm),
                                 "an invulnerable immortal lost hit points")
                god.sync("peace")

                for client in (god, imm, trustee):
                    client.sync("save")
                    client.send("quit")
                    self.assertTrue(client.wait_closed())

            # --- Achievements: a trusted mortal is caught up like any. ---
            def earned(name: str) -> set:
                text = (mud.player_dir / name).read_text(encoding="latin-1")
                return set(re.findall(r"^Achv (\S+) ", text, re.M))

            self.assertTrue({"weapons-1", "mastered-1"} <= earned("Ztrustee"),
                            earned("Ztrustee"))
            self.assertFalse({"weapons-1", "mastered-1"} & earned("Zimmy"),
                             earned("Zimmy"))


if __name__ == "__main__":
    unittest.main()
