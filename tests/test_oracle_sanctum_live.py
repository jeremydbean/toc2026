"""Live check of the Oracle's sanctum.

PRAY takes the supplicant out of the world into her sanctum; every way out
puts them back in the room they prayed from, dazed for a tick: saying DONE,
walking down through the bead curtain, and quitting inside (the file saves
the room they prayed from, never the sanctum). Lying down to SLEEP there is
a way out too, whether you meant it or not: she sends you home at once
(owner, 2026-10-20).
"""
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

PW = "testpw12"
TEMPLE_NAME = "Before the Altar"

_SKIP = skip_reason()


def make(mud, name, pk=True):
    """A character in the Temple. A player killer by default: since
    2026-11-13 only they come back from her dazed (owner)."""
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError("character did not quit")
    if pk:
        patch_player_file(mud, name, Room=4207, Levl=15, Pk_State=1)
    else:
        patch_player_file(mud, name, Room=4207)


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class OracleSanctumLive(unittest.TestCase):
    def test_every_way_out_returns_you_to_where_you_prayed(self):
        with LiveMud() as mud:
            for name in ("Zpraydone", "Zpraydown", "Zprayquit", "Zpraysleep"):
                make(mud, name)

            # DONE sends you home, dazed.
            with mud.connect(timeout=120) as client:
                login(client, "Zpraydone", PW)
                out = client.command("pray", 1.5)
                self.assertIn("The Oracle's Sanctum", out)
                out = client.command("say done", 1.5)
                self.assertIn(TEMPLE_NAME, out)
                self.assertIn("dazed", out)
                client.send("quit")
                client.wait_closed()

            # Walking down through the beads does too.
            with mud.connect(timeout=120) as client:
                login(client, "Zpraydown", PW)
                out = client.command("pray", 1.5)
                self.assertIn("The Oracle's Sanctum", out)
                out = client.command("down", 1.5)
                self.assertIn(TEMPLE_NAME, out)
                self.assertIn("dazed", out)
                client.send("quit")
                client.wait_closed()

            # Sleeping there is not allowed: out at once, awake and dazed.
            with mud.connect(timeout=120) as client:
                login(client, "Zpraysleep", PW)
                out = client.command("pray", 1.5)
                self.assertIn("The Oracle's Sanctum", out)
                out = client.command("sleep", 1.5)
                self.assertIn("no inn", out)
                self.assertIn(TEMPLE_NAME, out)
                self.assertNotIn("You go to sleep", out)
                self.assertIn("dazed", out)
                client.send("quit")
                client.wait_closed()

            # Quitting inside saves the room you prayed from, not the sanctum.
            with mud.connect(timeout=120) as client:
                login(client, "Zprayquit", PW)
                out = client.command("pray", 1.5)
                self.assertIn("The Oracle's Sanctum", out)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            with mud.connect(timeout=120) as client:
                login(client, "Zprayquit", PW)
                out = client.command("look", 1.2)
                self.assertIn(TEMPLE_NAME, out)
                self.assertNotIn("The Oracle's Sanctum", out)


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class OracleDazeLive(unittest.TestCase):
    """The daze after an audience was a tick of lag, and lag counts down
    only while a command waits: the first thing typed sat unanswered for a
    minute and the game looked frozen (owner, 2026-10-27). Every command in
    the daze is answered now, with why and how long; it ends on the clock
    and says so."""

    def test_a_dazed_command_is_answered_at_once(self):
        with LiveMud(extra_env={"TOC_ORACLE_DAZE": "6"}) as mud:
            make(mud, "Zpraydaze")
            make(mud, "Zprayleave")
            with mud.connect(timeout=120) as client:
                login(client, "Zpraydaze", PW)
                self.assertIn("The Oracle's Sanctum", client.command("pray", 1.5))
                out = client.command("say done", 1.5)
                self.assertIn("needs a moment to recover", out)
                # Answered within a second, not held for the daze.
                mark = len(client.transcript)
                client.send("look")
                client.expect("still reeling", timeout=2)
                self.assertRegex(client.transcript[mark:], r"\(\d seconds? more\)")
                self.assertNotIn(TEMPLE_NAME, client.transcript[mark:])
                # It ends by itself, and says so; then commands work.
                client.expect("Your head clears", timeout=15)
                self.assertIn(TEMPLE_NAME, client.command("look", 1.5))

            # Praying from a safe room (the altar, 4208) costs no daze
            # (owner, 2026-10-27): the next command just works.
            make(mud, "Zpraysafe")
            patch_player_file(mud, "Zpraysafe", Room=4208)
            with mud.connect(timeout=120) as client:
                login(client, "Zpraysafe", PW)
                self.assertIn("The Oracle's Sanctum", client.command("pray", 1.5))
                out = client.command("say done", 1.5)
                self.assertIn("settles gently", out)
                self.assertNotIn("dazed", out)
                self.assertIn("Altar of the Temple", client.sync("look"))

            # Nobody but a player killer is dazed (owner, 2026-11-13), even
            # praying from the Temple floor, which is no safe room.
            make(mud, "Zpraycalm", pk=False)
            with mud.connect(timeout=120) as client:
                login(client, "Zpraycalm", PW)
                self.assertIn("The Oracle's Sanctum", client.command("pray", 1.5))
                out = client.command("say done", 1.5)
                self.assertIn("settles gently", out)
                self.assertNotIn("dazed", out)
                self.assertIn(TEMPLE_NAME, client.sync("look"))

            # QUIT is never refused: leaving the game escapes nothing.
            with mud.connect(timeout=120) as client:
                login(client, "Zprayleave", PW)
                client.command("pray", 1.5)
                client.command("say done", 1.5)
                client.send("quit")
                self.assertTrue(client.wait_closed(timeout=10))


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(_SKIP is not None, _SKIP or "")
class OracleAfterAFleeLive(unittest.TestCase):
    """Owner, 2026-11-13: "prevent players from fleeing and then
    immediately praying just to get away from a mob or a pkiller". A flee
    holds PRAY off (three minutes; TOC_ORACLE_FLEE_WAIT shortens it here),
    the refusal says how long, and it clears by itself."""

    def test_no_prayer_straight_after_a_flee(self):
        from live_mud import SPARRING_FLOOR, place_sparring_guard
        with LiveMud(fixtures=True, extra_env={"TOC_ORACLE_FLEE_WAIT": "8"}) as mud:
            make(mud, "Zfleegod")
            patch_player_file(mud, "Zfleegod", Levl=70)
            make(mud, "Zfleer", pk=False)
            patch_player_file(mud, "Zfleer", Levl=20, HMV="20000 20000 500 500 5000 5000",
                              HMVP="20000 500 5000")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zfleegod", PW)
                login(hero, "Zfleer", PW)
                place_sparring_guard(staff, "Zfleegod", SPARRING_FLOOR)
                staff.must(f"transfer zfleer {SPARRING_FLOOR}", "")
                hero.sync("kill sparring", 10)
                fled = ""
                for _ in range(30):
                    fled = hero.sync("flee", 10)
                    if "You flee from combat" in fled:
                        break
                    hero.drain(1)
                self.assertIn("You flee from combat", fled)
                refused = hero.sync("pray")
                self.assertIn("fresh from a fight", refused)
                self.assertRegex(refused, r"\(\d+ seconds? more\)")
                self.assertNotIn("The Oracle's Sanctum", refused)
                hero.drain(9)
                self.assertIn("The Oracle's Sanctum", hero.command("pray", 1.5))
                hero.command("say done", 1.5)
                hero.send("quit")
                hero.wait_closed()
                staff.send("quit")
                staff.wait_closed()
