"""Memory comes from the system allocator, so the sanitizers can see it.

ROM recycled memory through its own pools: alloc_mem's size-class free
lists, and a free list per type -- characters, pcdata, objects,
descriptors, affects, extra descriptions, notes, bans, wizlist entries. A
freed block went to the next thing created, so AddressSanitizer never saw
a use after free or a double free in any of them: the block was "in use",
by the pool. alloc_mem is calloc and free_mem is free now (2026-11-11),
and characters, objects and descriptors are released to src/recycle.c,
which frees them at the top of the next pass of the game loop -- the game
still reads one it has just extracted (gone_after_blow), and that read
must stay valid for the rest of the pass.

Permanent memory stays permanent: alloc_perm's blocks are registered, and
free_mem leaves a pointer into one alone (is_perm_memory), as free_string
leaves the boot string space alone. An instance shares its prototype's
strings by pointer, so that is what keeps extracting it from freeing them.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

POOLS = (
    "char_free", "obj_free", "pcdata_free", "descriptor_free", "affect_free",
    "extra_descr_free", "note_free", "ban_free", "wiz_free", "room_aff_free",
    "room_index_free", "rgFreeList",
)


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def sources() -> dict[str, str]:
    return {
        p.name: strip_comments(p.read_text(encoding="latin-1"))
        for p in sorted(SRC.glob("*.[ch]"))
    }


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
                return text[brace:i + 1]
    raise AssertionError(f"unbalanced body for {signature}")


class MemoryPoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.src = sources()

    def test_no_free_list_pools_remain(self) -> None:
        found = []
        for name, text in self.src.items():
            for pool in POOLS:
                if re.search(r"\b" + pool + r"\b", text):
                    found.append(f"{name}: {pool}")
        self.assertEqual(found, [], "a recycling pool hides use after free from ASan")

    def test_alloc_mem_is_the_system_allocator(self) -> None:
        db = self.src["db.c"]
        alloc = function_body(db, "void *alloc_mem( int sMem )")
        free_ = function_body(db, "void free_mem( void *pMem, int sMem )")
        self.assertIn("calloc(", alloc)
        self.assertNotIn("alloc_perm", alloc)
        self.assertIn("free( pMem )", free_)
        # Permanent memory is never handed to free().
        self.assertIn("is_perm_memory( pMem )", free_)
        # The caller-visible ceiling the pager and output buffer rely on.
        self.assertIn("32768-64", db)
        self.assertIn("abort()", alloc)

    def test_shared_strings_stay_out_of_free(self) -> None:
        db = self.src["db.c"]
        free_string = function_body(db, "void free_string( char *pstr )")
        self.assertIn("string_space", free_string)
        self.assertIn("str_empty", free_string)

    def test_instances_are_allocated_and_released_through_recycle(self) -> None:
        db, save, handler, comm = (self.src[n] for n in ("db.c", "save.c", "handler.c", "comm.c"))
        self.assertIn("char_data_new( )", function_body(db, "CHAR_DATA *create_mobile("))
        self.assertIn("obj_data_new( )", function_body(db, "OBJ_DATA *create_object("))
        self.assertIn("char_data_release( ch )", function_body(db, "void free_char( CHAR_DATA *ch )"))
        self.assertIn("char_data_new( )", function_body(save, "bool load_char_obj("))
        self.assertEqual(handler.count("obj_data_release( obj )"), 2)
        self.assertIn("descriptor_data_new()", comm)
        self.assertIn("descriptor_data_release( dclose )",
                      function_body(comm, "void close_socket( DESCRIPTOR_DATA *dclose )"))
        # Released things are freed only where no pass is under way.
        loop = comm[comm.index("flush_container_lists();"):][:200]
        self.assertIn("recycle_flush();", loop)

    def test_extraction_refuses_a_second_release(self) -> None:
        handler = self.src["handler.c"]
        for sig in ("void extract_obj( OBJ_DATA *obj )", "void extract_obj_player( OBJ_DATA *obj )"):
            body = function_body(handler, sig)
            self.assertLess(body.index("obj_data_released( obj )"),
                            body.index("free_string"), sig)
        free_char = function_body(self.src["db.c"], "void free_char( CHAR_DATA *ch )")
        self.assertLess(free_char.index("char_data_released( ch )"),
                        free_char.index("free_string"))

    def test_recycle_is_built_by_cmake(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text()
        self.assertIn("src/recycle.c", cmake)


if __name__ == "__main__":
    unittest.main()
