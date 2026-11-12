"""Char.Items, the Mudlet package's Items pane (src/gmcp.c, review 2026-11-12).

Two faults, both invisible from the game's own side:

* The payload was built in a 4,096-byte array for up to a hundred carried
  things and handed to telnet_send_gmcp, whose frame is 2,048 bytes. Seventy-
  two things with 45-letter names (REDEEM RESTRING allows 45) ran off the
  end: toc_strlcat cut the JSON mid-string, nothing reached the client, and
  the snapshot was marked sent, so the pane went on showing a list that was
  no longer true. It is now a bounded DString, sent whole through
  telnet_send_gmcp_large; a list cut to its bounds says so in
  inventory_total and truncated, and the package shows the cut.
* The "has it changed" signature hashed vnums and wear slots only, so a
  weapon renamed with REDEEM RESTRING, or a thing turning invisible or
  coming into sight with DETECT INVIS, left the pane stale. It now hashes
  the name as sent and the sight test the payload uses.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from live_mud import (IAC, DO, TELOPT_GMCP, LiveMud, create_character, login,
                      patch_player_file, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zitempass1"
TEMPLE = 4207
VEST, DAGGER, SWORD = 3703, 3701, 3702      # school.are's sub issue kit
ITEM_INVIS = 32                             # extra flag F
WIELD = 16


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    depth, seen = 0, False
    for i in range(start, len(text)):
        if text[i] == "{":
            depth, seen = depth + 1, True
        elif text[i] == "}":
            depth -= 1
            if seen and depth == 0:
                return text[start:i + 1]
    raise AssertionError("unterminated: " + signature)


def obj(vnum: int, short: str | None = None, wear: int = -1, extra: int | None = None) -> str:
    lines = ["#O", "Vnum %d" % vnum, "Nest 0", "Wear %d" % wear, "Lev 1", "Cond 100"]
    if short is not None:
        lines.append("ShD %s~" % short)
    if extra is not None:
        lines.append("ExtF %d" % extra)
    return "\n".join(lines) + "\nEnd\n\n"


def add_lines(mud: LiveMud, name: str, objects=(), player_lines=()) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if player_lines:
        at = text.index("\nEnd\n")
        text = text[:at] + "\n" + "\n".join(player_lines) + text[at:]
    text = text.replace("#END", "".join(objects) + "#END", 1)
    path.write_text(text, encoding="latin-1")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.drain(1.0)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError("character did not leave the world")
    patch_player_file(mud, name, **fields)


def items_messages(client) -> list[str]:
    """Every Char.Items payload so far, as text."""
    out = []
    for block in client.subnegotiations(TELOPT_GMCP):
        text = block.decode("latin-1")
        if text.startswith("Char.Items "):
            out.append(text.split(" ", 1)[1])
    return out


def last_items(client) -> dict:
    payloads = items_messages(client)
    if not payloads:
        raise AssertionError("no Char.Items was sent")
    return json.loads(payloads[-1])


def names(payload: dict) -> list[str]:
    return [entry["name"] for entry in payload["inventory"]]


def cast(client, spell_and_target: str) -> str:
    """CAST until the spell is not lost to concentration."""
    reply = ""
    for _ in range(6):
        reply = client.sync("cast %s" % spell_and_target)
        if "lost your concentration" not in reply:
            return reply
    return reply


class SourceTests(unittest.TestCase):
    def test_the_payload_is_bounded_and_sent_whole(self) -> None:
        gmcp = source("gmcp.c")
        body = function_body(gmcp, "void gmcp_send_items(")
        self.assertIn("dstring_init_limit( &out, GMCP_ITEMS_MAX_BYTES )", body)
        self.assertIn("telnet_send_gmcp_large( d, \"Char.Items\"", body)
        self.assertNotIn("telnet_send_gmcp( d, \"Char.Items\"", body)
        self.assertNotIn("toc_strlcat", body, "the old fixed-array build")
        for key in ("inventory_total", "equipment_total", "truncated", "equipment_truncated"):
            self.assertIn('\\"%s\\"' % key, body)
        # The snapshot is marked only once the list really went out.
        mark = body.index("d->gmcp_items_valid = true")
        self.assertIn("if ( sent )", body[body.rindex("\n", 0, mark) - 200:mark])

    def test_the_signature_covers_what_the_pane_shows(self) -> None:
        body = function_body(source("gmcp.c"), "static uint32_t gmcp_items_signature(")
        self.assertIn("obj->short_descr", body)
        self.assertIn("can_see_obj( ch, obj )", body)
        self.assertNotIn("count < 200", body, "a change past the 200th thing was missed")

    def test_large_frames_are_their_own_function(self) -> None:
        proto = source("telnet_proto.c")
        large = function_body(proto, "bool telnet_send_gmcp_large(")
        self.assertIn("json_len > max_json", large)
        # The ordinary sender still drops what its frame cannot hold.
        small = function_body(proto, "void telnet_send_gmcp(")
        self.assertIn("if ( need >= sizeof(buf) )", small)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_a_long_list_arrives_whole_and_changes_are_sent(self) -> None:
        long_names = ["a sub issue vest of the tests, number %03d xyz" % i for i in range(72)]
        self.assertTrue(all(len(n) == 45 for n in long_names))
        odd = 'a "quoted" \\ vest, {0Bcaf\xe9{00 style'
        hoard_names = [("a heavy sub issue vest from the long hoard %03d " % i).ljust(250, "z")
                       for i in range(250)]
        with LiveMud() as mud:
            make(mud, "Zitemer", Levl=20, Room=TEMPLE, Cla=0,
                 HMV="500 500 2000 2000 500 500", HMVP="500 2000 500")
            add_lines(mud, "Zitemer",
                      [obj(VEST, n) for n in long_names]
                      + [obj(VEST, odd),
                         obj(VEST, "a vest nobody can see", extra=ITEM_INVIS),
                         obj(DAGGER),
                         obj(SWORD, "the sword the fixture wields", wear=WIELD)],
                      ["Achv boss-blaine 1700000000", "Achv boss-roland 1700000000",
                       "Sk 100 'detect invis'"])
            make(mud, "Zitemstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zitemhoard", Levl=20, Room=TEMPLE)
            add_lines(mud, "Zitemhoard", [obj(VEST, n) for n in hoard_names])

            with mud.connect(timeout=120) as client:
                client.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(client, "Zitemer", PW)
                client.drain(2.0)
                client.sync("look")

                # Seventy-two 45-letter names, quoting, a colour token and a
                # Latin-1 letter: one whole, readable payload.
                first = last_items(client)
                shown = names(first)
                self.assertEqual(first["truncated"], 0, first.get("inventory_total"))
                # 72 long names, the odd one and the dagger, beside whatever
                # a new character starts with; the invisible vest is not
                # seen and the sword is worn.
                own = first["inventory_total"] - 74
                self.assertGreaterEqual(own, 0, shown)
                for name in long_names:
                    self.assertIn(name, shown)
                self.assertIn('a "quoted" \\ vest, caf\xe9 style', shown)
                self.assertIn("a sub issue dagger", shown)
                self.assertNotIn("a vest nobody can see", shown)
                self.assertEqual(len(shown), first["inventory_total"])
                self.assertIn(
                    {"name": "the sword the fixture wields", "slot": WIELD}, first["equipment"])
                self.assertEqual(first["equipment_total"], len(first["equipment"]))
                self.assertEqual(first["equipment_truncated"], 0)
                self.assertGreater(len(items_messages(client)[-1]), 2048,
                                   "the payload fits the old frame: the test proves nothing")

                # Nothing changed: no new Char.Items at the next prompts.
                count = len(items_messages(client))
                client.sync("look")
                client.sync("look")
                client.sync("worth")
                self.assertEqual(len(items_messages(client)), count,
                                 "an unchanged inventory was sent again")

                # REDEEM RESTRING: same vnum, same slot, a new name.
                reply = client.sync("redeem restring dagger Zed's dagger of the pane test")
                self.assertIn("is now called", reply)
                client.sync("look")
                renamed = names(last_items(client))
                self.assertIn("Zed's dagger of the pane test", renamed)
                self.assertNotIn("a sub issue dagger", renamed)

                # Sight going and coming back with nothing moved: the room
                # made dark (can_see_obj sees nothing carried in the dark
                # without infravision), then lit again.
                # A lit light lights the room, so the starting banner comes
                # off first (a wear change, sent as one) and staff set the
                # flag from elsewhere.
                client.sync("remove banner")
                client.sync("look")
                self.assertFalse([e for e in last_items(client)["equipment"] if e["slot"] == 0])
                with mud.connect(timeout=120) as staff:
                    login(staff, "Zitemstaff", PW)
                    staff.must("goto 2401", "Oak")
                    count = len(items_messages(client))
                    staff.must("set room %d flags +dark" % TEMPLE, "dark")
                    client.sync("look")
                    self.assertGreater(len(items_messages(client)), count,
                                       "the dark changed nothing the pane was sent")
                    dark = last_items(client)
                    self.assertFalse(set(long_names) & set(names(dark)), names(dark))
                    self.assertNotIn({"name": "the sword the fixture wields", "slot": WIELD},
                                     dark["equipment"])
                    staff.must("set room %d flags -dark" % TEMPLE, "flags")
                    client.sync("look")
                    lit = last_items(client)
                    self.assertTrue(set(long_names) <= set(names(lit)))
                    self.assertIn({"name": "the sword the fixture wields", "slot": WIELD},
                                  lit["equipment"])
                    own = lit["inventory_total"] - 74       # the banner is carried now
                    staff.send("quit")

                # DETECT INVIS: the invisible vest comes into sight.
                count = len(items_messages(client))
                reply = cast(client, "'detect invis'")
                self.assertIn("eyes tingle", reply.lower())
                client.sync("look")
                self.assertGreater(len(items_messages(client)), count)
                seen = last_items(client)
                self.assertEqual(seen["inventory_total"], 75 + own)
                self.assertIn("a vest nobody can see", names(seen))
                client.send("quit")
                self.assertTrue(client.wait_closed())

            # Two hundred and fifty 250-letter names: cut to the byte bound,
            # whole, and the cut is counted.
            with mud.connect(timeout=120) as client:
                client.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                login(client, "Zitemhoard", PW)
                client.drain(2.0)
                client.sync("look")
                raw = items_messages(client)[-1]
                payload = json.loads(raw)
                self.assertLessEqual(len(raw.encode("latin-1")), 24 * 1024)
                hoard = set(hoard_names)
                listed = [n for n in names(payload) if n in hoard]
                starter = len(payload["inventory"]) - len(listed)
                self.assertEqual(payload["inventory_total"], 250 + starter)
                self.assertGreater(payload["truncated"], 0)
                self.assertEqual(len(payload["inventory"]) + payload["truncated"],
                                 payload["inventory_total"])
                # In the order the game keeps them (the last read is first),
                # whole entries, only the tail left off.
                self.assertIn(listed, (hoard_names[:len(listed)],
                                       hoard_names[::-1][:len(listed)]),
                              "a cut list keeps its order and drops only the tail")
                self.assertTrue(re.fullmatch(r"\{.*\}", raw, re.S))
                client.send("quit")
                self.assertTrue(client.wait_closed())


if __name__ == "__main__":
    unittest.main()
