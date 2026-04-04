#!/usr/bin/env python3
"""Scan all .are files for actual typos and show exact context."""
import os
import re

arefiles = sorted([f for f in os.listdir('area') if f.endswith('.are')])

# Patterns to search for: (regex_pattern, description)
patterns = [
    # Clear misspellings
    (r'\beminat(?!e)', 'eminates→emanates', lambda m: 'emanates' in m.string[m.start()-5:m.end()+10] and m.string[m.start()-5:m.end()+10]),
    (r'\beminates\b', 'eminates→emanates'),
    (r'\bdissapear', 'dissapear→disappear'),
    (r'\bpharoah', 'pharoah→pharaoh'),
    (r'\bcompletly\b', 'completly→completely'),
    (r'\brecieve\b', 'recieve→receive'),
    (r'\bthier\b', 'thier→their'),
    (r'\bposession\b', 'posession→possession'),
    (r'\bencounterd\b', 'encounterd→encountered'),
    (r'\baccomodat', 'accomodate→accommodate'),
    (r'\boccassion', 'occassion→occasional'),
    (r'\bwierd\b', 'wierd→weird'),
    (r'\boccured\b', 'occured→occurred'),
    (r'\bembara[sc][sc]', 'embarass→embarrass'),
    (r'\bseperat', 'seperate→separate'),
    (r'\brythm\b', 'rythm→rhythm'),
    (r'\bprivelege\b', 'privelege→privilege'),
    (r'\bdefinately\b', 'definately→definitely'),
    (r'\bpowerfully\b', ''),  # skip correctly spelled
    (r'\bpowerfull\b', 'powerfull→powerful'),
    (r'\bcarefull\b', 'carefull→careful (not carefully)'),
    (r'\bthemself\b', ''),  # skip
    (r'\bthem selves\b', 'them selves→themselves'),
    (r'\byour self\b', 'your self→yourself'),
    (r'\bhim self\b', 'him self→himself'),
    (r'\bher self\b', 'her self→herself'),
    # Doubled words
    (r'\bthe the\b', 'doubled: the the'),
    (r'\bof of\b', 'doubled: of of'),
    (r'\bin in\b', 'doubled: in in (but not innin)'),
    (r'\byou you\b', 'doubled: you you'),
    (r'\ba a\b', 'doubled: a a'),
    (r'\bto to\b', 'doubled: to to'),
    # too/to confusion (adjective context)
    (r' to long\b', 'to→too long'),
    (r' to dark\b', 'to→too dark'),
    (r' to thick\b', 'to→too thick'),
    (r' to many\b', 'to→too many'),
    (r' to much\b', 'to→too much'),
    (r' to bad\b', 'to→too bad'),
    (r' to close\b.*\b(disc|you|them|him|wall|him|her|it|door|edge|line)', 'to→too close'),
    # a/an errors
    (r'\b[Aa] [aeiou][a-z]', 'possible a→an'),
    # in you 
    (r'\bin you\b(?! know|\b(are|is|were|have|\s*$))', 'in you→in your'),
    # other
    (r'\btthe\b', 'tthe→the (double t)'),
    (r'\btheis\b', 'theis→this'),
    (r'\bthrouogh\b', 'throuogh→through'),
]

# Simpler, more targeted patterns
search_patterns = [
    (r'eminates', 'eminates→emanates'),
    (r'dissapear\w*', 'dissapear→disappear'),
    (r'pharoah\w*', 'pharoah→pharaoh'),
    (r'completly', 'completly→completely'),
    (r'recieve\w*', 'recieve→receive'),
    (r'\bthier\b', 'thier→their'),
    (r'\bposession', 'posession→possession'),
    (r'encounterd', 'encounterd→encountered'),
    (r'accomodat\w*', 'accomodate→accommodate'),
    (r'occassion\w*', 'occassion→occasional'),
    (r'\bwierd\b', 'wierd→weird'),
    (r'\boccured\b', 'occured→occurred'),
    (r'embaras{1}[^s]', 'embaras→embarrass'),
    (r'seperat\w*', 'seperate→separate'),
    (r'\brythm\b', 'rythm→rhythm'),
    (r'privelege\w*', 'privelege→privilege'),
    (r'definately', 'definately→definitely'),
    (r'powerfull(?!y)', 'powerfull→powerful'),
    (r'carefull(?!y|n)', 'carefull→careful'),
    (r'them selves', 'them selves→themselves'),
    (r'your self', 'your self→yourself'),
    (r'him self', 'him self→himself'),
    (r'her self', 'her self→herself'),
    (r'\bthe the\b', 'doubled: the the'),
    (r'\bof of\b', 'doubled: of of (check context)'),
    (r'\byou you\b', 'doubled: you you'),
    (r'\ba a\b', 'doubled: a a'),
    (r'\bto to\b', 'doubled: to to'),
    (r' to long\b', 'to→too long'),
    (r' to dark\b', 'to→too dark'),
    (r' to thick\b', 'to→too thick'),
    (r' to many\b', 'to→too many'),
    (r' to much\b', 'to→too much'),
    (r' to bad\b', 'to→too bad'),
    (r'\btthe\b', 'tthe→the (double t)'),
    (r'\btheis\b', 'theis→this'),
    (r'\bthrouogh\b', 'throuogh→through'),
    (r'in you travels', 'in you travels→in your travels'),
    (r'Proprieter', 'Proprieter→Proprietor'),
    (r'\ba old\b', 'a→an old'),
    (r'\ba eerie\b', 'a→an eerie'),
    (r'\ba ancient\b', 'a→an ancient'),
    (r'\ba evil\b', 'a→an evil'),
    (r'\ba ugly\b', 'a→an ugly'),
    (r'\ba odd\b', 'a→an odd'),
    (r'\ba open\b', 'a→an open'),
    (r'\ba elite\b', 'a→an elite'),
    (r'\ba enormous\b', 'a→an enormous'),
]

results = {}
skip_files = {'korzath2old.are', 'savedTrinidad.are'}
for fname in arefiles:
    if fname in skip_files:
        continue
    path = 'area/' + fname
    try:
        text = open(path, encoding='latin-1').read()
        lines = text.split('\n')
        file_hits = []
        for pat, desc in search_patterns:
            for lnum, line in enumerate(lines, 1):
                # Skip comment lines and stat lines (lines starting with D, S, M, C, E, O followed by numbers)
                stripped = line.strip()
                if stripped.startswith('*') or stripped.startswith('#'):
                    continue
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    file_hits.append((lnum, desc, line.strip()[:100]))
        if file_hits:
            results[fname] = file_hits
    except Exception as ex:
        print(f'ERROR {fname}: {ex}')

for fname in sorted(results.keys()):
    print(f'\n=== {fname} ===')
    for lnum, desc, context in results[fname][:30]:  # max 30 per file
        print(f'  L{lnum} [{desc}]: {context[:90]}')
