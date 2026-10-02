"""Live check of the Oracle's read-only lookup bridge.

The web poller appends "<id>\\t<kind>\\t<arg>" to area/oracle.query; the game
drains it on its pulse, runs a fixed read-only scan, and appends
"<id>\\t<finding>" to area/oracle.queryresult. This boots a real server and
exercises all three kinds: a mob's live location, a player's live gear, and
an object that does not exist.
"""
import time
import unittest

from live_mud import LiveMud, create_character, skip_reason

PW = "testpw12"
NAME = "Zbridger"

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
            with mud.connect(timeout=120) as client:
                create_character(client, NAME, PW)

                area = mud.root / "area"
                query = area / "oracle.query"
                result = area / "oracle.queryresult"
                query.write_text(
                    "r1\tmob\tdummy\n"
                    "r2\teq\t%s\n"
                    "r3\tobj\tzzqqxnothing\n" % NAME,
                    encoding="utf-8")

                got = wait_for_results(result, {"r1", "r2", "r3"})

        self.assertIn("r1", got, "the game never answered the mob lookup")
        self.assertIn("(2419)", got["r1"], "dummy should be in room 2419: " + got["r1"])
        self.assertIn("r2", got)
        self.assertIn("%s is wearing right now" % NAME, got["r2"])
        self.assertIn("r3", got)
        self.assertIn("No 'zzqqxnothing'", got["r3"])


if __name__ == "__main__":
    unittest.main()
