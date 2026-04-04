#!/usr/bin/env python3
import os, re

AREA = 'area'
SKIP = {'korzath2old.are', 'savedTrinidad.are'}

pats = [
    (r'\bsorceror\b', 'sorceror->sorcerer'),
    (r'\buntill\b', 'untill->until'),
    (r'\ba ugly\b', 'a->an ugly'),
    (r'\ba elf\b', 'a->an elf'),
    (r'\ba elven\b', 'a->an elven'),
    (r'\ba empty\b', 'a->an empty'),
    (r'\ba ominous\b', 'a->an ominous'),
    (r'\ba enormous\b', 'a->an enormous'),
    (r'\ba unusual\b', 'a->an unusual'),
    (r'\ba eerie\b', 'a->an eerie'),
    (r'\ba awful\b', 'a->an awful'),
    (r'\ba undead\b', 'a->an undead'),
    (r'\ba orc\b', 'a->an orc'),
    (r'\ba overgrown\b', 'a->an overgrown'),
    (r'\boccaision\w*', 'occaision->occasion'),
    (r'\bneccessary\b', 'neccessary->necessary'),
    (r'\bcollossal\b', 'collossal->colossal'),
    (r'\bequiped\b', 'equiped->equipped'),
    (r'\bApon\b', 'Apon->Upon'),
    (r'\bwere wolf\b', 'were wolf->werewolf'),
    (r'\bseperate\b', 'seperate->separate'),
    (r'\bseperates\b', 'seperates->separates'),
    (r'\bseperating\b', 'seperating->separating'),
    (r'\bextreamly\b', 'extreamly->extremely'),
    (r'\bextremly\b', 'extremly->extremely'),
    (r'\bextemely\b', 'extemely->extremely'),
    (r'\bimediatly\b', 'imediatly->immediately'),
    (r'\bimediately\b', 'imediately->immediately'),
    (r'\bfamilliar\b', 'familliar->familiar'),
    (r'\bunmistakeable\b', 'unmistakeable->unmistakable'),
    (r'\buseing\b', 'useing->using'),
    (r'\bdisapear\w*', 'disapear->disappear'),
    (r'\bcolosal\b', 'colosal->colossal'),
    (r'\bmanacal\b', 'manacal->maniacal'),
    (r'\bwether\b', 'wether->whether/weather'),
]

rxpats = [(re.compile(p, re.IGNORECASE), d) for p, d in pats]

found = {}
for fname in sorted(os.listdir(AREA)):
    if not fname.endswith('.are') or fname in SKIP:
        continue
    text = open(os.path.join(AREA, fname), encoding='latin-1').read()
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('*') or s.startswith('#'):
            continue
        if re.match(r'^[A-Z\d]\s*[-\d]', s):
            continue
        for rx, d in rxpats:
            m = rx.search(line)
            if m:
                key = (fname, d, m.group().lower())
                if key not in found:
                    found[key] = (i, s[:90])

for (fname, d, match), (ln, ctx) in sorted(found.items()):
    print(f'{fname} L{ln} [{d}] "{match}": {ctx}')
