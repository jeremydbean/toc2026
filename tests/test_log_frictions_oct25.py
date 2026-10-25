"""Three frictions from the logs of 2026-10-25.

* Alaric, newly a monk, ate eight guano pills in a row: stone skin is
  refused to monks and necromancers (HELP ARMOR says so), and the refusal
  read "Spell failed.", like a miss.
* Trentlin typed "shove goriya so" and was told it was no direction;
  SHOVE took only n/north and the like, where moving takes any start of
  a direction's name.
* Trentlin found Level 7's Hidden Cistern -- the tip of the nose the
  hook-nosed old man hints at -- and spent minutes on LOOK CISTERN, LOOK
  NOSE, LOOK TIP and TAP NOSE: the room named all of them and answered
  none. Its LOOK details come from data/hyrule_room_prose.json.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_FLOOR, create_character, login, patch_player_file,
                      place_sparring_guard, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zfrictpass1"
CISTERN = 30543
GUANO = 16046   # a pill of stone skin and fly, pirate.are


class SourceTests(unittest.TestCase):
    def test_stone_skin_refusal_is_not_a_miss(self) -> None:
        src = (ROOT / "src" / "magic.c").read_text(encoding="latin-1")
        body = src[src.index("void spell_stone_skin("):]
        body = body[:body.index("\n}\n")]
        refusal = body[body.index("CLASS_MONK"):body.index("return;")]
        self.assertNotIn("Spell failed", refusal)
        self.assertIn("monk or a necromancer", refusal)

    def test_cistern_names_what_it_describes(self) -> None:
        prose = json.loads((ROOT / "data" / "hyrule_room_prose.json").read_text(encoding="utf-8"))
        words = " ".join(extra["keywords"] for extra in prose["dungeons"]["L7:C5"]["extras"]).split()
        for word in ("cistern", "nose", "tip", "moss", "water"):
            self.assertIn(word, words)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_pill_shove_and_cistern(self) -> None:
        with LiveMud(fixtures=True) as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zfriction", PW)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zfriction", Levl=70, Cla=4)

            with mud.connect(timeout=120) as client:
                login(client, "Zfriction", PW)
                client.sync("scroll 0")

                client.sync(f"load obj {GUANO}")
                ate = client.sync("eat guano")
                self.assertIn("never takes on a monk", ate, ate)
                self.assertNotIn("Spell failed", ate, ate)

                client.must("set skill self shove 100", "skill is now 100")
                # The fixture world's guard: not aggressive, so SHOVE gets
                # as far as the direction, and it stays where it is put.
                place_sparring_guard(client, "zfriction", SPARRING_FLOOR)
                bad = client.sync("shove guard sideways")
                self.assertIn("valid Direction", bad, bad)
                shoved = client.sync("shove guard so")
                self.assertNotIn("valid Direction", shoved, shoved)
                self.assertNotIn("aren't here", shoved, shoved)

                client.sync(f"goto {CISTERN}")
                for word in ("cistern", "nose", "tip", "moss"):
                    seen = client.sync(f"look {word}")
                    self.assertNotIn("do not see that here", seen, seen)
                self.assertIn("hook-nosed old man", client.sync("look nose"))


if __name__ == "__main__":
    unittest.main()
