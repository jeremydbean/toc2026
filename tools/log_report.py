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
              each session's coin split by where it came from
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
    parser.add_argument("--since", help="UTC 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' (default: 24 hours ago)")
    parser.add_argument("--player", help="only this player's commands, deaths and coin")
    parser.add_argument("--chat", type=int, default=60, help="most chat lines to show (default 60)")
    args = parser.parse_args()

    if args.since:
        fmt = "%Y-%m-%d %H:%M" if " " in args.since else "%Y-%m-%d"
        since = datetime.strptime(args.since, fmt).replace(tzinfo=timezone.utc)
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

    for when, text in lines:
        last_lines = (last_lines + [(when, text)])[-6:]
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

    journal_report(args, since, buffs)
    progress_report(args, since)

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
    "linkdead > quit"."""
    merged = []
    open_at = {}
    for r in rows:
        try:
            start = int(r[0]) - int(str(r[7]).rstrip("s"))
        except (IndexError, ValueError):
            merged.append(r)
            continue
        prev = open_at.get(r[2])
        if prev is not None and abs(prev[0] - start) <= 2:
            # The sitting is listed where it ended, in time order.
            joined = list(r)
            joined[6] = merged[prev[1]][6] + " > " + r[6]
            merged[prev[1]] = None
            r = joined
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

    crash = git_show(args.ref, "log/crash.log")
    blocks = [b for b in crash.split("=== crash:")[1:]]
    print(f"\n== crashes ({len(blocks)} on record)")
    for block in blocks[-3:]:
        lines = block.strip().splitlines()
        print(f"  signal{clean(lines[0])[:120]}")
        for line in lines[1:-1][-8:]:
            print(f"    {clean(line)[:140]}")


# log/progress.tsv (src/playlog.c): epoch, kind (kill, flee, death), the
# character's file Id (never a name), level, class, remorts, hp%, mana%,
# foe vnum, foe level, area file; a kill adds encounter ms, base, rested
# and accepted xp, and group members, then (2026-10-26) guild, buffs worn
# (T E S H or -), damage dealt and taken, hit points recovered and mana
# spent in the fight. Reported in aggregate only: the
# ids count independent characters and are never printed.
def progress_summary(text: str, since: datetime) -> dict:
    by_foe: dict = {}
    by_area: dict = {}
    characters: set = set()
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
        if kind != "kill" or len(f) < 16:
            continue
        here["kills"] += 1
        foe = by_foe.setdefault((area, f[8], f[9]), {"kills": 0, "xp": 0, "ms": 0, "timed": 0,
                                                     "timed_xp": 0, "untimed": 0,
                                                     "times": [], "who": set()})
        foe["kills"] += 1
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
    return {"by_foe": by_foe, "by_area": by_area, "characters": len(characters)}


def progress_report(args, since) -> None:
    summary = progress_summary(git_show(args.ref, "log/progress.tsv"), since)
    by_foe = summary["by_foe"]
    print(f"\n== progression ({summary['characters']} distinct characters; aggregates only)")
    if not by_foe and not summary["by_area"]:
        print("  (no log/progress.tsv records in the window)")
        return
    print("  area                 foe    lvl  kills chars  med s  xp/combat-min  untimed")
    for (area, vnum, level), foe in sorted(by_foe.items(), key=lambda kv: -kv[1]["kills"])[:25]:
        times = sorted(foe["times"])
        median = times[len(times) // 2] / 1000 if times else 0
        rate = foe["timed_xp"] / (foe["ms"] / 60000) if foe["ms"] else 0
        print(f"  {area[:20]:<20} {vnum:>6} {level:>4} {foe['kills']:>6} {len(foe['who']):>5}"
              f" {median:>6.1f} {rate:>14.0f} {foe['untimed']:>8}")
    print("  area                 kills  flees deaths chars")
    for area, here in sorted(summary["by_area"].items(), key=lambda kv: -kv[1]["kills"])[:25]:
        print(f"  {area[:20]:<20} {here['kills']:>5} {here['flee']:>6} {here['death']:>6} {len(here['who']):>5}")


if __name__ == "__main__":
    sys.exit(main())
