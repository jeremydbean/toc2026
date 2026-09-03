#!/usr/bin/env python3
import re
from pathlib import Path

ROM_PATH = Path("area/rom.are")

# Keyed by marker expected in the header (upper-cased).
SEE_ALSO = {
    "WIZLIST": "IMMORTAL, LEVELS, WHO",
    "SOCIALS": "EMOTE, CHANNELS, SAY",
    "'NEWBIE INFO'": "BEGINNERS, RULES, GAIN",
    "IMOTD": "MOTD, JOBS, COMMANDMENTS",
    "JOBS": "COMMANDMENTS, QUESTS, WIZHELP",
    "COMMANDMENTS": "JOBS, IMOTD, WIZHELP",
    "PUFF": "ROM, STORY, CREDITS",
    "RULES": "BEGINNERS, PKILL, THIEF",
    "NEWS": "CHANGES, MOTD, IMOTD",
    "STORY": "DIKU, MERC, ROM",
    "DELETE": "QUIT, SAVE, PASSWORD",
    "HEALER": "HEAL, SHOPS, REPAIR",
    "TAX TAXES": "BANK, GOLD, BALANCE",
    "GAIN": "TRAIN, PRACTICE, GUILDS",
    "CLONE": "MLOAD, OLOAD, PURGE",
    "SKILLS SPELLS": "PRACTICE, GAIN, SPELLGROUP",
    "OUTFIT": "EQUIPMENT, WEAR, BEGINNERS",
    "AUTO AUTO": "CONFIG, SPLIT, SACRIFICE",
    "COUNT": "WHO, USERS, SCORE",
    "CHANGES": "NEWS, MOTD, IMOTD",
    "GATE": "SUMMON, RECALL, IPORTAL",
    "IPORTAL": "GATE, TRANSFER, RECALL",
}

REPLACEMENTS = {
    "'NEWBIE INFO'": (
        "New players should begin with HELP BEGINNERS and HELP RULES.\n\n"
        "If you are unsure where to train, use HELP GAIN and ask on INFO for\n"
        "a trainer for your class or guild path."
    ),
    "NEWS": (
        "Use HELP NEWS for current updates and patch notes.\n\n"
        "This ROM legacy entry is kept for compatibility with older help sets."
    ),
    "CHANGES": (
        "Use HELP NEWS for current gameplay and system changes.\n\n"
        "This ROM legacy entry is preserved for compatibility."
    ),
}


def marker_for_header(header: str):
    h = header.upper()
    if "GREETING" in h:
        return None
    if h.startswith("-1 COMMANDMENTS"):
        return "COMMANDMENTS"
    if h.startswith("0 AUTO "):
        return "AUTO AUTO"
    for marker in SEE_ALSO:
        if marker in h:
            return marker
    return None


def main() -> int:
    content = ROM_PATH.read_text(encoding="latin-1")

    # Limit changes to #HELPS section only.
    hs = content.find("#HELPS")
    if hs == -1:
        raise RuntimeError("Could not find #HELPS section in area/rom.are")

    # rom.are can omit a #0 section delimiter and end immediately after helps.
    he = content.find("\n#0", hs)
    if he == -1:
        he = len(content)

    helps = content[hs:he]

    entry_re = re.compile(r"\n(?P<header>-?\d+ [^\n~]+)~\n(?P<body>.*?)\n~", re.DOTALL)
    out = []
    pos = 0
    changed = 0

    for m in entry_re.finditer(helps):
        out.append(helps[pos:m.start()])
        header = m.group("header")
        body = m.group("body")

        marker = marker_for_header(header)
        if marker is None:
            out.append(m.group(0))
            pos = m.end()
            continue

        new_body = body

        if marker in REPLACEMENTS:
            # Replace very stale placeholders with modern pointers.
            new_body = REPLACEMENTS[marker]

        if "See also:" not in new_body and "See Also:" not in new_body:
            see = SEE_ALSO[marker]
            new_body = new_body.rstrip() + f"\n\nSee also: {see}"

        if new_body != body:
            changed += 1

        out.append(f"\n{header}~\n{new_body}\n~")
        pos = m.end()

    out.append(helps[pos:])
    new_helps = "".join(out)

    if changed == 0:
        print("No changes needed.")
        return 0

    new_content = content[:hs] + new_helps + content[he:]
    ROM_PATH.write_text(new_content, encoding="latin-1")
    print(f"Updated entries: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
