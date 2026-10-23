"""Disasters and the Great Black Dragon (src/disaster.c, owner 2026-10-23).

The disasters were rebuilt after an earthquake stunned a CI fixture: a
disaster now warns its area a cycle before the first blow, never kills,
throws a character down for a moment instead of stunning them to the next
tick, and passes by the Temple, the altar, safe rooms, arenas, staff and
anybody below level 10. Four bugs went with it: a sand storm blinded only
the already blind, an earthquake stunned for no damage on water and in the
air, a lightning storm needed a cloudy sky rather than lightning, and the
messages were misspelt.

The dragon used to snatch somebody anywhere in the world every few
pulses and leave them cursed and half dead, with nothing to fight. Now it
carries one character to another outdoor room of their area and lands
beside them, scaled to their level and not aggressive: fight it for its
hoard, or walk away and it leaves.

Random strikes are off in test worlds (TOC_NO_DISASTERS); DISASTER, the
staff command, drives these.
"""
from __future__ import annotations

import pathlib
import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zdisaster1"
SQUARE = 2401            # Center of Oak Tree Square: outdoors, not safe
TEMPLE = 4207
SOURCE = (ROOT / "src" / "disaster.c").read_text(encoding="latin-1")


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


class DisasterSourceTests(unittest.TestCase):
    def body(self, signature: str) -> str:
        text = SOURCE[SOURCE.index(signature):]
        return text[:text.index("\n}\n")]

    def test_the_four_bugs_stay_fixed(self) -> None:
        # The sand storm blinds the sighted.
        self.assertIn("if ( !IS_AFFECTED(vch, AFF_BLIND) )", SOURCE)
        # A lightning storm needs lightning.
        self.assertIn("weather_info.sky == SKY_LIGHTNING ? DISASTER_LIGHTNING", SOURCE)
        # Nothing is stunned: an earthquake knocks down for a moment.
        self.assertNotIn("POS_STUNNED;", SOURCE)
        self.assertIn("disaster_knock_down( vch );", self.body("static void disaster_strike_char("))
        # The misspellings are gone, here and from update.c.
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        for typo in ("You here a", "debree", "TIMBRE", "Your surrounded", "Pacos Bill",
                     "your safe indoors", "Your quick"):
            self.assertNotIn(typo, SOURCE + update, typo)

    def test_a_disaster_never_kills_and_warns_first(self) -> None:
        harm = self.body("static void disaster_harm(")
        self.assertIn("dam = UMIN( dam, vch->hit - 1 );", harm)
        self.assertNotRegex(SOURCE, r"[^_]damage\(\s*vch")    # no blow through damage()
        update = self.body("void disaster_update( void )")
        # A new strike only warns; the blow waits for the next cycle.
        self.assertIn("continue;                   /* warned; it strikes next cycle */", update)
        # The test switch stops the random strikes and nothing else.
        self.assertIn("random_off || number_range( 1, 10000 ) > DISASTER_CHANCE", update)

    def test_the_old_kidnapper_is_retired(self) -> None:
        special = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        kidnapper = special[special.index("bool spec_kidnapper("):]
        kidnapper = kidnapper[:kidnapper.index("\n}\n")]
        self.assertIn("return false;", kidnapper)
        self.assertNotIn("affect_to_char", kidnapper)


@unittest.skipIf(SKIP is not None, SKIP or "")
class DisasterLiveTests(unittest.TestCase):
    def test_an_earthquake_warns_strikes_and_spares_the_temple(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zquaker", Levl=70, Room=SQUARE)
            make(mud, "Zshaken", Levl=20, Room=SQUARE,
                 HMV="300 300 100 100 100 100", HMVP="300 100 100")
            make(mud, "Zsheltered", Levl=20, Room=TEMPLE,
                 HMV="300 300 100 100 100 100", HMVP="300 100 100")
            make(mud, "Ztiny", Levl=5, Room=SQUARE)
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as shaken, \
                    mud.connect(timeout=120) as sheltered, mud.connect(timeout=120) as tiny:
                for client, name in ((imm, "Zquaker"), (shaken, "Zshaken"),
                                     (sheltered, "Zsheltered"), (tiny, "Ztiny")):
                    login(client, name, PW)
                    run(client, "scroll 0", 0.5)
                marks = {c: len(c.transcript) for c in (shaken, sheltered, tiny)}
                said = run(imm, "disaster earthquake", 1.0)
                self.assertIn("strikes next cycle", said)
                self.assertIn("earthquake", run(imm, "disaster", 1.0))
                # The warning comes first, everywhere in the area.
                for client in (shaken, sheltered, tiny):
                    client.drain(0.5)
                    self.assertIn("ground begins to tremble",
                                  client.transcript[marks[client]:])
                # The first blow lands within a cycle or two (6-7.5 s each).
                deadline = time.time() + 20
                while time.time() < deadline:
                    shaken.drain(1.0)
                    if "The earth heaves" in shaken.transcript[marks[shaken]:]:
                        break
                seen = shaken.transcript[marks[shaken]:]
                self.assertIn("The earth heaves", seen)
                # Thrown down or not, never stunned and never dead.
                self.assertNotIn("too stunned", run(shaken, "say still here", 4.0))
                self.assertNotIn("You have been KILLED", shaken.transcript)
                run(imm, "disaster stop", 1.0)
                for client in (sheltered, tiny):
                    client.drain(0.5)
                    self.assertNotIn("The earth heaves", client.transcript[marks[client]:])
                self.assertIn("No area is suffering", run(imm, "disaster", 1.0))

    def test_the_dragon_carries_you_off_waits_and_leaves(self) -> None:
        with LiveMud(extra_env={"TOC_DRAGON_WAIT": "12"}) as mud:
            make(mud, "Zkeeper", Levl=70, Room=TEMPLE)
            make(mud, "Zprey", Levl=20, Room=SQUARE,
                 HMV="300 300 100 100 100 100", HMVP="300 100 100")
            make(mud, "Ztiny", Levl=5, Room=SQUARE)
            with mud.connect(timeout=120) as imm, mud.connect(timeout=120) as prey, \
                    mud.connect(timeout=120) as tiny:
                for client, name in ((imm, "Zkeeper"), (prey, "Zprey"), (tiny, "Ztiny")):
                    login(client, name, PW)
                    run(client, "scroll 0", 0.5)
                # Below level 10, or indoors, it cannot take you.
                self.assertIn("cannot reach them", run(imm, "disaster dragon ztiny", 1.0))
                self.assertIn("cannot reach them", run(imm, "disaster dragon zkeeper", 1.0))

                mark = len(prey.transcript)
                tiny_mark = len(tiny.transcript)
                self.assertIn("Done.", run(imm, "disaster dragon zprey", 1.5))
                prey.drain(1.0)
                seen = prey.transcript[mark:]
                self.assertIn("snatches you up in its claws", seen)
                self.assertIn("KILL DRAGON", seen)
                tiny.drain(0.5)
                self.assertIn("carries Zprey off", tiny.transcript[tiny_mark:])
                status = run(imm, "disaster", 1.0)
                room = int(re.search(r"waits in room (\d+) with Zprey", status).group(1))
                self.assertNotEqual(room, SQUARE)
                # It does not attack: stand beside it and nothing lands.
                mark = len(prey.transcript)
                prey.drain(4.0)
                self.assertNotRegex(prey.transcript[mark:], r"(?i)dragon('s)? \w+ (hits|misses|grazes)")
                self.assertIn("black dragon", run(prey, "look", 1.0).lower())

                # Unfought, it takes off: twelve seconds, on the next cycle.
                deadline = time.time() + 35
                while time.time() < deadline:
                    prey.drain(1.0)
                    if "takes to the sky" in prey.transcript[mark:]:
                        break
                self.assertIn("takes to the sky", prey.transcript[mark:])
                self.assertIn("No area is suffering", run(imm, "disaster", 1.0))

                # Again, and this time it is fought: its hoard lies in the corpse.
                self.assertIn("Done.", run(imm, "disaster dragon zprey", 1.5))
                run(imm, "goto zprey", 1.0)
                slain = run(imm, "slay dragon", 1.5)
                self.assertIn("hoard it carried spills", slain + prey.transcript[-800:])
                corpse = run(imm, "look in corpse", 1.5)
                self.assertRegex(corpse.lower(), r"coin|gold|silver|platinum|copper")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("Black dragon: snatched Zprey (level 20) from dresden.are", log)
        # Its hoard always holds a piece of gear for the level of the one it
        # took (owner, 2026-10-23), named in the log.
        slain = re.search(r"Black dragon: slain by Zkeeper, dropping ([^\n]*)", log)
        self.assertIsNotNone(slain, log[-2000:])
        self.assertNotIn("no gear", slain.group(1))
        self.assertNotIn(f"to room {room}", log.split("Black dragon: snatched", 1)[1][:200])


if __name__ == "__main__":
    unittest.main()
