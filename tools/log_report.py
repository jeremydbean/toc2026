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
  repeats     the same command typed five or more times running by one
              player: the reply did not tell them what they needed
              (TRACK, HIDE and REFRESH were found this way)
  deaths      who died, to what, where
  events      black market, treasure goblin, login fixes, quests paid
  coin        the biggest coin gains per player, to spot an exploit
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
                        r"|arrived|moved to) |\(social\))")
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
    recent = defaultdict(list)          # player -> last commands
    last_cmd = {}
    runs = []                           # (player, command, count, when)
    run_state = {}
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
        state = run_state.get(player)
        if state and state[0] == command:
            run_state[player] = (command, state[1] + 1, state[2])
        else:
            if state and state[1] >= 5 and state[0].lower() not in NOISY:
                runs.append((player, state[0], state[1], state[2]))
            run_state[player] = (command, 1, when)
    for player, state in run_state.items():
        if state[1] >= 5 and state[0].lower() not in NOISY:
            runs.append((player, state[0], state[1], state[2]))

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

    print("\n== repeats (5+ in a row)")
    for player, command, count, when in sorted(runs, key=lambda r: -r[2])[:25]:
        print(f"  {player:<14} x{count:<3} {clean(command)[:60]}  ({when:%m-%d %H:%M})")

    print(f"\n== deaths ({len(deaths)})")
    for when, text in deaths[-25:]:
        print(f"  {when:%m-%d %H:%M}  {text[:120]}")

    print(f"\n== events ({len(events)})")
    for when, text in events[-40:]:
        print(f"  {when:%m-%d %H:%M}  {text[:150]}")

    print("\n== coin picked up (platinum, gold)")
    for player, kinds in sorted(coin.items(), key=lambda kv: -kv[1]["platinum"])[:15]:
        print(f"  {player:<14} {kinds['platinum']}p {kinds['gold']}g")

    journal_report(args, since)

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


def journal_report(args, since) -> None:
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

    said_no = Counter((r[10], clean(r[12])[:90]) for r in commands
                      if r[1] == "cmd" and SAID_NO.match(r[12]))
    print("  what the game said no with (command: answer, times):")
    for (command, reply), n in said_no.most_common(15):
        print(f"    x{n:<4} {command}: {reply}")
    if not said_no:
        print("    (none)")

    for kind, title in (("anomaly", "anomalies"), ("bug", "BUG lines with what was running"),
                        ("report", "player reports with their last commands"),
                        ("session", "sessions")):
        picked = [r for r in rows if r[1] == kind]
        print(f"  {title} ({len(picked)}):")
        for r in picked[-15:]:
            when = datetime.fromtimestamp(int(r[0]), timezone.utc)
            print(f"    {when:%m-%d %H:%M} {r[2]:<12} {clean(' | '.join(r[6:]))[:160]}")

    crash = git_show(args.ref, "log/crash.log")
    blocks = [b for b in crash.split("=== crash:")[1:]]
    print(f"\n== crashes ({len(blocks)} on record)")
    for block in blocks[-3:]:
        lines = block.strip().splitlines()
        print(f"  signal{clean(lines[0])[:120]}")
        for line in lines[1:-1][-8:]:
            print(f"    {clean(line)[:140]}")


if __name__ == "__main__":
    sys.exit(main())
