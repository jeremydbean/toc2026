"""The dashboard's balance figures, kept up to date as log/progress.tsv grows.

Review, 2026-11-12: webadmin/balance.py read and reparsed the whole feed
after every appended row -- most of a second on a full 40,000-row feed --
and /api/leveling and /api/best_gear called it on the event loop. It now
reads only what was appended and figures again only the mobiles the new
rows touch, starts again from the beginning when the file is replaced
(the game's trim renames a new file over it), cut short or rewritten, and
runs off the event loop with one lock, so requests that arrive together
share one parse. The answer must be exactly what the one-pass functions
give for the same complete lines: that is what these tests hold it to.

Every feed here is synthetic, in temporary directories: numbers only.
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webadmin import balance  # noqa: E402

try:
    # httpx2 is what scripts/requirements.txt declares and CI installs;
    # plain httpx is only there when something else pulled it in.
    try:
        import httpx2 as httpx  # noqa: F401
    except ImportError:
        import httpx  # noqa: F401
    from webadmin import server  # noqa: E402
    WEB_SKIP = None
except Exception as exc:  # pragma: no cover - env dependent
    server = None
    WEB_SKIP = f"webadmin.server or httpx2 unavailable: {exc}"


def head(t, kind, who, level, vnum, foe_level, cls=3, area="zone.are"):
    return [str(t), kind, str(who), str(level), str(cls), "0", "100", "100",
            str(vnum), str(foe_level), area]


def row(fields, tail) -> str:
    return "\t".join(fields + [str(x) for x in tail]) + "\n"


def synthetic_feed(n_kills: int, seed: int = 11, start: int = 1_700_000_000) -> str:
    """Every kind of row the reader knows, in the game's layout: engage,
    slain, reward, drop and loot for each kill, flees and deaths (some on
    no encounter), legacy kill and drop rows, encounters that never end,
    and kills shared in one second."""
    rnd = random.Random(seed)
    out = []
    t = start
    mobs = [(3000 + i, 1 + (i * 7) % 50) for i in range(40)]
    for n in range(n_kills):
        vnum, fl = rnd.choice(mobs)
        kid = f"{start}-{n}"
        players = [65536 + rnd.randrange(12) for _ in range(1 if rnd.random() < 0.7 else 2)]
        lvl, cls, ms = max(1, fl + rnd.randint(-3, 3)), rnd.randrange(6), rnd.randint(1500, 30000)
        lead = players[0]
        out.append(row(head(t, "engage", lead, lvl, vnum, fl, cls),
                       [kid, 500, 100, 100, 100, 100, len(players), 0, lvl, "-"]))
        roll = rnd.random()
        if roll < 0.06:
            out.append(row(head(t + 3, rnd.choice(("flee", "death")), lead, lvl, vnum, fl, cls),
                           [rnd.randint(1, 90), 500, 80, kid]))
        elif roll < 0.09:
            pass                                    # an encounter that never ended
        elif roll < 0.14:
            members = rnd.choice((1, 2, 3))
            out.append(row(head(t, "kill", lead, lvl, vnum, fl, cls),
                           [ms, 120, 0, 120, members, -1, "-", 100, 20, 0, 0, 0, 300]))
            out.append(row(head(t, "drop", lead, lvl, vnum, fl, cls),
                           [1, 900, 20, f"{4000 + rnd.randrange(9)}"]))
        else:
            out.append(row(head(t, "slain", lead, lvl, vnum, fl, cls),
                           [kid, ms, "blow", "player", len(players), 0, 500, 500, 0,
                            rnd.randint(0, 200), rnd.randint(0, 9000), 8, 10, 7, 30]))
            for who in players:
                xp = rnd.randint(40, 400)
                out.append(row(head(t, "reward", who, lvl, vnum, fl, cls),
                               [ms, xp, 0, 0 if rnd.random() < 0.05 else xp, len(players),
                                -1, "-", 100, 20, 0, 0, 0, rnd.randint(0, 9000), 500, kid,
                                rnd.choice((1, 1, 2)), lvl, 100, 100, 100, 100]))
            items = f"{4000 + rnd.randrange(9)}:carried" if rnd.random() < 0.3 else "-"
            out.append(row(head(t, "drop", lead, lvl, vnum, fl, cls),
                           [kid, 0 if items == "-" else 1, 0 if items == "-" else 900, 20, items]))
            if rnd.random() < 0.5:
                out.append(row(head(t, "loot", lead, lvl, vnum, fl, cls),
                               [kid, "coin", 0, rnd.randint(1, 9000), 0, "coin", "get",
                                len(players)]))
        if rnd.random() < 0.03:
            out.append(row(head(t, "flee", 65536 + rnd.randrange(12), fl, vnum, fl), [50, 500, 9, "-"]))
        t += rnd.choice((0, 0, 1, 5, 30, 200, 900))
    return "".join(out)


def reference(data: bytes):
    """The one-pass answer for every complete line of `data`."""
    cut = data.rfind(b"\n") + 1
    return balance.compare(balance.summarize(data[:cut].decode("latin-1")))


def canonical(value) -> str:
    """A result as one exact string: keys as text, sorted; tuples and
    Counters as their plain forms; floats by repr, so 0.1 + 0.2 is not 0.3."""
    import json

    def plain(v):
        if isinstance(v, dict):
            return {repr(k) if not isinstance(k, str) else k: plain(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [plain(x) for x in v]
        if isinstance(v, float):
            return "f" + repr(v)
        return v
    return json.dumps(plain(value), sort_keys=True)


# canonical() of compare(summarize(synthetic_feed(1500))) -- its mobiles,
# bands and seen drops, and proposals() of it -- as the balance.py before
# the incremental reader (commit d1d458586) computed them. The new reader,
# one pass or grown in pieces, must give exactly these.
GOLDEN_FEED_KILLS = 1500
GOLDEN_SHA256 = {
    "mobs": "8b24d6a8c750913859a058827968910e4e4f0170a1936dd967c962b0b4db071e",
    "bands": "15f0af43c744a3a83fa76a44546a0157665ba66c32823d410f86d6c15bc76571",
    "seen": "a5b4601cb70beccf3c276636ce5b7f4f51300d2288da811c167ce358648ac59a",
    "proposals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
}


class BalanceCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "progress.tsv"
        balance._STATES.clear()
        balance.STATS.clear()

    def tearDown(self) -> None:
        balance._STATES.clear()
        self.tmp.cleanup()

    def write(self, data: bytes, mode: str = "wb") -> None:
        with open(self.path, mode) as fh:
            fh.write(data)

    def assertSameAnswer(self, data: bytes) -> None:
        got, want = balance.load(self.path), reference(data)
        for part in ("mobs", "bands", "seen"):
            self.assertEqual(got[part], want[part], part)
        self.assertEqual(got["summary"], want["summary"])

    def test_appends_in_pieces_come_to_the_one_pass_answer(self) -> None:
        data = synthetic_feed(700).encode("latin-1")
        rnd = random.Random(5)
        self.write(b"")
        pos = 0
        while pos < len(data):
            # Pieces of any size, cut anywhere -- inside a row too.
            nxt = min(len(data), pos + rnd.choice((1, 9, 80, 400, 3000, 12000)))
            self.write(data[pos:nxt], "ab")
            pos = nxt
            self.assertSameAnswer(data[:pos])
        self.assertEqual(balance.STATS["full"], 1, "one parse from the start, then growth")
        self.assertGreater(balance.STATS["grow"], 20)

    def test_the_figures_are_the_old_readers_exactly(self) -> None:
        import hashlib

        def digests(result):
            got = {part: hashlib.sha256(canonical(result[part]).encode()).hexdigest()
                   for part in ("mobs", "bands", "seen")}
            got["proposals"] = hashlib.sha256(
                canonical(balance.proposals(result)).encode()).hexdigest()
            return got

        data = synthetic_feed(GOLDEN_FEED_KILLS).encode("latin-1")
        self.assertEqual(digests(reference(data)), GOLDEN_SHA256, "one pass")
        half = data.rfind(b"\n", 0, len(data) // 2) + 1
        self.write(data[:half])
        balance.load(self.path)
        self.write(data[half:], "ab")
        self.assertEqual(digests(balance.load(self.path)), GOLDEN_SHA256, "grown in pieces")
        self.assertEqual(balance.STATS["grow"], 1)

    def test_an_unchanged_file_is_the_same_answer(self) -> None:
        self.write(synthetic_feed(80).encode("latin-1"))
        first = balance.load(self.path)
        self.assertIs(balance.load(self.path), first)
        self.assertEqual(balance.STATS["same"], 1)

    def test_a_row_still_being_written_is_not_read(self) -> None:
        data = synthetic_feed(60).encode("latin-1")
        self.write(data)
        before = balance.load(self.path)
        torn = row(head(1_800_000_000, "slain", 65540, 10, 3001, 10),
                   ["X-1", 9000, "blow", "player", 1, 0, 500, 500, 0, 20, 300, 5, 6, 5, 10])
        half = torn.encode()[:40]
        self.write(half, "ab")
        self.assertEqual(balance.load(self.path)["mobs"], before["mobs"])
        self.write(torn.encode()[40:], "ab")
        self.assertSameAnswer(data + torn.encode())
        self.assertEqual(balance.STATS["full"], 1)

    def test_the_games_trim_renamed_over_it_is_read_again(self) -> None:
        data = synthetic_feed(400).encode("latin-1")
        self.write(data)
        balance.load(self.path)
        # progress_trim: the newest lines written to a temporary file and
        # renamed over the feed -- another inode, maybe a longer file later.
        lines = data.splitlines(keepends=True)
        kept = b"".join(lines[len(lines) // 2:]) + synthetic_feed(30, seed=3).encode("latin-1")
        tmp = self.path.with_name("progress.tsv.tmp")
        tmp.write_bytes(kept)
        os.replace(tmp, self.path)
        self.assertSameAnswer(kept)
        self.assertEqual(balance.STATS["full"], 2)

    def test_a_shorter_or_rewritten_file_is_read_again(self) -> None:
        data = synthetic_feed(300).encode("latin-1")
        self.write(data)
        balance.load(self.path)
        with open(self.path, "r+b") as fh:          # cut short, in place
            fh.truncate(len(data) // 3)
        self.assertSameAnswer(data[:len(data) // 3])
        self.assertEqual(balance.STATS["full"], 2)
        # Rewritten in place, longer than before: the bytes read before are
        # not there any more, so it is not growth.
        other = synthetic_feed(320, seed=99).encode("latin-1")
        self.assertGreater(len(other), len(data) // 3)
        with open(self.path, "r+b") as fh:
            fh.write(other)
        self.assertSameAnswer(other)
        self.assertEqual(balance.STATS["full"], 3)

    def test_a_row_rewriting_a_kill_already_read_starts_again(self) -> None:
        data = synthetic_feed(120).encode("latin-1")
        self.write(data)
        balance.load(self.path)
        kid = next(line.split(b"\t")[11] for line in data.splitlines()
                   if line.split(b"\t")[1] == b"slain").decode()
        again = row(head(1_800_000_000, "slain", 65540, 10, 3999, 10),
                    [kid, 9000, "blow", "player", 1, 0, 500, 500, 0, 20, 300, 5, 6, 5, 10])
        self.write(again.encode(), "ab")
        self.assertSameAnswer(data + again.encode())
        self.assertEqual(balance.STATS["full"], 2, "another mobile's kill id: read again")

    def test_a_missing_file_is_nothing(self) -> None:
        self.assertEqual(balance.load(self.path)["mobs"], {})
        self.assertIsNone(balance.load(self.path)["summary"])

    def test_requests_together_share_one_parse(self) -> None:
        self.write(synthetic_feed(3000).encode("latin-1"))
        calls = []
        real = balance._full

        def counted(path, st):
            calls.append(1)
            time.sleep(0.2)             # long enough for every thread to be waiting
            return real(path, st)

        results = []
        with patch.object(balance, "_full", counted):
            threads = [threading.Thread(target=lambda: results.append(balance.load(self.path)))
                       for _ in range(6)]
            for th in threads:
                th.start()
            for th in threads:
                th.join(30)
        self.assertEqual(len(calls), 1, "one parse for six requests")
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r is results[0] for r in results))

    def test_the_figures_handed_out_do_not_change_under_a_reader(self) -> None:
        data = synthetic_feed(200).encode("latin-1")
        self.write(data)
        first = balance.load(self.path)
        frozen = reference(data)
        self.write(synthetic_feed(50, seed=4, start=1_700_900_000).encode("latin-1"), "ab")
        balance.load(self.path)
        self.assertEqual(first["mobs"], frozen["mobs"])
        self.assertEqual(first["summary"]["by_vnum"], frozen["summary"]["by_vnum"])

    def test_version_moves_with_the_feed(self) -> None:
        self.assertEqual(balance.version(self.path), "none")
        self.write(b"x\n")
        v1 = balance.version(self.path)
        self.write(b"y\n", "ab")
        self.assertNotEqual(balance.version(self.path), v1)

    def test_near_and_seen_drops_take_a_loaded_answer(self) -> None:
        self.write(synthetic_feed(600).encode("latin-1"))
        loaded = balance.load(self.path)
        for vnum in list(loaded["mobs"])[:10]:
            for level in (5, 20, 40):
                self.assertEqual(balance.near(loaded, vnum, level),
                                 balance.near(self.path, vnum, level))
        self.assertEqual(balance.seen_drops(loaded), balance.seen_drops(self.path))


@unittest.skipIf(WEB_SKIP is not None, WEB_SKIP or "")
class BalanceOffTheEventLoopTests(unittest.TestCase):
    def test_a_fast_route_answers_while_the_feed_is_parsed(self) -> None:
        from types import SimpleNamespace

        started = threading.Event()
        when: dict = {}
        real = balance.load

        def slow_load(path):
            when["start"] = time.perf_counter()
            started.set()
            time.sleep(1.5)              # a long feed's first parse
            return real(path)

        fake = SimpleNamespace(mobiles={}, rooms={}, objects={})

        async def scenario():
            transport = httpx.ASGITransport(app=server.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                leveling = asyncio.create_task(client.get("/api/leveling", params={"level": 20}))
                while not started.is_set():
                    await asyncio.sleep(0.01)
                health = await client.get("/api/health")
                # From the parse starting to the other route's answer: on
                # the event loop, the parse's whole 1.5 s.
                fast = time.perf_counter() - when["start"]
                self.assertFalse(leveling.done(), "the parse is still running")
                done = await leveling
                return health, fast, done

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(balance, "load", slow_load), \
                patch.object(server, "parser", fake), \
                patch.object(server, "load_directions", lambda: {"routes": []}), \
                patch.object(server, "PROGRESS_LOG", Path(tmp) / "progress.tsv"):
            health, fast, leveling = asyncio.run(scenario())
        self.assertEqual(health.status_code, 200)
        self.assertLess(fast, 0.75, "the health check waited on the parse")
        self.assertEqual(leveling.status_code, 200)


if __name__ == "__main__":
    unittest.main()
