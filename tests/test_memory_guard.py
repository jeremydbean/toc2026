"""Memory safeguards: a stale pointer is seen at once, logged and survived.

Since ROM's pools went (2026-11-11), a character, object or descriptor
handed to src/recycle.c is freed for real, and a pointer that outlives it
reads freed memory. The safeguards (owner, 2026-11-11):

1. Liveness by address (memtrack.c, 2026-11-12): registered live when
   made, dead when released, forgotten when freed, and looked up without
   reading the block -- so a pointer whose target the quarantine has
   already freed reads as "freed" instead of being read (the old
   MEM_ALIVE_*/MEM_DEAD_* tag check was itself a use after free then).
2. Quarantine: a released block is kept whole for MEM_QUARANTINE_SECS
   (TOC_MEM_QUARANTINE_SECS overrides; 0 under ASan) and a count cap, so a
   stale read behaves as the old pool did and the dead tag can be seen.
3. A sweep once a second (memguard.c) checks every stored pointer, writes
   "MEMORY: stale <field> on <who> -> dead <kind> (...)" to log/toc.log,
   a nameless BUG row to the play journal and a WIZINFO, and repairs it.
4. The hot spots that follow a pointer on a timer ask the same check.
5. crash.log carries a backtrace.
6. MEMCHECK shows it; MEMCHECK SELFTEST (TOC_MEMCHECK_SELFTEST=1 only)
   retires a mobile behind the caller's REPLY for the sweep to catch.
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
PW = "Zmemguardpw1"


def source(name: str) -> str:
    return (SRC / name).read_text(encoding="latin-1")


def body(name: str, start: str) -> str:
    text = source(name)
    return text.split(start, 1)[1].split("\n}\n", 1)[0]


class MemoryGuardSourceTests(unittest.TestCase):
    def test_every_release_tags_the_block_dead_and_quarantines_it(self) -> None:
        recycle = source("recycle.c")
        for kind, release in (("CHAR", "void char_data_release( CHAR_DATA *ch )"),
                              ("OBJ", "void obj_data_release( OBJ_DATA *obj )"),
                              ("DESC", "void descriptor_data_release( DESCRIPTOR_DATA *d )")):
            fn = body("recycle.c", release)
            self.assertIn(f"MEM_DEAD_{kind}", fn, release)
            self.assertIn("quarantine_push(", fn, release)
            self.assertIn("released twice", fn, release)
        self.assertIn('getenv( "TOC_MEM_QUARANTINE_SECS" )', recycle)
        self.assertIn("__SANITIZE_ADDRESS__", recycle)
        self.assertIn("MEM_QUARANTINE_MAX", body("recycle.c", "void recycle_flush( void )"))
        # Only recycle_flush frees a quarantined block.
        self.assertEqual(recycle.count("quarantine_free_block( e );"), 1)

    def test_everything_made_is_tagged_alive(self) -> None:
        self.assertIn("ch->mem_magic               = MEM_ALIVE_CHAR;",
                      body("db.c", "void clear_char( CHAR_DATA *ch )"))
        self.assertIn("MEM_ALIVE_OBJ", body("db.c", "OBJ_DATA *create_object("))
        self.assertIn("MEM_ALIVE_OBJ", source("save.c"))
        self.assertIn("dnew->mem_magic = MEM_ALIVE_DESC;", source("comm.c"))
        # free_char names a player for the quarantine before the name goes.
        free_char = body("db.c", "void free_char( CHAR_DATA *ch )")
        self.assertLess(free_char.index("recycle_label_char( ch );"),
                        free_char.index("free_string( ch->name"))

    def test_the_sweep_checks_every_stored_pointer(self) -> None:
        guard = source("memguard.c")
        for check in ("char_is_live( ch->master )", "char_is_live( ch->leader )",
                      "char_is_live( ch->pet )", "char_is_live( ch->questgiver )",
                      "desc_is_live( ch->desc )", "obj_is_live( ch->in_object )",
                      "obj_is_live( ch->pcdata->resurrect_corpse )",
                      "&ch->carrying", "&ch->pcdata->stash",
                      "char_is_live( obj->trapped )", "char_is_live( obj->carried_by )",
                      "obj_is_live( obj->in_obj )", "&obj->contains",
                      "&room->contents", "&room->people",
                      "desc_is_live( d->snoop_by )", "char_is_live( d->original )",
                      "char_is_live( d->character )", "desc_liveness( d )",
                      "memguard_fighting_ok( ch )", "memguard_hunting_ok( ch )",
                      "memguard_reply_ok( ch )", "memguard_hunter_slot_ok( i )",
                      "FOR_EACH_CHARACTER", "FOR_EACH_OBJECT"):
            self.assertIn(check, guard, check)
        self.assertIn('"MEMORY: stale %s on %s -> dead %s (%s)"', guard)
        self.assertIn("log_string( line );", guard)
        self.assertIn("playlog_bug( journal );", guard)
        self.assertIn("wizinfo( notice, level );", guard)
        # The repairs never follow the dead pointer into its strings.
        fighting = body("memguard.c", "bool memguard_fighting_ok( CHAR_DATA *ch )")
        self.assertLess(fighting.index("ch->fighting = NULL;"),
                        fighting.index("stop_fighting( ch, FALSE );"))
        self.assertNotIn("do_stop_hunting", body("memguard.c", "bool memguard_hunting_ok( CHAR_DATA *ch )"))
        self.assertIn("src/memguard.c", (ROOT / "CMakeLists.txt").read_text())

    def test_the_sweep_runs_once_a_second(self) -> None:
        handler = body("update.c", "void update_handler( void )")
        self.assertIn("pulse_memory\t= PULSE_PER_SECOND;", handler)
        self.assertLess(handler.index("memguard_sweep\t( );"), handler.index("area_update\t( );"))

    def test_the_hot_spots_ask_first(self) -> None:
        violence = body("fight.c", "void violence_update( void )")
        self.assertLess(violence.index("memguard_fighting_ok( ch )"),
                        violence.index("victim = ch->fighting"))
        hunt = body("hunt.c", "void hunt_victim(CHAR_DATA *ch, int ANNOY)")
        self.assertLess(hunt.index("memguard_hunting_ok( ch )"), hunt.index("ch->hunting->in_room"))
        self.assertIn("memguard_hunter_slot_ok( i )", body("update.c", "void hunting_update( void )"))
        reply = body("act_comm.c", "void do_reply( CHAR_DATA *ch, char *argument )")
        self.assertLess(reply.index("memguard_reply_ok( ch );"), reply.index("victim = ch->reply"))
        comm = source("comm.c")
        output = comm[comm.index('playlog_phase_enter( "output" );'):]
        self.assertLess(output.index("memguard_descriptor_ok( d );"),
                        output.index("if ( d->write_failed )"))

    def test_the_crash_handler_writes_a_backtrace(self) -> None:
        playlog = source("playlog.c")
        handler = body("playlog.c", "static void crash_handler( int sig )")
        self.assertIn("backtrace( frames, CRASH_FRAMES )", handler)
        self.assertIn("backtrace_symbols_fd( frames, depth, crash_fd );", handler)
        for unsafe in ("printf", "fopen", "malloc", "log_string", "backtrace_symbols("):
            self.assertNotIn(unsafe, handler)
        self.assertIn("#if defined(__GLIBC__)", playlog)
        self.assertLess(playlog.index("#define _GNU_SOURCE"), playlog.index("#include"))
        boot = body("playlog.c", "void playlog_boot( void )")
        self.assertIn("(void) backtrace( warm, 2 );", boot)
        self.assertIn("-rdynamic", (ROOT / "Makefile").read_text())
        self.assertIn("ENABLE_EXPORTS ON", (ROOT / "CMakeLists.txt").read_text())

    def test_memcheck_is_staff_and_steals_no_abbreviation(self) -> None:
        interp = source("interp.c")
        memory = interp.index('{ "memory",')
        memcheck = interp.index('{ "memcheck",')
        self.assertLess(memory, memcheck, "MEM must stay MEMORY")
        self.assertRegex(interp[memcheck:memcheck + 120], r"do_memcheck,\s*POS_DEAD,\s*IM,")
        selftest = body("memguard.c", "static void memcheck_selftest( CHAR_DATA *ch )")
        self.assertIn('getenv( "TOC_MEMCHECK_SELFTEST" )', selftest)
        # Retired as a bug would leave it: no extract_char, no free_char --
        # at the end of the next sweep, so the sweep after it is the first
        # to look, across at least one recycle_flush.
        retire = body("memguard.c", "static void mg_selftest_retire( void )")
        for part in (selftest, retire):
            self.assertNotIn("extract_char", part)
            self.assertNotIn("free_char", part)
        self.assertIn("char_data_release( mob );", retire)
        sweep = body("memguard.c", "void memguard_sweep( void )")
        self.assertIn("mg_selftest_retire( );", sweep)
        self.assertIn("60 MEMCHECK~", (ROOT / "area" / "commands.are").read_text(encoding="latin-1"))

    def test_liveness_never_reads_the_block(self) -> None:
        """A check of a pointer whose target may be freed reads only the
        address set (review, 2026-11-12: the mem_magic read was a use after
        free once the quarantine had freed the block)."""
        recycle = source("recycle.c")
        for sig in ("bool char_data_released( const CHAR_DATA *ch )",
                    "int char_liveness( const CHAR_DATA *ch )",
                    "bool char_is_live( const CHAR_DATA *ch )",
                    "bool obj_data_released( const OBJ_DATA *obj )",
                    "int obj_liveness( const OBJ_DATA *obj )",
                    "bool obj_is_live( const OBJ_DATA *obj )",
                    "int desc_liveness( const DESCRIPTOR_DATA *d )",
                    "bool desc_is_live( const DESCRIPTOR_DATA *d )",
                    "static int recycle_liveness( const void *p, int kind )"):
            fn = body("recycle.c", sig)
            self.assertNotIn("->", fn, sig)
            self.assertNotIn("mem_magic", fn, sig)
        # Registered at every allocation, marked dead at every release, and
        # forgotten before the free.
        for new, kind in (("CHAR_DATA *char_data_new( void )", "Q_CHAR"),
                          ("OBJ_DATA *obj_data_new( void )", "Q_OBJ"),
                          ("DESCRIPTOR_DATA *descriptor_data_new( void )", "Q_DESC")):
            self.assertIn("recycle_track( ", body("recycle.c", new), new)
            self.assertIn(kind, body("recycle.c", new), new)
        for release in ("void char_data_release( CHAR_DATA *ch )",
                        "void obj_data_release( OBJ_DATA *obj )",
                        "void descriptor_data_release( DESCRIPTOR_DATA *d )"):
            self.assertIn("memtrack_dead(", body("recycle.c", release), release)
        free_block = body("recycle.c", "static void quarantine_free_block( QUARANTINE_ENTRY *e )")
        self.assertLess(free_block.index("memtrack_forget( e->ptr );"),
                        free_block.index("free( e->ptr );"))
        self.assertIn("src/memtrack.c", (ROOT / "CMakeLists.txt").read_text())
        self.assertNotIn("mem_magic", source("memguard.c"))

    def test_a_freed_list_member_is_cut_never_followed(self) -> None:
        """A dead (quarantined) list member is unlinked through its own
        link; a freed one cannot be read, so the list is cut there and
        mg_relink finds the rest from their own side."""
        guard = source("memguard.c")
        for sig in ("static void mg_obj_list(", "static void mg_char_room_list("):
            fn = body("memguard.c", sig)
            dead = fn.index("if ( state == MEM_STATE_DEAD )")
            self.assertIn("next_", fn[dead:dead + 120], sig)
            self.assertIn("*link = NULL;", fn[dead:], sig)
        sweep = body("memguard.c", "void memguard_sweep( void )")
        self.assertIn("mg_desc_cut = TRUE;", sweep)
        self.assertIn("mg_relink( );", sweep)
        relink = body("memguard.c", "static void mg_relink( void )")
        for side in ("obj->carried_by->carrying", "obj->in_obj->contains",
                     "obj->in_room->contents", "ch->in_room->people", "descriptor_list = ch->desc"):
            self.assertIn(side, relink)
        self.assertIn('"MEMORY: stale %s on %s -> freed %s (gone from quarantine; not read)"', guard)


@unittest.skipIf(SKIP is not None, SKIP or "")
class MemoryGuardLiveTests(unittest.TestCase):
    def test_a_stale_reply_is_caught_logged_and_repaired(self) -> None:
        # Long enough for the sweep to find the block still in quarantine in
        # every build; ASan's own default is no window at all.
        self.play_selftest("30", "dead", r"\(mob \d+ ")

    def test_a_reply_to_a_freed_block_is_caught_without_reading_it(self) -> None:
        """No window: the retired mobile is freed at the next pass, before
        any sweep looks. The sweep used to read its tag -- a use after free
        ASan stopped the server on -- and now asks the address set, says
        "freed" and clears the pointer (review, 2026-11-12)."""
        self.play_selftest("0", "freed", r"\(gone from quarantine; not read\)")

    def play_selftest(self, window: str, state: str, detail: str) -> None:
        env = {"TOC_MEMCHECK_SELFTEST": "1", "TOC_MEM_QUARANTINE_SECS": window}
        with LiveMud(extra_env=env) as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zmemguard", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zmemguard", Levl=70, Room=4207)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zmemguard", PW)
                staff.sync("scroll 0")
                before = staff.must("memcheck", "Memory safeguards")
                self.assertIn("Stale pointers caught since boot: 0.", before)
                staff.must("memcheck selftest", "Self-test")

                log = mud.root / "log" / "toc.log"
                wanted = re.compile(rf"MEMORY: stale reply on Zmemguard -> {state} character {detail}")
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
                self.assertRegex(after, r"reply\s+1")
                self.assertIn("MEMORY: stale reply on Zmemguard", after)
                self.assertRegex(after, r"Sweep: \d+ runs; last \d+\.\d{3} ms")
                self.assertRegex(after, r"Tracked by address: \d+ live, \d+ in quarantine")
                if state == "freed":
                    self.assertIn("of them already freed: 1;", after)
                else:
                    self.assertNotIn("already freed", after)

                # Repaired: REPLY no longer follows it, and the game answers.
                self.assertIn("They aren't here.", staff.sync("reply hello"))
                self.assertIn("Zmemguard", staff.sync("who"))

                journal = (mud.root / "log" / "play.tsv").read_text(encoding="latin-1")
                self.assertIn(f"MEMORY: stale reply -> {state} character, repaired", journal)
                self.assertTrue(re.search(r"\tbug\t", journal))
                staff.send("quit")
                staff.wait_closed()


if __name__ == "__main__":
    unittest.main()
