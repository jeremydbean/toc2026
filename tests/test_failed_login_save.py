"""A character who never entered the game must not be written to disk.

Found while working out why one character could not log in: the log
showed the playerfile loading and the link closing a second later,
and the file's own timestamp had moved.  It had been rewritten by the
failed attempt.

close_socket() saves whatever character the descriptor is holding
whenever the connection is not CON_PLAYING.  At that point the
character has been loaded from disk at the name prompt and nothing
has happened to it, so the write adds nothing -- and it means anybody
who knows a character's name can make the game rewrite that
character's file, repeatedly, by fumbling the password.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def without_comments(text: str) -> str:
    """Strip C comments so an assertion cannot be satisfied by prose."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


class FailedLoginSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        cls.comm = comm
        start = comm.index("void close_socket(")
        cls.body = without_comments(comm[start:comm.index("\nbool read_from_descriptor", start)])

    def test_a_login_that_never_began_does_not_save(self) -> None:
        """The else branch is reached only for a descriptor that is
        not CON_PLAYING -- which is to say, one that never got in."""
        tail = self.body.split("dclose->connected == CON_PLAYING", 1)[1]
        self.assertIn("free_char( save_ch )", tail)
        self.assertNotIn("save_char_obj", tail,
                         "a character who never entered the game is "
                         "being written to disk again")

    def test_the_playing_branch_still_records_the_logout(self) -> None:
        """Fixing the above must not cost a real player their
        link-dead handling: that lives in the CON_PLAYING branch and
        is a different thing entirely."""
        self.assertIn("record_logout", self.body)
        self.assertIn("last_logout", self.body)

    def test_a_switched_character_is_returned_first(self) -> None:
        """A disconnect in were form used to mark the mob link-dead
        and roll the player's session back; the do_return above the
        branch is what prevents it, and it must stay above."""
        returned = self.body.index("do_return( dclose->character")
        branch = self.body.index("dclose->connected == CON_PLAYING")
        self.assertLess(returned, branch)

    def test_the_wrong_password_path_still_closes(self) -> None:
        """The refusal itself is correct and is not what changed."""
        nanny = without_comments(
            self.comm[self.comm.index("void nanny("):])
        password = nanny.split("case CON_GET_OLD_PASSWORD:", 1)[1][:600]
        self.assertIn("Wrong password", password)
        self.assertIn("close_socket( d )", password)


if __name__ == "__main__":
    unittest.main()
