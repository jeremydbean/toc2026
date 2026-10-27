"""The game's help, read the way the game reads it.

`db.c`'s `load_helps` reads each `#HELPS` section as a token stream -- a
number, then a `~`-terminated keyword string, then a `~`-terminated body --
from every file `area.lst` (then `built/built.lst`) lists, in that order,
and `do_help` in `act_info.c` answers HELP in two passes over that list:
an exact keyword first, then `is_name`'s prefix match, skipping entries
above the reader's trust. A spell group with no entry of its own is
answered from `group_table` after both passes find nothing.

The dashboard's help pages, the Oracle's grounding and the help tests all
read through this module, so they select exactly what HELP selects
(review, 2026-10-27: the old loader globbed every .are file, sorted by
title, decoded as UTF-8, split quoted phrases into words and skipped
headers that wrap a line -- HELP STONE SKIN worked in game and was a 404
on the website).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

try:  # imported as webadmin.help_index or, from webadmin/, as help_index
    from .area_parser import listed_area_files
except ImportError:  # pragma: no cover - the flat import the server uses
    from area_parser import listed_area_files


@dataclass
class HelpEntry:
    level: int
    keyword: str             # the keyword string as the game holds it
    text: str                # the body, newlines as \n
    source: str              # the area file it came from
    order: int               # its place in the game's help list
    words: List[str] = field(default_factory=list)   # one_argument's words

    @property
    def title(self) -> str:
        return self.words[0].title() if self.words else ""


def one_argument(s: str) -> tuple:
    """interp.c's one_argument: skip whitespace, a quoted run is one word,
    otherwise a word ends at a space; lowercased."""
    i = 0
    n = len(s)
    while i < n and s[i].isspace():
        i += 1
    end = " "
    if i < n and s[i] in "'\"":
        end = s[i]
        i += 1
    out = []
    while i < n:
        if s[i] == end:
            i += 1
            break
        out.append(s[i].lower())
        i += 1
    while i < n and s[i].isspace():
        i += 1
    return "".join(out), s[i:]


def words_of(s: str) -> List[str]:
    out = []
    rest = s
    while True:
        word, rest = one_argument(rest)
        if not word:
            return out
        out.append(word)


def is_name(string: str, namelist: str) -> bool:
    """handler.c's is_name: every word asked must be the prefix of some
    keyword, or the whole string equals one keyword."""
    names = words_of(namelist)
    whole = string.lower()
    for part in words_of(string):
        for name in names:
            if whole == name:
                return True
            if name.startswith(part):
                break
        else:
            return False
    return True


def keyword_exact(argument: str, keyword: str) -> bool:
    """act_info.c's help_keyword_exact: the argument equals one keyword,
    a quoted phrase counting as one."""
    if not argument:
        return False
    wanted = argument.lower()
    return any(word == wanted for word in words_of(keyword))


def _parse_section(text: str, source: str, start_order: int) -> List[HelpEntry]:
    """One #HELPS section, read as fread_number/fread_string read it."""
    entries: List[HelpEntry] = []
    i = 0
    n = len(text)

    def skip_space(j: int) -> int:
        while j < n and text[j].isspace():
            j += 1
        return j

    def read_string(j: int) -> tuple:
        j = skip_space(j)
        k = text.find("~", j)
        if k < 0:
            return None, n
        return text[j:k], k + 1

    while True:
        i = skip_space(i)
        if i >= n:
            break
        j = i
        if j < n and text[j] in "+-":
            j += 1
        while j < n and text[j].isdigit():
            j += 1
        try:
            level = int(text[i:j])
        except ValueError:
            break
        keyword, i = read_string(j)
        if keyword is None or keyword.startswith("$"):
            break
        body, i = read_string(i)
        if body is None:
            break
        # load_helps folds a header that wraps a line into one line, so a
        # keyword never runs into the next one across the line break.
        keyword = " ".join(keyword.replace("\r", " ").split())
        entries.append(HelpEntry(level=level, keyword=keyword,
                                 text=body.replace("\r", ""), source=source,
                                 order=start_order + len(entries),
                                 words=words_of(keyword)))
    return entries


def load_helps(area_dir: Path, files: Optional[Iterable[str]] = None) -> List[HelpEntry]:
    """Every help entry the game loads, in the game's order. Area files are
    Latin-1; anything a list does not name is never read."""
    area_dir = Path(area_dir)
    names = list(files) if files is not None else listed_area_files(area_dir)
    entries: List[HelpEntry] = []
    for name in names:
        path = area_dir / name
        try:
            content = path.read_text(encoding="latin-1")
        except OSError:
            continue
        marker = content.find("#HELPS")
        if marker < 0:
            continue
        entries += _parse_section(content[marker + len("#HELPS"):], name, len(entries))
    return entries


def ask(argument: str) -> str:
    """do_help's argall: the words of the argument joined by single spaces."""
    return " ".join(words_of(argument))


def lookup(entries: List[HelpEntry], argument: str, trust: int) -> Optional[HelpEntry]:
    """What HELP <argument> shows somebody of this trust, or None (the
    group fallback and the suggestions come after)."""
    argall = ask(argument or "summary")
    if not argall:
        argall = "summary"
    for entry in entries:
        if entry.level <= trust and keyword_exact(argall, entry.keyword):
            return entry
    for entry in entries:
        if entry.level <= trust and is_name(argall, entry.keyword):
            return entry
    return None


def reachable_by(entries: List[HelpEntry], entry: HelpEntry, trust: int) -> Optional[str]:
    """A keyword that brings this entry up at this trust, or None when every
    keyword it has lands on an earlier entry first."""
    for word in entry.words:
        if lookup(entries, "'%s'" % word if " " in word else word, trust) is entry:
            return word
    return None
