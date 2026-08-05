"""Match NESMaps sprite references against extracted Zelda I map overlays.

Run ``extract_zelda_reference.py`` first. The reference maps and sprites are
audit inputs only and are deliberately not checked into this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageSequence


@dataclass(frozen=True)
class SpriteTemplate:
    name: str
    category: str
    source: str
    frame: int
    image: Image.Image


ENEMY_NAMES = {
    "Aquamentus": "aquamentus",
    "Armos": "armos",
    "Gel": "gel",
    "Ghini": "ghini",
    "GoriyaBlue": "blue_goriya",
    "GoriyaRed": "red_goriya",
    "KeeseBlue": "keese",
    "LeeverBlue": "blue_leever",
    "LeeverRed": "red_leever",
    "LynelBlue": "blue_lynel",
    "LynelRed": "red_lynel",
    "MolblinBlue": "blue_moblin",
    "MolblinRed": "red_moblin",
    "Moldorm": "moldorm",
    "OctorokBlue": "blue_octorok",
    "OctorokRed": "red_octorok",
    "Peahat": "peahat",
    "Rock": "falling_rock",
    "Rope": "rope",
    "Stalfos": "stalfos",
    "TektiteBlue": "blue_tektite",
    "TektiteRed": "red_tektite",
    "Trap": "blade_trap",
    "WallMaster": "wallmaster",
    "Zola": "zora",
}

ITEM_NAMES = {
    "2ndPotion": "red_potion",
    "5Rupies": "five_rupees",
    "Arrow": "arrow",
    "BlueCandle": "blue_candle",
    "BlueRing": "blue_ring",
    "Bomb": "bomb",
    "BookOfMagic": "magic_book",
    "Boomerang": "wooden_boomerang",
    "Bow": "bow",
    "Clock": "clock",
    "Compass": "compass",
    "Fairy": "fairy",
    "Food": "bait",
    "Heart": "heart",
    "HeartContainer": "heart_container",
    "Key": "key",
    "Letter": "letter",
    "LifePotion": "blue_potion",
    "MagicalBoomerang": "magical_boomerang",
    "MagicalKey": "magical_key",
    "MagicalRod": "magical_rod",
    "MagicalShield": "magical_shield",
    "Map": "map",
    "PowerBracelet": "power_bracelet",
    "Raft": "raft",
    "Recorder": "recorder",
    "RedCandle": "red_candle",
    "RedRing": "red_ring",
    "Rupy": "rupee",
    "SilverArrow": "silver_arrow",
    "Stepladder": "stepladder",
    "Sword": "wooden_sword",
    "Triforce": "triforce",
    "WhiteSword": "white_sword",
}

OTHER_NAMES = {
    "EnemyCloud": "enemy_cloud",
    "Fire": "fire",
    "Link": "link",
    "LinkSwingSword": "link",
    "Merchant": "merchant",
    "OldMan": "old_man",
}


def sprite_identity(path: Path) -> tuple[str, str] | None:
    stem = path.stem.removeprefix("ZeldaSprite")
    stem = re.sub(r"(Front|Back|Left|Right|Down|Up|DL|DR|UL|UR)$", "", stem)
    for names, category in (
        (ENEMY_NAMES, "enemy"),
        (ITEM_NAMES, "item"),
        (OTHER_NAMES, "other"),
    ):
        if stem in names:
            return names[stem], category
    return None


def rendered_frames(path: Path) -> list[Image.Image]:
    source = Image.open(path)
    rendered: list[Image.Image] = []
    fingerprints: set[tuple[tuple[int, int], bytes]] = set()
    for frame in ImageSequence.Iterator(source):
        rgba = frame.convert("RGBA")
        alpha = rgba.getchannel("A")
        bounds = alpha.getbbox()
        if bounds is None:
            continue
        rgba = rgba.crop(bounds)
        output = Image.new("RGB", rgba.size, "white")
        output.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
        fingerprint = (output.size, output.tobytes())
        if fingerprint not in fingerprints:
            fingerprints.add(fingerprint)
            rendered.append(output)
    return rendered


def load_templates(sprite_dir: Path) -> list[SpriteTemplate]:
    templates = []
    for path in sorted(sprite_dir.iterdir()):
        identity = sprite_identity(path)
        if identity is None:
            continue
        name, category = identity
        for frame_number, image in enumerate(rendered_frames(path)):
            templates.append(
                SpriteTemplate(
                    name=name,
                    category=category,
                    source=path.name,
                    frame=frame_number,
                    image=image,
                )
            )
    return templates


def color_positions(image: Image.Image) -> dict[tuple[int, int, int], list[tuple[int, int]]]:
    positions: dict[tuple[int, int, int], list[tuple[int, int]]] = defaultdict(list)
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            color = pixels[x, y]
            if color != (255, 255, 255):
                positions[color].append((x, y))
    return positions


def find_template(
    target: Image.Image,
    target_positions: dict[tuple[int, int, int], list[tuple[int, int]]],
    template: SpriteTemplate,
) -> list[tuple[int, int, int, int]]:
    template_pixels = template.image.load()
    anchors = [
        (len(target_positions.get(template_pixels[x, y], [])), x, y, template_pixels[x, y])
        for y in range(template.image.height)
        for x in range(template.image.width)
        if template_pixels[x, y] != (255, 255, 255)
    ]
    if not anchors:
        return []
    _, anchor_x, anchor_y, anchor_color = min(anchors)
    matches = []
    for target_x, target_y in target_positions.get(anchor_color, []):
        left = target_x - anchor_x
        top = target_y - anchor_y
        right = left + template.image.width
        bottom = top + template.image.height
        if left < 0 or top < 0 or right > target.width or bottom > target.height:
            continue
        candidate = target.crop((left, top, right, bottom))
        if ImageChops.difference(candidate, template.image).getbbox() is None:
            matches.append((left, top, right, bottom))
    return matches


def cell_identity(path: Path) -> tuple[str, str]:
    match = re.fullmatch(r"(.+)-([A-P][1-8])", path.stem)
    if match is None:
        raise ValueError(f"Unrecognized extracted cell name: {path.name}")
    return match.group(1), match.group(2)


def unmatched_components(
    target: Image.Image,
    detections: list[dict[str, object]],
) -> list[tuple[tuple[int, int, int, int], Image.Image, int]]:
    remaining = target.copy()
    draw = ImageDraw.Draw(remaining)
    for detection in detections:
        draw.rectangle(tuple(detection["bounds"]), fill="white")

    mask = remaining.convert("L").point(lambda pixel: 0 if pixel == 255 else 255)
    dilated = mask.filter(ImageFilter.MaxFilter(5))
    pixels = dilated.load()
    original_pixels = mask.load()
    visited: set[tuple[int, int]] = set()
    components = []

    for start_y in range(dilated.height):
        for start_x in range(dilated.width):
            if not pixels[start_x, start_y] or (start_x, start_y) in visited:
                continue
            pending = [(start_x, start_y)]
            visited.add((start_x, start_y))
            original_points = []
            while pending:
                x, y = pending.pop()
                if original_pixels[x, y]:
                    original_points.append((x, y))
                for next_x, next_y in (
                    (x - 1, y),
                    (x + 1, y),
                    (x, y - 1),
                    (x, y + 1),
                ):
                    point = (next_x, next_y)
                    if (
                        0 <= next_x < dilated.width
                        and 0 <= next_y < dilated.height
                        and pixels[next_x, next_y]
                        and point not in visited
                    ):
                        visited.add(point)
                        pending.append(point)
            if len(original_points) < 5:
                continue
            xs, ys = zip(*original_points)
            bounds = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
            components.append((bounds, remaining.crop(bounds), len(original_points)))
    return components


def save_component_atlas(
    output_path: Path,
    clusters: dict[tuple[tuple[int, int], bytes], dict[str, object]],
) -> list[dict[str, object]]:
    candidates = [
        record
        for record in clusters.values()
        if record["image"].width <= 40 and record["image"].height <= 40
    ]
    candidates.sort(key=lambda record: (-len(record["examples"]), record["digest"]))
    columns = 8
    cell_width = 150
    cell_height = 124
    rows = max(1, math.ceil(len(candidates) / columns))
    atlas = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(atlas)
    diagnostics = []
    for index, record in enumerate(candidates):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        image = record["image"]
        scale = min(4, 80 // max(image.size))
        rendered = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling.NEAREST,
        )
        atlas.paste(rendered, (x + (cell_width - rendered.width) // 2, y + 2))
        draw.text(
            (x + 3, y + 86),
            f"{index}: x{len(record['examples'])} {image.width}x{image.height}",
            fill="black",
        )
        draw.text((x + 3, y + 98), record["digest"], fill="black")
        draw.text((x + 3, y + 110), record["examples"][0], fill="black")
        diagnostics.append(
            {
                "id": index,
                "digest": record["digest"],
                "size": list(image.size),
                "pixel_count": record["pixel_count"],
                "examples": record["examples"],
            }
        )
    atlas.save(output_path)
    return diagnostics


def extract_cells(
    cells_dir: Path,
    templates: list[SpriteTemplate],
    component_atlas: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    maps: dict[str, dict[str, object]] = defaultdict(dict)
    component_clusters: dict[tuple[tuple[int, int], bytes], dict[str, object]] = {}
    for path in sorted(cells_dir.glob("*.png")):
        map_name, coordinate = cell_identity(path)
        target = Image.open(path).convert("RGB")
        positions = color_positions(target)
        detections = []
        seen: set[tuple[str, tuple[int, int, int, int]]] = set()
        for template in templates:
            for bounds in find_template(target, positions, template):
                identity = (template.name, bounds)
                if identity in seen:
                    continue
                seen.add(identity)
                detections.append(
                    {
                        "name": template.name,
                        "category": template.category,
                        "bounds": list(bounds),
                        "source": template.source,
                        "frame": template.frame,
                    }
                )

        counts = Counter(
            detection["name"]
            for detection in detections
            if detection["category"] in {"enemy", "item", "other"}
        )
        maps[map_name][coordinate] = {
            "entities": dict(sorted(counts.items())),
            "detections": sorted(
                detections,
                key=lambda item: (item["bounds"][1], item["bounds"][0], item["name"]),
            ),
        }
        for bounds, component, pixel_count in unmatched_components(target, detections):
            fingerprint = (component.size, component.tobytes())
            digest = hashlib.sha256(component.tobytes()).hexdigest()[:12]
            record = component_clusters.setdefault(
                fingerprint,
                {
                    "image": component,
                    "digest": digest,
                    "pixel_count": pixel_count,
                    "examples": [],
                },
            )
            record["examples"].append(
                f"{map_name}:{coordinate}@{bounds[0]},{bounds[1]}"
            )
    component_diagnostics = save_component_atlas(component_atlas, component_clusters)
    return (
        {name: cells for name, cells in sorted(maps.items())},
        component_diagnostics,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cells_dir", type=Path)
    parser.add_argument("sprite_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    templates = load_templates(args.sprite_dir)
    maps, components = extract_cells(
        args.cells_dir,
        templates,
        args.output.with_name(f"{args.output.stem}-unmatched.png"),
    )
    output = {
        "template_count": len(templates),
        "maps": maps,
        "unmatched_components": components,
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
