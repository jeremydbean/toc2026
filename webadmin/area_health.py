from __future__ import annotations

from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from webadmin.area_parser import AreaParser, flag_bit, parse_flag_value
except ImportError:  # pragma: no cover - supports direct script execution
    from area_parser import AreaParser, flag_bit, parse_flag_value


REVERSE_DIRECTIONS = {0: 2, 1: 3, 2: 0, 3: 1, 4: 5, 5: 4}
ISOLATED_RESTRICTION_FLAGS = {
    "jail": flag_bit("B"),
    "private": flag_bit("J"),
    "solitary": flag_bit("L"),
    "implementor-only": flag_bit("O"),
    "gods-only": flag_bit("P"),
}


def _issue(
    severity: str,
    code: str,
    message: str,
    area_file: Optional[str] = None,
    vnum: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if area_file is not None:
        result["area_file"] = area_file
    if vnum is not None:
        result["vnum"] = vnum
    if detail:
        result["detail"] = detail
    return result


def _listed_area_files(area_directory: Path) -> Tuple[List[str], List[str]]:
    listed: List[str] = []
    missing: List[str] = []
    area_list_file = area_directory / "area.lst"

    if not area_list_file.exists():
        return listed, ["area.lst"]

    for raw_line in area_list_file.read_text(encoding="latin-1", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("$") or not line.endswith(".are"):
            continue
        listed.append(line)
        if not (area_directory / line).exists():
            missing.append(line)

    return listed, missing


def _raw_vnum_locations(area_directory: Path, filenames: Iterable[str]) -> Dict[Tuple[str, int], List[str]]:
    locations: Dict[Tuple[str, int], List[str]] = defaultdict(list)

    for filename in filenames:
        section = ""
        path = area_directory / filename
        if not path.exists():
            continue

        for line in path.read_text(encoding="latin-1", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped in ("#MOBILES", "#OBJECTS", "#ROOMS"):
                section = stripped[1:].lower()
                continue
            if stripped.startswith("#") and not stripped[1:2].isdigit():
                section = ""
                continue
            if section and stripped.startswith("#") and stripped[1:].isdigit():
                vnum = int(stripped[1:])
                if vnum > 0:
                    locations[(section, vnum)].append(filename)

    return locations


def _count_by_severity(issues: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(issue["severity"] for issue in issues)
    return {
        "critical": counts.get("critical", 0),
        "warning": counts.get("warning", 0),
        "info": counts.get("info", 0),
    }


def _declares_area(area_directory: Path, filename: str) -> bool:
    path = area_directory / filename
    if not path.exists():
        return False

    for raw_line in path.read_text(encoding="latin-1", errors="ignore").splitlines():
        fields = raw_line.strip().split(maxsplit=1)
        if fields and fields[0] == "#AREA":
            return True
    return False


def _world_room_components(parser: AreaParser) -> Dict[int, int]:
    neighbors: Dict[int, set[int]] = {vnum: set() for vnum in parser.rooms}

    def connect(first: int, second: int) -> None:
        if first in neighbors and second in neighbors:
            neighbors[first].add(second)
            neighbors[second].add(first)

    for room in parser.rooms.values():
        for exit_data in room.exits:
            connect(room.vnum, exit_data.to_room)

        connect(room.vnum, room.teleport_to_room)

        for object_vnum in room.objects:
            obj = parser.objects.get(object_vnum)
            if obj is None or len(obj.values) < 2:
                continue
            travel_type = parse_flag_value(obj.values[0])
            destination = parse_flag_value(obj.values[1])

            is_portal = obj.item_type == "30" and travel_type != 4
            is_travel_manipulation = obj.item_type == "31" and travel_type in {6, 7, 8, 9}
            if is_portal or is_travel_manipulation:
                connect(room.vnum, destination)

    # Pet and mercenary storage is deliberately one vnum above a shop. The
    # relationship only becomes traversable through this special procedure,
    # so exits and reset objects alone cannot reveal it.
    mobiles = getattr(parser, "mobiles", {})
    for mob_vnum, special in getattr(parser, "mob_specials", {}).items():
        if special != "spec_pet_shop_owner":
            continue
        mob = mobiles.get(mob_vnum)
        if mob is None:
            continue
        for shop_vnum in mob.spawn_rooms:
            shop = parser.rooms.get(shop_vnum)
            if shop is None or not (parse_flag_value(shop.room_flags) & flag_bit("M")):
                continue
            connect(shop_vnum, shop_vnum + 1)

    component_by_room: Dict[int, int] = {}
    component_id = 0
    for start in sorted(neighbors):
        if start in component_by_room:
            continue
        queue: deque[int] = deque([start])
        component_by_room[start] = component_id
        while queue:
            current = queue.popleft()
            for next_room in sorted(neighbors[current]):
                if next_room not in component_by_room:
                    component_by_room[next_room] = component_id
                    queue.append(next_room)
        component_id += 1

    return component_by_room


def _room_area_components(
    parser: AreaParser,
    filename: str,
    component_by_room: Dict[int, int],
) -> List[List[int]]:
    grouped_rooms: Dict[int, List[int]] = defaultdict(list)
    for room in parser.rooms.values():
        if room.area_file == filename:
            grouped_rooms[component_by_room[room.vnum]].append(room.vnum)

    components = [sorted(component) for component in grouped_rooms.values()]
    components.sort(key=lambda component: (-len(component), component[0]))
    return components


def _component_restrictions(parser: AreaParser, component: Iterable[int]) -> Optional[List[str]]:
    """Return explicit isolation flags when every room in a group has one."""
    restrictions: set[str] = set()
    for vnum in component:
        room_flags = parse_flag_value(parser.rooms[vnum].room_flags)
        room_restrictions = {
            name for name, mask in ISOLATED_RESTRICTION_FLAGS.items() if room_flags & mask
        }
        if not room_restrictions:
            return None
        restrictions.update(room_restrictions)
    return sorted(restrictions)


def _component_samples(parser: AreaParser, components: List[List[int]]) -> str:
    samples = ", ".join(
        f'#{component[0]} "{parser.rooms[component[0]].name}" '
        f"({len(component)} room{'s' if len(component) != 1 else ''})"
        for component in components[:4]
    )
    if len(components) > 4:
        samples += f", plus {len(components) - 4} more"
    return samples


def build_area_health(parser: AreaParser, area_directory: Optional[Path] = None) -> Dict[str, Any]:
    """Return area-health summary and lint issues for parsed area data."""
    area_directory = area_directory or parser.area_directory
    issues: List[Dict[str, Any]] = []

    listed_files, missing_files = _listed_area_files(area_directory)
    for filename in missing_files:
        issues.append(
            _issue(
                "critical",
                "missing-area-file",
                f"{filename} is listed in area.lst but was not found.",
                filename,
            )
        )

    for parse_error in getattr(parser, "errors", []):
        filename = parse_error.get("file", "unknown")
        issues.append(
            _issue(
                "critical",
                "area-parse-error",
                f"{filename} failed to parse: {parse_error.get('error', 'unknown error')}",
                filename,
            )
        )

    raw_locations = _raw_vnum_locations(area_directory, listed_files)
    for (section, vnum), files in sorted(raw_locations.items()):
        unique_files = sorted(set(files))
        if len(files) > 1:
            issues.append(
                _issue(
                    "critical",
                    "duplicate-vnum",
                    f"{section} vnum {vnum} is defined {len(files)} times.",
                    unique_files[0],
                    vnum,
                    {"section": section, "files": unique_files},
                )
            )

    for filename in listed_files:
        if filename not in parser.areas:
            issues.append(
                _issue(
                    "warning",
                    "unparsed-area",
                    f"{filename} is listed but did not produce an area record.",
                    filename,
                )
            )

    component_by_room = _world_room_components(parser)

    for area in parser.areas.values():
        room_count = sum(1 for room in parser.rooms.values() if room.area_file == area.filename)
        mob_count = sum(1 for mob in parser.mobiles.values() if mob.area_file == area.filename)
        object_count = sum(1 for obj in parser.objects.values() if obj.area_file == area.filename)

        # area.lst also contains help and social-table files. They are loader
        # inputs, but they are not world areas and should not look empty here.
        if not _declares_area(area_directory, area.filename):
            continue

        if room_count == 0 and mob_count == 0 and object_count == 0:
            issues.append(
                _issue(
                    "warning",
                    "area-has-no-content",
                    f"{area.filename} has no parsed mobs, objects, or rooms.",
                    area.filename,
                )
            )
        elif room_count == 0:
            issues.append(
                _issue(
                    "info",
                    "area-has-no-rooms",
                    f"{area.filename} contains content but no rooms.",
                    area.filename,
                )
            )

        components = _room_area_components(parser, area.filename, component_by_room)
        if len(components) > 1:
            separated_groups = components[1:]
            restricted_groups: List[Tuple[List[int], List[str]]] = []
            unrestricted_groups: List[List[int]] = []
            for component in separated_groups:
                restrictions = _component_restrictions(parser, component)
                if restrictions:
                    restricted_groups.append((component, restrictions))
                else:
                    unrestricted_groups.append(component)

            if unrestricted_groups:
                issues.append(
                    _issue(
                        "warning",
                        "disconnected-area-rooms",
                        f"{area.filename} has {len(unrestricted_groups)} unrestricted disconnected "
                        f"travel group{'s' if len(unrestricted_groups) != 1 else ''}; "
                        f"groups start at {_component_samples(parser, unrestricted_groups)}.",
                        area.filename,
                        unrestricted_groups[0][0],
                        detail={
                            "component_sizes": [len(component) for component in components],
                            "unrestricted_starts": [
                                component[0] for component in unrestricted_groups
                            ],
                            "restricted_starts": [
                                component[0] for component, _ in restricted_groups
                            ],
                        },
                    )
                )

            if restricted_groups:
                restricted_components = [component for component, _ in restricted_groups]
                restrictions = sorted(
                    {name for _, names in restricted_groups for name in names}
                )
                issues.append(
                    _issue(
                        "info",
                        "restricted-isolated-rooms",
                        f"{area.filename} has {len(restricted_groups)} isolated travel "
                        f"group{'s' if len(restricted_groups) != 1 else ''} explicitly protected "
                        f"by {', '.join(restrictions)} flags; groups start at "
                        f"{_component_samples(parser, restricted_components)}.",
                        area.filename,
                        restricted_components[0][0],
                        detail={
                            "component_sizes": [
                                len(component) for component in restricted_components
                            ],
                            "sample_starts": [
                                component[0] for component in restricted_components[:8]
                            ],
                            "restrictions": restrictions,
                        },
                    )
                )

    for room in parser.rooms.values():
        for exit_data in room.exits:
            target = parser.rooms.get(exit_data.to_room)
            if target is None:
                detail = {"to_room": exit_data.to_room, "direction": exit_data.direction}
                if exit_data.to_room == -1:
                    issues.append(
                        _issue(
                            "info",
                            "exit-placeholder",
                            f"Room {room.vnum} has a descriptive exit with no destination.",
                            room.area_file,
                            room.vnum,
                            detail,
                        )
                    )
                elif exit_data.to_room <= 0:
                    issues.append(
                        _issue(
                            "warning",
                            "exit-target-invalid",
                            f"Room {room.vnum} exits to invalid room {exit_data.to_room}.",
                            room.area_file,
                            room.vnum,
                            detail,
                        )
                    )
                else:
                    issues.append(
                        _issue(
                            "critical",
                            "exit-target-missing",
                            f"Room {room.vnum} exits to missing room {exit_data.to_room}.",
                            room.area_file,
                            room.vnum,
                            detail,
                        )
                    )
                continue

            reverse = REVERSE_DIRECTIONS.get(exit_data.direction)
            if reverse is None:
                continue
            has_return = any(
                candidate.direction == reverse and candidate.to_room == room.vnum
                for candidate in target.exits
            )
            if not has_return:
                issues.append(
                    _issue(
                        "info",
                        "one-way-exit",
                        f"Room {room.vnum} exits to {target.vnum} without a direct reverse exit.",
                        room.area_file,
                        room.vnum,
                        {
                            "to_room": target.vnum,
                            "direction": exit_data.direction,
                            "expected_reverse_direction": reverse,
                        },
                    )
                )

    for mob in parser.mobiles.values():
        if not mob.spawn_rooms:
            issues.append(
                _issue(
                    "info",
                    "mob-has-no-spawn",
                    f"Mobile {mob.vnum} has no reset spawn room.",
                    mob.area_file,
                    mob.vnum,
                )
            )
        if mob.level < 0 or mob.level > 100:
            issues.append(
                _issue(
                    "warning",
                    "mob-level-outlier",
                    f"Mobile {mob.vnum} has unusual level {mob.level}.",
                    mob.area_file,
                    mob.vnum,
                    {"level": mob.level},
                )
            )

    room_object_vnums = {obj_vnum for room in parser.rooms.values() for obj_vnum in room.objects}
    for obj in parser.objects.values():
        if (
            obj.vnum not in room_object_vnums
            and not obj.carried_by
            and not obj.contained_by
        ):
            issues.append(
                _issue(
                    "info",
                    "object-has-no-source",
                    f"Object {obj.vnum} has no room, mobile, or container reset source.",
                    obj.area_file,
                    obj.vnum,
                )
            )
        # -1 asks the game to derive the object's level from its carrier.
        if obj.level < -1 or obj.level > 100:
            is_takeable = bool(parse_flag_value(obj.wear_flags) & flag_bit("A"))
            severity = "warning" if is_takeable else "info"
            code = "object-level-outlier" if is_takeable else "static-object-level-outlier"
            issues.append(
                _issue(
                    severity,
                    code,
                    f"Object {obj.vnum} has unusual level {obj.level}.",
                    obj.area_file,
                    obj.vnum,
                    {"level": obj.level},
                )
            )

    issues.sort(
        key=lambda issue: (
            {"critical": 0, "warning": 1, "info": 2}.get(issue["severity"], 9),
            issue.get("area_file", ""),
            issue.get("vnum", -1),
            issue["code"],
        )
    )

    return {
        "summary": {
            "areas": len(parser.areas),
            "mobiles": len(parser.mobiles),
            "objects": len(parser.objects),
            "rooms": len(parser.rooms),
            "listed_area_files": len(listed_files),
            "parse_errors": len(getattr(parser, "errors", [])),
            "issues": len(issues),
            "by_severity": _count_by_severity(issues),
        },
        "issues": issues,
    }
