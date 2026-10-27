"""DNS, and granting psionics to somebody who is not logged in.

DNS was a stub answering "That command is not available". GRANTPSI stopped
at "They aren't here", so it only worked if you and the target happened to
be online together.

The offline path is the one worth testing carefully: it loads the save
file, registers the character, changes it and writes it back, and every
exit has to either save or release that copy. A leak there would leave a
ghost in the world rather than fail visibly.
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

PASSWORD = "Zdnspsi11"
IMMORTAL_LEVEL = 70


def run(client, command: str, settle: float = 2.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def immortal(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)


@unittest.skipIf(SKIP is not None, SKIP or "")
class DnsTests(unittest.TestCase):
    def test_dns_reports_and_toggles(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zdnsimm")
            with mud.connect(timeout=120) as god:
                login(god, "Zdnsimm", PASSWORD)

                status = run(god, "dns")
                self.assertNotIn("not available", status)
                self.assertIn("Hostname lookups are", status)

                off = run(god, "dns off")
                self.assertIn("now OFF", off)
                self.assertIn("host names will not match", off)
                self.assertIn("OFF", run(god, "dns"))

                self.assertIn("now ON", run(god, "dns on"))

    def test_dns_list_shows_the_connected(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zdnslist")
            with mud.connect(timeout=120) as god:
                login(god, "Zdnslist", PASSWORD)
                listing = run(god, "dns list", settle=3.0)
                self.assertIn("Zdnslist", listing)
                self.assertIn("127.0.0.1", listing)

    def test_dns_resolves_an_address(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zdnslook")
            with mud.connect(timeout=120) as god:
                login(god, "Zdnslook", PASSWORD)
                reply = run(god, "dns 127.0.0.1", settle=4.0)
                self.assertRegex(reply, r"resolves to|has no host name")


@unittest.skipIf(SKIP is not None, SKIP or "")
class OfflineGrantPsiTests(unittest.TestCase):
    def test_a_saved_character_can_be_flagged(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpsiimm")
            with mud.connect(timeout=120) as maker:
                create_character(maker, "Zpsitarget", PASSWORD)
                maker.send("quit")
                maker.wait_closed()

            with mud.connect(timeout=120) as god:
                login(god, "Zpsiimm", PASSWORD)
                reply = run(god, "grantpsi Zpsitarget", settle=4.0)

                self.assertNotIn("aren't here", reply)
                self.assertIn("Grant flag applied", reply)

            saved = (mud.root / "player" / "Zpsitarget").read_text(
                encoding="latin-1", errors="replace")
            self.assertIn("PsiGrant 1", saved)

    def test_now_grants_at_once_even_when_they_are_offline(self) -> None:
        """NOW is now (owner, 2026-10-27), online or not: the loaded copy
        is granted, saved and extracted."""
        with LiveMud() as mud:
            immortal(mud, "Zpsiimmb")
            with mud.connect(timeout=120) as maker:
                create_character(maker, "Zpsitargtw", PASSWORD)
                maker.send("quit")
                maker.wait_closed()

            with mud.connect(timeout=120) as god:
                login(god, "Zpsiimmb", PASSWORD)
                reply = run(god, "grantpsi Zpsitargtw now", settle=4.0)
                self.assertIn("granted immediately", reply, reply)
                self.assertNotIn("Zpsitargtw", run(god, "who", settle=2.5))

            saved = saved_file(mud, "Zpsitargtw")
            self.assertRegex(saved, r"(?m)^Psionic\s+1$")
            self.assertIn("PsiGrant 0", saved)

    def test_above_the_band_a_plain_grant_waits_for_the_band(self) -> None:
        """Past level 21 the awakening check is behind them, so a plain
        GRANTPSI waits until they reach it again (owner, 2026-10-27); it
        used to land at once. LEVEL or NOW are the ways to give it sooner."""
        with LiveMud() as mud:
            immortal(mud, "Zpsiimmz")
            with mud.connect(timeout=120) as maker:
                create_character(maker, "Zpsihighz", PASSWORD)
                maker.send("quit")
                maker.wait_closed()
            patch_player_file(mud, "Zpsihighz", Levl=50)

            with mud.connect(timeout=120) as god:
                login(god, "Zpsiimmz", PASSWORD)
                reply = run(god, "grantpsi Zpsihighz", settle=4.0)
                self.assertIn("past the 18-21 awakening band", reply, reply)
                self.assertNotIn("Zpsihighz", run(god, "who", settle=2.5))

            saved = saved_file(mud, "Zpsihighz")
            self.assertIn("PsiGrant 1", saved)
            self.assertRegex(saved, r"(?m)^Psionic\s+0$")

    def test_an_unknown_name_is_refused_cleanly(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpsiimmc")
            with mud.connect(timeout=120) as god:
                login(god, "Zpsiimmc", PASSWORD)
                reply = run(god, "grantpsi Nosuchperson", settle=3.0)
                self.assertIn("online or saved", reply)

                # And the server is still healthy afterwards.
                self.assertIn("Zpsiimmc", run(god, "score", settle=3.0))

    def test_an_online_target_still_works(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpsiimmd")
            with mud.connect(timeout=120) as target:
                create_character(target, "Zpsionline", PASSWORD)
                target.drain(2.0)

                with mud.connect(timeout=120) as god:
                    login(god, "Zpsiimmd", PASSWORD)
                    reply = run(god, "grantpsi Zpsionline", settle=4.0)
                    self.assertIn("Grant flag applied", reply)
                    self.assertNotIn("not online", reply)


def saved_file(mud: LiveMud, name: str) -> str:
    return (mud.root / "player" / name).read_text(encoding="latin-1", errors="replace")


@unittest.skipIf(SKIP is not None, SKIP or "")
class GrantPsiLandsWhereAskedTests(unittest.TestCase):
    """Owner, 2026-10-27: GRANTPSI <name> lands at the next legitimate
    check -- the first level gained from 18 to 21 -- and LEVEL on the
    next level gained. Neither says a word to the player when it is
    given."""

    def test_plain_waits_for_the_band_and_level_takes_the_next_level(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpsigod")
            for name, level in (("Zpsiband", 16), ("Zpsinext", 10)):
                with mud.connect(timeout=120) as maker:
                    create_character(maker, name, PASSWORD)
                    maker.send("quit")
                    maker.wait_closed()
                patch_player_file(mud, name, Levl=level, Room=4207)

            with mud.connect(timeout=120) as god, \
                    mud.connect(timeout=120) as band, \
                    mud.connect(timeout=120) as nxt:
                login(god, "Zpsigod", PASSWORD)
                login(band, "Zpsiband", PASSWORD)
                login(nxt, "Zpsinext", PASSWORD)
                for c in (god, band, nxt):
                    c.sync("scroll 0")
                # ADVANCE wants its target in the same room.
                god.must("goto 4207", "Before the Altar")

                god.must("grantpsi zpsiband", "awakening check")
                god.must("grantpsi zpsinext level", "next time they gain a level")
                # Not a word to either player.
                for c in (band, nxt):
                    heard = c.sync("save")
                    self.assertNotIn("mind", heard.lower(), heard)
                    self.assertNotIn("psion", heard.lower(), heard)
                self.assertIn("PsiGrant 1", saved_file(mud, "Zpsiband"))
                self.assertIn("PsiGrant 2", saved_file(mud, "Zpsinext"))

                # LEVEL: the next level, outside the band.
                god.must("advance zpsinext 11", "now level 11")
                nxt.sync("save")
                self.assertRegex(saved_file(mud, "Zpsinext"), r"(?m)^Psionic\s+1$")

                # Plain: 17 is not the check; 18 is.
                god.must("advance zpsiband 17", "now level 17")
                band.sync("save")
                self.assertRegex(saved_file(mud, "Zpsiband"), r"(?m)^Psionic\s+0$")
                god.must("advance zpsiband 18", "now level 18")
                band.sync("save")
                saved = saved_file(mud, "Zpsiband")
                self.assertRegex(saved, r"(?m)^Psionic\s+1$")
                self.assertIn("PsiGrant 0", saved)


if __name__ == "__main__":
    unittest.main()
