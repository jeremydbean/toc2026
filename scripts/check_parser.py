"""Print the world totals the dashboard's area parser reads."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repository root
sys.path.insert(0, str(ROOT))

from webadmin.area_parser import AreaParser  # noqa: E402

AREA_PATH = ROOT / "area"
parser = AreaParser(AREA_PATH)
parser.parse_all()

print(f"Mobs: {len(parser.mobiles)}")
print(f"Objects: {len(parser.objects)}")
print(f"Rooms: {len(parser.rooms)}")
print(f"Areas: {len(parser.areas)}")
