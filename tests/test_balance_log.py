"""Balancing the world from what players kill (owner, 2026-11-10: "log
everything in a way that'll allow you to balance the game learning from
players who play ... how hard a mob was, how much gold/experience/gear is
given ... several equally powerful mobs for players to choose, the oracle
and where to level and what gear should account for this").

The review of c7101e78 found the old feed counted a group kill once per
member (one "kill" row per player paid). log/progress.tsv now writes an
encounter id at the fight's start (engage), one slain row per mobile
death, a reward row per player paid, flee and death rows naming their
encounter, a drop row of what the corpse was made with (each object's
source) and a loot row for what a player takes back out. The mobile keeps
its own ledger -- the hit points that came off it and what it took off
players -- so a melee of several foes is never one total for all.
webadmin/balance.py joins it; tools/balance_report.py prints it; the
leveling guide, the Oracle and the Gear Finder use it, with the model
kept as a labelled fallback.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from live_mud import (SPARRING_FLOOR, SPARRING_GUARD, LiveMud, create_character,
                      login, patch_player_file, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webadmin import balance  # noqa: E402

SKIP = skip_reason()
sys.path.insert(0, str(ROOT / "tools"))


def consider_audit_pairs(text: str):
    import consider_audit
    return consider_audit.encounter_pairs(text)
PW = "Zbalpass11"
DAGGER = 3701


def head(epoch, kind, who, level, vnum, foe_level, area="zone.are", cls=3):
    return [str(epoch), kind, str(who), str(level), str(cls), "0", "100", "100",
            str(vnum), str(foe_level), area]


def line(fields, tail):
    return "\t".join(fields + [str(t) for t in tail])


class Feed:
    """Synthetic rows in the game's own layout."""

    def __init__(self):
        self.rows = []
        self.n = 0

    def kill(self, t, vnum, foe_level, players, ms, xp, accepted=None, coin=0,
             dealt=50, instant=False, by="player", pets=0, foes=1, gear=None,
             loot_coin=None, loot_items=(), level=22, cls=3):
        self.n += 1
        kid = f"1700000000-{self.n}"
        lead = players[0]
        self.rows.append(line(head(t, "engage", lead, level, vnum, foe_level, cls=cls),
                              [kid, 500, 100, 100, 100, 100, len(players), pets, 20, "-"]))
        self.rows.append(line(head(t, "slain", lead, level, vnum, foe_level, cls=cls),
                              [kid, -1 if instant else ms, "instant" if instant else "blow", by,
                               len(players), pets, 500, 500, 0, dealt, coin]))
        for who in players:
            self.rows.append(line(head(t, "reward", who, level, vnum, foe_level, cls=cls),
                                  [-1 if instant else ms, xp, 0,
                                   xp if accepted is None else accepted, len(players) + pets,
                                   -1, "-", 100, 20, 0, 0, 0, coin, 500, kid, foes,
                                   level if gear is None else gear, 100, 100, 100, 100]))
        items = ",".join(f"{v}:{src}" for v, src, _w in loot_items) or "-"
        worth = sum(w for _v, _s, w in loot_items)
        self.rows.append(line(head(t, "drop", lead, level, vnum, foe_level, cls=cls),
                              [kid, len(loot_items), worth, 20, items]))
        if loot_coin:
            self.rows.append(line(head(t, "loot", lead, level, vnum, foe_level, cls=cls),
                                  [kid, "coin", 0, loot_coin, 0, "coin", "get", len(players)]))
        return kid

    def event(self, t, kind, who, vnum, foe_level, enc="-", level=22):
        self.rows.append(line(head(t, kind, who, level, vnum, foe_level), [80, 500, 120, enc]))

    def legacy(self, t, who, vnum, foe_level, members, ms, xp, level=22):
        self.rows.append(line(head(t, "kill", who, level, vnum, foe_level),
                              [ms, xp, 0, xp, members, -1, "-", 100, 20, 0, 0, 0, 0]))

    def text(self):
        return "\n".join(self.rows) + "\n"


class BalanceModelTests(unittest.TestCase):
    def sample(self) -> Feed:
        f = Feed()
        t = 1000
        # Band 21-25: 2101-2103 pay 100 xp in 10 s; 2104 the same in 2 s.
        for vnum, ms in ((2101, 10000), (2102, 10000), (2103, 11000), (2104, 2000)):
            for i in range(6):
                f.kill(t, vnum, 23, [1 + i % 2], ms, 100, coin=500)
                t += 30
        for i in range(3):                      # 2103 sends one in three running
            f.event(t, "flee", 1, 2103, 23)
            t += 1
        for i in range(9):                      # one character's farm: untrusted
            f.kill(t + i, 2105, 23, [7], 3000, 100)
        return f

    def test_band_figures_and_findings(self) -> None:
        result = balance.compare(balance.summarize(self.sample().text()))
        mobs, band = result["mobs"], result["bands"][(21, 25)]
        self.assertAlmostEqual(mobs[2101]["xp_per_min"], 600.0)
        self.assertIn("generous", mobs[2104]["flags"])
        self.assertIn("risky", mobs[2103]["flags"])
        self.assertAlmostEqual(mobs[2103]["risk"], 3 / 9)
        self.assertEqual(mobs[2101]["coin_generated_per_kill"], 500)
        self.assertFalse(mobs[2105]["trusted"], "one character's kills rank nothing")
        self.assertEqual(sorted(band["equal"]), [2101, 2102])
        self.assertTrue(band["gap"], "two equal choices is a gap")
        props = balance.proposals(result)
        self.assertTrue(any(p["finding"] == "generous" and p["vnum"] == 2104 for p in props))
        self.assertTrue(any(p["finding"] == "gap" and p["band"] == "21-25" for p in props))

    def test_a_group_kill_is_one_kill_with_every_reward(self) -> None:
        f = Feed()
        for i in range(6):
            f.kill(1000 + 60 * i, 3000, 30, [1, 2], 12000, 200, accepted=150)
        m = balance.compare(balance.summarize(f.text()))["mobs"][3000]
        self.assertEqual(m["kills"], 6, "six kills, not twelve")
        self.assertEqual(m["characters"], 2)
        self.assertEqual(m["group_share"], 1.0)
        self.assertAlmostEqual(m["xp_per_min"], 1000.0, msg="200 offered each, over 12 s")
        self.assertAlmostEqual(m["accepted_xp_per_min"], 750.0)
        self.assertEqual(m["legacy"], 0)

    def test_legacy_rows_are_weighed_and_marked(self) -> None:
        f = Feed()
        for i in range(4):          # two members' rows for each of four kills
            f.legacy(1000 + i, 1, 3100, 30, 2, 9000, 100)
            f.legacy(1000 + i, 2, 3100, 30, 2, 9000, 100)
        m = balance.compare(balance.summarize(f.text()))["mobs"][3100]
        self.assertEqual(m["kills"], 4)
        self.assertEqual(m["legacy"], 8)
        out = self.report(f.text(), "--all")
        self.assertIn("legacy rows", out)

    def test_loot_against_what_was_made(self) -> None:
        f = Feed()
        for i in range(6):
            f.kill(1000 + 60 * i, 3200, 30, [1 + i % 2], 10000, 100, coin=1000,
                   loot_coin=1000 if i < 3 else None,
                   loot_items=((DAGGER, "carried", 300),) if i % 2 == 0 else ())
        m = balance.compare(balance.summarize(f.text()))["mobs"][3200]
        self.assertEqual(m["coin_generated_per_kill"], 1000)
        self.assertEqual(m["coin_looted_per_kill"], 500, "half the corpses were left")
        self.assertEqual(m["drop_rate"], 0.5)
        self.assertAlmostEqual(m["gear_generated_per_kill"], 150)
        self.assertAlmostEqual(m["unlooted_share"], 0.5)

    def test_instant_kills_zero_xp_pets_and_two_foes(self) -> None:
        f = Feed()
        for i in range(6):
            f.kill(1000 + 60 * i, 3300, 30, [1 + i % 2], 10000, 300,
                   accepted=0 if i < 2 else None, instant=i == 5,
                   by="pet" if i == 4 else "player", pets=1 if i == 4 else 0,
                   foes=2 if i == 3 else 1)
        m = balance.compare(balance.summarize(f.text()))["mobs"][3300]
        self.assertEqual(m["instant"], 1, "an instant kill has no time to divide by")
        self.assertEqual(m["median_seconds"], 10.0)
        self.assertAlmostEqual(m["capped_share"], 2 / 6)
        self.assertAlmostEqual(m["xp_per_min"], 1800.0, msg="offered xp, capped or not")
        self.assertAlmostEqual(m["multi_foe_share"], 1 / 6)
        self.assertAlmostEqual(m["group_share"], 1 / 6, msg="a pet makes it no solo kill")

    def test_downtime_and_quantiles(self) -> None:
        f = Feed()
        for i in range(8):
            f.kill(1000 + 40 * i, 3400, 30, [1 + i % 2], 5000 + 1000 * i, 120)
        m = balance.compare(balance.summarize(f.text()))["mobs"][3400]
        self.assertEqual(m["cycle_seconds"], 80.0, "each character kills every 80 s")
        self.assertAlmostEqual(m["xp_per_hour"], 120 * 3600 / 80)
        self.assertLess(m["p25_seconds"], m["median_seconds"])
        self.assertLess(m["median_seconds"], m["p75_seconds"])

    def test_kills_in_one_second_share_it(self) -> None:
        """Review, 2026-11-12: the journal stamps whole seconds, and two
        players each making two 100-xp kills a second read as 360,000 xp
        an hour, not about 720,000: every reward in a second looked up the
        one 1-second gap."""
        f = Feed()
        for second in range(6):
            for who in (1, 2):
                for _ in range(2):
                    f.kill(1000 + second, 3500, 30, [who], 300, 100)
        m = balance.compare(balance.summarize(f.text()))["mobs"][3500]
        self.assertEqual(m["kills"], 24)
        self.assertEqual(m["cycle_seconds"], 0.5, "two kills a second is half a second each")
        self.assertAlmostEqual(m["xp_per_hour"], 100 * 3600 / 0.5)

        # The seconds are counted once, never once per kill: each player's
        # five seconds after the first are spread over that second's two.
        cyc = balance.cycles(balance.records(f.text(), 0.0))
        self.assertEqual(len(cyc), 10)
        self.assertAlmostEqual(sum(v * 2 for v in cyc.values()), 2 * 5.0)

    def test_single_kills_and_a_long_break(self) -> None:
        f = Feed()
        # One kill every 20 s, then a break past CYCLE_CAP_S, then two kills
        # in one second ten seconds after a single one.
        t = 1000
        for _ in range(5):
            f.kill(t, 3600, 30, [1], 4000, 100)
            t += 20
        t += balance.CYCLE_CAP_S + 1000          # a break: no cycle across it
        f.kill(t, 3600, 30, [1], 4000, 100)
        f.kill(t + 10, 3600, 30, [1], 4000, 100)
        f.kill(t + 10, 3600, 30, [1], 4000, 100)
        cyc = balance.cycles(balance.records(f.text(), 0.0))
        times = sorted(cyc.items())
        self.assertEqual([v for _k, v in times], [20.0, 20.0, 20.0, 20.0, 5.0],
                         "four 20 s gaps, nothing across the break, 10 s shared by two")

    def test_sparse_data_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.tsv"
            f = Feed()
            for i in range(6):
                f.kill(1000 + 60 * i, 3500, 6, [1 + i % 2], 30000, 50, level=5)
            for i in range(6):
                f.kill(5000 + 60 * i, 3500, 6, [3 + i % 2], 1000, 50, level=30)
            f.kill(9000, 3600, 6, [1], 9000, 50, level=5)         # one kill: too few
            path.write_text(f.text(), encoding="latin-1")
            self.assertEqual(balance.near(path, 3500, 4)["median_seconds"], 30.0)
            self.assertEqual(balance.near(path, 3500, 31)["median_seconds"], 1.0)
            self.assertIsNone(balance.near(path, 3500, 18), "nobody near level 18")
            self.assertIsNone(balance.near(path, 3600, 5), "one kill is not a measure")

    def report(self, text: str, *extra: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "progress.tsv"
            path.write_text(text, encoding="latin-1")
            out = subprocess.run([sys.executable, "tools/balance_report.py", "--file", str(path),
                                  "--no-names", *extra], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def test_report_runs_on_a_file(self) -> None:
        out = self.report(self.sample().text())
        self.assertIn("foe levels 21-25", out)
        self.assertIn("** GAP **", out)
        self.assertIn("generous", out)
        self.assertIn("risky", out)
        self.assertIn("proposals (manual; nothing is changed)", out)
        one = self.report(self.sample().text(), "--vnum", "2101")
        self.assertIn("level 21-25", one)


class BalanceWiringTests(unittest.TestCase):
    def test_the_guide_the_oracle_and_the_finder_read_it(self) -> None:
        server = (ROOT / "webadmin" / "server.py").read_text(encoding="utf-8")
        guide = server.split("async def get_leveling(", 1)[1].split("\ndef ", 1)[0]
        # Loaded once, off the event loop, and every mobile read from that load.
        self.assertIn("bal = await balance.load_async(PROGRESS_LOG)", guide)
        self.assertIn("balance.near(bal, int(mob.vnum), level)", guide)
        self.assertIn('"basis": "measured" if close else "modelled"', guide)
        self.assertIn("if int(mob.vnum) in guardians:", guide)
        self.assertIn('"needs": needs', guide)
        self.assertNotIn("the game logs no combat damage", guide)
        self.assertNotIn("never the order", guide)
        finder = server.split("async def get_best_gear(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"seen_drops"', finder)
        self.assertIn("balance.seen_drops(await balance.load_async(PROGRESS_LOG))", finder)
        self.assertIn("players: %s kills by %s characters", server)
        self.assertIn('PROGRESS_LOG = Path(args.log_file).parent / "progress.tsv"', server)
        app = (ROOT / "webadmin" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('label: "Basis"', app)
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertIn("progress_drop( ch, victim, corpse );", fight)
        self.assertIn("progress_slain( ch, victim, players, pets );", fight)
        self.assertIn("victim->enc_taken += taken;", fight)
        obj = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        self.assertIn("progress_loot( ch, top, obj, copper );", obj)
        playlog = (ROOT / "src" / "playlog.c").read_text(encoding="latin-1")
        raw = playlog.split("static void progress_write_raw(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("IS_IMMORTAL( ch )", raw, "immortals write nothing; a trusted mortal is counted")
        self.assertIn("play_hidden( ch )", raw)


@unittest.skipIf(SKIP is not None, SKIP or "")
class BalanceLiveTests(unittest.TestCase):
    def test_kills_rewards_drops_and_loot_join_up(self) -> None:
        hearty = {"HMV": "5000 5000 3000 3000 1000 1000", "HMVP": "5000 3000 1000", "AfBy": 512}
        with LiveMud(fixtures=True) as mud:
            for name, level, extra in (("Zbalstaff", 70, {}), ("Zbalone", 30, dict(hearty, Cla=0)),
                                       ("Zbaltwo", 30, dict(hearty, Cla=0)),
                                       ("Zbalcap", 50, hearty)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=SPARRING_FLOOR, **extra)
            for who, skill in (("Zbaltwo", "charm person"), ("Zbalone", "magic missile")):
                path = mud.player_dir / who
                text = path.read_text(encoding="latin-1")
                at = text.index("\nEnd\n")
                path.write_text(text[:at] + f"\nSk 100 '{skill}'" + text[at:], encoding="latin-1")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as one, \
                    mud.connect(timeout=120) as two, mud.connect(timeout=120) as cap:
                for client, name in ((staff, "Zbalstaff"), (one, "Zbalone"),
                                     (two, "Zbaltwo"), (cap, "Zbalcap")):
                    login(client, name, PW)
                    client.sync("scroll 0")

                def frail_guard(gold: int = 0, level: int = 0) -> None:
                    staff.must(f"load mob {SPARRING_GUARD}", "You create")
                    staff.must("set char guard hp 5", "")
                    staff.must("restore guard", "")
                    if gold:
                        staff.must(f"set char guard gold {gold}", "Gold amount")
                    if level:
                        staff.must(f"set char guard level {level}", "")

                # (e) One group kill: one slain row, two rewards. The guard
                # carries a dagger and coin; only the dagger is taken.
                two.must("follow zbalone", "You now follow")
                one.must("group zbaltwo", "")
                frail_guard(gold=3)
                staff.must(f"load obj {DAGGER}", "You create")
                staff.must("give dagger guard", "You give")
                one.send("kill guard")
                one.expect("is DEAD", timeout=60)
                two.sync("get dagger corpse", timeout=60)
                staff.sync("purge")
                two.sync("follow self")

                # (f) Two foes on one player: the kill says so. One fights a
                # sturdy guard and strikes a frail one down with a spell.
                staff.must(f"load mob {SPARRING_GUARD}", "You create")
                one.sync("kill guard", timeout=60)
                frail_guard()
                one.send("cast 'magic missile' 1.guard")
                one.expect("is DEAD", timeout=60)
                staff.sync("peace")
                staff.sync("purge")

                # A pet's kill: credited to its master.
                staff.must(f"load mob {SPARRING_GUARD}", "You create")
                for _ in range(12):
                    two.sync("cast 'charm person' guard", timeout=60)
                    staff.sync("peace")
                    if "Master: Zbaltwo" in staff.must("stat mob guard", "Vnum:"):
                        break
                staff.must("set char guard damroll 300", "")
                staff.must("set char guard hitroll 300", "")
                frail_guard()
                two.send("order 2.guard kill 1.guard")
                two.expect("is DEAD", timeout=60)
                staff.sync("purge")

                # A level 50 accepts no experience; the kill still counts.
                frail_guard(level=50)
                cap.must("consider guard", "level")
                cap.send("kill guard")
                cap.expect("is DEAD", timeout=60)
                for client in (one, two, cap, staff):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")
        rows = [r.split("\t") for r in text.splitlines()]
        slain = [r for r in rows if r[1] == "slain"]
        rewards = [r for r in rows if r[1] == "reward"]
        self.assertEqual(len(slain), 4, text)
        group_kill = slain[0][11]
        paid = [r for r in rewards if r[25] == group_kill]
        self.assertEqual(len(paid), 2, "both members are paid: " + text)
        self.assertEqual(slain[0][15], "2", "two players credited")
        self.assertTrue(all(int(r[12]) > 0 for r in paid), "each has its own base xp")
        self.assertGreaterEqual(int(slain[0][21]), 3 * 10000, "three gold and its own roll, in copper")
        self.assertGreater(int(slain[0][18]), 0, "the hit points that came off it")
        drop = [r for r in rows if r[1] == "drop" and r[11] == group_kill]
        self.assertIn(f"{DAGGER}:carried", drop[0][15].split(","))
        loot = [r for r in rows if r[1] == "loot" and r[11] == group_kill]
        self.assertIn(("obj", str(DAGGER)), [(r[12], r[13]) for r in loot], loot)
        # The killer's AUTOGOLD took the coin: every copper made, looted.
        self.assertEqual(sum(int(r[14]) for r in loot if r[12] == "coin"), int(slain[0][21]), loot)
        engaged = {r[11]: r for r in rows if r[1] == "engage"}
        self.assertIn(group_kill, engaged)
        # Every encounter carries what CONSIDER would have said, unasked,
        # and the slain row the rounds it came to.
        self.assertIn(engaged[group_kill][25],
                      ("scratch", "easily", "win", "narrow", "even", "lose", "die"))
        self.assertGreater(float(engaged[group_kill][23]), 0, "predicted rounds")
        self.assertRegex(slain[0][22], r"^\d+$", "the rounds it fought")
        self.assertEqual(len(slain[0]), 26, slain[0])
        # Every kill's landed swings are among its swings: the first blow's
        # swing was lost before the encounter had its id (live, 2026-11-11).
        for row in slain:
            self.assertGreaterEqual(int(row[23]), int(row[24]), ("landed of swung", row))
        self.assertGreaterEqual(int(slain[0][23]), 1, "the killing swing counts")
        self.assertGreater(int(slain[1][25]), 0, "the magic missile's hit points")
        audit = consider_audit_pairs(text)
        self.assertGreaterEqual(len(audit), 4, "every fight held to its prediction")
        two_foes = [r for r in rewards if r[25] == slain[1][11]]
        self.assertEqual(two_foes[0][26], "2", "another foe was on them: " + text)
        self.assertEqual(slain[2][14], "pet", text)
        pet_paid = [r for r in rewards if r[25] == slain[2][11]]
        self.assertEqual(len(pet_paid), 1, text)
        capped = [r for r in rewards if r[25] == slain[3][11]]
        self.assertGreater(int(capped[0][12]), 0, "offered")
        self.assertEqual(capped[0][14], "0", "accepted nothing at level 50")
        self.assertNotIn("Zbal", text, "no names")
        # CONSIDER wrote what it predicted, and the audit joins it to the
        # kill that followed, exactly.
        considered = [r for r in rows if r[1] == "consider"]
        self.assertEqual(len(considered), 1, text)
        self.assertEqual(considered[0][8], str(SPARRING_GUARD))
        import consider_audit
        pairs = consider_audit.exact_pairs(consider_audit.outcomes(text))
        self.assertEqual(len(pairs), 1, pairs)
        self.assertEqual(pairs[0]["outcome"]["kind"], "kill")
        # The model reads it whole: one kill each, the group's counted once.
        result = balance.compare(balance.summarize(text))
        self.assertEqual(result["mobs"][SPARRING_GUARD]["kills"], 4)
        self.assertEqual(result["mobs"][SPARRING_GUARD]["capped_share"], 1 / 5)


if __name__ == "__main__":
    unittest.main()
