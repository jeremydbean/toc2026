#!/usr/bin/env python3
"""
Targeted fixer for Times of Chaos area files.
Fixes:
  1. Mob missing ACT_IS_NPC (A) in act_flags
  2. Mob missing IMM_SUMMON (A) and/or IMM_CHARM (B) in imm_flags
  3. Mob AGGRESSIVE (F) without STAY_AREA (G)
  4. British spellings → American spellings
  5. Specific confirmed typos
"""
import os, re, sys

AREA_DIR = "area"
SKIP = {"korzath2old.are", "savedTrinidad.are"}

DRY_RUN = "--dry-run" in sys.argv or "-n" in sys.argv

# ─────────────────────────────────────────────────────────────────────────────
# British → American spelling replacements (apply to description text lines only)
# We apply these to the ENTIRE file content with word-boundary matching.
# ─────────────────────────────────────────────────────────────────────────────
BRIT_FIXES = [
    # case-insensitive, replacement preserves sentence case
    ('colour',   'color'),
    ('colours',  'colors'),
    ('coloured', 'colored'),
    ('colourful','colorful'),
    ('armour',   'armor'),
    ('armours',  'armors'),
    ('armoured', 'armored'),
    ('favour',    'favor'),
    ('favoured',  'favored'),
    ('favourite', 'favorite'),
    ('favourites','favorites'),
    ('favours',   'favors'),
    ('honour',   'honor'),
    ('honoured', 'honored'),
    ('honourable','honorable'),
    ('behaviour','behavior'),
    ('neighbour','neighbor'),
    ('neighbours','neighbors'),
    ('rumour',   'rumor'),
    ('rumours',  'rumors'),
    ('harbour',  'harbor'),
    ('harbours', 'harbors'),
    ('humour',   'humor'),
    ('humo(u?)rous','humorous'),
    ('valour',   'valor'),
    ('valorous', 'valorous'),
    ('sabre',    'saber'),
    ('sabres',   'sabers'),
    ('traveller', 'traveler'),
    ('travellers','travelers'),
    ('armoury',  'armory'),
    ('armouries','armories'),
    ('multicoloured', 'multicolored'),
    ('colourless','colorless'),
    ('discoloured','discolored'),
]

# Simple typos (word-level, both cases handled)
TYPO_FIXES = [
    ('gaurd',       'guard'),
    ('gaurds',      'guards'),
    ('Gaurd',       'Guard'),
    ('Gaurds',      'Guards'),
    ('weild',       'wield'),
    ('weilds',      'wields'),
    ('weilded',     'wielded'),
    ('weilding',    'wielding'),
    ('Weild',       'Wield'),
    ('recieve',     'receive'),
    ('Recieve',     'Receive'),
    ('wierd',       'weird'),
    ('Wierd',       'Weird'),
    ('seperate',    'separate'),
    ('Seperate',    'Separate'),
    ('definately',  'definitely'),
    ('Definately',  'Definitely'),
    ('occured',     'occurred'),
    ('Occured',     'Occurred'),
    ('occurance',   'occurrence'),
    ('Occurance',   'Occurrence'),
    ('untill',      'until'),
    ('Untill',      'Until'),
    ('woudl',       'would'),
    ('coudl',       'could'),
    ('shoudl',      'should'),
    ('wispering',   'whispering'),
    ('Wispering',   'Whispering'),
    ('wisper',      'whisper'),
    ('Wisper',      'Whisper'),
    ('dieing',      'dying'),
    ('Dieing',      'Dying'),
    ('sorceror',    'sorcerer'),
    ('Sorceror',    'Sorcerer'),
    ('thier',       'their'),
    ('Thier',       'Their'),
    ('nad ',        'and '),    # space after to avoid proper-name clashes
    ('creatue ',    'creature '),
    ('creatues ',   'creatures '),
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def add_flag(flags_str, letter):
    """Add a letter to a flag string if not already present."""
    # Treat '0' (no flags) as empty string
    if flags_str == '0':
        flags_str = ''
    if letter in flags_str:
        return flags_str if flags_str else letter, False
    # Insert in alphabetical order (Z goes last)
    result = ''.join(sorted(set(flags_str + letter),
                            key=lambda c: (c == 'Z', c)))
    return result, True


def fix_british(content):
    changes = []
    for brit, amer in BRIT_FIXES:
        # Match word-boundary-sensitive pattern
        pattern = r'\b' + brit + r'\b'
        for m in re.finditer(pattern, content, re.IGNORECASE):
            word = m.group()
            if word[0].isupper():
                replacement = amer[0].upper() + amer[1:]
            else:
                replacement = amer
            if word != replacement:
                changes.append((m.start(), m.end(), replacement))
    # Apply in reverse order
    for start, end, repl in reversed(sorted(changes)):
        content = content[:start] + repl + content[end:]
    return content, len(changes)


def fix_typos(content):
    changes = []
    for wrong, right in TYPO_FIXES:
        pattern = r'\b' + re.escape(wrong) + r'\b'
        for m in re.finditer(pattern, content):
            if m.group() != right:
                changes.append((m.start(), m.end(), right))
    for start, end, repl in reversed(sorted(changes)):
        content = content[:start] + repl + content[end:]
    return content, len(changes)


# ─────────────────────────────────────────────────────────────────────────────
# Mob flag fixer
#
# Mob format after 3 tilde-terminated string fields (keywords, short, long, race):
#   ACT AFF ALIGN S                    (normal)
#   ACT AFF AFF2 ALIGN S               (AFF has Z)
# Then:
#   level hitroll HP MP DM DT
#   ac_p ac_b ac_s ac_e
#   OFF IMM RES VULN                   (normal)
#   OFF OFF2 IMM RES VULN              (OFF has Z)
#   pos1 pos2 sex gold
#   form parts SIZE mat
# ─────────────────────────────────────────────────────────────────────────────

def fix_mob_flags_in_block(vnum, block_lines):
    """
    Given the lines of a single mob block (after the #VNUM line),
    return (modified_lines, list_of_changes).
    """
    changes = []
    lines = list(block_lines)

    # Find the ACT/AFF/ALIGN S line: last token is 'S', first tokens are letter flags
    act_line_idx = None
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        parts = stripped.split()
        if parts and parts[-1] == 'S' and i >= 3:
            # Validate that first part looks like flags (letters only) and
            # there are 4 or 5 parts
            if len(parts) in (4, 5) and re.match(r'^[A-Z0-9]+$', parts[0]):
                act_line_idx = i
                break

    if act_line_idx is None:
        return lines, changes

    act_parts = lines[act_line_idx].split()

    # Determine if AFF has Z overflow
    aff_has_z = 'Z' in act_parts[1] if len(act_parts) > 1 else False
    # positions: 0=ACT, 1=AFF, [2=AFF2 if Z], align=[-2], S=[-1]

    # --- Fix 1: ACT_IS_NPC (A) ---
    act_flags = act_parts[0]
    new_act_flags, changed = add_flag(act_flags, 'A')
    if changed:
        act_parts[0] = new_act_flags
        changes.append(f'added ACT_IS_NPC(A) to act_flags (was {act_flags!r})')

    # --- Fix 2: ACT_STAY_AREA (G) when AGGRESSIVE (F) but not STAY_AREA ---
    if 'F' in act_parts[0] and 'G' not in act_parts[0]:
        new_act_flags2, changed2 = add_flag(act_parts[0], 'G')
        if changed2:
            act_parts[0] = new_act_flags2
            changes.append(f'added ACT_STAY_AREA(G) because mob is AGGRESSIVE(F)')

    # Rebuild act line with same indentation
    indent = len(lines[act_line_idx]) - len(lines[act_line_idx].lstrip())
    lines[act_line_idx] = ' ' * indent + ' '.join(act_parts)

    # --- Find OFF/IMM/RES/VULN line (3 lines after act_line_idx) ---
    off_line_idx = act_line_idx + 3
    if off_line_idx >= len(lines):
        return lines, changes

    off_parts = lines[off_line_idx].split()
    if not off_parts:
        return lines, changes

    # Determine if OFF has Z overflow
    off_has_z = 'Z' in off_parts[0] if off_parts else False
    if off_has_z:
        # OFF OFF2 IMM RES VULN = 5 tokens
        if len(off_parts) >= 5:
            imm_idx = 2
        else:
            return lines, changes
    else:
        # OFF IMM RES VULN = 4 tokens
        if len(off_parts) >= 4:
            imm_idx = 1
        else:
            return lines, changes

    imm_flags = off_parts[imm_idx]
    new_imm = imm_flags

    if 'A' not in new_imm:
        new_imm, _ = add_flag(new_imm, 'A')
        changes.append(f'added IMM_SUMMON(A) to imm_flags (was {imm_flags!r})')

    if 'B' not in new_imm:
        new_imm, _ = add_flag(new_imm, 'B')
        changes.append(f'added IMM_CHARM(B) to imm_flags (was {imm_flags!r})')

    if new_imm != imm_flags:
        off_parts[imm_idx] = new_imm
        indent2 = len(lines[off_line_idx]) - len(lines[off_line_idx].lstrip())
        lines[off_line_idx] = ' ' * indent2 + ' '.join(off_parts)

    return lines, changes


def fix_mob_section(section_text):
    """Fix all mob blocks in a section. Returns (new_text, changes_list)."""
    all_changes = []
    # Split on mob vnum markers, preserving the markers
    parts = re.split(r'^(#[0-9]+)\s*$', section_text, flags=re.MULTILINE)

    result = []
    i = 0
    while i < len(parts):
        token = parts[i]
        if re.match(r'^#[0-9]+$', token.strip()):
            vnum = token.strip()
            body = parts[i+1] if i+1 < len(parts) else ''
            # Split body into lines
            body_lines = body.split('\n')
            fixed_lines, changes = fix_mob_flags_in_block(vnum, body_lines)
            if changes:
                all_changes.append((vnum, changes))
            result.append(token)
            result.append('\n'.join(fixed_lines))
            i += 2
        else:
            result.append(token)
            i += 1

    return ''.join(result), all_changes


def fix_file(fpath):
    with open(fpath, encoding='latin-1') as f:
        original = f.read()

    content = original
    report = []

    # British spellings
    content, n = fix_british(content)
    if n:
        report.append(f'  {n} British spelling(s) fixed')

    # Typos
    content, n = fix_typos(content)
    if n:
        report.append(f'  {n} typo(s) fixed')

    # Mob flag fixes
    # Find #MOBILES section
    mob_match = re.search(r'^#MOBILES\s*\n', content, re.MULTILINE)
    end_match = re.search(r'^#0\s*\n', content[mob_match.end():] if mob_match else '', re.MULTILINE) if mob_match else None

    if mob_match and end_match:
        mob_start = mob_match.end()
        mob_end = mob_start + end_match.start()
        mob_section = content[mob_start:mob_end]

        fixed_mob, mob_changes = fix_mob_section(mob_section)
        if mob_changes:
            for vnum, clist in mob_changes:
                for c in clist:
                    report.append(f'  mob {vnum}: {c}')
            content = content[:mob_start] + fixed_mob + content[mob_end:]

    if content != original:
        if not DRY_RUN:
            with open(fpath, 'w', encoding='latin-1') as f:
                f.write(content)
        return report
    return []


def main():
    total_files = 0
    total_changed = 0

    for fname in sorted(os.listdir(AREA_DIR)):
        if not fname.endswith('.are') or fname in SKIP:
            continue
        fpath = os.path.join(AREA_DIR, fname)
        changes = fix_file(fpath)
        if changes:
            print(f"\n{fname}:")
            for line in changes:
                print(line)
            total_changed += 1
        total_files += 1

    mode = " (DRY RUN)" if DRY_RUN else ""
    print(f"\n{'='*60}")
    print(f"Processed {total_files} files, modified {total_changed}{mode}")


if __name__ == '__main__':
    main()
