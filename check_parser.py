import sys
from pathlib import Path
sys.path.append('.')
from webadmin.area_parser import AreaParser

AREA_PATH = Path('area')
parser = AreaParser(AREA_PATH)
parser.parse_all()

print(f"Mobs: {len(parser.mobiles)}")
print(f"Objects: {len(parser.objects)}")
print(f"Rooms: {len(parser.rooms)}")
print(f"Areas: {len(parser.areas)}")
