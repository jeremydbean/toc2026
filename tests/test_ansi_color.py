"""Colour codes reach players as colour, never as text (2026-10-23).

A sweep for colour bugs found these, each checked against a live server:

- Area names open with a level range in braces, and "{30 50}" begins
  with the colour token "{30": AREAS showed " 50} Anon The Abyss".
  area_shown_name() shows the range in square brackets.
- act() converted tokens in its format and sent substituted text ($t,
  $p) raw, so a coloured GOSSIP reached every listener as a literal
  "{0B".
- Every login set the colour flag back on, so COLOR OFF never survived
  a relog.
- A coloured TITLE never closed its colour, and TITLE's 45-byte cut
  could split a token in half.
- A colour slot set to "plain" emitted nothing, so the regular slot that
  closes fight and room-name lines ended no colour.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zansipass1"


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class ColourSourceTests(unittest.TestCase):
    def test_a_plain_slot_still_ends_the_colour_before_it(self) -> None:
        colour = (ROOT / "src" / "color.c").read_text(encoding="latin-1")
        marker = colour[colour.index("void color_append_marker("):]
        marker = marker[:marker.index("\n}\n")]
        self.assertIn("sequence = color_reset_code();", marker)

    def test_act_converts_tokens_in_substituted_text(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        act = comm[comm.index("void act_new("):]
        act = act[:act.index("\n}\n")]
        self.assertIn("color_parse_slot( i + 1, &color_slot )", act)

    def test_a_login_keeps_the_saved_colour_choice(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        self.assertNotIn("ch->pcdata->color = true;", comm)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ColourLiveTests(unittest.TestCase):
    def test_colour_codes_never_reach_a_player_as_text(self) -> None:
        with LiveMud() as mud:
            for name in ("Zspeaker", "Zlistener"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=20, Room=4207)

            with mud.connect(timeout=120) as speaker, mud.connect(timeout=120) as listener:
                login(speaker, "Zspeaker", PW)
                login(listener, "Zlistener", PW)
                for client in (speaker, listener):
                    run(client, "scroll 0", 1.0)

                # AREAS: the level range in brackets, not half eaten.
                areas = run(listener, "areas", 2.0)
                self.assertIn("[30 50]", areas)
                self.assertNotIn(" 50}", areas)

                # A coloured gossip is colour for the listener, not text.
                run(speaker, "gossip {0Bshiny{00 words", 1.5)
                heard = run(listener, "", 1.0) + listener.transcript[-400:]
                self.assertIn("shiny words", heard)
                self.assertNotIn("{0B", heard)

                # A coloured title closes its colour; a cut never splits a
                # token ("x" * 43 leaves the token's "{0" at the cut).
                run(speaker, "title {0Cthe Bright", 1.0)
                run(speaker, "save", 1.0)
                run(listener, "title " + "x" * 43 + "{0Ctail", 1.0)
                who = run(listener, "who", 1.5)
                self.assertNotIn("{0", who)

                # COLOR OFF survives a relog.
                self.assertIn("disabled", run(listener, "color off", 1.0))
                listener.send("quit")
                listener.wait_closed()
                speaker.send("quit")
                speaker.wait_closed()

            with mud.connect(timeout=120) as listener:
                login(listener, "Zlistener", PW)
                run(listener, "save", 1.0)
                listener.send("quit")
                listener.wait_closed()

            speaker_file = (mud.player_dir / "Zspeaker").read_text(encoding="latin-1")
            listener_file = (mud.player_dir / "Zlistener").read_text(encoding="latin-1")

        title = next(l for l in speaker_file.splitlines() if l.startswith("Titl"))
        self.assertTrue(title.rstrip("~").endswith("{00"), title)
        self.assertIn("ColFlag 0", listener_file)
        listener_title = next(l for l in listener_file.splitlines() if l.startswith("Titl"))
        self.assertNotIn("{0~", listener_title)
        self.assertTrue(listener_title.rstrip("~").rstrip().endswith("x"), listener_title)


if __name__ == "__main__":
    unittest.main()
