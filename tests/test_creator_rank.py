"""The creator and trust 71 (owner, 2026-10-22).

Killuminati, and only Killuminati, is the creator: get_trust() is 72
whatever his level, so he outranks every implementor and his WIZINVIS
defaults to 72, hidden from everyone. TRUST may now give 71, and only he
can, since nobody else's trust reaches it; 71 outranks every implementor
and sees him at WIZI 71. SHUTDOWN, REBOOT, LOG, SNOOP, BAN, ALLOW,
WIZLOCK, NEWLOCK, DENY and UNDENY are his alone, and the notices of his
arrival and departure go out at his WIZINVIS level. He always logs in
wizinvis, at 72 unless he left at a level of his own.

The fixture is a synthetic Killuminati in a throwaway world -- the
creator is a name, so the test has to use it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
PASSWORD = "Zcreator1"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=70, Room=TEMPLE)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CreatorRankTests(unittest.TestCase):
    def test_the_creator_and_trust_seventy_one(self) -> None:
        with LiveMud() as mud:
            for name in ("Killuminati", "Zimpl", "Zmisery"):
                make(mud, name)
            with mud.connect(timeout=120) as creator, \
                    mud.connect(timeout=120) as impl, \
                    mud.connect(timeout=120) as trusted:
                login(creator, "Killuminati", PASSWORD)
                login(impl, "Zimpl", PASSWORD)
                login(trusted, "Zmisery", PASSWORD)

                # The creator's commands are his alone.
                for command in ("shutdown", "log zmisery", "snoop zmisery",
                                "ban zsomesite", "wizlock", "deny zmisery"):
                    self.assertIn("Huh?", run(impl, command), command)

                # Only the creator can give 71, and 71 then outranks 70.
                self.assertIn("Limited to your trust", run(impl, "trust zmisery 71"))
                self.assertIn("trusted at level 71", run(creator, "trust zmisery 71"))
                self.assertIn("outrank", run(impl, "trust zmisery 0"))
                trusted.drain(1.0)
                self.assertIn("trusted at level 71", trusted.transcript)
                self.assertIn("You failed", run(impl, "nochannels zmisery"))
                self.assertIn("Zmisery", run(creator, "stat zmisery"))

                # He logged in wizinvis at his own trust: hidden from all.
                run(impl, "holylight")
                run(trusted, "holylight")
                self.assertNotIn("Killuminati", run(impl, "who"))
                self.assertNotIn("Killuminati", run(trusted, "who"))
                self.assertNotIn("Killuminati", run(impl, "look"))
                # 71 outranks the creator in nothing: he is not even there.
                self.assertIn("aren't here", run(trusted, "nochannels killuminati"))

                # WIZI 71 lets trust 71 see him, and still not 70.
                run(creator, "wizinvis 71")
                self.assertIn("Killuminati", run(trusted, "who"))
                self.assertNotIn("Killuminati", run(impl, "who"))

                # He always arrives wizinvis at 72 (owner, 2026-10-22), even
                # having left visible, and his arrival reaches nobody below.
                run(creator, "wizinvis")
                self.assertIn("Killuminati", run(impl, "who"))
                creator.send("quit")
                self.assertTrue(creator.wait_closed())
                impl.drain(1.0)
                trusted.drain(1.0)
                mark_impl, mark_trusted = len(impl.transcript), len(trusted.transcript)
                with mud.connect(timeout=120) as again:
                    login(again, "Killuminati", PASSWORD)
                    again.drain(1.5)
                    self.assertIn("Killuminati", run(again, "who"))
                    impl.drain(1.0)
                    trusted.drain(1.0)
                    self.assertNotIn("Killuminati", impl.transcript[mark_impl:])
                    self.assertNotIn("Killuminati", trusted.transcript[mark_trusted:])
                    self.assertNotIn("Killuminati", run(impl, "who"))
                    self.assertNotIn("Killuminati", run(trusted, "who"))
                    again.send("quit")
                    again.wait_closed()
                for client in (impl, trusted):
                    client.send("quit")
                    client.wait_closed()

            # The log files keep the record.
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("Killuminati@", log)
            self.assertIn("Killuminati set Zmisery's trust to 71.", log)

    def test_the_review_bypasses_are_closed(self) -> None:
        """The independent review (2026-10-22): a 71 passing on 71, an
        implementor demoting, SETting or SET SKILLing a higher rank, SET
        DENY and PARDON DENY beside the creator-only DENY, the TRUST notice
        naming a hidden target, LOAD refusing the creator a portal, and a
        switched creator named by WHO and SOCKETS."""
        with LiveMud() as mud:
            for name in ("Killuminati", "Zimpl", "Zmisery", "Zother"):
                make(mud, name)
            with mud.connect(timeout=120) as creator, \
                    mud.connect(timeout=120) as impl, \
                    mud.connect(timeout=120) as trusted:
                login(creator, "Killuminati", PASSWORD)
                login(impl, "Zimpl", PASSWORD)
                login(trusted, "Zmisery", PASSWORD)
                self.assertIn("trusted at level 71", run(creator, "trust zmisery 71"))

                # R1: only the creator gives 71, not a 71.
                self.assertIn("Only the creator gives", run(trusted, "trust zimpl 71"))
                # R2, R3: a higher rank cannot be demoted or SET.
                self.assertIn("outrank", run(impl, "advance zmisery 1"))
                self.assertIn("outrank", run(impl, "set char zmisery hp 123"))
                self.assertIn("outrank", run(impl, "set skill zmisery dagger 1"))
                # R4: SET DENY and PARDON DENY are the creator's, even on
                # yourself -- the rank check alone would let these through.
                self.assertIn("Only the creator", run(impl, "set char zimpl deny on"))
                self.assertIn("Only the creator", run(impl, "pardon zimpl deny"))
                # R7: the creator loads a portal at the default level.
                self.assertNotIn("can not load", run(creator, "load obj 26"))

                # R6: a TRUST notice naming a hidden target stays hidden.
                run(creator, "wizinvis")                 # visible
                run(trusted, "wizinvis 71")
                impl.drain(1.0)
                mark = len(impl.transcript)
                self.assertIn("trusted at level 71", run(creator, "trust zmisery 71"))
                impl.drain(1.0)
                self.assertNotIn("Zmisery", impl.transcript[mark:])
                run(trusted, "wizinvis")

                # R5: switched, he is not named by WHO or SOCKETS.
                run(creator, "wizinvis 72")
                run(creator, "load mob 29012")
                self.assertIn("Possessed by you", run(creator, "switch guard"))
                self.assertNotIn("Killuminati", run(impl, "who"))
                self.assertNotIn("Killuminati", run(impl, "sockets"))
                self.assertNotIn("Killuminati", run(impl, "sockets killuminati"))
                run(creator, "return")
                for client in (creator, impl, trusted):
                    client.send("quit")
                    client.wait_closed()
            saved = (mud.player_dir / "Zmisery").read_text(encoding="latin-1")
        self.assertRegex(saved, r"(?m)^Levl 70$")
        self.assertNotRegex(saved, r"(?m)^HMV\s+123 ")

    def test_the_creator_cannot_die_and_turns_a_slay_back(self) -> None:
        """The protections follow the creator (owner, 2026-10-22): a SLAY
        aimed at him strikes down whoever threw it, and a mobile's blows
        hold him at one hit point -- no death, no kill recorded."""
        with LiveMud() as mud:
            for name in ("Killuminati", "Zimpl"):
                make(mud, name)
            # Level 20: combat keeps any level 70 at one hit point on its
            # own, so only a mortal body reaches the death itself. The
            # creator is a name, not a level -- he is still the creator.
            patch_player_file(mud, "Killuminati", Levl=20)
            with mud.connect(timeout=120) as creator, mud.connect(timeout=120) as impl:
                login(creator, "Killuminati", PASSWORD)
                login(impl, "Zimpl", PASSWORD)
                run(creator, "wizinvis")                 # visible, so he can be aimed at
                self.assertIn("redirecting the strike back", run(impl, "slay killuminati", 2.0))
                run(creator, "goto 4202")                # the Temple refuses a fight
                run(creator, "load mob 29012")
                run(creator, "set char killuminati hp 1")
                mark = len(creator.transcript)
                run(creator, "kill guard", 0.5)
                creator.drain(20.0)                      # several rounds at one hit point
                fight = creator.transcript[mark:]
                self.assertIn("security guard", fight)
                self.assertNotIn("You have been KILLED", fight)
                run(creator, "peace", 1.0)
                run(creator, "purge guard", 1.0)
                self.assertIn("Killuminati", run(creator, "score", 3.0))
                for client in (creator, impl):
                    client.send("quit")
                    client.wait_closed()
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
        self.assertIn("Zimpl struck at Killuminati and was struck down by the ward.", log)
        self.assertNotIn("Killuminati killed by", log)

    def test_the_creator_flag_is_granted_kept_and_taken(self) -> None:
        """The creator's rank is a saved flag (owner, 2026-10-22): the
        founder grants it, online or off; it survives a login, which then
        comes in wizinvis; nobody else grants it, nobody takes it from the
        founder, the founder outranks the creators he makes, and taking it
        away brings the WIZINVIS level down with it."""
        with LiveMud() as mud:
            for name in ("Killuminati", "Zgranted", "Zimpl", "Zoffline"):
                make(mud, name)
            with mud.connect(timeout=120) as founder, \
                    mud.connect(timeout=120) as granted, \
                    mud.connect(timeout=120) as impl:
                login(founder, "Killuminati", PASSWORD)
                login(granted, "Zgranted", PASSWORD)
                login(impl, "Zimpl", PASSWORD)

                self.assertIn("Huh?", run(granted, "snoop zimpl"))
                self.assertIn("now holds the creator's rank", run(founder, "creator zgranted on"))
                self.assertIn("now being snooped", run(granted, "snoop zimpl"))
                run(granted, "snoop zgranted")                # cancel
                self.assertIn("(founder)", run(granted, "creator"))
                self.assertIn("Only the founding creator", run(granted, "creator zimpl on"))
                self.assertIn("outrank", run(granted, "set char killuminati hp 5"))
                self.assertIn("not yours to change", run(founder, "creator killuminati off"))
                self.assertIn("they are offline", run(founder, "creator zoffline on"))

                # Kept across a login, which comes in wizinvis at 72.
                granted.send("quit")
                self.assertTrue(granted.wait_closed())
                with mud.connect(timeout=120) as again:
                    login(again, "Zgranted", PASSWORD)
                    self.assertNotIn("Zgranted", run(impl, "who"))
                    self.assertIn("now being snooped", run(again, "snoop zimpl"))
                    run(again, "snoop zgranted")

                    # Taken away: the commands go, and so does the hiding.
                    self.assertIn("no longer holds", run(founder, "creator zgranted off"))
                    self.assertIn("Huh?", run(again, "snoop zimpl"))
                    self.assertIn("Zgranted", run(impl, "who"))
                    again.send("quit")
                    again.wait_closed()
                for client in (founder, impl):
                    client.send("quit")
                    client.wait_closed()
            offline = (mud.player_dir / "Zoffline").read_text(encoding="latin-1")
            revoked = (mud.player_dir / "Zgranted").read_text(encoding="latin-1")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
        self.assertRegex(offline, r"(?m)^Creator 1$")
        self.assertNotRegex(revoked, r"(?m)^Creator ")
        self.assertIn("Killuminati granted the creator's rank to Zgranted.", log)
        self.assertIn("Killuminati took the creator's rank from Zgranted.", log)


class HuntingAccessTests(unittest.TestCase):
    """The Coven's underbrush is closed, not locked, from both sides, and
    Upper Argo's imp 1020 does not attack on sight (review, 2026-10-22: the
    reverse side was still reset locked)."""

    def test_both_sides_of_the_underbrush_and_the_imp(self) -> None:
        root = Path(__file__).resolve().parents[1] / "area"
        coven = (root / "coven.are").read_text(encoding="latin-1")
        resets = coven[coven.index("#RESETS"):]
        for room, door in (("24112", "1"), ("24143", "3")):
            self.assertRegex(resets, rf"(?m)^D 0 {room} {door} 1\b", (room, door))
        uargo = (root / "uargo.are").read_text(encoding="latin-1")
        block = uargo[uargo.index("#1020\n"):]
        act = block.split("~")[5].split()[0]
        self.assertNotIn("F", act, "imp 1020 is aggressive again")


if __name__ == "__main__":
    unittest.main()
