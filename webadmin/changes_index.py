"""The game's CHANGES list, read for the website (2026-11-12).

area/changes.dat is what src/changes.c reads: comment lines starting with
'#' (anywhere), then entries headed `@ <id> <yyyy-mm-dd>` and
optionally ` staff`, each followed by its text and a blank line, newest
first. A staff entry is shown in game to staff alone, so the website shows
it only to an authenticated request.

No fastapi here, so the reader can be tested wherever Python runs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

# As src/changes.c reads a header with sscanf: words split on any
# whitespace, the third word "staff" in any case.
HEADER = re.compile(r"^@\s*(\S+)\s+(\S+)(?:\s+(\S+))?")


def parse_changes(text: str) -> List[Dict[str, Any]]:
    """Every entry, in file order (newest first): id, date, staff, and
    the text as paragraphs, each paragraph's wrapped lines joined."""
    entries: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None
    paragraph: List[str] = []

    def close_paragraph() -> None:
        if current is not None and paragraph:
            current["paragraphs"].append(" ".join(paragraph))
        paragraph.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("#"):
            continue
        found = HEADER.match(line)
        if found:
            close_paragraph()
            current = {"id": found.group(1), "date": found.group(2),
                       "staff": (found.group(3) or "").lower() == "staff", "paragraphs": []}
            entries.append(current)
            continue
        if current is None:
            continue
        if not line.strip():
            close_paragraph()
        else:
            paragraph.append(line.strip())
    close_paragraph()
    return entries


def read_changes(path: Path) -> List[Dict[str, Any]]:
    """The file as entries; an unreadable or missing file is no entries.
    Latin-1, like every file the game reads."""
    try:
        return parse_changes(path.read_text(encoding="latin-1"))
    except OSError:
        return []


def visible_changes(entries: List[Dict[str, Any]], staff: bool) -> List[Dict[str, Any]]:
    """What a reader may see: staff entries only for staff."""
    return [entry for entry in entries if staff or not entry["staff"]]
