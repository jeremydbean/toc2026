"""Catalog door graphics from NESMaps First Quest dungeon backgrounds."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


CELL_WIDTH = 256
CELL_HEIGHT = 176
PATCHES = {
    "north": (96, 0, 160, 48),
    "east": (208, 48, 256, 128),
    "south": (96, 128, 160, 176),
    "west": (0, 48, 48, 128),
}


def room_coordinates(diagnostics_path: Path) -> dict[int, list[str]]:
    diagnostics = json.loads(diagnostics_path.read_text(encoding="ascii"))
    return {
        int(record["map"].removeprefix("level-")): [
            cell["coordinate"]
            for cell in record["cells"]
            if cell["room_frame"]
        ]
        for record in diagnostics
        if record["map"].startswith("level-")
    }


def coordinate_box(coordinate: str, rows: int) -> tuple[int, int, int, int]:
    column = ord(coordinate[0]) - ord("A")
    row_from_top = rows - int(coordinate[1])
    return (
        column * CELL_WIDTH,
        row_from_top * CELL_HEIGHT,
        (column + 1) * CELL_WIDTH,
        (row_from_top + 1) * CELL_HEIGHT,
    )


def save_atlas(
    output_dir: Path,
    direction: str,
    records: dict[tuple[tuple[int, int], bytes], dict[str, object]],
) -> list[dict[str, object]]:
    sorted_records = sorted(
        records.values(),
        key=lambda record: (-len(record["examples"]), record["digest"]),
    )
    columns = 6
    cell_width = 180
    cell_height = 150
    rows = max(1, math.ceil(len(sorted_records) / columns))
    atlas = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(atlas)
    diagnostics = []
    for index, record in enumerate(sorted_records):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        image = record["image"]
        scale = min(2, 104 // max(image.size))
        rendered = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling.NEAREST,
        )
        atlas.paste(rendered, (x + (cell_width - rendered.width) // 2, y + 2))
        draw.text(
            (x + 3, y + 112),
            f"{index}: x{len(record['examples'])} {record['digest']}",
            fill="black",
        )
        draw.text((x + 3, y + 126), record["examples"][0], fill="black")
        diagnostics.append(
            {
                "id": index,
                "digest": record["digest"],
                "examples": record["examples"],
            }
        )
    atlas.save(output_dir / f"dungeon-doors-{direction}.png")
    return diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("diagnostics", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    coordinates = room_coordinates(args.diagnostics)
    patches: dict[
        str, dict[tuple[tuple[int, int], bytes], dict[str, object]]
    ] = defaultdict(dict)
    for level, rooms in coordinates.items():
        background = Image.open(
            args.source_dir / f"Level{level}Q1BG.png"
        ).convert("RGB")
        rows = background.height // CELL_HEIGHT
        for coordinate in rooms:
            room = background.crop(coordinate_box(coordinate, rows))
            for direction, box in PATCHES.items():
                patch = room.crop(box)
                red, green, blue = patch.split()
                black_mask = ImageChops.lighter(
                    ImageChops.lighter(red, green), blue
                ).point(lambda channel: 255 if channel else 0)
                fingerprint = (black_mask.size, black_mask.tobytes())
                record = patches[direction].setdefault(
                    fingerprint,
                    {
                        "image": patch,
                        "digest": hashlib.sha256(black_mask.tobytes()).hexdigest()[:12],
                        "examples": [],
                    },
                )
                record["examples"].append(f"level-{level}:{coordinate}")

    diagnostics = {
        direction: save_atlas(args.output_dir, direction, records)
        for direction, records in patches.items()
    }
    (args.output_dir / "dungeon-doors.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="ascii"
    )


if __name__ == "__main__":
    main()
