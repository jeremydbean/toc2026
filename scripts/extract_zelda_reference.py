"""Extract room-level diagnostics from paired Zelda I map images.

The source images are intentionally not stored in this repository. Download the
labeled and background-only First Quest maps from NESMaps, then point this tool
at that directory. Pixels shared by each pair are removed so room sprites,
items, doors, and annotations can be audited independently of the scenery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


CELL_WIDTH = 256
CELL_HEIGHT = 176
TILE_SIZE = 16
LEVELS = range(1, 10)


def changed_bounds(
    labeled: Image.Image, background: Image.Image, box: tuple[int, int, int, int]
) -> tuple[int, int, int, int] | None:
    difference = ImageChops.difference(labeled.crop(box), background.crop(box))
    bounds = difference.getbbox()
    if bounds is None:
        return None

    return (
        box[0] + bounds[0],
        box[1] + bounds[1],
        box[0] + bounds[2],
        box[1] + bounds[3],
    )


def difference_cell(
    labeled: Image.Image,
    background: Image.Image,
    box: tuple[int, int, int, int],
) -> tuple[Image.Image, int]:
    labeled_cell = labeled.crop(box)
    background_cell = background.crop(box)
    difference = ImageChops.difference(labeled_cell, background_cell)
    mask = difference.convert("L").point(lambda pixel: 255 if pixel else 0)
    output = Image.new("RGB", labeled_cell.size, "white")
    output.paste(labeled_cell, mask=mask)
    changed_pixels = mask.histogram()[255]
    return output, changed_pixels


def extract_overworld_tiles(source_dir: Path, output_dir: Path) -> None:
    background = Image.open(source_dir / "ZeldaOverworldMapQ1BG.png").convert("RGB")
    tile_records: dict[str, dict[str, object]] = {}

    for screen_row in range(8):
        for screen_column in range(16):
            coordinate = f"{chr(ord('A') + screen_column)}{8 - screen_row}"
            screen_left = (screen_column + 1) * CELL_WIDTH
            screen_top = screen_row * CELL_HEIGHT
            for tile_row in range(CELL_HEIGHT // TILE_SIZE):
                for tile_column in range(CELL_WIDTH // TILE_SIZE):
                    box = (
                        screen_left + tile_column * TILE_SIZE,
                        screen_top + tile_row * TILE_SIZE,
                        screen_left + (tile_column + 1) * TILE_SIZE,
                        screen_top + (tile_row + 1) * TILE_SIZE,
                    )
                    tile = background.crop(box)
                    digest = hashlib.sha256(tile.tobytes()).hexdigest()[:12]
                    record = tile_records.setdefault(
                        digest,
                        {"image": tile, "positions": []},
                    )
                    record["positions"].append(
                        {
                            "screen": coordinate,
                            "column": tile_column,
                            "row": tile_row,
                        }
                    )

    sorted_records = sorted(
        tile_records.items(),
        key=lambda item: (-len(item[1]["positions"]), item[0]),
    )
    atlas_columns = 10
    atlas_cell_width = 96
    atlas_cell_height = 92
    atlas_rows = math.ceil(len(sorted_records) / atlas_columns)
    atlas = Image.new(
        "RGB",
        (atlas_columns * atlas_cell_width, atlas_rows * atlas_cell_height),
        "white",
    )
    draw = ImageDraw.Draw(atlas)
    diagnostics = []
    screen_tiles = {
        f"{chr(ord('A') + column)}{row}": [
            [None for _ in range(CELL_WIDTH // TILE_SIZE)]
            for _ in range(CELL_HEIGHT // TILE_SIZE)
        ]
        for row in range(1, 9)
        for column in range(16)
    }
    for index, (digest, record) in enumerate(sorted_records):
        x = (index % atlas_columns) * atlas_cell_width
        y = (index // atlas_columns) * atlas_cell_height
        tile = record["image"].resize((64, 64), Image.Resampling.NEAREST)
        atlas.paste(tile, (x + 16, y + 2))
        draw.text((x + 3, y + 68), f"{index}: {len(record['positions'])}", fill="black")
        draw.text((x + 3, y + 79), digest, fill="black")
        diagnostics.append(
            {
                "id": index,
                "digest": digest,
                "count": len(record["positions"]),
                "positions": record["positions"],
            }
        )
        for position in record["positions"]:
            screen_tiles[position["screen"]][position["row"]][
                position["column"]
            ] = index

    atlas.save(output_dir / "overworld-tiles.png")
    (output_dir / "overworld-tiles.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="ascii"
    )
    edge_tiles = {
        coordinate: {
            "north": tiles[0],
            "east": [row[-1] for row in tiles],
            "south": tiles[-1],
            "west": [row[0] for row in tiles],
        }
        for coordinate, tiles in screen_tiles.items()
    }
    (output_dir / "overworld-edge-tiles.json").write_text(
        json.dumps(edge_tiles, indent=2) + "\n", encoding="ascii"
    )

    horizontal_pairs: dict[tuple[int, int], list[dict[str, object]]] = {}
    vertical_pairs: dict[tuple[int, int], list[dict[str, object]]] = {}
    for row in range(1, 9):
        for column in range(15):
            west = f"{chr(ord('A') + column)}{row}"
            east = f"{chr(ord('A') + column + 1)}{row}"
            for tile_row in range(CELL_HEIGHT // TILE_SIZE):
                pair = (
                    screen_tiles[west][tile_row][-1],
                    screen_tiles[east][tile_row][0],
                )
                horizontal_pairs.setdefault(pair, []).append(
                    {"west": west, "east": east, "tile_row": tile_row}
                )
    for row in range(2, 9):
        for column in range(16):
            north = f"{chr(ord('A') + column)}{row}"
            south = f"{chr(ord('A') + column)}{row - 1}"
            for tile_column in range(CELL_WIDTH // TILE_SIZE):
                pair = (
                    screen_tiles[north][-1][tile_column],
                    screen_tiles[south][0][tile_column],
                )
                vertical_pairs.setdefault(pair, []).append(
                    {"north": north, "south": south, "tile_column": tile_column}
                )

    tile_images = {
        index: record["image"]
        for index, (_, record) in enumerate(sorted_records)
    }
    save_edge_pair_atlas(
        output_dir,
        "horizontal",
        horizontal_pairs,
        tile_images,
    )
    save_edge_pair_atlas(
        output_dir,
        "vertical",
        vertical_pairs,
        tile_images,
    )


def save_edge_pair_atlas(
    output_dir: Path,
    orientation: str,
    pairs: dict[tuple[int, int], list[dict[str, object]]],
    tile_images: dict[int, Image.Image],
) -> None:
    sorted_pairs = sorted(pairs.items(), key=lambda item: (-len(item[1]), item[0]))
    columns = 8
    cell_width = 150
    cell_height = 92 if orientation == "horizontal" else 154
    rows = math.ceil(len(sorted_pairs) / columns)
    atlas = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(atlas)
    diagnostics = []

    for index, (pair, positions) in enumerate(sorted_pairs):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        first = tile_images[pair[0]].resize((64, 64), Image.Resampling.NEAREST)
        second = tile_images[pair[1]].resize((64, 64), Image.Resampling.NEAREST)
        if orientation == "horizontal":
            atlas.paste(first, (x + 10, y + 2))
            atlas.paste(second, (x + 74, y + 2))
            text_y = y + 68
        else:
            atlas.paste(first, (x + 43, y + 2))
            atlas.paste(second, (x + 43, y + 66))
            text_y = y + 132
        draw.text(
            (x + 3, text_y),
            f"{index}: {pair[0]}/{pair[1]} x{len(positions)}",
            fill="black",
        )
        draw.line(
            (
                (x + 74, y + 2, x + 74, y + 66)
                if orientation == "horizontal"
                else (x + 43, y + 66, x + 107, y + 66)
            ),
            fill="red",
            width=1,
        )
        diagnostics.append(
            {
                "id": index,
                "tiles": list(pair),
                "count": len(positions),
                "positions": positions,
            }
        )

    atlas.save(output_dir / f"overworld-{orientation}-edge-pairs.png")
    (output_dir / f"overworld-{orientation}-edge-pairs.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="ascii"
    )


def extract_map(
    labeled_path: Path,
    background_path: Path,
    output_dir: Path,
    output_stem: str,
    source_column_offset: int = 0,
    columns: int | None = None,
    room_frames: bool = True,
) -> dict[str, object]:
    labeled = Image.open(labeled_path).convert("RGB")
    background = Image.open(background_path).convert("RGB")
    if labeled.size != background.size:
        raise ValueError(f"{output_stem} map pair has mismatched dimensions")

    source_columns = labeled.width // CELL_WIDTH
    rows = labeled.height // CELL_HEIGHT
    columns = source_columns - source_column_offset if columns is None else columns
    if source_column_offset + columns > source_columns:
        raise ValueError(f"{output_stem} column selection exceeds the source map")

    atlas = Image.new("RGB", (columns * CELL_WIDTH, rows * CELL_HEIGHT), "white")
    atlas_draw = ImageDraw.Draw(atlas)
    cells_dir = output_dir / "cells"
    cells_dir.mkdir(exist_ok=True)
    cells: list[dict[str, object]] = []

    for row in range(rows):
        for column in range(columns):
            source_column = column + source_column_offset
            source_box = (
                source_column * CELL_WIDTH,
                row * CELL_HEIGHT,
                (source_column + 1) * CELL_WIDTH,
                (row + 1) * CELL_HEIGHT,
            )
            atlas_box = (
                column * CELL_WIDTH,
                row * CELL_HEIGHT,
                (column + 1) * CELL_WIDTH,
                (row + 1) * CELL_HEIGHT,
            )
            bounds = changed_bounds(labeled, background, source_box)
            room_frame = room_frames or (
                background.getpixel((source_box[0], source_box[1])) != (0, 0, 0)
            )
            if bounds is None and not room_frame:
                continue

            cell, changed_pixels = difference_cell(labeled, background, source_box)
            atlas.paste(cell, atlas_box[:2])
            coordinate = f"{chr(ord('A') + column)}{rows - row}"
            atlas_draw.rectangle(atlas_box, outline=(80, 80, 80), width=1)
            atlas_draw.rectangle(
                (
                    atlas_box[0] + 2,
                    atlas_box[1] + 2,
                    atlas_box[0] + 34,
                    atlas_box[1] + 17,
                ),
                fill="white",
            )
            atlas_draw.text(
                (atlas_box[0] + 4, atlas_box[1] + 3), coordinate, fill="black"
            )
            cell.save(cells_dir / f"{output_stem}-{coordinate}.png")
            cells.append(
                {
                    "coordinate": coordinate,
                    "column": column,
                    "row": rows - row,
                    "room_frame": room_frame,
                    "changed_pixels": changed_pixels,
                    "changed_bounds": list(bounds) if bounds else None,
                }
            )

    atlas.save(output_dir / f"{output_stem}-difference.png")
    return {
        "map": output_stem,
        "columns": columns,
        "rows": rows,
        "cells": cells,
    }


def extract_level(source_dir: Path, output_dir: Path, level: int) -> dict[str, object]:
    labeled_path = source_dir / f"Level{level}Q1.png"
    background_path = source_dir / f"Level{level}Q1BG.png"
    return extract_map(
        labeled_path,
        background_path,
        output_dir,
        f"level-{level}",
        room_frames=False,
    )


def extract_overworld(source_dir: Path, output_dir: Path) -> dict[str, object]:
    return extract_map(
        source_dir / "ZeldaOverworldMapQ1.png",
        source_dir / "ZeldaOverworldMapQ1BG.png",
        output_dir,
        "overworld",
        source_column_offset=1,
        columns=16,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    diagnostics = [extract_overworld(args.source_dir, args.output_dir)]
    diagnostics.extend(
        extract_level(args.source_dir, args.output_dir, level) for level in LEVELS
    )
    extract_overworld_tiles(args.source_dir, args.output_dir)
    (args.output_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="ascii"
    )


if __name__ == "__main__":
    main()
