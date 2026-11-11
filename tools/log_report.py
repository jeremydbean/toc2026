#!/usr/bin/env python3
"""One report of what players did and what went wrong, from the synced logs.

The game host's log/toc.log and log/channels.tsv reach git every five
minutes. This reads them from a git ref (origin/main by default, after
`git fetch`) and prints, for a window of time:

  players     who played and for how many commands
  bugs        every "[*****] BUG:" line, grouped, with the watched
              commands just before the first of each
  refused     commands the game refused ("(refused) <word>" in the
              watch log) -- a word typed again and again is a command
              players expect (CHAT was found this way). Very frequent
              words from one player are likely aliases, listed apart.
  help        HELP that did not help: a topic read and then its word
              refused within ten minutes (HELP HEROQUEST taught commands
              that did not exist, 2026-10-22), and HELP that found nothing
  repeats     the same command typed five or more times running by one
              player, outside a fight: the reply did not tell them what
              they needed (TRACK, HIDE and REFRESH were found this way)
  deaths      who died, to what, where
  events      black market, treasure goblin, login fixes; the same event
              again and again (the goblin drifting every ten minutes) is
              one line with a count
  quests      what the quest master handed out, by area and kind
  coin        the biggest coin gains per player, to spot an exploit, and
              each session's coin split by where it came from; what coin
              was spent on, where experience came from, what each kind of
              quest paid in kills, and what each foe carried
  deep        pulses past their budget and what took the time, deaths
              with the killing blow (one-blow deaths apart), things gone
              from players and why, quests lost and their targets
  memory      MEMORY lines (stale pointers memguard.c caught and repaired)
              by field, the newest five, and the backtraces of the latest
              crashes in log/crash.log
  chat        public channel lines (never tells; they are not logged)

Addresses and hostnames are stripped from everything printed. Run from
the repository root:

    git fetch -q origin main && python3 tools/log_report.py            # last 24h
    python3 tools/log_report.py --since "2026-10-20 00:00"
    python3 tools/log_report.py --since 2026-10-20 --player Trentlin
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = re.compile(r"^(\w{3} \w{3} [ \d]\d \d\d:\d\d:\d\d \d{4}) :: (.*)$")
WATCHED = re.compile(r"^Log (\w+) \[(-|\d+)\]: (.*)$")   # "-": a room the game hides
IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
IPV6 = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{1,4}:){3,7}[0-9a-fA-F]{1,4}(?![\w:])"
                  r"|(?<![\w:])[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4})*::[0-9a-fA-F:]*")
HOST = re.compile(r"@\S+")
# A resolved address (DNS lookup is on by default): name.isp.tld.
HOSTNAME = re.compile(r"\b(?:[A-Za-z0-9-]+\.)+(?:com|net|org|edu|gov|mil|io|co|us|uk|ca|au|de|fr|"
                      r"nl|ru|br|jp|info|biz|[a-z]{2})\b")
# Lines that exist to name a player's address; nothing in them is worth
# printing once the address is gone.
ADDRESS_LINES = ("shares an address", "Sock.sinaddr")
# What watch_log writes beside the typed commands: purse changes, trades,
# the stash, socials. Not commands, so not counted as typed.
EVENT_LINE = re.compile(r"^(?:(?:coin|gold|copper|silver|platinum) [+-]\d"
                        r"|(?:bought|sold|stashed|withdrew|gave|received|on|level|killed"
                        r"|arrived|moved to|died to) |\(social\)"
                        r"|(?:affects off|quest assigned|quest complete|daily quest complete"
                        r"|daily points):)")
QUEST_ASSIGNED = re.compile(r"^quest assigned: (kill|recover) .* in (\S+), (\d+) minutes?, (\w+)$")
HELP_WINDOW = timedelta(minutes=10)
EVENT_PREFIXES = ("Black market:", "Treasure goblin:", "Login fix", "Stray mage groups:",
                  "Mage weapon floors:")
NOISY = {"l", "look", "sc", "scan", "n", "s", "e", "w", "u", "d", "ne", "nw", "se", "sw",
         "north", "south", "east", "west", "up", "down", "k", "kill", "get all", "get coins",
         "sac", "sac cor", "get all cor", "score", "sco", "inv", "i", "eq", "wor", "worth", "save",
         ""}


def clean(text: str) -> str:
    """Never print an address or a hostname."""
    if any(marker in text for marker in ADDRESS_LINES):
        return "(a line about a player's address, left out)"
    text = IPV6.sub("<ip>", IPV4.sub("<ip>", text))
    return HOSTNAME.sub("<host>", HOST.sub("@<host>", text))


def git_show(ref: str, path: str) -> str:
    out = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT, capture_output=True)
    return out.stdout.decode("latin-1", "replace") if out.returncode == 0 else ""


PRICE_UNITS = {"p": 1_000_000, "g": 10_000, "s": 100, "c": 1}


def parse_price(text: str) -> int:
    """format_price's words back to copper: "1p 20g", "5s", "free"."""
    total = 0
    for amount, letter in re.findall(r"(\d+)([pgsc])\b", text):
        total += int(amount) * PRICE_UNITS[letter]
    return total


def parse_tally(field: str, prefix: str, coin: bool) -> dict:
    """A session's "spent on: stash 1550p, heal 5g" or "exp: kills +900,
    flee -10" as {label: amount}; "none" or a missing column is {}."""
    if not field.startswith(prefix):
        return {}
    body = field[len(prefix):].strip()
    if body in ("", "none"):
        return {}
    out = {}
    for part in body.split(", "):
        if coin:
            m = re.match(r"^(.*?) ((?:\d+[pgsc] ?)+|free)$", part)
            if m:
                out[m.group(1)] = out.get(m.group(1), 0) + parse_price(m.group(2))
        else:
            m = re.match(r"^(.*) ([+-]\d+)$", part)
            if m:
                out[m.group(1)] = out.get(m.group(1), 0) + int(m.group(2))
    return out


def economy_summary(rows) -> dict:
    """Where coin went and experience came from, over every sitting in
    the window, and what each kind of quest paid against the kill it is
    priced in (2026-11-05). Sittings are merged first, since a link loss
    and the quit after it carry the same running totals."""
    spent: Counter = Counter()
    exp: Counter = Counter()
    for r in merge_sittings([r for r in rows if r[1] == "session"]):
        for field in r[6:]:
            for label, amount in parse_tally(field, "spent on: ", True).items():
                spent[label] += amount
            for label, amount in parse_tally(field, "exp: ", False).items():
                exp[label] += amount
    quests: dict = {}
    for r in rows:
        if r[1] != "outcome" or len(r) < 11 or r[6] != "quest-complete" or r[7] != "success":
            continue
        words = dict(w.split("=", 1) for w in r[10].split() if "=" in w)
        kind = r[10].split()[0] if r[10] else "-"
        q = quests.setdefault(kind, {"n": 0, "coin": 0, "kills": 0.0, "priced": 0, "points": 0})
        q["n"] += 1
        coin = int(words.get("coin", "0").lstrip("+") or 0)
        q["coin"] += coin
        kill = int(words.get("kill", "0") or 0)
        if kill > 0:            # rows from before 2026-11-05 carry no kill=
            q["kills"] += coin / kill
            q["priced"] += 1
        q["points"] += int(words.get("offered", "0") or 0)
    return {"spent": spent, "exp": exp, "quests": quests}


def deep_summary(rows) -> dict:
    """The deep bug rows (2026-11-05): stalls by the phase that took the
    time, deaths by killer with the one-blow ones apart, things gone from
    players by why, and lost quests by target -- a target the world held
    none of (alive=0) could never have been finished."""
    stalls: Counter = Counter()
    stall_ms: dict = {}
    deaths: Counter = Counter()
    one_blow = []
    gone: Counter = Counter()
    lost: Counter = Counter()
    impossible: Counter = Counter()
    for r in rows:
        kind = r[1] if len(r) > 1 else ""
        if kind == "stall" and len(r) > 8:
            m = re.match(r"^slowest (\S+) (\d+)ms$", r[7])
            phase = m.group(1) if m else "?"
            stalls[phase] += 1
            total = int(r[6].rstrip("ms") or 0) if r[6].rstrip("ms").isdigit() else 0
            stall_ms[phase] = max(stall_ms.get(phase, 0), total)
        elif kind == "death" and len(r) > 7:
            deaths[r[6]] += 1
            words = dict(re.findall(r"(\w+)=(-?\d+)", r[7]))
            last = re.search(r"last=(\d+)", r[7])
            dam = int(last.group(1)) if last else 0
            before = int(words.get("hp_before", 0))
            top = int(words.get("max_hp", 0))
            # Killed by one blow from at least half health.
            if top > 0 and dam >= before and before * 2 >= top:
                one_blow.append((r[2], r[6], dam, before, top))
        elif kind == "item" and len(r) > 9:
            gone[(r[9], r[7])] += 1
        elif kind == "outcome" and len(r) > 10 and r[6] == "quest-failed":
            target = re.search(r"target=(\S+)", r[10])
            name = target.group(1) if target else "?"
            lost[(name, r[8])] += 1
            if "alive=0" in r[10]:
                impossible[name] += 1
    return {"stalls": stalls, "stall_ms": stall_ms, "deaths": deaths, "one_blow": one_blow,
            "gone": gone, "lost": lost, "impossible": impossible}


def format_copper(copper: int) -> str:
    """The game's own way of writing a sum: 148p 72g 11s."""
    sign = "-" if copper < 0 else ""
    copper = abs(copper)
    parts = []
    for unit, letter in ((1_000_000, "p"), (10_000, "g"), (100, "s"), (1, "c")):
        if copper >= unit:
            parts.append(f"{copper // unit}{letter}")
            copper %= unit
    return sign + (" ".join(parts) if parts else "0c")


def collapse_events(events):
    """(count, first, last, text) per kind of event, most frequent first.

    The goblin drifts to a new area every ten minutes and said so 275 times
    in two days, burying the twenty other events. Rooms, numbers and stock
    ids are what change between two of the same event, so they are left out
    of the key."""
    groups = {}
    for when, text in events:
        key = re.sub(r"room \d+ \([^)]*\)", "room ...", text)
        key = re.sub(r"\d+", "#", key)
        if key in groups:
            count, first, _, _ = groups[key]
            groups[key] = (count + 1, first, when, text)
        else:
            groups[key] = (1, when, when, text)
    return sorted(groups.values(), key=lambda g: (-g[0], g[2]))


def unhelpful_help(lines):
    """HELP <topic> then the topic's word refused within HELP_WINDOW.

    `lines` are (when, player, command) watch-log entries in order. A
    player who reads a topic and is then told "Huh?" by the word it named
    was taught something the game does not have."""
    read = {}
    found = []
    for when, player, command in lines:
        lower = command.lower()
        if lower.startswith("help "):
            topic = lower[5:].strip().strip("'\"")
            if topic:
                read[(player, topic.split()[0])] = when
            continue
        if lower.startswith("(refused)"):
            word = (lower[len("(refused)"):].split() or [""])[0]
            when_read = read.get((player, word))
            if word and when_read is not None and when - when_read <= HELP_WINDOW:
                found.append((when, player, word))
                del read[(player, word)]
    return found


def help_misses(rows):
    """Counter of HELP topics that found nothing ("No help on that word"),
    from the journal's cmd rows: a topic players look for and the game
    does not have."""
    misses = Counter()
    for r in rows:
        if r[1] == "cmd" and len(r) >= 13 and r[10] == "help" \
                and r[12].startswith("No help on that word"):
            topic = r[11].strip().strip("'\"").lower()
            if topic:
                misses[topic] += 1
    return misses


def journal_repeats(rows, least: int = 5):
    """Runs of one command typed `least` or more times, outside a fight.

    Typing SMITE thirteen times in a fight is fighting; typing MINDBAR
    twenty times standing is a player whose reply did not say enough. Rows
    in a fight neither extend nor break a run."""
    runs = []
    state = {}
    for r in rows:
        if r[1] not in ("cmd", "refused") or len(r) < 13:
            continue
        if r[9] == "fight" or r[6] == "fighting":
            continue
        if r[10] == "(unknown)":
            continue    # the journal never writes the word, so two typos look alike
        player = r[2]
        command = f"{r[10]} {r[11]}".strip()
        current = state.get(player)
        if current and current[0] == command:
            state[player] = (command, current[1] + 1, current[2])
            continue
        if current and current[1] >= least and current[0].split(" ")[0].lower() not in NOISY:
            runs.append((player, current[0], current[1], current[2]))
        state[player] = (command, 1, int(r[0]))
    for player, current in state.items():
        if current[1] >= least and current[0].split(" ")[0].lower() not in NOISY:
            runs.append((player, current[0], current[1], current[2]))
    return sorted(runs, key=lambda run: -run[2])


def parse_time(stamp: str) -> datetime:
    return datetime.strptime(stamp, "%a %b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ref", default="origin/main")
    parser.add_argument("--since", help="UTC 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM' or "
                        "'YYYY-MM-DDTHH:MM' (default: 24 hours ago)")
    parser.add_argument("--player", help="only this player's commands, deaths and coin")
    parser.add_argument("--chat", type=int, default=60, help="most chat lines to show (default 60)")
    args = parser.parse_args()

    if args.since:
        stamp = args.since.strip().replace("T", " ")
        try:
            fmt = "%Y-%m-%d %H:%M" if " " in stamp else "%Y-%m-%d"
            since = datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            parser.error("--since takes 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' (UTC)")
    else:
        since = datetime.now(timezone.utc) - timedelta(hours=24)

    lines = []
    for raw in git_show(args.ref, "log/toc.log").splitlines():
        m = STAMP.match(raw)
        if not m:
            continue
        when = parse_time(m.group(1))
        if when >= since:
            lines.append((when, m.group(2)))
    print(f"Log report from {since:%Y-%m-%d %H:%M} UTC ({len(lines)} log lines, ref {args.ref})")

    per_player = Counter()
    help_lines = []                     # (when, player, command) for unhelpful_help
    quests = Counter()                  # target area
    quest_kinds = Counter()
    buffs = defaultdict(list)           # player -> (when, "affects off: ...")
    unknown = defaultdict(Counter)
    bugs = defaultdict(list)
    deaths = []
    events = []
    coin = defaultdict(Counter)
    last_lines = []

    memory_lines = []                   # (when, "MEMORY: ...") for the memory section

    for when, text in lines:
        last_lines = (last_lines + [(when, text)])[-6:]
        if text.startswith("MEMORY:"):
            memory_lines.append((when, text))
            continue
        if "[*****] BUG:" in text:
            bugs[text.split("BUG:", 1)[1].strip()].append((when, [clean(t) for _, t in last_lines[:-1]]))
            continue
        if text.startswith(EVENT_PREFIXES):
            events.append((when, clean(text)))
            continue
        m = WATCHED.match(text)
        if not m:
            if " killed by " in text and not text.startswith("Log "):
                deaths.append((when, clean(text)))
            continue
        player, room, command = m.group(1), m.group(2), m.group(3).strip()
        if args.player and player.lower() != args.player.lower():
            continue
        if command.startswith(("arrived ", "moved to ")):
            continue
        qm = QUEST_ASSIGNED.match(command)
        if qm:
            quests[qm.group(2)] += 1
            quest_kinds[f"{qm.group(1)}, {qm.group(4)}"] += 1
            continue
        if command.startswith("affects off:"):
            buffs[player].append((when, command))
            continue
        if command.lower().startswith(("help ", "(refused)")):
            help_lines.append((when, player, command))
        cm = re.match(r"coin \+(\d+) (\w+)", command)
        if cm:
            coin[player][cm.group(2)] += int(cm.group(1))
            continue
        if command.startswith("(refused)"):
            word = (command[len("(refused)"):].split() or [""])[0]
            if word:
                unknown[player][word.lower()] += 1
            per_player[player] += 1
            continue
        if EVENT_LINE.match(command):
            continue
        per_player[player] += 1

    print("\n== players")
    for player, count in per_player.most_common():
        print(f"  {player:<14} {count} commands")

    print(f"\n== bugs ({sum(len(v) for v in bugs.values())})")
    for message, hits in sorted(bugs.items(), key=lambda kv: -len(kv[1]))[:20]:
        print(f"  x{len(hits):<4} {clean(message)}  (first {hits[0][0]:%m-%d %H:%M})")
        for before in hits[0][1][-3:]:
            print(f"         before: {before[:110]}")

    print("\n== refused commands")
    for player, words in sorted(unknown.items()):
        # A word refused once is left out: a password typed at the wrong
        # moment is refused exactly once, and log/ is public anyway --
        # this report is not going to repeat it.
        common = [f"{w} x{n}" for w, n in words.most_common() if 2 <= n < 50][:12]
        aliases = [f"{w} x{n}" for w, n in words.most_common() if n >= 50]
        if common:
            print(f"  {player:<14} {', '.join(common)}")
        if aliases:
            print(f"  {'':<14} (likely aliases: {', '.join(aliases)})")

    print("\n== help that did not help")
    misses = unhelpful_help(help_lines)
    for when, player, word in misses[-15:]:
        print(f"  {when:%m-%d %H:%M}  {player:<14} read HELP {word}, then '{word}' was refused")
    if not misses:
        print("  (none)")

    print(f"\n== deaths ({len(deaths)})")
    for when, text in deaths[-25:]:
        print(f"  {when:%m-%d %H:%M}  {text[:120]}")

    print(f"\n== events ({len(events)})")
    for count, first, last, text in collapse_events(events)[:30]:
        if count == 1:
            print(f"  {last:%m-%d %H:%M}  {text[:150]}")
        else:
            print(f"  x{count:<4} {first:%m-%d %H:%M} to {last:%m-%d %H:%M}, last: {text[:110]}")

    print(f"\n== quests assigned ({sum(quests.values())})")
    if quests:
        print("  by area: " + ", ".join(f"{a} x{n}" for a, n in quests.most_common(12)))
        print("  by kind: " + ", ".join(f"{k} x{n}" for k, n in quest_kinds.most_common()))
    else:
        print("  (none)")

    print("\n== coin picked up (platinum, gold)")
    for player, kinds in sorted(coin.items(), key=lambda kv: -kv[1]["platinum"])[:15]:
        print(f"  {player:<14} {kinds['platinum']}p {kinds['gold']}g")

    memory_report(memory_lines, git_show(args.ref, "log/crash.log"))
    journal_report(args, since, buffs)
    progress_report(args, since)
    hyrule_report(args, since)
    activity_report(args, since)

    print("\n== public chat")
    rows = []
    for raw in git_show(args.ref, "log/channels.tsv").splitlines():
        parts = raw.split("\t", 3)
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        when = datetime.fromtimestamp(int(parts[0]), timezone.utc)
        speaker = parts[2]
        # Mobiles speak too (shopkeepers, the quest master); keep players.
        if when < since or " " in speaker or speaker[:1].islower():
            continue
        rows.append(f"  {when:%m-%d %H:%M} [{parts[1]}] {speaker}: {clean(parts[3])[:150]}")
    for row in rows[-args.chat:]:
        print(row)
    if not rows:
        print("  (none)")
    return 0


# The play journal (src/playlog.c): epoch, kind, name, level, room, area,
# then the kind's fields. A cmd/refused row continues position, hp%, ms,
# fight, command, args, reply.
SAID_NO = re.compile(
    r"^(You can't|You cannot|You don't|You do not|You aren't|You are not|You have no|"
    r"You need|You must|You're not|There is no|There's no|They aren't here|You see no|"
    r"Huh|What\?|Nothing|No one|Not |You failed|You lack|That isn't|It isn't|You haven't)",
    re.IGNORECASE)


def merge_sittings(rows):
    """One line per sitting. A session line is written at link loss and
    again at the QUIT or shutdown that ends the same sitting, and the game
    counts from the same logon both times, so the second line repeats the
    first and adds what came after. Keep the last line of each sitting
    (same name, same start: epoch less seconds played) and say how it went:
    "linkdead > quit".

    Only a link loss leaves a sitting open: QUIT and shutdown end it, so
    the next line is a new sitting however close its start (review,
    2026-10-30: a quit, a login and a quit two seconds apart read as one
    "quit > quit" and lost the first session's numbers)."""
    merged = []
    open_at = {}
    for r in rows:
        try:
            start = int(r[0]) - int(str(r[7]).rstrip("s"))
        except (IndexError, ValueError):
            merged.append(r)
            continue
        prev = open_at.pop(r[2], None)
        if prev is not None and abs(prev[0] - start) <= 2:
            # The sitting is listed where it ended, in time order.
            joined = list(r)
            joined[6] = merged[prev[1]][6] + " > " + r[6]
            merged[prev[1]] = None
            r = joined
        if str(r[6]).split(" > ")[-1] == "linkdead":
            open_at[r[2]] = (start, len(merged))
        merged.append(r)
    return [r for r in merged if r is not None]


def journal_report(args, since, buffs=None) -> None:
    rows = []
    for raw in git_show(args.ref, "log/play.tsv").splitlines():
        fields = raw.split("\t")
        if len(fields) < 6 or not fields[0].isdigit():
            continue
        if datetime.fromtimestamp(int(fields[0]), timezone.utc) < since:
            continue
        if args.player and fields[2].lower() != args.player.lower() and fields[1] != "bug":
            continue
        rows.append(fields)
    print(f"\n== play journal ({len(rows)} records)")
    commands = [r for r in rows if r[1] in ("cmd", "refused") and len(r) >= 13]

    slow = sorted((r for r in commands if r[8].isdigit() and int(r[8]) >= 250),
                  key=lambda r: -int(r[8]))[:10]
    print("  slowest commands (250 ms and up):")
    for r in slow:
        print(f"    {r[8]:>6} ms  {r[2]:<12} {r[10]} {clean(r[11])[:40]}  [room {r[4]}]")
    if not slow:
        print("    (none)")

    # A reply keeps its first lines joined with " // "; the refusal is the first.
    said_no = Counter((r[10], clean(r[12].split(" // ")[0])[:90]) for r in commands
                      if r[1] == "cmd" and SAID_NO.match(r[12]))
    print("  what the game said no with (command: answer, times):")
    for (command, reply), n in said_no.most_common(15):
        print(f"    x{n:<4} {command}: {reply}")
    if not said_no:
        print("    (none)")

    # 2026-11-03: a cmd row may carry what its handler said it came to
    # (column 13, "result:reason") and an outcome row says how an
    # operation ended, under its recovery id. Older rows have neither.
    ended = Counter()
    for r in commands:
        if len(r) > 13 and r[13] not in ("-", "") and not r[13].startswith("success"):
            ended[(r[10], r[13])] += 1
    for r in rows:
        if r[1] == "outcome" and len(r) > 8 and r[7] != "success":
            ended[(r[6], f"{r[7]}:{r[8]}")] += 1
    print("  what did not succeed, as the game said (op: result:reason, times):")
    for (op, how), n in ended.most_common(15):
        print(f"    x{n:<4} {op}: {clean(how)[:80]}")
    if not ended:
        print("    (none)")

    misses = help_misses(commands)
    print("  HELP that found nothing:")
    for topic, n in misses.most_common(15):
        print(f"    x{n:<4} help {clean(topic)[:60]}")
    if not misses:
        print("    (none)")

    print("  repeats (5+ in a row, outside a fight):")
    runs = journal_repeats(commands)
    for player, command, count, start in runs[:20]:
        when = datetime.fromtimestamp(start, timezone.utc)
        print(f"    {player:<12} x{count:<3} {clean(command)[:60]}  ({when:%m-%d %H:%M})")
    if not runs:
        print("    (none)")

    for kind, title in (("anomaly", "anomalies"), ("bug", "BUG lines with what was running"),
                        ("report", "player reports with their last commands"),
                        ("session", "sessions")):
        picked = [r for r in rows if r[1] == kind]
        if kind == "session":
            picked = merge_sittings(picked)
        print(f"  {title} ({len(picked)}):")
        for r in picked[-15:]:
            when = datetime.fromtimestamp(int(r[0]), timezone.utc)
            fields = list(r[6:])
            if kind == "session":
                # "+740662061 copper" reads better as the game writes it.
                fields = [re.sub(r"^([+-]?\d+) copper$",
                                 lambda m: format_copper(int(m.group(1))) + " net", f)
                          for f in fields]
            print(f"    {when:%m-%d %H:%M} {r[2]:<12} {clean(' | '.join(fields))[:240]}")
            if kind == "anomaly" and buffs:
                # What wore off just before is usually the answer.
                before = [text for at, text in buffs.get(r[2], [])
                          if timedelta(0) <= when - at <= timedelta(minutes=3)]
                if before:
                    print(f"      just before: {clean(before[-1])[:150]}")

    economy = economy_summary(rows)
    print("  coin spent, by what it went on (2026-11-05 on):")
    for label, copper in economy["spent"].most_common(12):
        print(f"    {format_copper(copper):>16}  {clean(label)}")
    if not economy["spent"]:
        print("    (none recorded)")
    print("  experience, by where it came from (capped: offered and refused):")
    for label, amount in sorted(economy["exp"].items(), key=lambda kv: -abs(kv[1]))[:12]:
        print(f"    {amount:>+14,}  {clean(label)}")
    if not economy["exp"]:
        print("    (none recorded)")
    print("  quests paid, by kind (coin also as kills at the questor's level):")
    for kind, q in sorted(economy["quests"].items(), key=lambda kv: -kv[1]["n"]):
        each = f"~{q['kills'] / q['priced']:.0f} kills each" if q["priced"] else "kills -"
        print(f"    {kind:<10} x{q['n']:<4} coin {format_copper(q['coin']):>14}"
              f"  {each}  points offered {q['points']}")
    if not economy["quests"]:
        print("    (none recorded)")

    deep = deep_summary(rows)
    print("  pulses past their quarter second, by the phase that took longest:")
    for phase, n in deep["stalls"].most_common(10):
        print(f"    x{n:<4} {clean(phase):<24} worst {deep['stall_ms'][phase]} ms")
    if not deep["stalls"]:
        print("    (none recorded)")
    print("  player deaths, by killer:")
    for killer, n in deep["deaths"].most_common(12):
        print(f"    x{n:<4} {clean(killer)[:60]}")
    if not deep["deaths"]:
        print("    (none recorded)")
    for who, killer, dam, before, top in deep["one_blow"][-10:]:
        print(f"    one blow: {who:<12} {dam} from {before}/{top} hp by {clean(killer)[:40]}")
    print("  things gone from players (why: what), consumables left out:")
    for (why, what), n in deep["gone"].most_common(15):
        print(f"    x{n:<4} {clean(why)[:24]:<24} {clean(what)[:50]}")
    if not deep["gone"]:
        print("    (none recorded)")
    print("  quests lost (target, how):")
    for (target, how), n in deep["lost"].most_common(12):
        flag = "  <- none left in the world" if target in deep["impossible"] else ""
        print(f"    x{n:<4} {clean(target):<14} {clean(how)}{flag}")
    if not deep["lost"]:
        print("    (none recorded)")

    crash = git_show(args.ref, "log/crash.log")
    blocks = crash_blocks(crash)
    print(f"\n== crashes ({len(blocks)} on record)")
    for block in blocks[-3:]:
        print(f"  signal{clean(block['head'])[:120]}")
        for line in block["commands"][-8:]:
            print(f"    {clean(line)[:140]}")


# log/toc.log's MEMORY lines (src/memguard.c): "MEMORY: stale <field> on
# <who> -> dead <kind> (<what it was>)", or "MEMORY: N more stale <field>
# not logged in the last minute" past the per-field burst.
MEMORY_STALE = re.compile(r"^MEMORY: stale (.+?) on (.+?) -> dead (\w+) \((.*)\)$")
MEMORY_MORE = re.compile(r"^MEMORY: (\d+) more stale (.+?) not logged")


def crash_blocks(text: str) -> list:
    """crash.log's entries: the head line, the commands, the build and the
    backtrace (src/playlog.c's crash_handler; older entries have none)."""
    blocks = []
    for raw in text.split("=== crash:")[1:]:
        lines = [line for line in raw.strip().splitlines() if line != "=== end ==="]
        if not lines:
            continue
        block = {"head": lines[0], "commands": [], "build": "", "backtrace": []}
        in_trace = False
        for line in lines[1:]:
            if line.startswith("--- backtrace"):
                in_trace = True
            elif in_trace:
                block["backtrace"].append(line)
            elif line.startswith("build "):
                block["build"] = line[len("build "):].strip()
            else:
                block["commands"].append(line)
        blocks.append(block)
    return blocks


def memory_summary(lines) -> dict:
    """MEMORY lines counted by field, with the newest kept whole."""
    by_field = Counter()
    newest = []
    for when, text in lines:
        m = MEMORY_STALE.match(text)
        if m:
            by_field[m.group(1)] += 1
            newest.append((when, text))
            continue
        m = MEMORY_MORE.match(text)
        if m:
            by_field[m.group(2)] += int(m.group(1))
    return {"by_field": by_field, "newest": newest[-5:]}


def memory_report(lines, crash_text: str) -> None:
    s = memory_summary(lines)
    blocks = crash_blocks(crash_text)
    total = sum(s["by_field"].values())
    print(f"\n== memory ({total} stale pointers caught; {len(blocks)} crashes on record)")
    if total:
        print("  by field: " + ", ".join(f"{f} x{n}" for f, n in s["by_field"].most_common()))
        for when, text in s["newest"]:
            print(f"  {when:%m-%d %H:%M}  {clean(text)[:150]}")
    else:
        print("  (no MEMORY lines in the window)")
    for block in blocks[-2:]:
        build = f" build {block['build']}" if block["build"] else ""
        print(f"  crash: signal{clean(block['head'])[:100]}{build}")
        for line in block["backtrace"][:16]:
            print(f"    {clean(line)[:140]}")
        if not block["backtrace"]:
            print("    (no backtrace recorded)")


# log/progress.tsv (src/playlog.c): epoch, kind (kill, flee, death), the
# character's file Id (never a name), level, class, remorts, hp%, mana%,
# foe vnum, foe level, area file; a kill adds encounter ms, base, rested
# and accepted xp, and group members, then (2026-10-26) guild, buffs worn
# (T E S H or -), damage dealt and taken, hit points recovered and mana
# spent in the fight, then (2026-11-05) the coin the foe carried, in
# copper. Reported in aggregate only: the
# ids count independent characters and are never printed.
def progress_summary(text: str, since: datetime) -> dict:
    by_foe: dict = {}
    by_area: dict = {}
    characters: set = set()
    kills_seen: set = set()
    legacy = 0
    for raw in text.splitlines():
        f = raw.split("\t")
        if len(f) < 11 or not f[0].isdigit():
            continue
        if datetime.fromtimestamp(int(f[0]), timezone.utc) < since:
            continue
        kind, who, area = f[1], f[2], f[10]
        characters.add(who)
        here = by_area.setdefault(area, {"kills": 0, "flee": 0, "death": 0, "who": set()})
        here["who"].add(who)
        if kind in ("flee", "death"):
            here[kind] += 1
            continue
        # A reward row (2026-11-10) is one player's pay for a kill shared by
        # the kill id; a legacy kill row was the same, with no id, so a
        # group kill counted once per member -- it is still counted that
        # way, and the header says how many such rows there were.
        if kind not in ("kill", "reward") or len(f) < 16:
            continue
        first = True
        if kind == "reward" and len(f) > 25:
            first = f[25] not in kills_seen
            kills_seen.add(f[25])
        else:
            legacy += 1
        if first:
            here["kills"] += 1
        foe = by_foe.setdefault((area, f[8], f[9]), {"kills": 0, "xp": 0, "ms": 0, "timed": 0,
                                                     "timed_xp": 0, "untimed": 0,
                                                     "times": [], "who": set(),
                                                     "coin": 0, "coined": 0})
        if first:
            foe["kills"] += 1
        if first and len(f) > 23 and f[23].isdigit():
            foe["coin"] += int(f[23])
            foe["coined"] += 1
        foe["who"].add(who)
        xp = int(f[14]) if f[14].lstrip("-").isdigit() else 0
        foe["xp"] += xp
        # A rate counts only kills with a measured encounter: a -1 (a
        # fatality, a kill with no fight begun) or a 0 has no time to
        # divide by, and its experience must not ride on the others'.
        if f[11].isdigit() and int(f[11]) > 0:
            foe["ms"] += int(f[11])
            foe["timed"] += 1
            foe["timed_xp"] += xp
            foe["times"].append(int(f[11]))
        else:
            foe["untimed"] += 1
    return {"by_foe": by_foe, "by_area": by_area, "characters": len(characters),
            "legacy": legacy}


def progress_report(args, since) -> None:
    summary = progress_summary(git_show(args.ref, "log/progress.tsv"), since)
    by_foe = summary["by_foe"]
    print(f"\n== progression ({summary['characters']} distinct characters; aggregates only;"
          f" {summary.get('legacy', 0)} legacy rows count a group kill once per member;"
          " tools/balance_report.py has the full balance view)")
    if not by_foe and not summary["by_area"]:
        print("  (no log/progress.tsv records in the window)")
        return
    print("  area                 foe    lvl  kills chars  med s  xp/combat-min  untimed"
          "  coin/kill")
    for (area, vnum, level), foe in sorted(by_foe.items(), key=lambda kv: -kv[1]["kills"])[:25]:
        times = sorted(foe["times"])
        median = times[len(times) // 2] / 1000 if times else 0
        rate = foe["timed_xp"] / (foe["ms"] / 60000) if foe["ms"] else 0
        coin = format_copper(foe["coin"] // foe["coined"]) if foe["coined"] else "-"
        print(f"  {area[:20]:<20} {vnum:>6} {level:>4} {foe['kills']:>6} {len(foe['who']):>5}"
              f" {median:>6.1f} {rate:>14.0f} {foe['untimed']:>8}  {coin:>9}")
    print("  area                 kills  flees deaths chars")
    for area, here in sorted(summary["by_area"].items(), key=lambda kv: -kv[1]["kills"])[:25]:
        print(f"  {area[:20]:<20} {here['kills']:>5} {here['flee']:>6} {here['death']:>6} {len(here['who']):>5}")


# log/hyrule.tsv (src/hyrulelog.c): epoch, kind, name, level, remorts,
# class, room, zone, then key=value words.
ZONE_ORDER = ["over"] + [f"L{n}" for n in range(1, 10)]


def hyrule_rows(text: str, since: datetime) -> list:
    out = []
    for raw in text.splitlines():
        f = raw.split("\t")
        if len(f) < 8 or not f[0].isdigit():
            continue
        when = datetime.fromtimestamp(int(f[0]), timezone.utc)
        if when < since:
            continue
        row = {"when": when, "kind": f[1], "name": f[2], "lvl": f[3], "remorts": f[4],
               "cls": f[5], "room": f[6], "zone": f[7]}
        for word in " ".join(f[8:]).split():
            key, _, value = word.partition("=")
            row.setdefault(key, value)
        out.append(row)
    return out


def _median(values):
    """The median, or None for no samples: the mean of the middle two for
    an even count (review, 2026-11-10: [10, 90] read 90, the upper one)."""
    values = list(values)
    return statistics.median(values) if values else None


def _num(row, key, default=None):
    value = row.get(key, "")
    return int(value) if value.lstrip("-").isdigit() else default


def hyrule_summary(rows) -> dict:
    zones: dict = {}
    furthest: dict = {}
    guardians: dict = {}
    gates: Counter = Counter()
    got: Counter = Counter()
    got_how: dict = {}
    claims: Counter = Counter()
    seals: Counter = Counter()
    cleared: Counter = Counter()
    deaths: Counter = Counter()
    for r in rows:
        kind, zone, who = r["kind"], r["zone"], r["name"]
        if kind == "enter" and zone in ZONE_ORDER:
            z = zones.setdefault(zone, {"visits": 0, "secs": [], "who": set()})
            z["visits"] += 1
            z["who"].add(who)
            if ZONE_ORDER.index(zone) > ZONE_ORDER.index(furthest.get(who, "over")):
                furthest[who] = zone
            else:
                furthest.setdefault(who, zone)
        elif kind == "leave" and zone in ZONE_ORDER:
            secs = _num(r, "secs")
            if secs is not None:
                zones.setdefault(zone, {"visits": 0, "secs": [], "who": set()})["secs"].append(secs)
        elif kind == "gate":
            gates[(r.get("dungeon", "?"), r.get("gate", "?"), r.get("need_name", "?"))] += 1
        elif kind == "got":
            key = (r.get("obj", "?"), r.get("obj_name", "?"))
            got[key] += 1
            got_how.setdefault(key, Counter())[r.get("how", "?")] += 1
        elif kind == "claim":
            claims[r.get("what", "?")] += 1
        elif kind == "seal":
            seals[(zone, r.get("obj_name", "?"))] += 1
        elif kind == "cleared":
            cleared[zone] += 1
        elif kind == "death":
            deaths[(zone, r.get("foe_name", "-"), r.get("guardian", "0"))] += 1
        if kind in ("engage", "guardian-down") or (kind in ("flee", "death")
                                                     and r.get("guardian") == "1"):
            foe = (r.get("foe", "?"), r.get("foe_name", "?"))
            g = guardians.setdefault(foe, {"engage": 0, "down": 0, "flee": 0, "death": 0,
                                           "who": set(), "kill_secs": [], "party": [],
                                           "levels": [], "flee_hp": [], "death_hp": [],
                                           "start_hp": []})
            g["who"].add(who)
            if kind == "engage":
                g["engage"] += 1
                if _num(r, "foe_hp") is not None:
                    g["start_hp"].append(_num(r, "foe_hp"))
            elif kind == "guardian-down":
                g["down"] += 1
                if _num(r, "secs", -1) >= 0:
                    g["kill_secs"].append(_num(r, "secs"))
                if _num(r, "party") is not None:
                    g["party"].append(_num(r, "party"))
                g["levels"] += [int(x) for x in r.get("levels", "").split(",") if x.isdigit()]
            elif kind == "flee":
                g["flee"] += 1
                if _num(r, "foe_hp") is not None:
                    g["flee_hp"].append(_num(r, "foe_hp"))
            else:
                g["death"] += 1
                if _num(r, "foe_hp", -1) >= 0:
                    g["death_hp"].append(_num(r, "foe_hp"))
    return {"zones": zones, "furthest": furthest, "guardians": guardians, "gates": gates,
            "got": got, "got_how": got_how, "claims": claims, "seals": seals,
            "cleared": cleared, "deaths": deaths,
            "characters": len({r["name"] for r in rows})}


def hyrule_report(args, since) -> None:
    rows = hyrule_rows(git_show(args.ref, "log/hyrule.tsv"), since)
    s = hyrule_summary(rows)
    print(f"\n== hyrule ({s['characters']} characters, {len(rows)} records; log/hyrule.tsv)")
    if not rows:
        print("  (no log/hyrule.tsv records in the window)")
        return
    print("  where they went (visits, characters, minutes in all, median minutes a visit):")
    for zone in ZONE_ORDER:
        z = s["zones"].get(zone)
        if not z:
            continue
        med = _median(z["secs"])
        print(f"    {zone:<5} {z['visits']:>5} visits {len(z['who']):>3} chars"
              f" {sum(z['secs']) / 60:>8.0f} min  median {med / 60 if med is not None else 0:>5.1f}")
    print("  furthest reached:", ", ".join(f"{who} {zone}" for who, zone in
                                         sorted(s["furthest"].items(), key=lambda kv:
                                                -ZONE_ORDER.index(kv[1]))) or "(none)")
    print("  guardians (engaged, slain, fled, deaths; median fight s, party, levels;"
          " guardian hp% left at flee / death):")
    for (vnum, name), g in sorted(s["guardians"].items(), key=lambda kv: kv[0][0]):
        med = lambda v: "-" if _median(v) is None else f"{_median(v):g}"
        print(f"    {vnum:>6} {name[:20]:<20} {g['engage']:>3} {g['down']:>3} {g['flee']:>3}"
              f" {g['death']:>3}   {med(g['kill_secs']):>5}s party {med(g['party']):>2}"
              f" lvl {med(g['levels']):>3}   flee {med(g['flee_hp']):>3}% death"
              f" {med(g['death_hp']):>3}%  ({len(g['who'])} chars)")
    if not s["guardians"]:
        print("    (none)")
    print("  gates that turned somebody back (dungeon, gate, what it wanted):")
    for (dungeon, gate, need), n in s["gates"].most_common(15):
        print(f"    x{n:<4} L{dungeon} {gate:<8} {need.replace('_', ' ')}")
    if not s["gates"]:
        print("    (none)")
    print("  deaths in Hyrule (zone, foe):")
    for (zone, foe, guardian), n in s["deaths"].most_common(15):
        print(f"    x{n:<4} {zone:<5} {foe.replace('_', ' ')}{' (guardian)' if guardian == '1' else ''}")
    if not s["deaths"]:
        print("    (none)")
    print("  what they came away with (object, times, how):")
    for (vnum, name), n in s["got"].most_common(25):
        hows = ", ".join(f"{how} {c}" for how, c in s["got_how"][(vnum, name)].most_common(3))
        print(f"    x{n:<4} {vnum:>6} {name.replace('_', ' ')[:32]:<32} {hows}")
    if not s["got"]:
        print("    (none)")
    print("  claims:", ", ".join(f"{what} {n}" for what, n in s["claims"].most_common()) or "(none)")
    print("  seals opened:", ", ".join(f"{zone} {name.replace('_', ' ')} {n}" for (zone, name), n
                                     in s["seals"].most_common(12)) or "(none)")
    print("  rooms cleared:", ", ".join(f"{zone} {n}" for zone, n in
                                      sorted(s["cleared"].items(), key=lambda kv:
                                             ZONE_ORDER.index(kv[0]) if kv[0] in ZONE_ORDER else 99))
          or "(none)")


# The play journal's activity rows (src/playlog.c, 2026-11-10): coin, got,
# level, area, achieved, skill, quest. Columns after the common six:
#   coin      delta(+/-copper)  source  how  from  wealth_after
#   got       vnum  name  type  level  cost  how  from
#   level     from  to  class  remorts  exp  secs_since_last  how
#   area      from_area  to_area  secs_in_from  how
#   achieved  key  points  total  how
#   skill     skill  before  after  success|mistake  how
#   quest     kind  kill|recover  vnum  name  level  area  minutes
def activity_rows(text: str, since: datetime) -> list:
    out = []
    for raw in text.splitlines():
        f = raw.split("\t")
        if len(f) < 7 or not f[0].isdigit():
            continue
        if f[1] not in ("coin", "got", "level", "area", "achieved", "skill", "quest"):
            continue
        when = datetime.fromtimestamp(int(f[0]), timezone.utc)
        if when >= since:
            out.append((when, f))
    return out


def activity_summary(rows) -> dict:
    coin_moves = []
    coin_by_source: Counter = Counter()
    got: Counter = Counter()
    got_how: dict = {}
    levels: dict = {}
    area_secs: Counter = Counter()
    area_visits: Counter = Counter()
    achieved: Counter = Counter()
    skills: Counter = Counter()
    quests: Counter = Counter()
    for when, f in rows:
        kind, who = f[1], f[2]
        if kind == "coin" and len(f) >= 11:
            amount = int(f[6]) if f[6].lstrip("+-").isdigit() else 0
            coin_moves.append((abs(amount), amount, when, who, f[3], f[7], f[8], f[9],
                               int(f[10]) if f[10].lstrip("-").isdigit() else 0))
            coin_by_source[f[7]] += amount
        elif kind == "got" and len(f) >= 13:
            key = (f[6], f[7])
            got[key] += 1
            got_how.setdefault(key, Counter())[f[11]] += 1
        elif kind == "level" and len(f) >= 13:
            secs = int(f[11]) if f[11].lstrip("-").isdigit() else -1
            levels.setdefault(who, []).append((when, f[6], f[7], secs))
        elif kind == "area" and len(f) >= 10:
            secs = int(f[8]) if f[8].isdigit() else 0
            area_secs[f[6]] += secs
            area_visits[f[7]] += 1
        elif kind == "achieved" and len(f) >= 7:
            achieved[f[6]] += 1
        elif kind == "skill" and len(f) >= 10:
            skills[f[6]] += 1
        elif kind == "quest" and len(f) >= 13:
            quests[(f[6], f[7])] += 1
    coin_moves.sort(reverse=True)
    return {"coin_moves": coin_moves, "coin_by_source": coin_by_source, "got": got,
            "got_how": got_how, "levels": levels, "area_secs": area_secs,
            "area_visits": area_visits, "achieved": achieved, "skills": skills,
            "quests": quests}


def activity_report(args, since) -> None:
    rows = activity_rows(git_show(args.ref, "log/play.tsv"), since)
    s = activity_summary(rows)
    print(f"\n== activity ({len(rows)} coin/item/level/area/achievement/skill/quest rows)")
    if not rows:
        print("  (none in the window)")
        return
    print("  biggest coin moves (amount, source, command, from, wealth after):")
    for _, amount, when, who, lvl, source, how, src, wealth in s["coin_moves"][:12]:
        print(f"    {when:%m-%d %H:%M} {who:<12} L{lvl:<3} {format_copper(abs(amount)):>16}"
              f" {'+' if amount > 0 else '-'} {source:<9} {how:<16} {src[:28]:<28}"
              f" now {format_copper(wealth)}")
    print("  coin by source:", ", ".join(
        f"{src} {'+' if v >= 0 else '-'}{format_copper(abs(v))}"
        for src, v in s["coin_by_source"].most_common()) or "(none)")
    print("  objects gained (vnum, times, how):")
    for (vnum, name), n in s["got"].most_common(15):
        hows = ", ".join(f"{h} {c}" for h, c in s["got_how"][(vnum, name)].most_common(3))
        print(f"    x{n:<4} {vnum:>6} {name.replace('_', ' ')[:30]:<30} {hows}")
    print("  levels gained (character: from->to, minutes the level took):")
    for who, gains in sorted(s["levels"].items()):
        steps = ", ".join(f"{a}->{b}" + (f" {secs // 60}m" if secs >= 0 else "")
                          for _, a, b, secs in gains[-8:])
        print(f"    {who:<12} {steps}")
    print("  hours spent by area:", ", ".join(
        f"{a} {secs / 3600:.1f}" for a, secs in s["area_secs"].most_common(10)) or "(none)")
    print("  achievements earned:", ", ".join(
        f"{k} {n}" for k, n in s["achieved"].most_common(10)) or "(none)")
    print("  skill gains:", ", ".join(
        f"{k} {n}" for k, n in s["skills"].most_common(10)) or "(none)")
    print("  quests assigned:", ", ".join(
        f"{k}/{t} {n}" for (k, t), n in s["quests"].most_common()) or "(none)")


if __name__ == "__main__":
    sys.exit(main())
