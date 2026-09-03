from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ListIteratorContractTests(unittest.TestCase):
    """Source-level guards for the container list iterator.

    extract_char() removes the element a FOR_EACH_CHARACTER loop is standing
    on whenever a mobile dies inside the loop, which happens in
    violence_update(), aggr_update(), char_update(), do_mindblast(),
    spell_earthquake() and about a dozen other places. list_remove() used to
    free the node immediately, leaving the iterator cursor -- which aliases
    node->next -- dangling. Because `next` is the last field of LIST_NODE,
    glibc leaves it readable in a freed chunk until that chunk is recycled, so
    the defect showed up only as rare unreproducible corruption rather than a
    reliable crash.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.list_c = (ROOT / "src" / "list.c").read_text(encoding="utf-8")
        cls.list_h = (ROOT / "src" / "list.h").read_text(encoding="utf-8")
        cls.container = (ROOT / "src" / "container.c").read_text(encoding="utf-8")
        cls.comm = (ROOT / "src" / "comm.c").read_text(encoding="utf-8")

    def _list_remove_body(self) -> str:
        match = re.search(
            r"void list_remove\(.*?\n\{(?P<body>.*?)\n\}", self.list_c, re.DOTALL
        )
        self.assertIsNotNone(match, "could not locate list_remove()")
        return match.group("body")

    def test_list_remove_defers_the_free(self) -> None:
        body = self._list_remove_body()

        # The eager free is the bug. It must not come back.
        self.assertNotIn("free( node )", body)
        self.assertNotIn("free(node)", body)

        # Tombstone plus park for later reclamation.
        self.assertIn("node->data = NULL", body)
        self.assertIn("node->prev = list->pending", body)
        self.assertIn("list->pending = node", body)

    def test_pending_chain_must_not_reuse_the_next_pointer(self) -> None:
        """The parked chain has to hang off `prev`.

        A parked node's `next` is what lets a cursor sitting on it walk
        forward, so threading the free list through `next` would reintroduce
        the defect in a subtler form.
        """
        body = self._list_remove_body()
        self.assertNotIn("node->next = list->pending", body)
        self.assertIn("LIST_NODE *pending;", self.list_h)

    def test_iterator_skips_tombstoned_nodes(self) -> None:
        match = re.search(
            r"void \*list_iterator_next\(.*?\n\{(?P<body>.*?)\n\}",
            self.list_c,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")

        self.assertIn("while ( ( node = *iter->pnext ) != NULL )", body)
        self.assertIn("if ( node->data != NULL )", body)

    def test_flush_is_reachable_and_wired_into_the_game_loop(self) -> None:
        self.assertIn("void list_flush_pending( LIST *list )", self.list_c)
        self.assertIn("void    list_flush_pending( LIST *list );", self.list_h)

        # Both game-wide containers are reclaimed.
        self.assertIn("list_flush_pending( &character_list )", self.container)
        self.assertIn("list_flush_pending( &object_list )", self.container)

        # And the flush actually runs, once per pass of the main loop.
        self.assertIn("flush_container_lists();", self.comm)
        loop = self.comm[self.comm.index("void game_loop_unix"):]
        self.assertIn("flush_container_lists();", loop)

    def test_list_init_clears_the_pending_chain(self) -> None:
        match = re.search(
            r"void list_init\(.*?\n\{(?P<body>.*?)\n\}", self.list_c, re.DOTALL
        )
        self.assertIsNotNone(match)
        self.assertIn("list->pending = NULL", match.group("body"))

    @unittest.skipIf(shutil.which("gcc") is None, "gcc is not available")
    def test_behavioural_harness_passes_under_sanitizers(self) -> None:
        """Compile and run the C harness when a compiler is present.

        scripts/validate.sh runs this too; doing it here as well means a plain
        `python -m unittest` on a machine with gcc still catches a regression.
        """
        source = ROOT / "tests" / "test_list_iterator.c"
        self.assertTrue(source.is_file())

        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_list_iterator"
            build = subprocess.run(
                [
                    "gcc",
                    "-g",
                    "-fsanitize=address,undefined",
                    f"-I{ROOT / 'src'}",
                    "-o",
                    str(binary),
                    str(source),
                    str(ROOT / "src" / "list.c"),
                ],
                capture_output=True,
                text=True,
            )
            if build.returncode != 0:
                self.skipTest(f"harness did not build here: {build.stderr[:400]}")

            run = subprocess.run(
                [str(binary)],
                capture_output=True,
                text=True,
                env={"ASAN_OPTIONS": "detect_leaks=1"},
            )
            self.assertEqual(
                run.returncode,
                0,
                f"iterator harness failed:\n{run.stdout}\n{run.stderr}",
            )
            self.assertIn("ALL PASS", run.stdout)


if __name__ == "__main__":
    unittest.main()
