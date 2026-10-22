"""damage() says whether a blow landed, never whether it killed.

A 2025 pass read its result as "the victim died" at more than twenty call
sites and cut every multi-hit spell, trap and flood off at its first
landed blow: one magic missile, one skeletal hand, one tentacle a target,
chain lightning that never chained, dirt that never blinded, stun traps
and stunning blows that never stunned, enervate that never healed, and a
cauldron explosion that never used up its ingredients (2026-10-04). The
test after a blow is gone_after_blow(); nothing may branch on damage()'s
result directly again.

die_follower() was an empty stub over the same period, so followers kept
pointing at characters who had quit.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

BRANCH_ON_DAMAGE = re.compile(r"(?:\bif|\bwhile|&&|\|\||\?)\s*\(?\s*!?\s*damage\s*\(")

# The same mistake one step removed: `killed = damage(...)` and then
# `if (killed) break;`. Meteor swarm did exactly that and stopped every
# target at its first landed meteor (audit, 2026-10-22); the line test
# above could not see it.
ASSIGN_FROM_DAMAGE = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*damage\s*\(")


def branch_on(name: str) -> re.Pattern[str]:
    return re.compile(r"(?:\bif|\bwhile|&&|\|\||\?)\s*\(?\s*!?\s*" + re.escape(name) + r"\b")


def strip_comments(text: str) -> str:
    # Keep the newlines a comment spanned, so reported line numbers are
    # the file's own.
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def damage_result_branches(path_name: str, text: str) -> list[str]:
    """Branches on a variable that holds damage()'s result.

    Read from the assignment to the end of the enclosing function (a `}`
    in column 0). A condition that also asks gone_after_blow() is asking
    whether the blow landed *and* whether the victim is still there,
    which is the right pair of questions (one_hit's lycanthropy bite).
    """
    lines = text.splitlines()
    found = []
    for number, line in enumerate(lines):
        for match in ASSIGN_FROM_DAMAGE.finditer(line):
            pattern = branch_on(match.group(1))
            for later in range(number + 1, len(lines)):
                if lines[later].startswith("}"):
                    break
                if pattern.search(lines[later]) and "gone_after_blow" not in lines[later]:
                    found.append(f"{path_name}:{later + 1}: {lines[later].strip()}"
                                 f" (holds damage() from line {number + 1})")
    return found


class DamageResultTests(unittest.TestCase):
    def test_nothing_branches_on_damage_result(self) -> None:
        offenders = []
        for path in sorted(SRC.glob("*.c")):
            text = strip_comments(path.read_text(encoding="latin-1"))
            for number, line in enumerate(text.splitlines(), 1):
                if BRANCH_ON_DAMAGE.search(line):
                    offenders.append(f"{path.name}:{number}: {line.strip()}")
        self.assertEqual(offenders, [], "use gone_after_blow() after damage()")

    def test_nothing_branches_on_a_saved_damage_result(self) -> None:
        offenders = []
        for path in sorted(SRC.glob("*.c")):
            text = strip_comments(path.read_text(encoding="latin-1"))
            offenders.extend(damage_result_branches(path.name, text))
        self.assertEqual(offenders, [], "use gone_after_blow() after damage()")

    def test_the_saved_result_check_finds_the_old_meteor_swarm(self) -> None:
        old = (
            "void spell_meteor_swarm( int sn )\n"
            "{\n"
            "    while ( count > 0 )\n"
            "    {\n"
            "        gch_killed = damage(ch,gch,dice(level,7),sn,DAM_FIRE);\n"
            "        if (gch_killed)\n"
            "            break;\n"
            "    }\n"
            "}\n"
            "void one_hit( void )\n"
            "{\n"
            "    landed = damage( ch, victim, dam, dt, dam_type );\n"
            "    if ( landed && !gone_after_blow( victim, struck_in )\n"
            "}\n"
        )
        found = damage_result_branches("magic2.c", old)
        self.assertEqual(len(found), 1, found)
        self.assertIn("gch_killed", found[0])

    def test_an_aura_never_burns_its_own_wearer(self) -> None:
        """Poison ticks are damage(ch, ch); the aura reflected them back."""
        fight = (SRC / "fight.c").read_text(encoding="latin-1")
        body = fight[fight.index("bool damage( CHAR_DATA *ch"):]
        body = body[:body.index("AFF2_FLAMING_COLD")]
        self.assertIn("if ( ch != victim )", body)

    def test_gone_after_blow_reads_the_room(self) -> None:
        fight = (SRC / "fight.c").read_text(encoding="latin-1")
        body = fight[fight.index("bool gone_after_blow("):]
        body = body[:body.index("}")]
        self.assertIn("ch->in_room == NULL", body)
        self.assertIn("ch->in_room != room", body)

    def test_die_follower_is_not_a_stub(self) -> None:
        stubs = (SRC / "stubs.c").read_text(encoding="latin-1")
        body = stubs[stubs.index("void die_follower( CHAR_DATA *ch )"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("stop_follower( fch )", body)
        self.assertIn("fch->leader = fch", body)
        self.assertIn("dismiss_undead_servants( ch )", body)

    def test_raised_undead_are_no_kill_and_do_not_outlive_their_master(self) -> None:
        fight = (SRC / "fight.c").read_text(encoding="latin-1")
        gain = fight[fight.index("void group_gain("):]
        gain = gain[:gain.index("quest_record_kill(ch, victim)")]
        self.assertIn("MOB_VNUM_ANIMATE", gain)
        remort = (SRC / "act_info.c").read_text(encoding="latin-1")
        remort = remort[remort.index("void do_remort("):]
        self.assertIn("dismiss_undead_servants( ch )", remort[:remort.index("\n}\n")])

    def test_murder_asks_nokill_like_kill(self) -> None:
        fight = (SRC / "fight.c").read_text(encoding="latin-1")
        murder = fight[fight.index("void do_murder("):]
        murder = murder[:murder.index("\n}\n")]
        self.assertIn("ACT_NOKILL", murder)

    def test_pocket_rooms_do_not_borrow_the_void_pointer(self) -> None:
        magic2 = (SRC / "magic2.c").read_text(encoding="latin-1")
        for spell in ("void spell_rope_trick(", "void spell_haven("):
            body = magic2[magic2.index(spell):]
            body = body[:body.index("\n}\n")]
            self.assertNotIn("was_in_room =", body, spell)


try:
    from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
    LIVE_SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover
    LIVE_SKIP = str(exc)

PW = "Zundead1"
TEMPLE = 4207


@unittest.skipIf(LIVE_SKIP is not None, LIVE_SKIP or "")
class UndeadOutliveNoMasterTests(unittest.TestCase):
    def test_a_vampire_crumbles_when_its_necromancer_quits(self) -> None:
        with LiveMud() as mud:
            for name in ("Zraiser", "Zwatcher"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zraiser", Cla=5, Gui=5, Levl=50, Room=TEMPLE,
                              HMV="500 500 2000 2000 500 500",
                              HMVP="500 2000 500", Sk="100 'create vampire'")
            patch_player_file(mud, "Zwatcher", Room=TEMPLE)
            with mud.connect(timeout=120) as watcher:
                login(watcher, "Zwatcher", PW)
                with mud.connect(timeout=120) as raiser:
                    login(raiser, "Zraiser", PW)
                    for _ in range(4):  # a cast can fail; the cap is one
                        raiser.send("cast 'create vampire'")
                        raiser.drain(3)
                    self.assertIn("vampire", raiser.transcript.lower())
                    watcher.send("look")
                    watcher.drain(2)
                    self.assertIn("vampire", watcher.transcript.lower())
                    raiser.send("quit")
                    self.assertTrue(raiser.wait_closed())
                watcher.drain(2)
                seen = watcher.transcript
                watcher.send("look")
                watcher.drain(2)
                after = watcher.transcript[len(seen):]
                watcher.send("quit")
                self.assertTrue(watcher.wait_closed())
            self.assertIn("crumbles into dust", seen)
            self.assertNotIn("vampire", after.lower())


if __name__ == "__main__":
    unittest.main()
