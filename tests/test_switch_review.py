"""SWITCH, played (review, 2026-11-13).

An immortal who SWITCHes into a mobile hands it their descriptor, and
get_trust() reads a switched mobile's trust from the immortal behind it.
These tests play what that touches:

- ORDER and CHARM PERSON: a mortal who charms the mobile an immortal is in
  could ORDER it to run any command at the immortal's trust -- ADVANCE
  included.
- QUIT and SAVE typed while switched did nothing and said nothing.
- A body forced to QUIT while its player was switched was extracted under
  them, leaving them inside the mobile with no body and no way back.
- RETURN needs immortal trust; anybody switched may always go home.

Synthetic Z characters in throwaway worlds only.
"""
from __future__ import annotations

import time
import unittest

from live_mud import (
    SPARRING_FLOOR,
    LiveMud,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zswitchpw1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


def field(mud: LiveMud, name: str, key: str) -> str | None:
    for line in (mud.player_dir / name).read_text(encoding="latin-1").split("\n"):
        if line.split(" ")[0] == key:
            return line[len(key):].strip()
    return None


@unittest.skipIf(SKIP is not None, SKIP or "")
class SwitchOrderTests(unittest.TestCase):
    def test_no_mortal_commands_a_mobile_somebody_is_in(self) -> None:
        """A level 40 mortal ADVANCEd themselves to 45 by charming the
        guard an immortal was in and ORDERing it (live, old build). Both
        routes are closed: CHARM finds no hold on an occupied mobile, and
        ORDER refuses a follower somebody has since switched into."""
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zswimm", Levl=70, Room=TEMPLE)
            # Enough to outlast the guard: a missed charm is an offensive
            # cast, and the guard fights back (a 20 hp mage died of it).
            make(mud, "Zswmage", Levl=40, Cla=0, Room=TEMPLE,
                 HMV="9000 9000 400 400 100 100", HMVP="9000 400 100")
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as mage:
                login(imm, "Zswimm", PW)
                login(mage, "Zswmage", PW)
                for client in (imm, mage):
                    client.sync("scroll 0")
                place_sparring_guard(imm, "Zswimm", SPARRING_FLOOR)
                imm.must("set skill zswmage charm 100", "skill set to 100")
                imm.must(f"transfer zswmage {SPARRING_FLOOR}", "")

                # Switched first: the charm finds no hold, and costs no roll.
                imm.must("switch guard", "Possessed")
                refused = mage.sync("cast 'charm person' guard")
                self.assertIn("already occupied", refused)
                # Refused before the provocation: no fight, no mana spent.
                self.assertNotIn("<*>", refused)
                self.assertIn("400m", refused.split("already occupied")[-1])
                imm.must("return", "old self")

                # Charmed first, then switched into: ORDER refuses it.
                tried = ""
                for _ in range(40):
                    imm.must("restore zswmage", "")
                    # A missed charm starts a fight, and a master's blow on
                    # their own charmed follower breaks the charm (damage()),
                    # so a charm that landed mid-fight could be gone before
                    # STAT looked -- on a slow runner, every time (CI,
                    # 2026-11-14). Stop the fight before each try.
                    imm.sync("peace")
                    mage.sync("stand")
                    tried = mage.sync("cast 'charm person' guard")
                    if "Master: Zswmage" in imm.sync("stat mob guard"):
                        break
                else:
                    self.fail("the charm never landed: mage in %s; guard: %s; %s" % (
                        room_of(imm, "Zswmage"),
                        [l for l in imm.sync("stat mob guard").splitlines() if "Room" in l],
                        mage.transcript[-1200:]))
                imm.must("switch guard", "Possessed")
                self.assertIn("answers to the one inside", mage.sync("order guard advance zswmage 45"))
                mage.sync("order all advance zswmage 45")
                mage.drain(3)
                imm.drain(1)
                self.assertNotIn("orders you", imm.transcript)
                mage.send("quit")
                mage.wait_closed()
                imm.sync("return")
            level = int(field(mud, "Zswmage", "Levl") or 0)
        self.assertEqual(40, level, "a mortal ADVANCEd themselves through a switched mobile")


@unittest.skipIf(SKIP is not None, SKIP or "")
class SwitchHousekeepingTests(unittest.TestCase):
    def test_quit_save_and_a_forced_quit_while_switched(self) -> None:
        env = {"TOC_FAULT": "autowrite"}           # no autosave muddies the file
        with LiveMud(fixtures=True, extra_env=env) as mud:
            make(mud, "Zswboss", Levl=70, Room=TEMPLE)
            make(mud, "Zswimm", Levl=65, Room=TEMPLE)
            with mud.connect(timeout=120) as boss, mud.connect(timeout=120) as imm:
                login(boss, "Zswboss", PW)
                login(imm, "Zswimm", PW)
                for client in (boss, imm):
                    client.sync("scroll 0")
                place_sparring_guard(boss, "Zswboss", SPARRING_FLOOR)
                imm.must("switch sparring", "Possessed")

                # SAVE writes the immortal's own file.
                path = mud.player_dir / "Zswimm"
                before = path.stat().st_mtime_ns
                time.sleep(1.1)
                saved = imm.sync("save")
                self.assertNotEqual(before, path.stat().st_mtime_ns, "SAVE while switched: " + saved)

                # QUIT says something and puts them back in their body.
                said = imm.sync("quit")
                self.assertIn("own body", said.lower(), said)
                self.assertEqual(TEMPLE, room_of(boss, "Zswimm"))
                self.assertIn("aren't switched", imm.sync("return"))

                # Switched again, the body is forced to quit: they are put
                # back in it first, never left in the mobile with no body.
                imm.must("switch sparring", "Possessed")
                boss.sync("force zswimm quit")
                self.assertTrue(imm.wait_closed(), "the forced quit did not end the session")


if __name__ == "__main__":
    unittest.main()
