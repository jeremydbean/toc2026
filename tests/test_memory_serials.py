"""Memory safeguards: an address reused by the same kind, and stand-ins.

The address set (src/memtrack.c) answered "live" for any address holding a
character, object or descriptor of the kind asked about, so a stale
pointer whose address had been freed and handed to a new block of the same
kind read as live and was followed (AGENTS.md, Memory Safeguards: "What it
cannot see"). And the stand-ins that are never allocated -- the descriptor
offline_player_load fills, gear_compare's candidate object, a corpse
record's vessel -- were never registered, so they read as freed.

Since 2026-11-12:

1. Every registration has a serial of its own. The long-lived pointers --
   fighting, master, leader, pet, hunting, reply, questgiver, desc,
   in_object, an object's trapped, the hunter list, a descriptor's
   character, original and snoop_by -- keep a MEM_REF beside them, written
   only by SET_CHAR_REF, SET_OBJ_REF and SET_DESC_REF, and the sweep and
   the hot spots answer MEM_STATE_REUSED when the address's serial is no
   longer the one the pointer was set with: "-> reused", repaired as
   "freed", never read.
2. Stand-ins are registered while in use (mem_standin_begin/_end): live,
   never released, and the sweep says if one is left registered.

The C harnesses (tests/test_memory_ranges.py) play the set; this module
holds the source to the rules and plays MEMCHECK SELFTEST REUSE live.
"""

from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PW = "Zmemserialpw1"

# Field -> (struct it lives on, kind it points at).
REF_FIELDS = {
    "fighting": ("char_data", "CHAR"), "master": ("char_data", "CHAR"),
    "leader": ("char_data", "CHAR"), "pet": ("char_data", "CHAR"),
    "hunting": ("char_data", "CHAR"), "reply": ("char_data", "CHAR"),
    "questgiver": ("char_data", "CHAR"), "desc": ("char_data", "DESC"),
    "in_object": ("char_data", "OBJ"), "trapped": ("obj_data", "CHAR"),
    "character": ("descriptor_data", "CHAR"), "original": ("descriptor_data", "CHAR"),
    "snoop_by": ("descriptor_data", "DESC"),
}


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="latin-1")


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError(f"no end to {signature}")


def struct_body(text: str, name: str) -> str:
    return function_body(text, f"struct  {name}\n") if f"struct  {name}\n" in text \
        else function_body(text, f"struct {name}\n")


class SerialSourceTests(unittest.TestCase):
    def test_no_long_lived_pointer_is_written_by_hand(self) -> None:
        """A write that skips the macro leaves the ref naming the old
        pointer: the check then falls back to the address (and says so),
        and the reuse it exists to see goes unseen. One set comparison."""
        fields = "|".join(REF_FIELDS)
        raw = re.compile(rf"(?:->|\.)(?:{fields})\s*=(?!=)")
        hunter = re.compile(r"hunter_list\s*\[[^\]]*\]\s*\.\s*ch\s*=(?!=)")
        found = set()
        for path in sorted(SRC.glob("*.c")):
            for n, line in enumerate(strip_comments(path.read_text(encoding="latin-1"))
                                     .split("\n"), 1):
                if raw.search(line) or hunter.search(line):
                    found.add(f"{path.name}:{n}: {line.strip()}")
        self.assertEqual(found, set())

    def test_every_field_keeps_its_ref(self) -> None:
        merc = strip_comments(source("merc.h"))
        for field, (struct, _kind) in REF_FIELDS.items():
            self.assertRegex(struct_body(merc, struct), rf"MEM_REF\s+{field}_ref;", field)
        self.assertRegex(struct_body(merc, "hunter_data"), r"MEM_REF\s+ch_ref;")
        for kind in ("CHAR", "OBJ", "DESC"):
            macro = merc[merc.index(f"#define SET_{kind}_REF"):]
            macro = macro[:macro.index("while ( 0 )")]
            self.assertIn("field##_ref", macro, kind)
            self.assertIn(f"MEMTRACK_KIND_{kind}", macro, kind)

    def test_the_sweep_and_hot_spots_ask_with_the_ref(self) -> None:
        guard = strip_comments(source("memguard.c"))
        for field, (struct, kind) in REF_FIELDS.items():
            holder = {"char_data": "ch", "obj_data": "obj", "descriptor_data": "d"}[struct]
            label = f"d {field}" if struct == "descriptor_data" else field
            self.assertRegex(
                guard,
                rf'mg_ref\(\s*"{label}",\s*{holder}->{field},\s*&{holder}->{field}_ref,\s*'
                rf'MEMTRACK_KIND_{kind}\s*\)', field)
        self.assertRegex(guard, r'mg_ref\(\s*"hunter_list",\s*hunter,\s*&hunter_list\[slot\]\.ch_ref')
        # A reused address is reported and never read for a label.
        self.assertIn("-> reused %s (its address now holds a newer one; not read)", guard)
        report = function_body(guard, "static void mg_report_state(")
        self.assertIn("if ( !reused )", report)

    def test_the_ref_check_reads_only_the_address_set(self) -> None:
        recycle = strip_comments(source("recycle.c"))
        check = function_body(recycle, "int mem_ref_liveness( const void *p, const MEM_REF *ref, int kind )")
        self.assertNotRegex(check[check.index("{"):], r"\bp->|\*\s*p\b")
        self.assertIn("memtrack_lookup( p, kind, &serial )", check)
        self.assertIn("MEM_STATE_REUSED", check)
        track = strip_comments(source("memtrack.c"))
        self.assertIn("mt_next_serial++", function_body(track, "static bool mt_register("))

    def test_stand_ins_are_registered_while_in_use(self) -> None:
        save = strip_comments(source("save.c"))
        load = function_body(save, "CHAR_DATA *offline_player_load(")
        self.assertLess(load.index("mem_standin_begin( d, MEMTRACK_KIND_DESC );"),
                        load.index("load_char_obj( d, proper )"))
        # Every way out after the begin ends it first.
        after = load[load.index("mem_standin_begin("):]
        returns = [m.start() for m in re.finditer(r"\breturn\b", after)]
        self.assertEqual(len(returns), 3)
        for pos in returns:
            self.assertIn("mem_standin_end( d );", after[max(0, pos - 200):pos], pos)
        vessel = function_body(save, "int corpse_file_read(")
        self.assertLess(vessel.index("mem_standin_begin( &vessel, MEMTRACK_KIND_CHAR );"),
                        vessel.index("read_objects_aside( &vessel"))
        self.assertLess(vessel.index("read_objects_aside( &vessel"),
                        vessel.index("mem_standin_end( &vessel );"))
        gear = strip_comments(source("gear_compare.c"))
        for sig in ("static void gear_find_guardian_drops(", "static void gear_find_upgrades("):
            fn = function_body(gear, sig)
            self.assertNotRegex(fn, r"\breturn\b", sig)
            self.assertLess(fn.index("mem_standin_begin( &candidate, MEMTRACK_KIND_OBJ );"),
                            fn.index("gear_object_from_index( &candidate"), sig)
            self.assertIn("mem_standin_end( &candidate );", fn, sig)
        recycle = strip_comments(source("recycle.c"))
        for release in ("void char_data_release( CHAR_DATA *ch )",
                        "void obj_data_release( OBJ_DATA *obj )",
                        "void descriptor_data_release( DESCRIPTOR_DATA *d )"):
            self.assertIn("memtrack_is_standin(", function_body(recycle, release), release)
        sweep = function_body(strip_comments(source("memguard.c")), "void memguard_sweep( void )")
        self.assertIn("recycle_standins( &now, &ever );", sweep)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SerialLiveTests(unittest.TestCase):
    def test_a_reply_to_a_reused_address_is_caught_by_its_serial(self) -> None:
        """MEMCHECK SELFTEST REUSE ends the mobile's registration behind the
        caller's REPLY and registers its address again as a new character,
        as the allocator does. By address it reads live -- the old sweep
        passed it -- and the serial says reused."""
        env = {"TOC_MEMCHECK_SELFTEST": "1", "TOC_MEM_QUARANTINE_SECS": "30"}
        with LiveMud(extra_env=env) as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zmemserial", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmemserial", Levl=70, Room=4207)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zmemserial", PW)
                staff.sync("scroll 0")
                before = staff.must("memcheck", "Memory safeguards")
                self.assertIn("Stale pointers caught since boot: 0.", before)
                staff.must("memcheck selftest reuse", "reused")

                log = mud.root / "log" / "toc.log"
                wanted = re.compile(r"MEMORY: stale reply on Zmemserial -> reused character "
                                    r"\(its address now holds a newer one; not read\)")
                deadline = time.monotonic() + 15
                text = ""
                while time.monotonic() < deadline:
                    text = log.read_text(encoding="latin-1", errors="replace")
                    if wanted.search(text):
                        break
                    staff.drain(0.5)
                self.assertRegex(text, wanted)

                after = staff.must("memcheck", "Memory safeguards")
                self.assertIn("Stale pointers caught since boot: 1.", after)
                self.assertIn("reused by the same kind: 1;", after)
                self.assertRegex(after, r"reply\s+1")
                self.assertNotIn("written without their serial", after)
                # Repaired: REPLY no longer follows it, and the game answers.
                self.assertIn("They aren't here.", staff.sync("reply hello"))
                self.assertIn("Zmemserial", staff.sync("who"))
                journal = (mud.root / "log" / "play.tsv").read_text(encoding="latin-1")
                self.assertIn("MEMORY: stale reply -> reused character, repaired", journal)
                staff.send("quit")
                staff.wait_closed()

    def test_stand_ins_come_and_go_with_their_commands(self) -> None:
        """COMPARE UPGRADES uses two stack candidates and GRANTPSI on a
        player who is not in the game a stack descriptor: each is
        registered while the command runs and gone after, so the sweep
        finds none left over."""
        with LiveMud() as mud:
            for name in ("Zmemstand", "Zmemaway"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmemstand", Levl=70, Room=4207)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zmemstand", PW)
                staff.sync("scroll 0")
                before = staff.must("memcheck", "Memory safeguards")
                self.assertRegex(before, r"Stand-ins: 0 registered now, 0 since boot")
                staff.sync("compare upgrades")
                staff.must("grantpsi zmemaway", "Zmemaway")
                staff.drain(2.5)   # at least two sweeps
                after = staff.must("memcheck", "Memory safeguards")
                found = re.search(r"Stand-ins: (\d+) registered now, (\d+) since boot; "
                                  r"(\d+) sweeps? found one left over", after)
                self.assertIsNotNone(found, after)
                now, ever, leaks = map(int, found.groups())
                self.assertEqual(now, 0, after)
                self.assertGreaterEqual(ever, 3, after)
                self.assertEqual(leaks, 0, after)
                self.assertIn("Stale pointers caught since boot: 0.", after)
                staff.send("quit")
                staff.wait_closed()


if __name__ == "__main__":
    unittest.main()
