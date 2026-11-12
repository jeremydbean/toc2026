"""CMake's binary directory (2026-11-12).

Every CMake tree wrote bin/rom, so building the Release tree after the
sanitizer one replaced the sanitizer binary a test was about to run.
TOC_BIN_DIR names where a tree writes it; the default stays bin/, where
the docs, the area scripts (../bin/rom) and CI look.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CMakeLayoutTests(unittest.TestCase):
    def test_the_binary_directory_is_a_cache_option_defaulting_to_bin(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text()
        self.assertRegex(cmake, r'set\(TOC_BIN_DIR "\$\{CMAKE_SOURCE_DIR\}/bin" CACHE PATH')
        self.assertIn('set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${TOC_BIN_DIR}")', cmake)
        self.assertIsNone(re.search(r'CMAKE_RUNTIME_OUTPUT_DIRECTORY "\$\{CMAKE_SOURCE_DIR\}/bin"',
                                    cmake), "the default comes from TOC_BIN_DIR only")

    def test_ci_still_finds_bin_rom(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text()
        self.assertIn("bin/rom", workflow)


if __name__ == "__main__":
    unittest.main()
