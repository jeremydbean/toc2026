#!/usr/bin/env python3
"""
Batch fix script for .are file typos and grammar errors.
Uses latin-1 encoding required for ROM area files.
Run from the toc2026-1 root directory.
"""

import os

AREA_DIR = os.path.join(os.path.dirname(__file__), 'area')

def fix_file(filename, replacements, encoding='latin-1'):
    """Apply list of (old, new) replacements to a file."""
    filepath = os.path.join(AREA_DIR, filename)
    with open(filepath, encoding=encoding) as f:
        text = f.read()
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    if text != original:
        with open(filepath, 'w', encoding=encoding) as f:
            f.write(text)
        count = sum(original.count(old) for old, _ in replacements)
        print(f'  {filename}: {count} replacements applied')
    else:
        print(f'  {filename}: no changes (patterns not found or already correct)')
    return text != original


def fix_file_binary(filename, replacements):
    """Apply list of (bytes_old, bytes_new) replacements to a binary file (for \\r\\r\\n files)."""
    filepath = os.path.join(AREA_DIR, filename)
    with open(filepath, 'rb') as f:
        data = f.read()
    original = data
    for old, new in replacements:
        data = data.replace(old, new)
    if data != original:
        with open(filepath, 'wb') as f:
            f.write(data)
        print(f'  {filename}: binary replacements applied')
    else:
        print(f'  {filename}: no changes (binary patterns not found)')
    return data != original


print('Applying typo/grammar fixes to .are files...')
print()

# ---- ag.are ----
# 7 A->An article fixes + 62 "to dark to tell" -> "too dark to tell"
fix_file('ag.are', [
    # A -> An article corrections
    ('A odd looking animal like dagger lies here.~',
     'An odd looking animal-like dagger lies here.~'),
    ('A odd looking plate with a strap lies humming in the dirt.~',
     'An odd looking plate with a strap lies humming in the dirt.~'),
    ('A evil looking dagger lies in the dust.~',
     'An evil looking dagger lies in the dust.~'),
    ('A odd looking metal rod lies on the floor.~',
     'An odd looking metal rod lies on the floor.~'),
    ('A odd looking key lies on the floor.~',
     'An odd looking key lies on the floor.~'),
    ('A odd looking ring lies in the dirt.~',
     'An odd looking ring lies in the dirt.~'),
    # "to dark to tell" exit descriptions -> "too dark to tell"
    ('\nto dark to tell\n', '\ntoo dark to tell\n'),
    ('D3 to dark to tell', 'D3 too dark to tell'),
])

# ---- camelot.are ----
fix_file('camelot.are', [
    ('HONOR SEPERATES THE KNIGHT', 'HONOR SEPARATES THE KNIGHT'),
])

# ---- dresden.are ----
fix_file('dresden.are', [
    ('in you travels.  May', 'in your travels.  May'),
    ('you you see a wonderful', 'you see a wonderful'),
    ('Grunar the Dwarf Proprieter', 'Grunar the Dwarf Proprietor'),
    ('Broad steps leading up the the University of Magic.',
     'Broad steps leading up the University of Magic.'),
    ('God of of Secrecy and Stealth', 'God of Secrecy and Stealth'),
    ('you see the the slums section', 'you see the slums section'),
])

# ---- dresden_halloween.are ----
fix_file('dresden_halloween.are', [
    ('you you see a wonderful', 'you see a wonderful'),
    ('Broad steps leading up the the University of Magic.',
     'Broad steps leading up the University of Magic.'),
    ('God of of Secrecy and Stealth', 'God of Secrecy and Stealth'),
    ('you see the the slums section', 'you see the slums section'),
])

# ---- dresden_xmas.are ----
fix_file('dresden_xmas.are', [
    ('you you see a wonderful', 'you see a wonderful'),
    ('Broad steps leading up the the University of Magic.',
     'Broad steps leading up the University of Magic.'),
    ('God of of Secrecy and Stealth', 'God of Secrecy and Stealth'),
    ('you see the the slums section', 'you see the slums section'),
])

# ---- hell.are ----
fix_file('hell.are', [
    ('Thier deaths seem like minutes', 'Their deaths seem like minutes'),
])

# ---- highland.are ----
fix_file('highland.are', [
    ('continues uphill. Tthe\nterrain is also', 'continues uphill. The\nterrain is also'),
])

# ---- horde.are ----
fix_file('horde.are', [
    ('A ancient dragon skull hangs', 'An ancient dragon skull hangs'),
])

# ---- kerofk.are ----
fix_file('kerofk.are', [
    ('a old looking man', 'an old looking man'),
])

# ---- korzath2.are ----
fix_file('korzath2.are', [
    ('see the the source', 'see the source'),
])

# ---- mid_hall.are ----
fix_file('mid_hall.are', [
    ('The the chain reaches', 'The chain reaches'),
])

# ---- mid_ruin.are ----
fix_file('mid_ruin.are', [
    ('lined up on thier sides as a form', 'lined up on their sides as a form'),
])

# ---- midennir_halloween.are (binary: has \r\r\n line endings) ----
fix_file_binary('midennir_halloween.are', [
    (b'near the the barren wastes', b'near the barren wastes'),
])

# ---- moria.are ----
fix_file('moria.are', [
    ('A ancient heavy oak staff is here.~', 'An ancient heavy oak staff is here.~'),
])

# ---- mountain.are ----
fix_file('mountain.are', [
    ('A Elite Guard~', 'An Elite Guard~'),
    ('marks this as a Elite trooper', 'marks this as an Elite trooper'),
])

# ---- oldthalo.are ----
fix_file('oldthalo.are', [
    ('A odd clear stone lies at your feet.~', 'An odd clear stone lies at your feet.~'),
])

# ---- prison.are ----
fix_file('prison.are', [
    ('used for seperating the head', 'used for separating the head'),
])

# ---- pyramid.are ----
# 20x pharoah->pharaoh, 17x pharoahs->pharaohs, 1x Pharoah, 1x Pharoahs, + "you you" punctuation
fix_file('pyramid.are', [
    # Plurals first to avoid double-replacement
    ('pharoahs', 'pharaohs'),
    ('Pharoahs', 'Pharaohs'),
    ('pharoah', 'pharaoh'),
    ('Pharoah', 'Pharaoh'),
    # "Above you you see" -> "Above you, you see"
    ('Above you you see tiny beams', 'Above you, you see tiny beams'),
])

# ---- redfern.are ----
fix_file('redfern.are', [
    ('anchored to the the tower of some citadel', 'anchored to the tower of some citadel'),
])

# ---- school.are ----
fix_file('school.are', [
    ('will be the the mob factory', 'will be the mob factory'),
])

# ---- sewer.are ----
fix_file('sewer.are', [
    ("there's a ENORMOUS quadruple", "there's an ENORMOUS quadruple"),
    ('This looks like a evil dragon', 'This looks like an evil dragon'),
])

# ---- smurf.are ----
fix_file('smurf.are', [
    ('Road continues to to the south and west', 'Road continues to the south and west'),
])

# ---- uargo.are ----
fix_file('uargo.are', [
    ('With little difficutly you work', 'With little difficulty you work'),
    ('grey scenery of of Mt. Ulmo', 'grey scenery of Mt. Ulmo'),
    ('there are definately the', 'there are definitely the'),
])

# ---- ultima.are ----
fix_file('ultima.are', [
    ('The shepherd is a a patient old man', 'The shepherd is a patient old man'),
    ('Through the his wrinkled face', 'Through his wrinkled face'),
    ('but in the his spare time', 'but in his spare time'),
    ('There is a a glint of gold.', 'There is a glint of gold.'),
])

# ---- valhalla.are ----
fix_file('valhalla.are', [
    ('you be carefull not to anger', 'you be careful not to anger'),
    ('thier natural habitats', 'their natural habitats'),
])

# ---- wyvern.are ----
fix_file('wyvern.are', [
    ('at the entrance to dark forest comprised', 'at the entrance to the dark forest comprised'),
])

print()
print('Done. Verify with: make 2>&1 | grep -iE "error|warning"')
