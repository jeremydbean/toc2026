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
    can reach (--write-keywords regenerates it);
  - every See also destination and every HELP <TOPIC> a page advertises
    reaches the page it names for the page's own reader (help_index.resolve,
    do_help whole: exact, prefix, phrase, group, first word) -- by its exact
    keyword or a group of exactly that name; a prefix landing elsewhere
    (PET -> PETRIFY), the first-word fallback, nothing, a page above the
    reader (*-above-reader) and a display label ('GODTALK (@)') are findings;
  - no command is split over two pages by a stem of its name (NERVE and
    'NERVE DAMAGE', NOCHANNEL and NOCHANNELS), unless distinct_pages says why;
  - no staff command's page is open to mortals (REPORTS, MIRROR, INVULN);
  - Syntax: lines start with something the game answers, do not advertise a
    token the command refuses (DROP 10 COINS), and no command page names a
    minimum level its command does not have (HELP SAVE said level 3).

Findings named in data/help_audit_baseline.json are reported as known and
do not fail; a new one does; a baseline entry no finding has any more is
reported as stale so it can be taken out (--write-baseline rewrites it).

  python3 tools/help_audit.py              # report, exit 1 on a new finding
  python3 tools/help_audit.py --known      # the baselined findings too
  python3 tools/help_audit.py --lengths    # words per page (information)
  python3 tools/help_audit.py --inventory  # a markdown inventory, to stdout
  python3 tools/help_audit.py --write-baseline
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

    def render(row) -> str:
        # A keyword too long for its column takes the next one too, so
        # the word after it never runs into it.
        out = ""
        for j, w in enumerate(row):
            if j < len(row) - 1:
                out += w.ljust(-(-(len(w) + 1) // width) * width)
            else:
                out += w
        return out

    lines = []
    row = []
    for w in words:
        # A row ends at four keywords or before one would pass column 79
        # (test_help_audit's narrow terminal).
        if row and (len(row) == cols or len(render(row + [w])) > 79):
            lines.append(render(row).rstrip())
            row = []
        row.append(w)
    if row:
        lines.append(render(row).rstrip())
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


class Finding(str):
    """A finding's message (it is the string), with a kind and a stable
    key the baseline can name: "<kind>: <what>", free of levels and
    line numbers, so the key survives a page being reworded or relevelled and
    goes stale only when the problem itself is gone."""
    kind: str
    key: str

    def __new__(cls, kind: str, what: str, message: str) -> "Finding":
        self = super().__new__(cls, message)
        self.kind = kind
        self.key = "%s: %s" % (kind, what)
        return self


def coverage_findings(entries, exc) -> list:
    """The original audit: commands, skills and effects covered, shared
    keywords listed, level tables and KEYWORDS generated."""
    findings = []
    cmd_skip = exc["commands_without_help"]
    entries = entries if entries is not None else help_index.load_helps(AREA)

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
            findings.append(Finding("help-gate", name,
                                    "help gate above the command: %s (command %d, help %d: %s)"
                                    % (name, level, top.level, top.keyword)))
        elif mine is None:
            findings.append(Finding("command-no-help", name,
                                    "command with no help: %s (level %d)" % (name, level)))

    skill_skip = exc["skills_without_player_help"]
    for name, levels, fun in skills():
        if name in skill_skip or fun == "spell_null" and name in exc.get("passives_in_group_pages", {}):
            continue
        learnable = any(1 <= lv < UNAVAILABLE for lv in levels)
        if not learnable:
            continue
        if help_index.lookup(entries, name, 1) is None:
            findings.append(Finding("skill-no-help", name,
                                    "learnable skill with no level-1 help: %s" % name))

    for name in exc["obtainable_effects"]:
        if help_index.lookup(entries, name, 1) is None:
            findings.append(Finding("effect-no-help", name,
                                    "obtainable effect with no mortal help: %s" % name))

    allowed = {k.lower() for k in exc["shared_keywords"]}
    for word, why in exc["shared_keywords"].items():
        if why.get("kind") not in ("staff-first", "alias", "overview") or not why.get("why"):
            findings.append(Finding("exception-format", "shared_keywords " + word,
                                    "shared_keywords[%r] needs a kind and a reason" % word))
    by_word = keyword_owners(entries)
    for word, owners in sorted(by_word.items()):
        if len(owners) > 1 and word not in allowed:
            findings.append(Finding(
                "shared-keyword", word,
                "keyword shared by %d pages, not listed as intended: %r (%s)"
                % (len(owners), word, "; ".join("%s:%d %s" % (e.source, e.level, e.keyword[:30])
                                                for e in owners))))
    for word in sorted(allowed):
        owners = by_word.get(word, [])
        if len(owners) < 2:
            findings.append(Finding("shared-keyword-stale", word,
                                    "shared_keywords lists %r, which is no longer shared" % word))
            continue
        kind = exc["shared_keywords"][word]["kind"]
        # Staff get the first page their trust reaches, so the staff page
        # has to come first in the game's list or they never see it.
        if kind == "staff-first" and owners[0].level <= max(e.level for e in owners[1:]):
            findings.append(Finding("staff-first-order", word,
                                    "%r is a staff/public split, but the staff page does not come first"
                                    % word))

    for name in LEVEL_TABLE_FILES:
        for lineno, skill, old, new in level_tables((AREA / name).read_text(encoding="latin-1")):
            if new is None:
                findings.append(Finding("level-table", "%s %s" % (name, skill),
                                        "%s:%d: a level table for no skill the table knows (%r)"
                                        % (name, lineno, skill)))
            elif old != new:
                findings.append(Finding("level-table", "%s %s" % (name, skill),
                                        "%s:%d: %s levels are %s, the page says %s"
                                        % (name, lineno, skill, new, old)))

    path = AREA / "toc.are"
    text = path.read_text(encoding="latin-1")
    start, end = keywords_entry_span(text)
    if text[start:end] != keywords_text(entries):
        findings.append(Finding("keywords-stale", "toc.are",
                                "KEYWORDS in area/toc.are is stale: run tools/help_audit.py --write-keywords"))
    return findings


def keyword_owners(entries) -> dict:
    by_word = {}
    for entry in entries:
        for word in set(entry.words):
            by_word.setdefault(word, []).append(entry)
    return by_word


# ---------------------------------------------------------------------------
# Cross-references: See also lists and advertised HELP queries
# ---------------------------------------------------------------------------

def page_name(entry) -> str:
    """A page as a finding names it: its first keyword, as typed."""
    return entry.words[0].upper() if entry.words else entry.keyword.upper()


def reader_trust(entry) -> int:
    """The lowest trust that reads this page: a level 0 page's reader may
    be a level 1 character, and a page below zero (MOTD) is shown to all."""
    return max(entry.level, 1)


SEE_ALSO_LINE = re.compile(r"^\s*see also\b\s*:?\s*(.*)$", re.I)
SEE_ALSO_LEAD = re.compile(r"^(?:the\s+)?(?:helps?|topics?|pages?)\s+(?:on|for)\s+", re.I)
LIST_SPLIT = re.compile(r"\s*,\s*|\s+(?:and|or)\s+", re.I)
REFERENCE_CHARS = re.compile(r"^[A-Za-z0-9'_ -]+$")
CONTINUED = re.compile(r"(?:,|\b(?:and|or))\s*$", re.I)


def see_also_lists(text: str) -> list:
    """Every See also list in a page body: (line number, [destinations as
    written]).  A list runs on to the next line while its last line ends
    with a comma, 'and' or 'or'; 'See also helps on X' and a leading HELP
    on a destination are read as the destination."""
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        m = SEE_ALSO_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        start = i
        body = m.group(1)
        while CONTINUED.search(body) and i + 1 < len(lines) and lines[i + 1].strip():
            i += 1
            body += " " + lines[i].strip()
        body = SEE_ALSO_LEAD.sub("", body.strip())
        items = []
        for item in LIST_SPLIT.split(body):
            item = item.strip().rstrip(".;:").strip()
            item = re.sub(r"^help\s+", "", item, flags=re.I)
            if item:
                items.append(item)
        out.append((start + 1, items))
        i += 1
    return out


# HELP X in prose: an upper-case topic, words run together while each is
# upper case, never across another HELP; a placeholder after it (HELP
# GROUP <name>) means the line shows syntax, not a topic.
HELP_REF = re.compile(r"\b[Hh][Ee][Ll][Pp]\s+('[^'\n]+'|[A-Z][A-Z0-9_-]*(?: (?!HELP\b)[A-Z][A-Z0-9_-]*)*)\b(?!'?\s*<)")


def help_references(text: str) -> list:
    """(line number, topic) for every HELP <TOPIC> a page advertises
    outside its See also lists."""
    out = []
    for lineno, line in enumerate(text.split("\n"), 1):
        if SEE_ALSO_LINE.match(line):
            continue
        for m in HELP_REF.finditer(line):
            out.append((lineno, m.group(1)))
    return out


def malformed_reference(item: str) -> bool:
    """A destination nobody can type as written: a display label such as
    'GODTALK (@)', unbalanced quotes, or prose rather than a topic."""
    quoted = item[:1] in "'\"" and item[-1:] == item[:1] and len(item) > 1
    bare = item[1:-1] if quoted else item
    if not REFERENCE_CHARS.match(bare) or "'" in bare.strip("'") and not quoted:
        return True
    return len(bare.split()) > 4


def describe(res, trust: int) -> str:
    if res.how is None:
        return "reaches nothing at trust %d" % trust
    if res.how in ("group", "group-command"):
        return "reaches group %r by %s at trust %d" % (
            res.group, "exact name" if res.how == "group-command" or res.group.lower() == res.argall
            else "prefix", trust)
    how = {"exact": "its exact keyword", "prefix": "prefix", "phrase": "phrase prefix",
           "first-word": "the first-word fallback"}[res.how]
    return "reaches %s (%s:%d) by %s at trust %d" % (
        page_name(res.entry), res.entry.source, res.entry.level, how, trust)


def reference_ok(res) -> bool:
    """A destination reaches the page it names: its exact keyword, or the
    group of exactly that name (HELP GROUP X, or the group fallback)."""
    if res.how in ("exact", "group-command"):
        return True
    return res.how == "group" and res.group.lower() == res.argall


def check_reference(entries, groups_in_order, entry, item: str, aliases: dict):
    """None when the destination is fine, else (kind suffix, why): "" for a
    destination that reaches the wrong page or nothing at all, "-above-reader"
    for one whose own page exists but sits above this page's reader."""
    if item.lower().strip("'\"") in aliases:
        return None
    low = reader_trust(entry)
    res = help_index.resolve(entries, item, low, groups_in_order)
    if reference_ok(res):
        return None
    why = describe(res, low)
    top = help_index.resolve(entries, item, MAX_LEVEL + 2, groups_in_order)
    if low < MAX_LEVEL + 2 and (top.how, top.entry, top.group) != (res.how, res.entry, res.group):
        why += "; " + describe(top, MAX_LEVEL + 2)
    return ("-above-reader" if reference_ok(top) else ""), why


def reference_findings(entries, groups_in_order, aliases=None) -> list:
    """See also destinations and advertised HELP queries that do not
    reach the page they name, at the trust of the page's own reader."""
    aliases = {k.lower(): v for k, v in (aliases or {}).items()}
    findings = []
    for entry in entries:
        name = page_name(entry)
        seen = set()
        for lineno, items in see_also_lists(entry.text):
            for item in items:
                if (item.lower(), "see") in seen:
                    continue
                seen.add((item.lower(), "see"))
                if malformed_reference(item):
                    findings.append(Finding(
                        "see-also-malformed", "%s -> %s" % (name, item),
                        "See also on %s (%s): %r is not a topic anybody can type"
                        % (name, entry.source, item)))
                    continue
                bad = check_reference(entries, groups_in_order, entry, item, aliases)
                if bad:
                    findings.append(Finding(
                        "see-also" + bad[0], "%s -> %s" % (name, item.upper()),
                        "See also on %s (%s): %s %s" % (name, entry.source, item, bad[1])))
        for lineno, item in help_references(entry.text):
            if (item.lower(), "help") in seen:
                continue
            seen.add((item.lower(), "help"))
            bad = check_reference(entries, groups_in_order, entry, item, aliases)
            if bad:
                findings.append(Finding(
                    "help-ref" + bad[0], "%s -> %s" % (name, item.upper()),
                    "HELP %s advertised on %s (%s): %s" % (item, name, entry.source, bad[1])))
    return findings


# ---------------------------------------------------------------------------
# Two pages for one command
# ---------------------------------------------------------------------------

STEM_SUFFIXES = ("s", "es", "r", "er")


def source_functions() -> dict:
    """Every do_ function's body in src/, by name."""
    out = {}
    for path in sorted((ROOT / "src").glob("*.c")):
        text = path.read_text(encoding="latin-1")
        for m in re.finditer(r"^void\s+(do_\w+)\s*\([^)]*\)\s*\n?\{", text, re.M):
            end = re.compile(r"^\}", re.M).search(text, m.end())
            out.setdefault(m.group(1), text[m.end():end.start() if end else len(text)])
    return out


def full_command_names() -> dict:
    """interp.c's full_command_names: a skill's whole name -> its command."""
    text = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
    m = re.search(r"full_command_names\[\]\s*=\s*\{(.*?)\};", text, re.S)
    return dict(re.findall(r'\{\s*"([^"]+)",\s*"([^"]+)"\s*\}', m.group(1))) if m else {}


def same_command(short: str, long: str, cmds: dict, skill_names: set, bodies: dict,
                 whole_names: dict) -> bool:
    """Whether two keywords name one command: a suffix of the same word
    (NOCHANNEL and NOCHANNELS) where either is a command, or a command and
    the multi-word skill it runs (NERVE and 'NERVE DAMAGE')."""
    rest = long[len(short):]
    if rest in STEM_SUFFIXES:
        # Two commands with functions of their own (GROUP and GROUPS,
        # REPORT and REPORTS) are two commands, not one.
        if short in cmds and long in cmds:
            return cmds[short] == cmds[long]
        return short in cmds or long in cmds
    if not rest.startswith(" ") or short not in cmds or long not in skill_names:
        return False
    if whole_names.get(long) == short:
        return True
    fun = cmds[short]
    if fun == "do_" + long.replace(" ", "_"):
        return True
    gsn = "gsn_" + re.sub(r"\W+", "_", long)
    return gsn in bodies.get(fun, "")


def alias_pair_findings(entries, cmds: dict, skill_names: set, bodies: dict,
                        whole_names: dict, distinct: dict) -> list:
    """Keyword pairs on two pages where one is a stem of the other and both
    name the same command (LISTEN and 'LISTEN AT DOOR'): a reader gets a
    different page depending on how much they type.  A staff page and a
    public page sharing a stem are the staff-first split, not this."""
    distinct = {k.lower() for k in distinct}
    owners = keyword_owners(entries)
    findings = []
    seen = set()
    words = sorted(owners)
    for short in words:
        if len(short) < 3:
            continue
        for long in words:
            if long == short or not long.startswith(short):
                continue
            if not same_command(short, long, cmds, skill_names, bodies, whole_names):
                continue
            for p in owners[short]:
                for q in owners[long]:
                    if p is q or short in q.words or long in p.words:
                        continue
                    if (p.level >= LEVEL_IMMORTAL) != (q.level >= LEVEL_IMMORTAL):
                        continue
                    pair = "%s / %s" % (short, long)
                    if pair in distinct or pair in seen:
                        continue
                    seen.add(pair)
                    findings.append(Finding(
                        "alias-pair", pair,
                        "%s and %s name one command on two pages: %s (%s:%d) and %s (%s:%d)"
                        % (short.upper(), long.upper(), page_name(p), p.source, p.level,
                           page_name(q), q.source, q.level)))
    return findings


# ---------------------------------------------------------------------------
# Staff commands with public help
# ---------------------------------------------------------------------------

LEVEL_IMMORTAL = MAX_LEVEL - 10


def staff_help_findings(entries, cmd_rows, shared: dict, allowed: dict) -> list:
    """A command only staff can type whose page every mortal reads (REPORTS,
    MIRROR, INVULN): the page should carry the command's rank."""
    shared = {k.lower() for k in shared}
    allowed = {k.lower() for k in allowed}
    findings = []
    seen = set()
    for name, level, show, fun in cmd_rows:
        if name in seen:
            continue
        seen.add(name)
        if level < LEVEL_IMMORTAL or name in shared or name in allowed:
            continue
        res = help_index.resolve(entries, name, level)
        if res.how != "exact" or res.entry.level >= LEVEL_IMMORTAL:
            continue
        findings.append(Finding(
            "staff-command-public-help", name,
            "%s is a level %d command, but its page %s (%s) is level %d"
            % (name.upper(), level, page_name(res.entry), res.entry.source, res.entry.level)))
    return findings


# ---------------------------------------------------------------------------
# Facts the pages state, held to the source
# ---------------------------------------------------------------------------

SYNTAX_LINE = re.compile(r"^\s*Syntax\s*:\s*(.*)$", re.I)


def social_names(area_dir: Path = AREA) -> set:
    """Every social's name, read as load_socials reads social.are."""
    import area_reader  # noqa: E402 - beside help_index in webadmin/
    out = set()
    for name in help_index.listed_area_files(area_dir):
        try:
            text = (area_dir / name).read_text(encoding="latin-1")
        except OSError:
            continue
        mark = text.find("#SOCIALS")
        if mark < 0:
            continue
        r = area_reader.TokenReader(text, mark + len("#SOCIALS"), name)
        while not r.at_end():
            word = r.word()
            if word == "#0":
                break
            out.add(word.lower())
            r.to_eol()
            for _ in range(8):
                if r.string_eol() == "#":
                    break
    return out


def syntax_lines(text: str) -> list:
    """(line number, the rest of the line) for every Syntax: line."""
    out = []
    for lineno, line in enumerate(text.split("\n"), 1):
        m = SYNTAX_LINE.match(line)
        if m and m.group(1).strip():
            out.append((lineno, m.group(1).strip()))
    return out


def command_known(word: str, names: list, socials: set, skill_names: set) -> bool:
    """Whether interpret() does something with this first word: a command
    or an abbreviation of one, a social, or a skill typed by name."""
    if word in socials or word in skill_names:
        return True
    if any(word == s.split()[0] for s in skill_names):
        return True
    return any(name.startswith(word) for name in names)


def syntax_findings(entries, cmd_rows, socials: set, skill_names: set) -> list:
    """A Syntax: line whose first word nothing in the game answers."""
    names = [row[0] for row in cmd_rows]
    findings = []
    for entry in entries:
        for lineno, rest in syntax_lines(entry.text):
            word = rest.split()[0].strip("'\"").lower()
            if not word[:1].isalpha():
                continue      # (automatic), <spell>, a bare 'quoted' name
            word = re.sub(r"[^a-z0-9_-].*$", "", word)
            if not word or command_known(word, names, socials, skill_names):
                continue
            findings.append(Finding(
                "syntax-unknown-command", "%s: %s" % (page_name(entry), word),
                "Syntax on %s (%s): %r is no command, social or skill"
                % (page_name(entry), entry.source, word)))
    return findings


# Tokens a command refuses outright, each with the words that prove it
# still does: a Syntax line that advertises one teaches a dead end.
# (DROP 10 COINS asks which coin: copper, silver, gold or platinum.)
SYNTAX_REFUSALS = {
    "drop": {"tokens": ("coins", "coin"), "function": "do_drop",
             "proof": "specify which type of coin"},
    "give": {"tokens": ("coins", "coin"), "function": "do_give",
             "proof": "specify which type of coin"},
}


def refused_token_findings(entries, bodies: dict, refusals=None) -> list:
    refusals = SYNTAX_REFUSALS if refusals is None else refusals
    findings = []
    for command, rule in sorted(refusals.items()):
        if rule["proof"] not in bodies.get(rule["function"], ""):
            findings.append(Finding(
                "syntax-refusal-stale", command,
                "SYNTAX_REFUSALS says %s refuses %s, but %s no longer says %r"
                % (command.upper(), "/".join(rule["tokens"]), rule["function"], rule["proof"])))
            continue
        for entry in entries:
            for lineno, rest in syntax_lines(entry.text):
                words = [w.strip("'\"<>[]().,").lower() for w in rest.split()]
                if not words or words[0] != command:
                    continue
                bad = sorted(set(words[1:]) & set(rule["tokens"]))
                if bad:
                    findings.append(Finding(
                        "syntax-refused-token", "%s %s" % (command, bad[0]),
                        "Syntax on %s (%s): %r -- %s refuses %r"
                        % (page_name(entry), entry.source, rest, command.upper(), bad[0])))
    return findings


LEVEL_CLAIM = re.compile(r"\b(?:must|need to|have to)\s+be\s+(?:at\s+least\s+)?level\s+(\d+)", re.I)
LEVEL_GATE = re.compile(r"->level\b|get_trust\s*\(|IS_IMMORTAL|IS_HERO|IS_TRUSTED|LEVEL_\w+")


def level_claim_findings(entries, cmd_rows, bodies: dict) -> list:
    """A command's page that names a minimum level the command does not
    have: its table level is lower and its function checks no level
    (HELP SAVE said level 3; SAVE is open from level 1)."""
    findings = []
    seen = set()
    pages = set()
    for name, level, show, fun in cmd_rows:
        if name in seen:
            continue
        seen.add(name)
        res = help_index.resolve(entries, name, max(level, 1))
        if res.how != "exact" or id(res.entry) in pages:
            continue
        pages.add(id(res.entry))
        body = bodies.get(fun)
        if body is None or LEVEL_GATE.search(body):
            continue
        for m in LEVEL_CLAIM.finditer(" ".join(res.entry.text.split())):
            claimed = int(m.group(1))
            if claimed > max(level, 1):
                findings.append(Finding(
                    "help-level-claim", page_name(res.entry),
                    "%s (%s) says level %d; the command is level %d and %s checks no level"
                    % (page_name(res.entry), res.entry.source, claimed, level, fun)))
                break
    return findings


# ---------------------------------------------------------------------------
# The whole audit, the baseline, and the reports
# ---------------------------------------------------------------------------

BASELINE = ROOT / "data" / "help_audit_baseline.json"


def all_findings(entries=None, exc=None, unused=None) -> list:
    """Every finding, known or new.  `unused`, a list, collects the
    exceptions in the new sections that excuse nothing any more."""
    entries = entries if entries is not None else help_index.load_helps(AREA)
    exc = exc if exc is not None else load_exceptions()
    cmd_rows = commands()
    live_names = {}
    for name, level, show, fun in cmd_rows:
        live_names.setdefault(name, fun)
    skill_names = {name.lower() for name, levels, fun in skills()}
    group_names = [name for name, members in groups()]
    bodies = source_functions()
    findings = coverage_findings(entries, exc)
    findings += exception_findings(exc)

    # Each excusable check runs with no exceptions, so an exception that
    # excuses nothing can be named, and is then filtered.
    aliases = {k.lower() for k in exc.get("reference_aliases", {})}
    refs = reference_findings(entries, group_names)
    used = {f.key.split(" -> ", 1)[1].lower().strip("'\"") for f in refs}
    findings += [f for f in refs if f.key.split(" -> ", 1)[1].lower().strip("'\"") not in aliases]
    unused_now = ["reference_aliases %r" % a for a in sorted(aliases - used)]

    distinct = {k.lower() for k in exc.get("distinct_pages", {})}
    pairs = alias_pair_findings(entries, live_names, skill_names, bodies, full_command_names(), {})
    used = {f.key.split(": ", 1)[1] for f in pairs}
    findings += [f for f in pairs if f.key.split(": ", 1)[1] not in distinct]
    unused_now += ["distinct_pages %r" % p for p in sorted(distinct - used)]

    allowed = {k.lower() for k in exc.get("staff_commands_public_help", {})}
    staff = staff_help_findings(entries, cmd_rows, exc["shared_keywords"], {})
    used = {f.key.split(": ", 1)[1] for f in staff}
    findings += [f for f in staff if f.key.split(": ", 1)[1] not in allowed]
    unused_now += ["staff_commands_public_help %r" % c for c in sorted(allowed - used)]

    findings += syntax_findings(entries, cmd_rows, social_names(), skill_names)
    findings += refused_token_findings(entries, bodies)
    findings += level_claim_findings(entries, cmd_rows, bodies)
    if unused is not None:
        unused += unused_now
    return findings


def exception_findings(exc) -> list:
    """Every entry in the new exception sections says why."""
    out = []
    for section in ("distinct_pages", "staff_commands_public_help", "reference_aliases"):
        for name, why in exc.get(section, {}).items():
            if not isinstance(why, str) or len(why) < 20:
                out.append(Finding("exception-format", "%s %s" % (section, name),
                                   "%s[%r] needs a reason" % (section, name)))
    return out


def load_baseline(path: Path = BASELINE) -> set:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    return set(data.get("findings", []))


def write_baseline(findings, path: Path = BASELINE) -> int:
    keys = sorted({f.key for f in findings})
    data = {
        "_comment": ("Help audit findings known when this was written (tools/help_audit.py "
                     "--write-baseline). A finding listed here is reported as known and does "
                     "not fail; a new one fails; an entry that no longer occurs is reported "
                     "as stale so it can be taken out. Fix the help rather than add to this."),
        "findings": keys,
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return len(keys)


def split_by_baseline(findings, baseline: set) -> tuple:
    """(new, known, stale): findings the baseline does not name, findings
    it does, and baseline keys no finding has any more."""
    new = [f for f in findings if f.key not in baseline]
    known = [f for f in findings if f.key in baseline]
    stale = sorted(baseline - {f.key for f in findings})
    return new, known, stale


def audit(entries=None, baseline=None) -> list:
    """The findings that fail: every finding the baseline does not name.
    Empty means the help covers the game as well as it did."""
    baseline = load_baseline() if baseline is None else baseline
    return split_by_baseline(all_findings(entries), baseline)[0]


def page_words(entry) -> int:
    return len(entry.text.split())


def lengths_report(entries) -> str:
    counts = sorted(((page_words(e), e) for e in entries), key=lambda t: -t[0])
    sizes = [n for n, e in counts]
    lines = ["%d help pages, %d words in all; median %d words"
             % (len(sizes), sum(sizes), sorted(sizes)[len(sizes) // 2] if sizes else 0)]
    for limit in (150, 250, 500):
        lines.append("  over %3d words: %d pages" % (limit, sum(1 for n in sizes if n > limit)))
    lines.append("Longest pages:")
    for n, e in counts[:25]:
        lines.append("  %5d  %-24s %s:%d" % (n, page_name(e)[:24], e.source, e.level))
    return "\n".join(lines)


def md(text: str) -> str:
    return str(text).replace("|", "\\|")


def inventory(entries, exc=None) -> str:
    """The help as an owner reads it: every page, its other keywords, who
    can read it and from where, the intended rank splits, and the groups
    answered from the group table."""
    exc = exc if exc is not None else load_exceptions()
    group_names = [name for name, members in groups()]
    out = ["# Help inventory", "",
           "Generated by `python3 tools/help_audit.py --inventory` from the help as the game "
           "loads it (area.lst order). A keyword marked *shadowed* reaches an earlier page.",
           "", "| # | Topic | Aliases | Level | File | Words | Notes |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    shared = {k.lower(): v for k, v in exc["shared_keywords"].items()}
    for i, entry in enumerate(entries, 1):
        trust = reader_trust(entry)
        aliases = []
        notes = []
        for word in entry.words[1:]:
            reach = help_index.lookup(entries, "'%s'" % word if " " in word else word, trust)
            aliases.append(word.upper() + ("" if reach is entry else " *(shadowed)*"))
        for word in entry.words:
            if word in shared:
                notes.append("%s %s" % (shared[word]["kind"], word.upper()))
        if help_index.reachable_by(entries, entry, MAX_LEVEL + 2) is None:
            notes.append("unreachable")
        out.append("| %d | %s | %s | %d | %s | %d | %s |" % (
            i, md(page_name(entry)), md(", ".join(aliases)), entry.level, entry.source,
            page_words(entry), md("; ".join(notes))))
    out += ["", "## Intended rank splits and aliases (data/help_coverage.json)", "",
            "| Keyword | Kind | Pages | Why |", "| --- | --- | --- | --- |"]
    owners = keyword_owners(entries)
    for word, why in sorted(shared.items()):
        pages = "; ".join("%s (%s:%d)" % (page_name(e), e.source, e.level)
                          for e in owners.get(word, []))
        out.append("| %s | %s | %s | %s |" % (word.upper(), why["kind"], md(pages), md(why["why"])))
    for section in ("distinct_pages", "staff_commands_public_help", "reference_aliases"):
        for name, why in sorted(exc.get(section, {}).items()):
            out.append("| %s | %s | | %s |" % (md(name.upper()), section, md(why)))
    out += ["", "## Groups answered from the group table", "",
            "HELP <group> with no page of its own shows the group's members (do_help's "
            "group fallback); HELP GROUP <name> always does.", "",
            "| Group | HELP <name> at trust 1 |", "| --- | --- |"]
    for name in group_names:
        res = help_index.resolve(entries, name, 1, group_names)
        if res.how == "group":
            answer = "group table" if res.group == name else "group %r" % res.group
        elif res.how is None:
            answer = "nothing"
        elif res.entry is not None:
            answer = "page %s (%s)" % (page_name(res.entry), res.how)
        else:
            answer = res.how
        out.append("| %s | %s |" % (name, md(answer)))
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write-keywords", action="store_true")
    ap.add_argument("--write-levels", action="store_true",
                    help="rewrite the spell and skill pages' class level tables from const.c")
    ap.add_argument("--write-baseline", action="store_true",
                    help="record every current finding in data/help_audit_baseline.json")
    ap.add_argument("--lengths", action="store_true",
                    help="print words per page (information, never a failure)")
    ap.add_argument("--inventory", action="store_true",
                    help="print a markdown inventory of the help and stop")
    ap.add_argument("--known", action="store_true",
                    help="print the known (baselined) findings as well")
    args = ap.parse_args(argv)
    if args.write_levels:
        print("%d level tables rewritten" % write_level_tables())
    entries = help_index.load_helps(AREA)
    if args.write_keywords:
        print("KEYWORDS rewritten" if write_keywords(entries) else "KEYWORDS already current")
        entries = help_index.load_helps(AREA)
    if args.inventory:
        sys.stdout.write(inventory(entries))
        return 0
    unused = []
    findings = all_findings(entries, unused=unused)
    for note in unused:
        print("unused exception in data/help_coverage.json (remove it): " + note)
    if args.write_baseline:
        print("%d findings written to %s" % (write_baseline(findings),
                                             BASELINE.relative_to(ROOT)))
    baseline = load_baseline()
    new, known, stale = split_by_baseline(findings, baseline)
    for f in new:
        print(f)
    if args.known:
        for f in known:
            print("known: " + f)
    for key in stale:
        print("stale baseline entry (no longer found; remove it): " + key)
    if args.lengths:
        print(lengths_report(entries))
    kinds = {}
    for f in findings:
        kinds.setdefault(f.kind, [0, 0])[0 if f.key in baseline else 1] += 1
    print("%d help entries, %d findings (%d known, %d stale baseline entries)"
          % (len(entries), len(new), len(known), len(stale)))
    for kind, (old, fresh) in sorted(kinds.items()):
        print("  %-28s %4d known %4d new" % (kind, old, fresh))
    return 1 if new else 0


if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # --inventory | head
    sys.exit(main())
