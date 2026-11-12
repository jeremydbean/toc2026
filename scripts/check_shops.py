"""Check every shop keeper and special-function mobile in loaded areas is
defined.

The world is read by webadmin/area_reader.py, token for token as
load_shops() and load_specials() read it.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repository root
sys.path.insert(0, str(ROOT))

from webadmin.area_reader import read_world  # noqa: E402

AREA_DIR = ROOT / "area"

areas = read_world(AREA_DIR)
mob_vnums = {m.vnum for area in areas for m in area.mobiles}

issues = []
for area in sorted(areas, key=lambda a: a.name):
    for shop in area.shops:
        if shop.keeper > 0 and shop.keeper not in mob_vnums:
            issues.append(f"{area.name}: SHOPS keeper {shop.keeper} not defined")
    for special in area.specials:
        if special.vnum > 0 and special.vnum not in mob_vnums:
            issues.append(f"{area.name}: SPECIALS mob {special.vnum} ({special.spec}) not defined")

if issues:
    print(f"ISSUES ({len(issues)}):")
    for i in issues:
        print(f"  {i}")
else:
    print("All shop keepers and special mobs are defined.")
