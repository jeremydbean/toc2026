"""Live check of the Oracle's sanctum.

PRAY takes the supplicant out of the world into her sanctum; every way out
puts them back in the room they prayed from, dazed for a tick: saying DONE,
walking down through the bead curtain, and quitting inside (the file saves
the room they prayed from, never the sanctum).
"""
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

PW = "testpw12"
TEMPLE_NAME = "Before the Altar"

_SKIP = skip_reason()


def make(mud, name):
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError("character did not quit")
    patch_player_file(mud, name, Room=4207)


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class OracleSanctumLive(unittest.TestCase):
    def test_every_way_out_returns_you_to_where_you_prayed(self):
        with LiveMud() as mud:
            for name in ("Zpraydone", "Zpraydown", "Zprayquit"):
                make(mud, name)

            # DONE sends you home, dazed.
            with mud.connect(timeout=120) as client:
                login(client, "Zpraydone", PW)
                out = client.command("pray", 1.5)
                self.assertIn("The Oracle's Sanctum", out)
                out = client.command("say done", 1.5)
                self.assertIn(TEMPLE_NAME, out)
                self.assertIn("dazed", out)
                client.send("quit")
                client.wait_closed()

            # Walking down through the beads does too.
            with mud.connect(timeout=120) as client:
                login(client, "Zpraydown", PW)
                out = client.command("pray", 1.5)
                self.assertIn("The Oracle's Sanctum", out)
                out = client.command("down", 1.5)
                self.assertIn(TEMPLE_NAME, out)
                self.assertIn("dazed", out)
                client.send("quit")
                client.wait_closed()

            # Quitting inside saves the room you prayed from, not the sanctum.
            with mud.connect(timeout=120) as client:
                login(client, "Zprayquit", PW)
                out = client.command("pray", 1.5)
                self.assertIn("The Oracle's Sanctum", out)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            with mud.connect(timeout=120) as client:
                login(client, "Zprayquit", PW)
                out = client.command("look", 1.2)
                self.assertIn(TEMPLE_NAME, out)
                self.assertNotIn("The Oracle's Sanctum", out)


if __name__ == "__main__":
    unittest.main()
