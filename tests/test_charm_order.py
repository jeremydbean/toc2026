"""CHARM PERSON, ORDER and NOFOLLOW on a player, played (review, 2026-11-14).

- The switch review's guard against charming an occupied mobile asked any
  descriptor, so every connected player became uncharmable, and ORDER
  skipped every connected follower.
- A charmed player ORDERed obeys in the room -- SAY, a step -- but not in
  what outlasts the charm or speaks past the room: ALIAS, a channel,
  NOSUMMON, RECALL SET, STASH.
- ORDER ALL asked no rank, so it ran a command at a follower's trust that
  ORDER <name> refused.
- NOFOLLOW let a charmed player walk out of the charm (FOLLOW SELF is
  refused for exactly that).
- A player's AUTOSAC read as a mobile's ACT_AGGRESSIVE, so SHOVE called
  them an aggressive monster; their PLR_LOG read as ACT_MOUNTABLE, so a
  watched player could not be charmed.

Synthetic Z characters in throwaway worlds only.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (
    SPARRING_FLOOR,
    SPARRING_GALLERY,
    LiveMud,
    create_character,
    login,
    patch_player_file,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zcharmpw1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


def charm(imm, mage, victim: str) -> None:
    """Cast until the charm lands (a 50% roll), keeping the peace between
    tries: a missed charm on a player starts a fight."""
    for _ in range(40):
        imm.must(f"restore {victim}", "")
        imm.must("restore zchmage", "")
        imm.sync("peace")
        mage.sync("stand")
        mage.sync(f"cast 'charm person' {victim}")
        if "Master: Zchmage" in imm.sync(f"stat {victim}"):
            imm.sync("peace")
            return
    raise AssertionError("the charm never landed: " + mage.transcript[-800:])


@unittest.skipIf(SKIP is not None, SKIP or "")
class CharmedPlayerOrderTests(unittest.TestCase):
    def test_charm_order_and_nofollow(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zchimm", Levl=70, Room=TEMPLE, Creator=1)  # LOG is the creator's
            make(mud, "Zchmage", Levl=30, Cla=0, Room=TEMPLE, Pk_State=1,
                 HMV="9000 9000 900 900 100 100", HMVP="9000 900 100")
            make(mud, "Zchvict", Levl=28, Room=TEMPLE, Pk_State=1,
                 HMV="9000 9000 100 100 100 100", HMVP="9000 100 100")
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as mage, \
                    mud.connect(timeout=120) as vict:
                login(imm, "Zchimm", PW)
                login(mage, "Zchmage", PW)
                login(vict, "Zchvict", PW)
                for client in (imm, mage, vict):
                    client.sync("scroll 0")
                imm.must("set skill zchmage charm 100", "skill set to 100")
                for who in ("zchimm", "zchmage", "zchvict"):
                    imm.must(f"transfer {who} {SPARRING_FLOOR}", "")
                # A watched player is charmed like anyone (PLR_LOG is the
                # bit ACT_MOUNTABLE is on a mobile).
                imm.must("log zchvict", "now being LOGGED")

                charm(imm, mage, "zchvict")

                # In the room, an order is obeyed.
                mage.must("order zchvict say I adore my master", "Ok.")
                self.assertIn("I adore my master", imm.drain(1))

                # What outlasts the charm or speaks past the room is not.
                for order in ("alias n quit", "gossip I am a fool",
                              "nosummon", "recall set", "stash link zchmage",
                              "tell zchimm hello"):
                    said = mage.sync(f"order zchvict {order}")
                    self.assertIn("will not do that", said, order)
                self.assertGreaterEqual(vict.drain(1).count("yours alone"), 6)
                self.assertNotIn("quit", vict.sync("alias").lower().replace("unalias", ""))
                self.assertNotIn("I am a fool", imm.drain(1))

                # ORDER ALL is refused what ORDER <name> is: a follower
                # trusted above the master runs nothing on the master's word.
                imm.must("trust zchvict 65", "")
                self.assertIn("Do it yourself", mage.sync(f"order zchvict goto {TEMPLE}"))
                mage.sync(f"order all goto {TEMPLE}")
                self.assertEqual(SPARRING_FLOOR, room_of(imm, "Zchvict"))
                imm.must("trust zchvict 0", "")

                # NOFOLLOW stops followers, but a charmed player still
                # follows their master.
                said = vict.sync("nofollow")
                self.assertIn("no longer accept followers", said)
                self.assertIn("Master: Zchmage", imm.sync("stat zchvict"))
                vict.sync("nofollow")
                for client in (mage, vict):
                    client.send("quit")
                    client.wait_closed()


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShoveAutosacTests(unittest.TestCase):
    def test_a_player_with_autosac_is_no_aggressive_monster(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zshimm", Levl=70, Room=TEMPLE)
            make(mud, "Zshover", Levl=30, Room=TEMPLE, Pk_State=1)
            make(mud, "Zshoved", Levl=30, Room=TEMPLE, Pk_State=1)
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as shover, \
                    mud.connect(timeout=120) as shoved:
                login(imm, "Zshimm", PW)
                login(shover, "Zshover", PW)
                login(shoved, "Zshoved", PW)
                for client in (imm, shover, shoved):
                    client.sync("scroll 0")
                imm.must("set skill zshover shove 100", "skill set to 100")
                for who in ("zshover", "zshoved"):
                    imm.must(f"transfer {who} {SPARRING_FLOOR}", "")
                said = shoved.sync("autosac")
                if "removed" in said.lower():
                    shoved.sync("autosac")
                tried = ""
                for _ in range(10):
                    tried = shover.sync("shove zshoved north")
                    self.assertNotIn("Aggresive", tried)
                    if room_of(imm, "Zshoved") == SPARRING_GALLERY:
                        break
                    imm.sync("peace")
                    shover.sync("stand")
                else:
                    self.fail("never shoved: " + tried)


class OrderRefusedNamesTests(unittest.TestCase):
    def test_every_refused_name_is_a_command(self) -> None:
        """order_refuses_command matches each name's function; a name that
        is no command refuses nothing, silently."""
        src = (Path(__file__).resolve().parent.parent / "src" / "interp.c").read_text(encoding="latin-1")
        block = re.search(r"order_refused_names\[\] =\s*\{(.*?)NULL", src, re.S).group(1)
        names = re.findall(r'"([a-z]+)"', block)
        commands = set(re.findall(r'^\s*\{\s*"([a-z_ ]+)",\s*do_', src, re.M))
        self.assertGreater(len(names), 40)
        self.assertEqual([], [n for n in names if n not in commands])


if __name__ == "__main__":
    unittest.main()
