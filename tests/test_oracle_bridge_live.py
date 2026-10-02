"""Live check of the Oracle's read-only lookup bridge.

The web poller appends "<id>\\t<kind>\\t<arg>" to area/oracle.query; the game
drains it on its pulse, runs a fixed read-only scan, and appends
"<id>\\t<finding>" to area/oracle.queryresult. This boots a real server and
exercises every kind: a mob's live location, a player's live gear, an object
that does not exist, a mobile's gear, and who is online -- with an immortal
connected and in plain sight, who must still not appear in any of it: she
reveals only what the asker could see, and never the staff.

It then prays, to check the game tells the poller a sitting has begun and
that WRONG with nothing yet said is answered politely rather than filed.
"""
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

PW = "testpw12"
NAME = "Zbridger"
HIDDEN = "Zhider"

_SKIP = skip_reason()


def wait_for_results(path, ids, timeout=10.0):
    got = {}
    deadline = time.time() + timeout
    while time.time() < deadline and len(got) < len(ids):
        time.sleep(0.25)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            rid, _, rest = line.partition("\t")
            if rid in ids:
                got[rid] = rest
    return got


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class OracleBridgeLive(unittest.TestCase):
    def test_game_answers_read_only_lookups(self):
        with LiveMud() as mud:
            # An immortal, visible and not wizinvis, made first and logged back
            # in below.
            with mud.connect(timeout=120) as setup:
                create_character(setup, HIDDEN, PW)
                setup.send("quit")
                self.assertTrue(setup.wait_closed())
            patch_player_file(mud, HIDDEN, Levl=70, Room=4207)

            with mud.connect(timeout=120) as hider, \
                    mud.connect(timeout=120) as client:
                login(hider, HIDDEN, PW)
                create_character(client, NAME, PW)

                area = mud.root / "area"
                query = area / "oracle.query"
                result = area / "oracle.queryresult"
                # "<id>\t<kind>\t<asker>\t<keyword>": answered as NAME sees it.
                query.write_text(
                    "r1\tmob\t{n}\tdummy\n"
                    "r2\teq\t{n}\t{n}\n"
                    "r3\tobj\t{n}\tzzqqxnothing\n"
                    "r4\twho\t{n}\tall\n"
                    "r5\teq\t{n}\t{h}\n"
                    "r6\tmobeq\t{n}\tdummy\n".format(n=NAME, h=HIDDEN),
                    encoding="utf-8")

                got = wait_for_results(result, {"r1", "r2", "r3", "r4", "r5", "r6"})

                ask = area / "oracle.ask"
                ask.write_text("", encoding="utf-8")
                prayed = client.command("pray", 1.5)
                wrong = client.command("say wrong", 1.0)
                spooled = ask.read_text(encoding="utf-8", errors="replace")

        self.assertIn("r1", got, "the game never answered the mob lookup")
        self.assertIn("(2419)", got["r1"], "dummy should be in room 2419: " + got["r1"])
        self.assertIn("r2", got)
        self.assertIn("%s is wearing right now" % NAME, got["r2"])
        self.assertIn("r3", got)
        self.assertIn("No 'zzqqxnothing'", got["r3"])

        # Who is on, as the asker could see it: the immortal is absent, and
        # asking after them by name says they are not online.
        self.assertIn("r4", got)
        self.assertIn(NAME, got["r4"])
        self.assertNotIn(HIDDEN, got["r4"])
        self.assertIn("r5", got)
        self.assertIn("%s is not online right now" % HIDDEN, got["r5"])

        # A mobile's gear, named by its short description, with its room.
        self.assertIn("r6", got)
        self.assertIn("(2419), is wearing right now", got["r6"])

        self.assertIn("The Oracle's Sanctum", prayed)
        self.assertIn("\t%s\t\x01SITTING" % NAME, spooled)
        self.assertIn("told you nothing yet", wrong)


if __name__ == "__main__":
    unittest.main()
