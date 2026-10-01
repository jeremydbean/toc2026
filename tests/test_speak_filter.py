"""The swedish and drunk speech filters are compiled and wired in.

Both lived in comm.c until a refactor moved swedish_speak into an
uncompiled src/swedish.txt and dropped speak_filter and drunk_speak
entirely, so the SWEDISH command set a flag nothing read. They are
restored in src/speak_filter.c and called from the speech paths.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


class SpeakFilterTests(unittest.TestCase):
    def test_the_filters_are_compiled(self):
        src = read("src", "speak_filter.c")
        self.assertIn("char *speak_filter(", src)
        self.assertIn("char *drunk_speak(", src)
        self.assertIn("swedish_speak(", src)
        # PLR_SWEDISH drives it, guarded by !IS_NPC since it shares the
        # act bitfield with the ACT_* flags.
        self.assertIn("PLR_SWEDISH", src)
        self.assertIn("IS_NPC( ch )", src)
        # No raw strcat/strcpy/sprintf reintroduced with the port.
        for banned in ("strcat(", "strcpy(", "sprintf("):
            self.assertNotIn(banned, src, banned)

    def test_the_new_file_is_in_cmake(self):
        self.assertIn("src/speak_filter.c", read("CMakeLists.txt"))

    def test_speech_paths_apply_the_filter(self):
        comm = read("src", "act_comm.c")
        for fn in ("void do_say(", "static void channel_say(",
                   "void do_tell(", "void do_reply("):
            body = comm[comm.index(fn):]
            body = body[:body.index("\n}")]
            self.assertIn("speak_filter( ch, argument )", body, fn)


if __name__ == "__main__":
    unittest.main()
