#!/usr/bin/env python3
"""Audit the game's help against what the game actually has.

Reads the help the way the game does (webadmin/help_index.py: area.lst
order, fread_string tokens, do_help's exact-then-prefix lookup and trust
filter) and checks it against the command table (src/interp.c), the skill
table and the groups (src/const.c):

  - every command a character can type has help they can read at the
    trust the command needs, unless data/help_coverage.json says why not;
  - no command's help sits above the command (a page only higher ranks
    can read, for a command lower ranks have);
  - every skill or spell some class can learn, and every effect players
    can come by on items, has help a mortal can read;
  - every keyword shared by two pages is listed in the exceptions as an
    intended alias, overview or staff/public split -- a new collision fails;
  - the KEYWORDS topic in area/toc.are lists exactly the keywords a mortal
    can reach (--write-keywords regenerates it).

  python3 tools/help_audit.py              # report, exit 1 on a finding
  python3 tools/help_audit.py --write-keywords

Run from the repository root.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webadmin"))
import help_index  # noqa: E402

AREA = ROOT / "area"
EXCEPTIONS = ROOT / "data" / "help_coverage.json"
MAX_LEVEL = 70
MACROS = {"CR": MAX_LEVEL + 2, "ML": MAX_LEVEL, "IM": MAX_LEVEL - 10,
          "HE": MAX_LEVEL - 19, "GOD": MAX_LEVEL - 1}
MACROS.update({"L%d" % n: MAX_LEVEL - n for n in range(1, 11)})
UNAVAILABLE = 62           # a skill level this high means "not this class"
MORTAL_TRUST = 59


def level_value(token: str) -> int:
    """A level as interp.c writes it: a number, a macro, or arithmetic on
    MAX_LEVEL and the macros (MAX_LEVEL - 3)."""
    expr = token.strip()
    names = dict(MACROS, MAX_LEVEL=MAX_LEVEL, LEVEL_IMMORTAL=MAX_LEVEL - 10,
                 LEVEL_HERO=MAX_LEVEL - 19, LEVEL_CREATOR=MAX_LEVEL + 2)
    for name in sorted(names, key=len, reverse=True):
        expr = re.sub(r"\b%s\b" % name, str(names[name]), expr)
    if not re.fullmatch(r"[\d\s+\-*/()]+", expr):
        raise ValueError("cannot read command level %r" % token)
    return int(eval(expr))  # digits and operators only, checked above


def commands() -> list:
    """(name, level, show) for every live row of interp.c's cmd_table."""
    text = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    table = text[text.index("const\tstruct\tcmd_type\tcmd_table") if "const\tstruct\tcmd_type\tcmd_table" in text
                 else text.index("cmd_table"):]
    out = []
    for m in re.finditer(r'\{\s*"([^"]*)",\s*(\w+),\s*(\w+),\s*([\w ]+?),\s*(\w+),\s*(\d)\s*\}', table):
        name = m.group(1)
        if not name:
            break
        out.append((name, level_value(m.group(4)), int(m.group(6)), m.group(2)))
    return out


def skills() -> list:
    """(name, levels by class, spell_fun) for every skill_table row."""
    text = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    start = re.search(r"skill_table\s*\[MAX_SKILL\]\s*=", text).end()
    body = text[start:re.search(r"group_table\s*\[MAX_GROUP\]\s*=", text).start()]
    out = []
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{([^}]*)\},\s*\{[^}]*\},\s*(\w+),', body):
        levels = [int(x) for x in re.findall(r"-?\d+", m.group(2))]
        out.append((m.group(1), levels, m.group(3)))
    return out


def groups() -> list:
    text = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
    body = text[re.search(r"group_table\s*\[MAX_GROUP\]\s*=", text).end():]
    out = []
    for m in re.finditer(r'\{\s*"([^"]+)",\s*\{[^}]*\},\s*\{([^}]*)\}', body):
        members = re.findall(r'"([^"]+)"', m.group(2))
        out.append((m.group(1), members))
    return out


CLASS_NAMES = ["Mage", "Cleric", "Thief", "Warrior", "Monk", "Necromancer"]
LEVEL_TABLE_FILES = ("spells.are", "skills.are")
FOR_RE = re.compile(r"^(?:For (?:the )?([a-z' -]+?)(?: spell)?, (?:the )?minimum level"
                    r"|Minimum levels for (?:the use of )?([a-z' -]+?) are)", re.I)
# A page whose keyword is not the skill's own name.
LEVEL_TABLE_ALIASES = {"sleepspell": "sleep"}


def level_line(levels) -> str:
    """A class level table as the spell and skill pages write it."""
    return "  ".join("%s:%s" % (c, l if l < UNAVAILABLE else "N/A")
                     for c, l in zip(CLASS_NAMES, levels))


def level_tables(text: str):
    """Every 'Mage:.. Cleric:..' minimum-level line in a help file, with the
    skill it describes and the line the skill table says it should be:
    (line number, skill, old line, new line).  A trains table ("Number of
    trains ...") is not a level table and is left alone."""
    table = {n.lower(): lv for n, lv, f in skills()}
    lines = text.split("\n")
    out = []
    entry_words = []
    for i, line in enumerate(lines):
        m = re.match(r"^-?\d+ (.*)~$", line)
        if m:
            entry_words = help_index.words_of(m.group(1))
            continue
        if not (line.startswith("Mage:") and "Cleric:" in line):
            continue
        context = [l for l in lines[max(0, i - 3):i] if l.strip()]
        if not context or "level" not in context[-1].lower() \
                or "train" in context[-1].lower():
            continue
        name = None
        for l in reversed(context):
            f = FOR_RE.match(l)
            if f:
                name = (f.group(1) or f.group(2)).lower()
                break
        if name is None:
            words = [LEVEL_TABLE_ALIASES.get(w, w) for w in entry_words]
            name = next((w for w in words if w in table), None)
        if name is None or name not in table:
            out.append((i + 1, name, line, None))
            continue
        out.append((i + 1, name, line, level_line(table[name])))
    return out


def write_level_tables() -> int:
    changed = 0
    for name in LEVEL_TABLE_FILES:
        path = AREA / name
        text = path.read_text(encoding="latin-1")
        lines = text.split("\n")
        for lineno, skill, old, new in level_tables(text):
            if new is not None and old != new:
                lines[lineno - 1] = new
                changed += 1
        path.write_text("\n".join(lines), encoding="latin-1")
    return changed


def load_exceptions() -> dict:
    return json.loads(EXCEPTIONS.read_text(encoding="utf-8"))


def mortal_keywords(entries) -> list:
    """Every keyword a mortal's HELP reaches its own page with."""
    seen = []
    for entry in entries:
        if entry.level > MORTAL_TRUST or entry.level < 0 and entry.words == ["keywords"]:
            continue
        for word in entry.words:
            if word in seen:
                continue
            if help_index.lookup(entries, word, MORTAL_TRUST) is entry:
                seen.append(word)
    return sorted(seen)


KEYWORDS_HEAD = """Helps are available for the following keywords.  If you try to see a
particular help and are told no help is available, it may be restricted
to those of a higher level than you.  A spell group with no page of its
own is answered from the group list: HELP GROUP <name> asks for the group
even where a command shares its name.  This list is generated from the
help itself (tools/help_audit.py --write-keywords).

"""


def keywords_text(entries) -> str:
    words = [w for w in mortal_keywords(entries) if w.isascii()]
    width = 19
    cols = 4
    lines = []
    for i in range(0, len(words), cols):
        row = words[i:i + cols]
        lines.append("".join(w.ljust(width) if j < len(row) - 1 else w
                             for j, w in enumerate(row)).rstrip())
    return KEYWORDS_HEAD + "\n".join(lines) + "\n"


def keywords_entry_span(text: str) -> tuple:
    m = re.search(r"^-1 KEYWORDS~\n", text, re.M)
    if m is None:
        raise SystemExit("area/toc.are has no '-1 KEYWORDS~' entry")
    end = text.index("\n~\n", m.end())
    return m.end(), end + 1


def write_keywords(entries) -> bool:
    path = AREA / "toc.are"
    text = path.read_text(encoding="latin-1")
    start, end = keywords_entry_span(text)
    new = text[:start] + keywords_text(entries) + text[end:]
    if new == text:
        return False
    path.write_text(new, encoding="latin-1")
    return True


def audit(entries=None) -> list:
    """Findings, each a string. Empty means the help covers the game."""
    entries = entries if entries is not None else help_index.load_helps(AREA)
    exc = load_exceptions()
    findings = []
    cmd_skip = exc["commands_without_help"]

    seen_names = set()
    for name, level, show, fun in commands():
        if name in seen_names:
            continue
        seen_names.add(name)
        trust = max(level, 1)
        mine = help_index.lookup(entries, name, trust)
        top = help_index.lookup(entries, name, MAX_LEVEL + 2)
        if name in cmd_skip:
            continue
        if mine is None and top is not None and name in exc["intended_gates"]:
            continue
        if mine is None and top is not None:
            findings.append("help gate above the command: %s (command %d, help %d: %s)"
                            % (name, level, top.level, top.keyword))
        elif mine is None:
            findings.append("command with no help: %s (level %d)" % (name, level))

    skill_skip = exc["skills_without_player_help"]
    for name, levels, fun in skills():
        if name in skill_skip or fun == "spell_null" and name in exc.get("passives_in_group_pages", {}):
            continue
        learnable = any(1 <= lv < UNAVAILABLE for lv in levels)
        if not learnable:
            continue
        if help_index.lookup(entries, name, 1) is None:
            findings.append("learnable skill with no level-1 help: %s" % name)

    for name in exc["obtainable_effects"]:
        if help_index.lookup(entries, name, 1) is None:
            findings.append("obtainable effect with no mortal help: %s" % name)

    allowed = {k.lower() for k in exc["shared_keywords"]}
    for word, why in exc["shared_keywords"].items():
        if why.get("kind") not in ("staff-first", "alias", "overview") or not why.get("why"):
            findings.append("shared_keywords[%r] needs a kind and a reason" % word)
    by_word = {}
    for entry in entries:
        for word in set(entry.words):
            by_word.setdefault(word, []).append(entry)
    for word, owners in sorted(by_word.items()):
        if len(owners) > 1 and word not in allowed:
            findings.append("keyword shared by %d pages, not listed as intended: %r (%s)"
                            % (len(owners), word, "; ".join("%s:%d %s" % (e.source, e.level, e.keyword[:30])
                                                           for e in owners)))
    for word in sorted(allowed):
        owners = by_word.get(word, [])
        if len(owners) < 2:
            findings.append("shared_keywords lists %r, which is no longer shared" % word)
            continue
        kind = exc["shared_keywords"][word]["kind"]
        # Staff get the first page their trust reaches, so the staff page
        # has to come first in the game's list or they never see it.
        if kind == "staff-first" and owners[0].level <= max(e.level for e in owners[1:]):
            findings.append("%r is a staff/public split, but the staff page does not come first"
                            % word)

    for name in LEVEL_TABLE_FILES:
        for lineno, skill, old, new in level_tables((AREA / name).read_text(encoding="latin-1")):
            if new is None:
                findings.append("%s:%d: a level table for no skill the table knows (%r)"
                                % (name, lineno, skill))
            elif old != new:
                findings.append("%s:%d: %s levels are %s, the page says %s"
                                % (name, lineno, skill, new, old))

    path = AREA / "toc.are"
    text = path.read_text(encoding="latin-1")
    start, end = keywords_entry_span(text)
    if text[start:end] != keywords_text(entries):
        findings.append("KEYWORDS in area/toc.are is stale: run tools/help_audit.py --write-keywords")
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write-keywords", action="store_true")
    ap.add_argument("--write-levels", action="store_true",
                    help="rewrite the spell and skill pages' class level tables from const.c")
    args = ap.parse_args(argv)
    if args.write_levels:
        print("%d level tables rewritten" % write_level_tables())
    entries = help_index.load_helps(AREA)
    if args.write_keywords:
        print("KEYWORDS rewritten" if write_keywords(entries) else "KEYWORDS already current")
        entries = help_index.load_helps(AREA)
    findings = audit(entries)
    for f in findings:
        print(f)
    print("%d help entries, %d findings" % (len(entries), len(findings)))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
