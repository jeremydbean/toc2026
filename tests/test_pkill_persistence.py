from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PkillPersistenceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "pkill.c").read_text(encoding="utf-8")
        match = re.search(
            r"void load_pkills\s*\([^)]*\).*?\{(?P<body>.*)\n\}",
            cls.source,
            re.DOTALL,
        )
        if match is None:
            raise AssertionError("load_pkills implementation was not found")
        cls.body = match.group("body")

    def test_loader_uses_bounded_lines_instead_of_eof_token_polling(self) -> None:
        self.assertIn("fgets(line, sizeof(line), fp)", self.body)
        self.assertIn("feof(fp)", self.body)
        self.assertNotIn("fread_word", self.body)

    def test_loader_rejects_malformed_and_oversized_records(self) -> None:
        self.assertIn("Skipping oversized line in pkill file", self.body)
        self.assertIn("Skipping malformed line in pkill file", self.body)
        self.assertIn("parse_pkill_count", self.body)
        self.assertIn("errno == ERANGE", self.source)

    def test_missing_terminator_finishes_cleanly_and_closes_file(self) -> None:
        self.assertIn("ended without a terminator", self.body)
        self.assertIn("fclose(fp)", self.body)

    def test_writer_uses_temp_file_and_terminator(self) -> None:
        self.assertIn('fopen( PKILLFILE ".tmp", "w" )', self.source)
        self.assertIn('fprintf(fp,"%s\\n","$")', self.source)
        self.assertIn('rename( PKILLFILE ".tmp", PKILLFILE )', self.source)


if __name__ == "__main__":
    unittest.main()
