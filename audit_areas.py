#!/usr/bin/env python3
"""
Comprehensive area file auditor for Times of Chaos MUD.
Checks: typos, structural issues, mob/object/reset inconsistencies.
"""
import os, re, sys
from collections import defaultdict

AREA_DIR = "area"
SKIP = {"korzath2old.are", "savedTrinidad.are"}
REPORT = defaultdict(list)

# ─────────────────────────────────────────────────────────────────────────────
# Known typos: (pattern, replacement, context_note)
# Patterns already fixed in previous audit passes are marked # DONE
# ─────────────────────────────────────────────────────────────────────────────
TYPOS = [
    # a/an errors – new patterns not previously covered
    (r'\ba elf\b', 'an elf', 'a/an'),
    (r'\ba undead\b', 'an undead', 'a/an'),
    (r'\ba elven\b', 'an elven', 'a/an'),
    (r'\ba ancient\b', 'an ancient', 'a/an'),
    (r'\ba eerie\b', 'an eerie', 'a/an'),
    (r'\ba enormous\b', 'an enormous', 'a/an'),
    (r'\ba orc\b', 'an orc', 'a/an'),
    (r'\ba orcish\b', 'an orcish', 'a/an'),
    (r'\ba odd\b', 'an odd', 'a/an'),
    (r'\ba opening\b', 'an opening', 'a/an'),
    (r'\ba overwhelming\b', 'an overwhelming', 'a/an'),
    (r'\ba ornate\b', 'an ornate', 'a/an'),
    (r'\ban sword\b', 'a sword', 'a/an'),
    (r'\ban dagger\b', 'a dagger', 'a/an'),
    (r'\ban spear\b', 'a spear', 'a/an'),
    (r'\ban staff\b', 'a staff', 'a/an'),
    (r'\ban shield\b', 'a shield', 'a/an'),
    (r'\ban blade\b', 'a blade', 'a/an'),
    (r'\ban bow\b', 'a bow', 'a/an'),
    (r'\ban cloak\b', 'a cloak', 'a/an'),
    (r'\ban scroll\b', 'a scroll', 'a/an'),
    (r'\ban potion\b', 'a potion', 'a/an'),
    (r'\ban flask\b', 'a flask', 'a/an'),
    (r'\ban wand\b', 'a wand', 'a/an'),
    (r'\ban stone\b', 'a stone', 'a/an'),
    (r'\ban ring\b', 'a ring', 'a/an'),
    (r'\ban gauntlet\b', 'a gauntlet', 'a/an'),
    (r'\ban boot\b', 'a boot', 'a/an'),
    (r'\ban belt\b', 'a belt', 'a/an'),
    (r'\ban key\b', 'a key', 'a/an'),
    (r'\ban crystal\b', 'a crystal', 'a/an'),
    (r'\ban gem\b', 'a gem', 'a/an'),
    # Double spaces in descriptions (non-tilde lines)
    # Misspellings
    (r'\brecieve\b', 'receive', 'spelling'),
    (r'\bRecieve\b', 'Receive', 'spelling'),
    (r'\bbelive\b', 'believe', 'spelling'),
    (r'\bBelive\b', 'Believe', 'spelling'),
    (r'\bwierd\b', 'weird', 'spelling'),
    (r'\bWierd\b', 'Weird', 'spelling'),
    (r'\bquite\b(?= large|\s+big|\s+tall)', None, 'check-quite-vs-quiet'),  # flag only
    (r'\bquiet\b(?= large|\s+big|\s+tall)', None, 'check-quiet-vs-quite'),
    (r'\bseperate\b', 'separate', 'spelling'),
    (r'\bSeperate\b', 'Separate', 'spelling'),
    (r'\bocurr', 'occurr', 'spelling'),
    (r'\boccured\b', 'occurred', 'spelling'),
    (r'\boccured\b', 'occurred', 'spelling'),
    (r'\boccurance\b', 'occurrence', 'spelling'),
    (r'\bdefinately\b', 'definitely', 'spelling'),
    (r'\bDefinately\b', 'Definitely', 'spelling'),
    (r'\bexistance\b', 'existence', 'spelling'),
    (r'\bExistance\b', 'Existence', 'spelling'),
    (r'\boccasionaly\b', 'occasionally', 'spelling'),
    (r'\boccasionally\b', None, None),  # correct, skip
    (r'\bthroughout\b', None, None),
    (r'\bgaurds?\b', 'guard(s)', 'spelling'),  # gaurd -> guard
    (r'\bgaurd\b', 'guard', 'spelling'),
    (r'\bGaurd\b', 'Guard', 'spelling'),
    (r'\bdestroied\b', 'destroyed', 'spelling'),
    (r'\brecognize\b', None, None),
    (r'\brecognise\b', 'recognize', 'spelling'),
    (r'\brecognised\b', 'recognized', 'spelling'),
    (r'\btraveler\b', None, None),
    (r'\btraveller\b', 'traveler', 'spelling'),
    (r'\bweilds?\b', 'wields', 'spelling'),  # weild -> wield
    (r'\bweilded\b', 'wielded', 'spelling'),
    (r'\bweilding\b', 'wielding', 'spelling'),
    (r'\bweild\b', 'wield', 'spelling'),
    (r'\bWeild\b', 'Wield', 'spelling'),
    (r'\buntill\b', 'until', 'spelling'),
    (r'\bUntill\b', 'Until', 'spelling'),
    (r'\bweapon\'s\b', "weapon's", None),  # OK
    (r'\barmour\b', 'armor', 'spelling'),
    (r'\bArmour\b', 'Armor', 'spelling'),
    (r'\bfavour\b', 'favor', 'spelling'),
    (r'\bFavour\b', 'Favor', 'spelling'),
    (r'\bhonour\b', 'honor', 'spelling'),
    (r'\bHonour\b', 'Honor', 'spelling'),
    (r'\bcolour\b', 'color', 'spelling'),
    (r'\bColour\b', 'Color', 'spelling'),
    (r'\bbehaviour\b', 'behavior', 'spelling'),
    (r'\bBehaviour\b', 'Behavior', 'spelling'),
    (r'\bneighbour\b', 'neighbor', 'spelling'),
    (r'\brumour\b', 'rumor', 'spelling'),
    (r'\bharbour\b', 'harbor', 'spelling'),
    (r'\bhumour\b', 'humor', 'spelling'),
    (r'\bvalour\b', 'valor', 'spelling'),
    (r'\bsabre\b', 'saber', 'spelling'),
    (r'teh\b', 'the', 'spelling'),
    (r'\bnad\b', 'and', 'spelling'),
    (r'\bthier\b', 'their', 'spelling'),
    (r'\bThier\b', 'Their', 'spelling'),
    (r'\bWether\b', 'Whether', 'spelling'),
    (r'\bwether\b', 'whether', 'spelling'),
    (r'\bwoudl\b', 'would', 'spelling'),
    (r'\bcoudl\b', 'could', 'spelling'),
    (r'\bshoudl\b', 'should', 'spelling'),
    (r'\bmagitian\b', 'magician', 'spelling'),
    (r'\bwarroir\b', 'warrior', 'spelling'),
    (r'\bsorcerer\b', None, None),  # correct
    (r'\bsorceror\b', 'sorcerer', 'spelling'),
    (r'\bSorceror\b', 'Sorcerer', 'spelling'),
    (r'\brythm\b', 'rhythm', 'spelling'),
    (r'\brhthym\b', 'rhythm', 'spelling'),
    (r'\bcreatue\b', 'creature', 'spelling'),
    (r'\bCreatue\b', 'Creature', 'spelling'),
    (r'\bcreatues\b', 'creatures', 'spelling'),
    (r'\bsurrond\b', 'surround', 'spelling'),
    (r'\bsurronds\b', 'surrounds', 'spelling'),
    (r'\bsorrounded\b', 'surrounded', 'spelling'),
    (r'\bsurrounding\b', None, None),
    (r'\bcommited\b', 'committed', 'spelling'),
    (r'\bcommiting\b', 'committing', 'spelling'),
    (r'\boccasion\b', None, None),
    (r'\bwispering\b', 'whispering', 'spelling'),
    (r'\bwhisper\b', None, None),
    (r'\bwisper\b', 'whisper', 'spelling'),
    (r'\bWisper\b', 'Whisper', 'spelling'),
    (r'\bdieing\b', 'dying', 'spelling'),
    (r'\blightning\b', None, None),
    # NOTE: 'lighting' (present participle of 'light') is correct English
    # and is NOT a misspelling of 'lightning'. Removed that check.
    # double-word  
    (r'\bthe the\b', 'the', 'double-word'),
    (r'\band and\b', 'and', 'double-word'),
    (r'\bof of\b', 'of', 'double-word'),
    (r'\bin in\b', 'in', 'double-word'),
    (r'\bis is\b', 'is', 'double-word'),
    (r'\ba a\b', 'a', 'double-word'),
    (r'\bto to\b', 'to', 'double-word'),
    (r'\bit it\b', 'it', 'double-word'),
    (r'\bthat that\b', 'that', 'double-word'),
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def iter_areas():
    for fname in sorted(os.listdir(AREA_DIR)):
        if not fname.endswith('.are') or fname in SKIP:
            continue
        yield fname, os.path.join(AREA_DIR, fname)


def parse_sections(content):
    """Split area content into named sections."""
    sections = {}
    # Find all section headers
    pattern = re.compile(r'^(#AREA|#HELPS|#MOBILES|#OBJECTS|#ROOMS|#RESETS|#SHOPS|#SPECIALS)', re.MULTILINE)
    matches = list(pattern.finditer(content))
    for i, m in enumerate(matches):
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        sections[m.group(1)] = content[m.start():end]
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# Text / typo checks (description lines only – skip tilde-only and data lines)
# ─────────────────────────────────────────────────────────────────────────────
def check_typos(fname, content):
    issues = []
    for pattern, fix, category in TYPOS:
        if fix is None and category is None:
            continue  # correct word, skip
        for m in re.finditer(pattern, content, re.IGNORECASE):
            # find the line number
            line_no = content[:m.start()].count('\n') + 1
            snippet = content[max(0, m.start()-30):m.end()+30].replace('\n', ' ').strip()
            if fix and category not in ('check-quite-vs-quiet', 'check-quiet-vs-quite'):
                issues.append((line_no, category, f"'{m.group()}' → '{fix}': ...{snippet}..."))
            else:
                issues.append((line_no, 'review', f"check '{m.group()}': ...{snippet}..."))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Parse individual mob blocks
# ─────────────────────────────────────────────────────────────────────────────
def parse_mobs(section_text):
    """Yield (vnum_str, lines_list) for each mob block."""
    blocks = re.split(r'^(#[A-Z0-9]+)', section_text, flags=re.MULTILINE)
    i = 0
    while i < len(blocks):
        if blocks[i].startswith('#') and blocks[i] not in ('#MOBILES', '#0'):
            vnum = blocks[i].strip()
            body = blocks[i+1] if i+1 < len(blocks) else ''
            yield vnum, body.strip().splitlines()
            i += 2
        else:
            i += 1


def check_mobs(fname, section):
    issues = []
    for vnum, lines in parse_mobs(section):
        if len(lines) < 10:
            issues.append((vnum, 'format', f'mob block too short ({len(lines)} lines) – possibly malformed'))
            continue

        # Find the "ACT AFF ALIGN S|M" line – ends with literal " S" or " M"
        # When ACT or AFF flags include Z (FLAGS2 overflow), there's an extra token
        # Formats:
        #   ACT AFF ALIGN S
        #   ACT AFF_FLAGS2 AFF ALIGN S   (ACT has Z)
        #   ACT AFF AFF_FLAGS2 ALIGN S   (AFF has Z)
        #   ACT ACT_FLAGS2 AFF ALIGN S   (ACT has Z)
        act_line = None
        act_idx = None
        for i, l in enumerate(lines):
            stripped = l.rstrip()
            if (stripped.endswith(' S') or stripped.endswith(' M')) and i >= 4:
                act_line = l.strip()
                act_idx = i
                break

        if act_line is None:
            issues.append((vnum, 'format', 'cannot find ACT/AFF/ALIGN S line'))
            continue

        parts = act_line.split()
        if len(parts) < 3:
            issues.append((vnum, 'format', f'ACT/AFF/ALIGN S line malformed: {act_line!r}'))
            continue

        # Parse flexibly: last token is S/M, second-to-last is alignment (int),
        # first token is act_flags. If alignment isn't parseable at parts[-2],
        # this is a malformed line.
        mob_type = parts[-1]   # S or M
        try:
            alignment = int(parts[-2])
        except ValueError:
            issues.append((vnum, 'format', f'alignment not int in: {act_line!r}'))
            continue

        act_flags = parts[0]
        # AFF flags: token [1], but if ACT has Z there may be an ACT_FLAGS2 token
        # The second-to-last token is alignment, the one before that is AFF (or AFF_FLAGS2)
        # We only need act_flags and aff_flags for our checks
        # aff_flags is the last alphabetic token before the alignment
        aff_index = len(parts) - 3  # typically parts[1], but could be parts[2] for Z-overflow
        aff_flags = parts[1] if aff_index >= 1 else '0'

        # ACT checks
        if 'A' not in act_flags:
            issues.append((vnum, 'mob-flags', f'missing ACT_IS_NPC (A) in act_flags: {act_flags!r}'))

        if 'F' in act_flags and 'G' not in act_flags:
            issues.append((vnum, 'mob-flags', 'AGGRESSIVE (F) without STAY_AREA (G) – mob will wander across zone boundaries'))

        if 'J' in act_flags:
            issues.append((vnum, 'permission', 'ACT_TRAIN (J) set – requires IMP permission'))

        if 'K' in act_flags:
            issues.append((vnum, 'permission', 'ACT_PRACTICE (K) set – requires IMP permission'))

        # AFF sanity
        if 'X' in aff_flags:
            issues.append((vnum, 'mob-flags', 'AFF_PLAGUE (X) set – mob will actively spread plague to players'))

        # Alignment vs anti-evil/good flags (check AFF flags for rough guide)
        if alignment > 500 and 'J' in aff_flags:  # very good but protect (used for evil) may be odd
            pass  # not certain enough to flag

        # Find OFF/IMM/RES/VULN line (line after several stat lines after act_line)
        # Typically: act_line+1=level line, +2=ac line, +3=off/imm/res/vuln
        if act_idx + 3 < len(lines):
            off_line = lines[act_idx + 3]
            oparts = off_line.strip().split()
            if len(oparts) >= 2:
                imm_flags = oparts[1]
                if 'A' not in imm_flags and 'B' not in imm_flags:
                    issues.append((vnum, 'mob-flags', f'missing IMM_SUMMON (A) and IMM_CHARM (B) in imm_flags: {imm_flags!r}'))
                elif 'A' not in imm_flags:
                    issues.append((vnum, 'mob-flags', f'missing IMM_SUMMON (A) in imm_flags: {imm_flags!r}'))
                elif 'B' not in imm_flags:
                    issues.append((vnum, 'mob-flags', f'missing IMM_CHARM (B) in imm_flags: {imm_flags!r}'))

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Parse individual object blocks
# ─────────────────────────────────────────────────────────────────────────────
def parse_objects(section_text):
    blocks = re.split(r'^(#[A-Z0-9]+)', section_text, flags=re.MULTILINE)
    i = 0
    while i < len(blocks):
        if blocks[i].startswith('#') and blocks[i] not in ('#OBJECTS', '#0'):
            vnum = blocks[i].strip()
            body = blocks[i+1] if i+1 < len(blocks) else ''
            yield vnum, body.strip().splitlines()
            i += 2
        else:
            i += 1


def check_objects(fname, section):
    issues = []
    for vnum, lines in parse_objects(section):
        if len(lines) < 6:
            issues.append((vnum, 'format', f'object block too short ({len(lines)} lines)'))
            continue

        # Skip tilde-ended strings to find the type/flags line
        # Lines: 0=keywords~ 1=shortname~ 2=longdesc~ 3=material~ 4=type flags flags2 wearflags
        # But some fields may span multiple lines before the tilde

        # Collect tilde-terminated fields
        idx = 0
        tilde_count = 0
        type_line_idx = None
        for i, l in enumerate(lines):
            if l.rstrip().endswith('~'):
                tilde_count += 1
                if tilde_count == 4:  # after keywords, short, long, material
                    type_line_idx = i + 1
                    break

        if type_line_idx is None or type_line_idx >= len(lines):
            issues.append((vnum, 'format', 'cannot find type/flags line'))
            continue

        # Skip blank lines between material~ and type/flags line
        while type_line_idx < len(lines) and lines[type_line_idx].strip() == '':
            type_line_idx += 1
        if type_line_idx >= len(lines):
            issues.append((vnum, 'format', 'cannot find type/flags line after material'))
            continue

        type_line = lines[type_line_idx].strip()
        tparts = type_line.split()
        if len(tparts) < 2:
            issues.append((vnum, 'format', f'type/flags line too short: {type_line!r}'))
            continue

        try:
            item_type = int(tparts[0])
        except ValueError:
            issues.append((vnum, 'format', f'item_type not int: {tparts[0]!r}'))
            continue

        item_flags = tparts[1] if len(tparts) > 1 else '0'
        # FLAGS2 token (Z in extra_flags) is optional — only present when Z is set
        if 'Z' in item_flags:
            item_flags2 = tparts[2] if len(tparts) > 2 else '0'
            wear_flags = tparts[3] if len(tparts) > 3 else '0'
        else:
            item_flags2 = '0'
            wear_flags = tparts[2] if len(tparts) > 2 else '0'

        # Values line
        val_line_idx = type_line_idx + 1
        if val_line_idx >= len(lines):
            continue
        val_line = lines[val_line_idx].strip()
        vparts = val_line.split()

        # Level/weight/cost/condition line
        lvl_line_idx = val_line_idx + 1
        if lvl_line_idx < len(lines):
            lvl_line = lines[lvl_line_idx].strip()
            lparts = lvl_line.split()
        else:
            lparts = []

        # --- WEAPON checks ---
        if item_type == 5:
            # Must have wield wear flag N
            if 'N' not in wear_flags:
                issues.append((vnum, 'object-flags', f'WEAPON (type 5) missing WIELD wear flag (N) in wear_flags: {wear_flags!r}'))
            # Must have TAKE flag A
            if 'A' not in wear_flags:
                issues.append((vnum, 'object-flags', f'WEAPON (type 5) missing TAKE flag (A) in wear_flags: {wear_flags!r}'))
            # Weapon class must be 0-9
            if len(vparts) >= 1:
                try:
                    wclass = int(vparts[0])
                    if wclass < 0 or wclass > 9:
                        issues.append((vnum, 'object-values', f'invalid weapon class {wclass} (must be 0-9)'))
                except ValueError:
                    issues.append((vnum, 'object-values', f'weapon class not int: {vparts[0]!r}'))
            # Damage type must be 0-32
            if len(vparts) >= 4:
                try:
                    dtype = int(vparts[3])
                    if dtype < 0 or dtype > 32:
                        issues.append((vnum, 'object-values', f'invalid damage type {dtype} (must be 0-32)'))
                except ValueError:
                    pass

        # --- ARMOR checks ---
        if item_type == 9:
            if 'A' not in wear_flags:
                issues.append((vnum, 'object-flags', f'ARMOR (type 9) missing TAKE flag (A) in wear_flags: {wear_flags!r}'))
            # Should have at least one wear location (not just A)
            wear_locs = [c for c in wear_flags if c not in ('0', 'A', 'N', 'O', 'P', 'Z')]
            if not wear_locs:
                issues.append((vnum, 'object-flags', f'ARMOR (type 9) has no wear location flags beyond TAKE: {wear_flags!r}'))

        # --- CLOTHING checks ---
        if item_type == 11:
            if 'A' not in wear_flags:
                issues.append((vnum, 'object-flags', f'CLOTHING (type 11) missing TAKE flag (A)'))

        # --- CONTAINER checks ---
        if item_type == 15:
            if len(vparts) >= 2:
                try:
                    cont_flags = int(vparts[1])
                    if cont_flags < 0 or cont_flags > 31:
                        issues.append((vnum, 'object-values', f'container flags {cont_flags} out of range (0-31)'))
                except ValueError:
                    pass

        # --- SCROLL/POTION/PILL/WAND/STAFF checks ---
        if item_type in (2, 3, 4, 10, 26):
            if len(vparts) >= 2:
                try:
                    sn1 = int(vparts[1])
                    if sn1 < 0:
                        issues.append((vnum, 'object-values', f'negative spell slot: {sn1}'))
                except ValueError:
                    pass

        # --- TAKE flag required for non-furniture items ---
        if item_type not in (12, 13, 23, 25) and 'A' not in wear_flags and wear_flags != '0':
            issues.append((vnum, 'object-flags', f'item type {item_type} may be missing TAKE flag (A); wear_flags={wear_flags!r}'))

        # --- Apply type bounds check ---
        # Scan remaining lines for 'A' apply blocks
        valid_applies = set(range(0, 26))  # 0=NONE through 25=IMMUNITY (from merc.h)
        for i2 in range(type_line_idx + 2, len(lines)):
            al = lines[i2].strip()
            if al == 'A':
                if i2 + 1 < len(lines):
                    aparts = lines[i2+1].strip().split()
                    if len(aparts) >= 2:
                        try:
                            atype = int(aparts[0])
                            aval = int(aparts[1])
                            if atype not in valid_applies:
                                issues.append((vnum, 'object-values', f'unknown apply type {atype} (valid: {sorted(valid_applies)})'))
                            # Flag suspiciously large bonuses
                            if atype in (18, 19) and aval > 15:
                                issues.append((vnum, 'balance', f'apply type {atype} value {aval} is very high (>15 hitroll/damroll)'))
                            if atype in (1,2,3,4,5) and aval > 6:
                                issues.append((vnum, 'balance', f'apply type {atype} (stat) value {aval} is very high (>6)'))
                            if atype == 13 and aval > 500:
                                issues.append((vnum, 'balance', f'apply HIT {aval} is very high (>500)'))
                        except ValueError:
                            pass

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Check resets
# ─────────────────────────────────────────────────────────────────────────────
def check_resets(fname, section):
    issues = []
    valid_wear_locs = set(range(-1, 18))
    for line_no, line in enumerate(section.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('*') or line == 'S':
            continue
        parts = line.split()
        if not parts:
            continue
        cmd = parts[0].upper()

        if cmd == 'E':
            if len(parts) >= 5:
                try:
                    wear_loc = int(parts[4])
                    if wear_loc not in valid_wear_locs:
                        issues.append((line_no, 'reset', f'E reset invalid wear_loc {wear_loc}: {line!r}'))
                except ValueError:
                    issues.append((line_no, 'reset', f'E reset non-int wear_loc: {line!r}'))
            else:
                issues.append((line_no, 'reset', f'E reset too few fields: {line!r}'))

        elif cmd == 'D':
            if len(parts) >= 5:
                try:
                    door_dir = int(parts[3])
                    door_state = int(parts[4])
                    if door_dir < 0 or door_dir > 9:
                        issues.append((line_no, 'reset', f'D reset invalid door direction {door_dir}: {line!r}'))
                    if door_state < 0 or door_state > 5:
                        issues.append((line_no, 'reset', f'D reset invalid door state {door_state}: {line!r}'))
                except ValueError:
                    pass

        elif cmd == 'M':
            if len(parts) < 5:
                issues.append((line_no, 'reset', f'M reset too few fields: {line!r}'))

        elif cmd == 'O':
            if len(parts) < 5:
                issues.append((line_no, 'reset', f'O reset too few fields: {line!r}'))

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Check shops
# ─────────────────────────────────────────────────────────────────────────────
def check_shops(fname, section):
    issues = []
    for line_no, line in enumerate(section.splitlines(), 1):
        line = line.split(';')[0].strip()  # strip comments
        if not line or line in ('#SHOPS', '0'):
            continue
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            buy_pct = int(parts[7])
            sell_pct = int(parts[8])
            open_hr = int(parts[9])
            close_hr = int(parts[10]) if len(parts) > 10 else None
            if buy_pct < 100:
                issues.append((line_no, 'shop', f'buy% {buy_pct} < 100 (players buy cheaper than list price): {line!r}'))
            if sell_pct > 100:
                issues.append((line_no, 'shop', f'sell% {sell_pct} > 100 (players sell for more than list price): {line!r}'))
            if open_hr < 0 or open_hr > 23:
                issues.append((line_no, 'shop', f'open_hr {open_hr} out of range 0-23'))
            if close_hr is not None and (close_hr < 0 or close_hr > 23):
                issues.append((line_no, 'shop', f'close_hr {close_hr} out of range 0-23'))
        except (ValueError, IndexError):
            pass
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Check room format (basic: every room should end with S)
# ─────────────────────────────────────────────────────────────────────────────
def check_rooms(fname, section):
    issues = []
    # Each room block between #VNUM and the next #VNUM (or #0) must end with a line that is just 'S'
    blocks = re.split(r'^(#[A-Z0-9]+)', section, flags=re.MULTILINE)
    i = 0
    while i < len(blocks):
        if blocks[i].startswith('#') and blocks[i] not in ('#ROOMS', '#0'):
            vnum = blocks[i].strip()
            body = blocks[i+1] if i+1 < len(blocks) else ''
            room_lines = [l.strip() for l in body.strip().splitlines()]
            # Last non-empty line should be 'S'
            non_empty = [l for l in room_lines if l]
            if non_empty and non_empty[-1] != 'S':
                issues.append((vnum, 'format', f'room does not end with S; last line: {non_empty[-1]!r}'))
            i += 2
        else:
            i += 1
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    total_files = 0
    total_issues = 0

    for fname, fpath in iter_areas():
        with open(fpath, encoding='latin-1') as f:
            content = f.read()

        file_issues = []

        # Typo scan
        for line_no, category, msg in check_typos(fname, content):
            file_issues.append((line_no, category, msg))

        sections = parse_sections(content)

        # Mob checks
        if '#MOBILES' in sections:
            for vnum, category, msg in check_mobs(fname, sections['#MOBILES']):
                file_issues.append((vnum, category, msg))

        # Object checks
        if '#OBJECTS' in sections:
            for vnum, category, msg in check_objects(fname, sections['#OBJECTS']):
                file_issues.append((vnum, category, msg))

        # Reset checks
        if '#RESETS' in sections:
            for line_no, category, msg in check_resets(fname, sections['#RESETS']):
                file_issues.append((line_no, category, msg))

        # Shop checks
        if '#SHOPS' in sections:
            for line_no, category, msg in check_shops(fname, sections['#SHOPS']):
                file_issues.append((line_no, category, msg))

        # Room checks
        if '#ROOMS' in sections:
            for vnum, category, msg in check_rooms(fname, sections['#ROOMS']):
                file_issues.append((vnum, category, msg))

        if file_issues:
            REPORT[fname] = file_issues
            total_issues += len(file_issues)

        total_files += 1

    # Output report
    print(f"\n=== AREA AUDIT REPORT — {total_files} files, {total_issues} issues ===\n")
    for fname in sorted(REPORT.keys()):
        issues = REPORT[fname]
        print(f"--- {fname} ({len(issues)} issues) ---")
        for ref, cat, msg in issues:
            print(f"  [{cat}] {ref}: {msg}")
        print()

    print(f"Total: {total_issues} issues across {len(REPORT)} files.")


if __name__ == '__main__':
    main()
