"""
Parse ROM 2.4 area files and build searchable database
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


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
    alignment: int
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
    wear_flags: str
    values: List[int]
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
    room_flags: int
    sector_type: int
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
        mob_match = re.search(r'#MOBILES\s*$(.*?)^#', content, re.MULTILINE | re.DOTALL)
        if not mob_match:
            return
        
        mob_section = mob_match.group(1)
        lines = [line.rstrip() for line in mob_section.split('\n')]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
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
                alignment = int(act_line[2]) if len(act_line) > 2 else 0
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
        obj_match = re.search(r'#OBJECTS\s*$(.*?)^#', content, re.MULTILINE | re.DOTALL)
        if not obj_match:
            return
        
        obj_section = obj_match.group(1)
        lines = [line.rstrip() for line in obj_section.split('\n')]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
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
                item_type = type_line[0] if len(type_line) > 0 else "1"
                extra_flags = type_line[1] if len(type_line) > 1 else "0"
                extra_flags2 = type_line[2] if len(type_line) > 2 else "0"
                wear_flags = type_line[3] if len(type_line) > 3 else "A"
                i += 1
                
                # Parse values line
                values_line = lines[i].split()
                values = [int(v) if v.lstrip('-').isdigit() else 0 for v in values_line[:4]]
                while len(values) < 4:
                    values.append(0)
                i += 1
                
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
        room_match = re.search(r'#ROOMS\s*$(.*?)^#', content, re.MULTILINE | re.DOTALL)
        if not room_match:
            return
        
        room_section = room_match.group(1)
        lines = [line.rstrip() for line in room_section.split('\n')]
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
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
                room_flags = int(afs_line[1]) if len(afs_line) > 1 else 0
                sector_type = int(afs_line[2]) if len(afs_line) > 2 else 0
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
