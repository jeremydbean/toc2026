"""
Parse ROM 2.4 area files and build searchable database
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any


# Apply location mappings (for object affects)
APPLY_LOCATIONS = {
    1: 'strength',
    2: 'dexterity',
    3: 'intelligence',
    4: 'wisdom',
    5: 'constitution',
    6: 'sex',
    12: 'mana',
    13: 'hit points',
    14: 'movement',
    17: 'armor class',
    18: 'hitroll',
    19: 'damroll',
    23: 'save vs breath',
    24: 'save vs spell',
}

# Item type mappings
ITEM_TYPES = {
    1: 'light',
    2: 'scroll',
    3: 'wand',
    4: 'staff',
    5: 'weapon',
    6: 'treasure',
    8: 'treasure',
    9: 'armor',
    10: 'potion',
    11: 'clothing',
    12: 'furniture',
    13: 'trash',
    15: 'container',
    17: 'drink container',
    18: 'key',
    19: 'food',
    20: 'money',
    22: 'boat',
    23: 'npc corpse',
    25: 'fountain',
    26: 'pill',
    28: 'map',
    29: 'scuba gear',
    30: 'portal',
    31: 'manipulation',
    33: 'saddle',
    37: 'action',
}

# Weapon class mappings
WEAPON_CLASSES = {
    0: 'exotic',
    1: 'sword',
    2: 'dagger',
    3: 'spear',
    4: 'mace',
    5: 'axe',
    6: 'flail',
    7: 'whip',
    8: 'polearm',
    9: 'bow',
}

# Weapon type flags
WEAPON_TYPES = {
    'A': 'flaming',
    'B': 'frost',
    'C': 'vampiric',
    'D': 'sharp',
    'E': 'vorpal',
    'F': 'two-hands',
}

# Damage type names
DAMAGE_TYPES = {
    0: 'none',
    1: 'slice',
    2: 'stab',
    3: 'slash',
    4: 'whip',
    5: 'claw',
    6: 'blast',
    7: 'pound',
    8: 'crush',
    9: 'grep',
    10: 'bite',
    11: 'pierce',
    12: 'suction',
}

# Container flags
CONTAINER_FLAGS = {
    1: 'closeable',
    2: 'pickproof',
    4: 'closed',
    8: 'locked',
    16: 'trapped',
}

# Liquid types
LIQUID_TYPES = {
    0: 'water',
    1: 'beer',
    2: 'wine',
    3: 'ale',
    4: 'dark ale',
    5: 'whiskey',
    6: 'lemonade',
    7: 'firebreather',
    8: 'local specialty',
    9: 'slime mold juice',
    10: 'milk',
    11: 'tea',
    12: 'coffee',
    13: 'blood',
    14: 'salt water',
    15: 'cola',
}

# Object flags (extra_flags)
ITEM_FLAGS = {
    'A': 'glow',
    'B': 'hum',
    'C': 'dark',
    'D': 'lock',
    'E': 'evil',
    'F': 'invis',
    'G': 'magic',
    'H': 'nodrop',
    'I': 'bless',
    'J': 'anti-good',
    'K': 'anti-evil',
    'L': 'anti-neutral',
    'M': 'noremove',
    'N': 'inventory',
    'O': 'nopurge',
    'P': 'rot-death',
    'S': 'bounce',
    'T': 'tport',
    'U': 'noidentify',
    'V': 'nolocate',
    'W': 'race-restricted',
    'Z': 'flags2',
}

# Wear flags
WEAR_FLAGS = {
    'A': 'take',
    'B': 'finger',
    'C': 'neck',
    'D': 'body',
    'E': 'head',
    'F': 'legs',
    'G': 'feet',
    'H': 'hands',
    'I': 'arms',
    'J': 'shield',
    'K': 'about',
    'L': 'waist',
    'M': 'wrist',
    'N': 'wield',
    'O': 'hold',
    'P': 'two-hands',
}

# Mob ACT flags
ACT_FLAGS = {
    'A': 'is-npc',
    'B': 'sentinel',
    'C': 'scavenger',
    'D': 'is-healer',
    'E': 'gain',
    'F': 'aggressive',
    'G': 'stay-area',
    'H': 'wimpy',
    'I': 'pet',
    'J': 'train',
    'K': 'practice',
    'L': 'update-always',
    'M': 'nopush',
    'O': 'undead',
    'Q': 'cleric',
    'R': 'mage',
    'S': 'thief',
    'T': 'warrior',
    'U': 'noalign',
    'V': 'nopurge',
    'W': 'mountable',
    'X': 'nokill',
    'Z': 'flags2',
}

# Mob AFFECTED_BY flags
AFFECTED_FLAGS = {
    'A': 'blind',
    'B': 'invisible',
    'C': 'detect-evil',
    'D': 'detect-invis',
    'E': 'detect-magic',
    'F': 'detect-hidden',
    'G': 'berserk',
    'H': 'sanctuary',
    'I': 'faerie-fire',
    'J': 'infravision',
    'K': 'curse',
    'L': 'swim',
    'M': 'poison',
    'N': 'protect',
    'O': 'regeneration',
    'P': 'sneak',
    'Q': 'hide',
    'R': 'sleep',
    'S': 'charm',
    'T': 'flying',
    'U': 'pass-door',
    'V': 'haste',
    'W': 'calm',
    'X': 'plague',
    'Y': 'weaken',
    'Z': 'flags2',
}

# Mob OFF_BITS
OFF_FLAGS = {
    'A': 'area-attack',
    'B': 'backstab',
    'C': 'bash',
    'D': 'berserk',
    'E': 'disarm',
    'F': 'dodge',
    'G': 'fade',
    'H': 'fast',
    'I': 'kick',
    'J': 'kick-dirt',
    'K': 'parry',
    'L': 'rescue',
    'M': 'tail',
    'N': 'trip',
    'O': 'crush',
    'P': 'assist-all',
    'Q': 'assist-align',
    'R': 'assist-race',
    'S': 'assist-players',
    'T': 'assist-guards',
    'U': 'assist-vnum',
    'V': 'summoner',
    'W': 'needs-master',
    'Z': 'flags2',
}

# Mob IMMUNITIES
IMM_FLAGS = {
    'A': 'summon',
    'B': 'charm',
    'C': 'magic',
    'D': 'weapon',
    'E': 'bash',
    'F': 'pierce',
    'G': 'slash',
    'H': 'fire',
    'I': 'cold',
    'J': 'lightning',
    'K': 'acid',
    'L': 'poison',
    'M': 'negative',
    'N': 'holy',
    'O': 'energy',
    'P': 'mental',
    'Q': 'disease',
    'R': 'drowning',
    'S': 'light',
    'Z': 'flags2',
}

# Mob RESISTANCES (same flags as IMM, different context)
RES_FLAGS = IMM_FLAGS.copy()

# Mob VULNERABILITIES
VULN_FLAGS = {
    'C': 'magic',
    'D': 'weapon',
    'E': 'bash',
    'F': 'pierce',
    'G': 'slash',
    'H': 'fire',
    'I': 'cold',
    'J': 'lightning',
    'K': 'acid',
    'L': 'poison',
    'M': 'negative',
    'N': 'holy',
    'O': 'energy',
    'P': 'mental',
    'Q': 'disease',
    'R': 'drowning',
    'S': 'light',
    'T': 'wood',
    'U': 'silver',
    'Z': 'flags2',
}


def decode_flags(flag_string: str, flag_map: Dict[str, str]) -> List[str]:
    """Convert flag letters to human-readable names."""
    if not flag_string or flag_string == '0':
        return []
    return [flag_map.get(char, char) for char in flag_string if char in flag_map]


def decode_applies(affects: List[Dict[str, int]]) -> List[str]:
    """Convert affect location/modifier pairs to human-readable strings."""
    result = []
    for affect in affects:
        location = affect.get('location', 0)
        modifier = affect.get('modifier', 0)
        
        location_name = APPLY_LOCATIONS.get(location, f'unknown-{location}')
        
        # Format with +/- sign
        if modifier > 0:
            result.append(f'+{modifier} {location_name}')
        elif modifier < 0:
            result.append(f'{modifier} {location_name}')
        else:
            result.append(f'{location_name}')
    
    return result


def interpret_values(item_type_num: int, values: List[str]) -> Dict[str, Any]:
    """Interpret value fields based on item type."""
    result = {}
    
    try:
        item_type_num = int(item_type_num)
    except (ValueError, TypeError):
        return result
    
    # Ensure we have 5 values
    while len(values) < 5:
        values.append('0')
    
    if item_type_num == 1:  # ITEM_LIGHT
        result['hours'] = values[2]
        if values[2] == '9999':
            result['hours_text'] = 'infinite'
        elif values[2] == '0':
            result['hours_text'] = 'dead'
        else:
            result['hours_text'] = f'{values[2]} hours'
    
    elif item_type_num in [2, 10, 26]:  # SCROLL, POTION, PILL
        result['spell_level'] = values[0]
        result['spell1'] = values[1]
        result['spell2'] = values[2]
        result['spell3'] = values[3]
    
    elif item_type_num in [3, 4]:  # WAND, STAFF
        result['spell_level'] = values[0]
        result['max_charges'] = values[1]
        result['current_charges'] = values[2]
        result['spell_num'] = values[3]
    
    elif item_type_num == 5:  # WEAPON
        try:
            weapon_class = int(values[0])
            result['weapon_class'] = WEAPON_CLASSES.get(weapon_class, f'unknown-{weapon_class}')
            result['num_dice'] = values[1]
            result['size_dice'] = values[2]
            result['damage_text'] = f"{values[1]}d{values[2]}"
            
            # Damage type
            dam_type_str = values[3]
            if dam_type_str.isdigit():
                dam_type = int(dam_type_str)
                result['damage_type'] = DAMAGE_TYPES.get(dam_type, f'unknown-{dam_type}')
            else:
                result['damage_type'] = dam_type_str
            
            # Weapon type flags
            weapon_flags = values[4] if len(values) > 4 else '0'
            result['weapon_flags'] = decode_flags(weapon_flags, WEAPON_TYPES)
        except (ValueError, IndexError):
            pass
    
    elif item_type_num == 9:  # ARMOR
        result['ac_pierce'] = values[0]
        result['ac_bash'] = values[1]
        result['ac_slash'] = values[2]
        result['ac_magic'] = values[3]
        result['ac_summary'] = f"Pierce: {values[0]}, Bash: {values[1]}, Slash: {values[2]}, Magic: {values[3]}"
    
    elif item_type_num == 15:  # CONTAINER
        try:
            result['capacity'] = values[0]
            container_flags_val = int(values[1])
            
            # Decode container flags from bitfield
            container_flag_list = []
            for bit_val, flag_name in CONTAINER_FLAGS.items():
                if container_flags_val & bit_val:
                    container_flag_list.append(flag_name)
            result['container_flags'] = container_flag_list
            result['key_vnum'] = values[2]
        except (ValueError, IndexError):
            pass
    
    elif item_type_num == 17:  # DRINK_CON
        result['capacity'] = values[0]
        result['current_quantity'] = values[1]
        try:
            liquid_type = int(values[2])
            result['liquid_type'] = LIQUID_TYPES.get(liquid_type, f'unknown-{liquid_type}')
        except (ValueError, IndexError):
            pass
        poisoned = values[3] if len(values) > 3 else '0'
        result['poisoned'] = poisoned != '0'
    
    elif item_type_num == 19:  # FOOD
        result['hours_of_food'] = values[0]
    
    elif item_type_num == 20:  # MONEY
        result['gold_value'] = values[0]
    
    elif item_type_num == 25:  # FOUNTAIN
        result['capacity'] = values[0]
        result['current_quantity'] = values[1]
    
    elif item_type_num == 30:  # PORTAL
        result['portal_type'] = values[0]
        result['to_room'] = values[1]
        result['timer'] = values[2]
        result['closeable'] = values[3]
        result['key_vnum'] = values[4]
    
    elif item_type_num == 31:  # MANIPULATION
        manip_types = {1: 'flip', 2: 'move', 3: 'pull', 4: 'push', 5: 'turn', 
                       6: 'climb up', 7: 'climb down', 8: 'crawl', 9: 'jump'}
        try:
            manip_type = int(values[0])
            result['manip_type'] = manip_types.get(manip_type, f'unknown-{manip_type}')
        except (ValueError, IndexError):
            pass
        result['room_goes_to'] = values[1]
        result['door'] = values[2]
        result['object_state'] = values[3]
    
    elif item_type_num == 37:  # ACTION
        action_types = {1: 'recall', 2: 'death', 3: 'poison'}
        try:
            action_type = int(values[0])
            result['action_type'] = action_types.get(action_type, f'unknown-{action_type}')
        except (ValueError, IndexError):
            pass
        result['poison_duration'] = values[2]
    
    return result


@dataclass
class Mobile:
    vnum: int
    keywords: str
    short_desc: str
    long_desc: str
    description: str
    race: str
    act_flags: str
    affected_by: str
    alignment: str
    level: int
    hitroll: int
    ac: List[int]
    hitp_dice: str
    dam_dice: str
    dam_type: int
    off_flags: str
    imm_flags: str
    res_flags: str
    vuln_flags: str
    start_pos: str
    default_pos: str
    sex: str
    wealth: int
    form: str
    parts: str
    size: str
    material: str
    area_file: str = ""
    area_name: str = ""
    drops: List[int] = field(default_factory=list)  # Object vnums this mob can drop


@dataclass
class Object:
    vnum: int
    keywords: str
    short_desc: str
    long_desc: str
    material: str
    item_type: str
    extra_flags: str
    extra_flags2: str
    wear_flags: str
    values: List[str]
    level: int
    weight: int
    cost: int
    condition: str
    extra_descr: List[Dict[str, str]] = field(default_factory=list)
    affects: List[Dict[str, int]] = field(default_factory=list)
    area_file: str = ""
    area_name: str = ""
    carried_by: List[int] = field(default_factory=list)  # Mob vnums that carry this


@dataclass
class Exit:
    direction: int
    description: str
    keyword: str
    locks: int
    key_vnum: int
    to_room: int


@dataclass
class Room:
    vnum: int
    name: str
    description: str
    area_prefix: str
    room_flags: str
    sector_type: str
    exits: List[Exit] = field(default_factory=list)
    extra_descr: List[Dict[str, str]] = field(default_factory=list)
    area_file: str = ""
    area_name: str = ""


@dataclass
class Reset:
    command: str
    arg1: int
    arg2: int
    arg3: int
    arg4: int = 0


@dataclass
class Area:
    filename: str
    name: str
    builders: str = ""
    vnums: str = ""
    credits: str = ""
    security: int = 9


class AreaParser:
    DIRECTIONS = ["north", "east", "south", "west", "up", "down"]
    
    def __init__(self, area_directory: Path):
        self.area_directory = area_directory
        self.mobiles: Dict[int, Mobile] = {}
        self.objects: Dict[int, Object] = {}
        self.rooms: Dict[int, Room] = {}
        self.areas: Dict[str, Area] = {}
        self.resets: Dict[str, List[Reset]] = {}
        
    def parse_all(self) -> None:
        """Parse all .are files in the directory"""
        area_list_file = self.area_directory / "area.lst"
        if not area_list_file.exists():
            raise FileNotFoundError(f"area.lst not found in {self.area_directory}")
            
        with open(area_list_file, 'r', encoding='latin-1', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('$') and line.endswith('.are'):
                    area_file = self.area_directory / line
                    if area_file.exists():
                        try:
                            self.parse_area_file(area_file)
                        except Exception as e:
                            print(f"Error parsing {line}: {e}")
        
        # Build cross-references
        self._build_cross_references()
    
    def _build_cross_references(self) -> None:
        """Build relationships between mobs and objects based on resets"""
        for area_file, resets in self.resets.items():
            current_mob_vnum = None
            
            for reset in resets:
                if reset.command == 'M':  # Mobile reset
                    current_mob_vnum = reset.arg1
                elif reset.command == 'G' and current_mob_vnum:  # Give object to mob
                    obj_vnum = reset.arg1
                    if obj_vnum in self.objects and current_mob_vnum in self.mobiles:
                        if obj_vnum not in self.mobiles[current_mob_vnum].drops:
                            self.mobiles[current_mob_vnum].drops.append(obj_vnum)
                        if current_mob_vnum not in self.objects[obj_vnum].carried_by:
                            self.objects[obj_vnum].carried_by.append(current_mob_vnum)
                elif reset.command == 'E' and current_mob_vnum:  # Equip object on mob
                    obj_vnum = reset.arg1
                    if obj_vnum in self.objects and current_mob_vnum in self.mobiles:
                        if obj_vnum not in self.mobiles[current_mob_vnum].drops:
                            self.mobiles[current_mob_vnum].drops.append(obj_vnum)
                        if current_mob_vnum not in self.objects[obj_vnum].carried_by:
                            self.objects[obj_vnum].carried_by.append(current_mob_vnum)
    
    def parse_area_file(self, filepath: Path) -> None:
        """Parse a single .are file"""
        with open(filepath, 'r', encoding='latin-1', errors='ignore') as f:
            content = f.read()
        
        area_name = self._extract_area_name(content)
        area = Area(filename=filepath.name, name=area_name)
        self.areas[filepath.name] = area
        
        # Parse each section
        self._parse_mobiles(content, filepath.name, area_name)
        self._parse_objects(content, filepath.name, area_name)
        self._parse_rooms(content, filepath.name, area_name)
        self._parse_resets(content, filepath.name)
    
    def _extract_area_name(self, content: str) -> str:
        """Extract area name from #AREA section"""
        match = re.search(r'#AREA\s+([^\n]+?)~', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return "Unknown Area"
    
    def _read_to_tilde(self, lines: List[str], index: int) -> tuple[str, int]:
        """Read lines until hitting a tilde, return combined text and new index"""
        text_parts = []
        while index < len(lines):
            line = lines[index]
            if line.rstrip().endswith('~'):
                text_parts.append(line.rstrip()[:-1])
                return '\n'.join(text_parts), index + 1
            text_parts.append(line.rstrip())
            index += 1
        return '\n'.join(text_parts), index
    
    def _parse_mobiles(self, content: str, area_file: str, area_name: str) -> None:
        """Parse #MOBILES section"""
        mob_match = re.search(r'#MOBILES\s*\n(.*?)(?=^#[A-Z])', content, re.MULTILINE | re.DOTALL)
        if not mob_match:
            return
        
        mob_section = mob_match.group(1)
        lines = [line.rstrip() for line in mob_section.split('\n')]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip blank lines
            if not line:
                i += 1
                continue
            
            # Check for vnum
            if line.startswith('#'):
                if line == '#0':
                    break
                    
                try:
                    vnum = int(line[1:])
                except ValueError:
                    i += 1
                    continue
                
                # Read mobile data
                i += 1
                if i >= len(lines):
                    break
                
                keywords = lines[i].rstrip('~')
                i += 1
                
                short_desc = lines[i].rstrip('~')
                i += 1
                
                long_desc, i = self._read_to_tilde(lines, i)
                description, i = self._read_to_tilde(lines, i)
                
                race = lines[i].rstrip('~')
                i += 1
                
                # Parse act/affected flags line
                act_line = lines[i].split()
                act_flags = act_line[0] if len(act_line) > 0 else ""
                affected_by = act_line[1] if len(act_line) > 1 else ""
                
                # Handle optional 3rd flag set (some areas have 3 flag sets before alignment)
                # We look for the alignment (which should be a number, usually 0 or negative)
                # If the 3rd token is not a number, we assume it's another flag set
                idx = 2
                if len(act_line) > 3 and not act_line[2].lstrip('-').isdigit():
                    affected_by += " " + act_line[2]
                    idx += 1
                
                alignment = act_line[idx] if len(act_line) > idx else "0"
                i += 1
                
                # Parse level/hitroll line
                level_line = lines[i].split()
                level = int(level_line[0]) if len(level_line) > 0 else 1
                hitroll = int(level_line[1]) if len(level_line) > 1 else 0
                hitp_dice = level_line[2] if len(level_line) > 2 else "1d1+0"
                dam_dice = level_line[3] if len(level_line) > 3 else "1d1+0"
                dam_type = int(level_line[4].replace('d', '').replace('D', '').split('+')[0]) if len(level_line) > 4 else 0
                i += 1
                
                # Parse AC line
                ac_line = lines[i].split()
                ac = [int(ac_line[j]) if j < len(ac_line) else 0 for j in range(4)]
                i += 1
                
                # Parse off/imm/res/vuln flags
                flags_line = lines[i].split()
                off_flags = flags_line[0] if len(flags_line) > 0 else ""
                imm_flags = flags_line[1] if len(flags_line) > 1 else ""
                res_flags = flags_line[2] if len(flags_line) > 2 else ""
                vuln_flags = flags_line[3] if len(flags_line) > 3 else ""
                i += 1
                
                # Parse position line
                pos_line = lines[i].split()
                start_pos = pos_line[0] if len(pos_line) > 0 else "standing"
                default_pos = pos_line[1] if len(pos_line) > 1 else "standing"
                sex = pos_line[2] if len(pos_line) > 2 else "0"
                wealth = int(pos_line[3]) if len(pos_line) > 3 else 0
                i += 1
                
                # Parse form/parts line
                form_line = lines[i].split()
                form = form_line[0] if len(form_line) > 0 else ""
                parts = form_line[1] if len(form_line) > 1 else ""
                size = form_line[2] if len(form_line) > 2 else "medium"
                material = form_line[3] if len(form_line) > 3 else "flesh"
                i += 1
                
                mob = Mobile(
                    vnum=vnum,
                    keywords=keywords,
                    short_desc=short_desc,
                    long_desc=long_desc,
                    description=description,
                    race=race,
                    act_flags=act_flags,
                    affected_by=affected_by,
                    alignment=alignment,
                    level=level,
                    hitroll=hitroll,
                    ac=ac,
                    hitp_dice=hitp_dice,
                    dam_dice=dam_dice,
                    dam_type=dam_type,
                    off_flags=off_flags,
                    imm_flags=imm_flags,
                    res_flags=res_flags,
                    vuln_flags=vuln_flags,
                    start_pos=start_pos,
                    default_pos=default_pos,
                    sex=sex,
                    wealth=wealth,
                    form=form,
                    parts=parts,
                    size=size,
                    material=material,
                    area_file=area_file,
                    area_name=area_name
                )
                
                self.mobiles[vnum] = mob
            else:
                i += 1
    
    def _parse_objects(self, content: str, area_file: str, area_name: str) -> None:
        """Parse #OBJECTS section"""
        obj_match = re.search(r'#OBJECTS\s*\n(.*?)(?=^#[A-Z])', content, re.MULTILINE | re.DOTALL)
        if not obj_match:
            return
        
        obj_section = obj_match.group(1)
        lines = [line.rstrip() for line in obj_section.split('\n')]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip blank lines
            if not line:
                i += 1
                continue
            
            if line.startswith('#'):
                if line == '#0':
                    break
                
                try:
                    vnum = int(line[1:])
                except ValueError:
                    i += 1
                    continue
                
                i += 1
                if i >= len(lines):
                    break
                
                keywords = lines[i].rstrip('~')
                i += 1
                
                short_desc = lines[i].rstrip('~')
                i += 1
                
                long_desc = lines[i].rstrip('~')
                i += 1
                
                material = lines[i].rstrip('~')
                i += 1
                
                # Parse type/flags line
                type_line = lines[i].split()
                values_inline = False
                values = []
                
                # Debug print for school.are object 3745
                if vnum == 3745:
                    print(f"DEBUG: vnum={vnum} type_line={type_line} len={len(type_line)}")

                # Check for inline values (heuristic: if line has >= 8 tokens, assume 3 flags + 5 values)
                if len(type_line) >= 8:
                    values_inline = True
                    values = type_line[-5:]
                    flag_parts = type_line[:-5]
                else:
                    flag_parts = type_line
                
                item_type = flag_parts[0] if len(flag_parts) > 0 else "1"
                extra_flags = flag_parts[1] if len(flag_parts) > 1 else "0"
                
                if len(flag_parts) >= 4:
                    extra_flags2 = flag_parts[2]
                    wear_flags = flag_parts[3]
                elif len(flag_parts) == 3:
                    extra_flags2 = "0"
                    wear_flags = flag_parts[2]
                else:
                    extra_flags2 = "0"
                    wear_flags = "A"
                
                i += 1
                
                if not values_inline:
                    # Parse values line
                    values_line = lines[i].split()
                    values = []
                    for v in values_line:
                        values.append(v)
                    i += 1
                
                # Ensure at least 5 values
                while len(values) < 5:
                    values.append("0")
                
                # Parse level/weight/cost line
                lwc_line = lines[i].split()
                level = int(lwc_line[0]) if len(lwc_line) > 0 else 0
                weight = int(lwc_line[1]) if len(lwc_line) > 1 else 0
                cost = int(lwc_line[2]) if len(lwc_line) > 2 else 0
                condition = lwc_line[3] if len(lwc_line) > 3 else "P"
                i += 1
                
                extra_descr = []
                affects = []
                
                # Parse extra descriptions and affects
                while i < len(lines) and not lines[i].startswith('#'):
                    if lines[i].strip() == 'E':
                        i += 1
                        keywords_ed = lines[i].rstrip('~')
                        i += 1
                        desc_ed, i = self._read_to_tilde(lines, i)
                        extra_descr.append({'keywords': keywords_ed, 'description': desc_ed})
                    elif lines[i].strip() == 'A':
                        i += 1
                        affect_line = lines[i].split()
                        if len(affect_line) >= 2:
                            affects.append({
                                'location': int(affect_line[0]),
                                'modifier': int(affect_line[1])
                            })
                        i += 1
                    else:
                        i += 1
                
                obj = Object(
                    vnum=vnum,
                    keywords=keywords,
                    short_desc=short_desc,
                    long_desc=long_desc,
                    material=material,
                    item_type=item_type,
                    extra_flags=extra_flags,
                    extra_flags2=extra_flags2,
                    wear_flags=wear_flags,
                    values=values,
                    level=level,
                    weight=weight,
                    cost=cost,
                    condition=condition,
                    extra_descr=extra_descr,
                    affects=affects,
                    area_file=area_file,
                    area_name=area_name
                )
                
                self.objects[vnum] = obj
            else:
                i += 1
    
    def _parse_rooms(self, content: str, area_file: str, area_name: str) -> None:
        """Parse #ROOMS section"""
        room_match = re.search(r'#ROOMS\s*\n(.*?)(?=^#[A-Z])', content, re.MULTILINE | re.DOTALL)
        if not room_match:
            return
        
        room_section = room_match.group(1)
        lines = [line.rstrip() for line in room_section.split('\n')]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip blank lines
            if not line:
                i += 1
                continue
            
            if line.startswith('#'):
                if line == '#0':
                    break
                
                try:
                    vnum = int(line[1:])
                except ValueError:
                    i += 1
                    continue
                
                i += 1
                if i >= len(lines):
                    break
                
                name = lines[i].rstrip('~')
                i += 1
                
                description, i = self._read_to_tilde(lines, i)
                
                # Parse area/flags/sector line
                afs_line = lines[i].split()
                area_prefix = afs_line[0] if len(afs_line) > 0 else ""
                room_flags = afs_line[1] if len(afs_line) > 1 else "0"
                sector_type = afs_line[2] if len(afs_line) > 2 else "0"
                i += 1
                
                exits = []
                extra_descr = []
                
                # Parse exits and extra descriptions
                while i < len(lines) and not lines[i].startswith('#'):
                    if lines[i].strip().startswith('D'):
                        direction = int(lines[i].strip()[1])
                        i += 1
                        exit_desc = lines[i].rstrip('~')
                        i += 1
                        keyword = lines[i].rstrip('~')
                        i += 1
                        lock_line = lines[i].split()
                        locks = int(lock_line[0]) if len(lock_line) > 0 else 0
                        key_vnum = int(lock_line[1]) if len(lock_line) > 1 else -1
                        to_room = int(lock_line[2]) if len(lock_line) > 2 else 0
                        i += 1
                        exits.append(Exit(direction, exit_desc, keyword, locks, key_vnum, to_room))
                    elif lines[i].strip() == 'E':
                        i += 1
                        keywords_ed = lines[i].rstrip('~')
                        i += 1
                        desc_ed, i = self._read_to_tilde(lines, i)
                        extra_descr.append({'keywords': keywords_ed, 'description': desc_ed})
                    elif lines[i].strip() == 'S':
                        i += 1
                        break
                    else:
                        i += 1
                
                room = Room(
                    vnum=vnum,
                    name=name,
                    description=description,
                    area_prefix=area_prefix,
                    room_flags=room_flags,
                    sector_type=sector_type,
                    exits=exits,
                    extra_descr=extra_descr,
                    area_file=area_file,
                    area_name=area_name
                )
                
                self.rooms[vnum] = room
            else:
                i += 1
    
    def _parse_resets(self, content: str, area_file: str) -> None:
        """Parse #RESETS section"""
        reset_match = re.search(r'#RESETS\s*$(.*?)^S', content, re.MULTILINE | re.DOTALL)
        if not reset_match:
            return
        
        reset_section = reset_match.group(1)
        resets = []
        
        for line in reset_section.split('\n'):
            line = line.strip()
            if not line or line.startswith('*'):
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                cmd = parts[0]
                arg1 = int(parts[2]) if len(parts) > 2 else 0
                arg2 = int(parts[3]) if len(parts) > 3 else 0
                arg3 = int(parts[4]) if len(parts) > 4 else 0
                arg4 = int(parts[5]) if len(parts) > 5 else 0
                
                resets.append(Reset(cmd, arg1, arg2, arg3, arg4))
        
        self.resets[area_file] = resets
