#!/usr/bin/env python3
import os, re

AREA_DIR = 'area'
SKIP = {'korzath2old.are', 'savedTrinidad.are'}

patterns = [
    'eminates', 'dissapear', 'completly', 'recieve', 'thier', 'posession',
    'encounterd', 'accomodat', 'wierd', 'occured', 'seperat', 'rythm',
    'privelege', 'definately', 'powerfull', 'them selves', 'the the',
    'of of', 'you you', 'to to', ' to long', ' to dark', ' to thick',
    ' to many', ' to much', 'tthe ', 'in you travels', 'Proprieter',
    'a old ', 'a ancient', 'a evil ', 'a ugly', 'a odd', 'a open ',
    'a elite', 'a ENORMOUS', 'lightening bolt', 'difficutly', 'carefull',
    'pharoah', 'weilding', 'wreckless', 'alot of', 'presense', 'noticable',
    'gaurd', 'differant', 'truely', 'arguement', 'succesful', 'knowlege',
    'beautifull', 'magnificant', 'exquisit',
]

pat_re = [(re.compile(p, re.IGNORECASE), p) for p in patterns]

for fname in sorted(os.listdir(AREA_DIR)):
    if not fname.endswith('.are') or fname in SKIP:
        continue
    text = open(os.path.join(AREA_DIR, fname), encoding='latin-1').read()
    lines = text.split('\n')
    hits = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('*') or s.startswith('#'):
            continue
        if re.match(r'^[A-Z\d]\s*[\d\-]', s):
            continue
        for rx, p in pat_re:
            if rx.search(line):
                hits.append((i, p, s[:90]))
                break
    if hits:
        print(f'=== {fname} ===')
        for ln, p, ctx in hits[:20]:
            print(f'  L{ln} {repr(p)}: {ctx}')
        if len(hits) > 20:
            print(f'  ...+{len(hits)-20} more')
        print()
