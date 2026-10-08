"""In-game building: rooms in words, shops, and WALKTO to a built area.

SET ROOM took flag letters and a sector number. It takes names now --
flags +indoors, sector forest, detail altar ... -- with the letters still
working, and a lowercase word that is no flag is refused rather than read
as letters. RSHOW reads a room back. SET MOB <vnum> SHOP makes and tunes a
shop in words. WALKTO finds an area built in game by its name, though the
generated destination list cannot hold it. Everything survives a reboot.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zbuildpw7"
LO, HI = 21400, 21419
ROOM, NORTH, KEEPER, BLADE = 21401, 21402, 21403, 21404


def run(client, command: str, settle: float = 1.0) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return re.sub(r"\x1b\[[0-9;]*m", "", client.transcript[mark:].replace("\r", ""))


def sheet(text: str, start: str, end: str) -> str:
    i = text.find(start)
    j = text.find(end, i)
    assert i >= 0 and j > i, "no sheet in: " + text
    return text[i:j]


@unittest.skipIf(SKIP is not None, SKIP or "")
class RoomShopTests(unittest.TestCase):
    def test_rooms_and_shops_in_words(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zmarket", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmarket", Levl=70, Room=4207)

            with mud.connect(timeout=120) as imm:
                login(imm, "Zmarket", PASSWORD)
                run(imm, "scroll 0")
                self.assertIn("Created area", run(imm, f"anew {LO} {HI} Zed Market"))
                run(imm, f"goto {ROOM}", 1.5)
                run(imm, f"set room {ROOM} name The Market Hall")

                out = run(imm, f"set room {ROOM} flags +indoors +no_mob")
                self.assertIn("flags are now: no_mob indoors", out, out)
                # The old letters still work: D is indoors, so -D takes it off.
                self.assertIn("flags are now: no_mob", run(imm, f"set room {ROOM} flags -D"))
                run(imm, f"set room {ROOM} flags +indoors")
                # A word that is no flag is refused, not read as letters.
                out = run(imm, f"set room {ROOM} flags +river")
                self.assertIn("Room flags:", out, out)
                self.assertIn("flags are now: no_mob indoors",
                              run(imm, f"set room {ROOM} flags +always_lit -always_lit"))

                self.assertIn("forest ground", run(imm, f"set room {ROOM} sector forest"))
                self.assertIn("Ground:", run(imm, f"set room {ROOM} sector lava"))
                # A typed ; separates commands; \; is a literal one.
                run(imm, f"set room {ROOM} desc Stalls crowd the hall\\; traders shout.")
                self.assertIn("added to", run(imm, f"set room {ROOM} desc + Coins clink."))
                self.assertIn("details are set",
                              run(imm, f"set room {ROOM} detail stalls Bright awnings sag."))
                run(imm, f"rlink north {NORTH}", 1.5)

                # A number past what a room's flags hold is refused: it would
                # save as a negative the loader cannot read (review).
                self.assertIn("beyond the flags",
                              run(imm, f"set room {ROOM} flags 2147483648"))

                # A door reset goes when the door does, or every reset would
                # close an open way nobody can then open (review).
                run(imm, "rlink north door", 1.5)
                self.assertIn("will be closed", run(imm, "place door north closed", 1.5))
                run(imm, "rlink north open", 1.5)
                self.assertNotIn("door north", run(imm, "resets", 1.5))

                # An apostrophe in an object's keywords no longer garbles DESC.
                run(imm, "ocreate 21405")
                run(imm, "set obj 21405 keywords o'brien club")
                run(imm, "set obj 21405 desc Knotted wood, worn smooth.")
                self.assertIn("details: o'brien club", run(imm, "oshow 21405", 1.5))

                # A shopkeeper, in words.
                run(imm, f"mcreate {KEEPER}")
                run(imm, f"set mob {KEEPER} keywords trader")
                run(imm, f"set mob {KEEPER} short the trader")
                run(imm, f"set mob {KEEPER} long The trader waits behind a stall.")
                self.assertIn("keeps a shop now", run(imm, f"set mob {KEEPER} shop"))
                run(imm, f"set mob {KEEPER} shop markup 150")
                run(imm, f"set mob {KEEPER} shop pays 50")
                out = run(imm, f"set mob {KEEPER} shop buys weapon armor")
                self.assertIn("buys weapon armor", out, out)
                self.assertIn("no item type called 'flibble'",
                              run(imm, f"set mob {KEEPER} shop buys flibble"))
                self.assertIn("open 0 to 23", run(imm, f"set mob {KEEPER} shop hours 0 23"))
                run(imm, f"ocreate {BLADE} 3021")
                run(imm, f"place mob {KEEPER}", 1.5)
                run(imm, f"place obj {BLADE} on {KEEPER}", 1.5)
                self.assertIn("a small sword", run(imm, "list", 1.5).lower())

                room_before = sheet(run(imm, f"rshow {ROOM}", 1.5), f"Room {ROOM}, in", "resets:")
                self.assertIn("ground: forest", room_before)
                self.assertIn("flags:  no_mob indoors", room_before)
                self.assertIn("Stalls crowd the hall; traders shout.\nCoins clink.", room_before)
                self.assertIn(f"north     to {NORTH}", room_before)
                self.assertIn("details: stalls", room_before)
                mob_before = sheet(run(imm, f"mshow {KEEPER}", 1.5), "shop:", "\n")
                self.assertIn("markup 150%, pays 50%, buys weapon armor, open 0 to 23",
                              mob_before)

                self.assertIn("Saved Zed Market", run(imm, "asave", 2.0))
                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            mud.restart()

            with mud.connect(timeout=120) as imm:
                login(imm, "Zmarket", PASSWORD)
                run(imm, "scroll 0")
                self.assertEqual(
                    sheet(run(imm, f"rshow {ROOM}", 1.5), f"Room {ROOM}, in", "resets:"),
                    room_before)
                self.assertEqual(sheet(run(imm, f"mshow {KEEPER}", 1.5), "shop:", "\n"),
                                 mob_before)

                # WALKTO knows the built area by name. From the Temple there
                # is no way in (nothing in the world links to it yet), and it
                # says so by name; from its own back room it walks.
                run(imm, "goto 4207", 1.5)
                self.assertIn("no way to Zed Market", run(imm, "walkto zed market", 1.5))
                run(imm, f"goto {NORTH}", 1.5)
                self.assertIn("You set off for Zed Market", run(imm, "walkto zed market", 1.5))
                self.assertIn("The Market Hall", run(imm, "look", 3.0))
                self.assertIn("Bright awnings sag.", run(imm, "look stalls"))


if __name__ == "__main__":
    unittest.main()
