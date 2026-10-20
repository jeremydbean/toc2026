#!/usr/bin/env python3
"""Build the seasonal area variants from their base files plus an overlay.

src/season.c swaps three areas for a holiday copy at boot: dresden, limbo
and midennir become <base>_halloween.are during Hallows End (Oct 18 to
Nov 1) and <base>_xmas.are during Winter Veil (Dec 16 to Jan 6). Until
October 2026 the copies were hand-kept snapshots of an older world, and
they had drifted: the Halloween dresden had no room 4216 (where every
dead player is moved, so a death would have crashed the game), limbo had
no Oracle, no Hermie and no sanctum, every object still carried the
pre-copper gold price, and the Quest Master was missing. Nobody noticed
because the files only load in season.

So the copies are generated now. The overlay in data/seasonal/ holds only
what a season changes: the #AREA line, the flavour text of rooms and
mobiles (name and description), extra descriptions a decorated room
answers LOOK with (the pumpkins, the coffins), the records that exist
only in season (a vendor, a treat), and the resets, shops and specials
that place them.
Everything else -- every object, every exit, every stat line, every price,
every reset of the ordinary world -- comes from the base file as it is
today, so the seasonal world can never again fall behind it.

    python3 scripts/build_seasonal_areas.py            # write the variants
    python3 scripts/build_seasonal_areas.py --check    # fail if they differ
    python3 scripts/build_seasonal_areas.py --extract --source-dir DIR
        # (bootstrap, done once in October 2026) read the overlays out of
        # the hand-kept variant files in DIR, judging flavour against the
        # other season's copy of the same area

Area files are Latin-1 token streams; this script keeps every record as its
own lines and never reformats one.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "area"
DATA = ROOT / "data" / "seasonal"

VARIANTS = [("dresden", "halloween"), ("dresden", "xmas"),
            ("limbo", "halloween"), ("limbo", "xmas"),
            ("midennir", "halloween"), ("midennir", "xmas")]

SECTION = re.compile(r"^#(AREA|AREADATA|HELPS|MOBILES|OBJECTS|ROOMS|RESETS|SHOPS|SPECIALS|\$)\b")
RECORD = re.compile(r"^#(\d+)\s*$")


# ----------------------------------------------------------------- parsing

def read(path: Path) -> list[str]:
    return path.read_text(encoding="latin-1").split("\n")


def sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    """[(name, lines-including-header), ...] in file order."""
    out: list[tuple[str, list[str]]] = []
    for line in lines:
        m = SECTION.match(line)
        if m:
            out.append((m.group(1), [line]))
        elif out:
            out[-1][1].append(line)
        else:
            out.append(("", [line]))   # anything before the first section
    return out


def records(body: list[str]) -> tuple[list[str], dict[int, list[str]], list[str]]:
    """Split a MOBILES/OBJECTS/ROOMS body into (head, {vnum: lines}, tail).

    head is the section header line (and any lines before the first
    record), tail is the '#0' terminator and whatever follows it. Records
    keep their '#vnum' line.
    """
    head: list[str] = []
    recs: dict[int, list[str]] = {}
    order: list[int] = []
    tail: list[str] = []
    current: list[str] | None = None
    for line in body:
        m = RECORD.match(line)
        if m and tail == []:
            vnum = int(m.group(1))
            if vnum == 0:
                tail.append(line)
                current = None
                continue
            current = [line]
            recs[vnum] = current
            order.append(vnum)
        elif tail:
            tail.append(line)
        elif current is not None:
            current.append(line)
        else:
            head.append(line)
    recs = {v: recs[v] for v in order}
    return head, recs, tail


def text_fields(lines: list[str], count: int) -> int:
    """Index just past the first `count` tilde-terminated fields, counting
    from line 1 (line 0 is the '#vnum' header)."""
    seen = 0
    for i in range(1, len(lines)):
        if lines[i].rstrip().endswith("~"):
            seen += 1
            if seen == count:
                return i + 1
    raise ValueError("record %s has fewer than %d text fields" % (lines[0], count))


TEXT_FIELDS = {"MOBILES": 4, "ROOMS": 2}   # keywords/short/long/desc; name/desc


def flavour(rec: list[str], section: str) -> list[str]:
    return rec[1:text_fields(rec, TEXT_FIELDS[section])]


def with_flavour(rec: list[str], section: str, text: list[str]) -> list[str]:
    return [rec[0]] + text + rec[text_fields(rec, TEXT_FIELDS[section]):]


def extra_lines(extras: list[dict]) -> list[str]:
    """The E records an overlay adds to a room, as the loader reads them:
    E, keywords~, the text, ~."""
    out: list[str] = []
    for extra in extras:
        out += ["E", extra["keywords"] + "~"] + list(extra["lines"]) + ["~"]
    return out


def with_extras(rec: list[str], extras: list[dict]) -> list[str]:
    """A room record with the overlay's extra descriptions added before its
    closing S, so a seasonal room can answer LOOK <pumpkins>."""
    if not extras:
        return rec
    end = len(rec) - 1 - rec[::-1].index("S")
    return rec[:end] + extra_lines(extras) + rec[end:]


def without_extras(rec: list[str], extras: list[dict]) -> list[str]:
    """The inverse of with_extras, for tests that compare a seasonal room's
    exits and flags to the base's."""
    added = extra_lines(extras)
    if not added:
        return rec
    text = "\n".join(rec)
    block = "\n".join(added) + "\n"
    assert text.count(block) == 1, "the overlay's extras are not in the record once"
    return text.replace(block, "", 1).split("\n")


def vnums_in(line: str) -> set[int]:
    return {int(n) for n in re.findall(r"\b(\d+)\b", line.split(";")[0].split("*")[0])}


# ----------------------------------------------------------------- building

def build(base_lines: list[str], overlay: dict) -> list[str]:
    out: list[str] = []
    extra = overlay.get("records", {})
    for name, body in sections(base_lines):
        if name == "AREA" and overlay.get("area"):
            out.extend(overlay["area"])
            continue
        if name in ("MOBILES", "OBJECTS", "ROOMS"):
            head, recs, tail = records(body)
            out.extend(head)
            texts = overlay.get("text", {}).get(name, {})
            extras = overlay.get("extras", {}).get(name, {})
            for vnum, rec in recs.items():
                if str(vnum) in texts:
                    rec = with_flavour(rec, name, texts[str(vnum)])
                if name == "ROOMS" and str(vnum) in extras:
                    rec = with_extras(rec, extras[str(vnum)])
                out.extend(rec)
            for vnum in sorted(int(v) for v in extra.get(name, {})):
                if vnum not in recs:
                    out.extend(extra[name][str(vnum)])
            out.extend(tail)
            continue
        if name in ("RESETS", "SHOPS", "SPECIALS") and overlay.get(name.lower()):
            # The section ends with its terminator ('S' or '0'); the seasonal
            # lines go just before it.
            end = len(body)
            while end > 1 and body[end - 1].strip() == "":
                end -= 1
            out.extend(body[:end - 1])
            out.extend(overlay[name.lower()])
            out.extend(body[end - 1:])
            continue
        out.extend(body)
    return out


# --------------------------------------------------------------- extraction

def world_vnums(name: str) -> set[int]:
    """Every vnum of one record kind across the areas area.lst loads."""
    out: set[int] = set()
    for entry in (AREA / "area.lst").read_text(encoding="latin-1").split("\n"):
        entry = entry.strip()
        if not entry or entry.startswith(("#", "$")) or not (AREA / entry).is_file():
            continue
        for sname, body in sections(read(AREA / entry)):
            if sname == name:
                out |= set(records(body)[1])
    return out


def extract(base_lines: list[str], seasonal_lines: list[str],
            reference_lines: list[str], old_base_lines: list[str] | None = None) -> dict:
    """What the seasonal file changes. Flavour text is text that differs
    both from the current base and from the reference -- the other
    season's copy of the same area, which was taken from the same old
    world: text the two copies share is simply that old world, and the
    current base is the better source for it."""
    base = dict(sections(base_lines))
    seas = dict(sections(seasonal_lines))
    ref = dict(sections(reference_lines))
    old = dict(sections(old_base_lines)) if old_base_lines else {}
    overlay: dict = {"area": seas.get("AREA", base.get("AREA")), "text": {}, "records": {}}
    seasonal_only: set[int] = set()
    for name in ("MOBILES", "OBJECTS", "ROOMS"):
        if name not in seas:
            continue
        _, brecs, _ = records(base.get(name, ["#" + name, "#0"]))
        _, srecs, _ = records(seas[name])
        _, rrecs, _ = records(ref.get(name, ["#" + name, "#0"]))
        _, orecs, _ = records(old.get(name, ["#" + name, "#0"]))
        elsewhere = world_vnums(name) - set(brecs)
        for vnum, rec in srecs.items():
            if vnum not in brecs:
                if vnum in elsewhere:
                    # An old copy of a record the world has moved elsewhere
                    # (the Quest Master sat in the Halloween limbo): loading
                    # it twice is a fatal duplicate at boot.
                    print(f"  dropping {name} {vnum}: it exists in another area now")
                    continue
                overlay["records"].setdefault(name, {})[str(vnum)] = rec
                seasonal_only.add(vnum)
            elif name in TEXT_FIELDS:
                text = flavour(rec, name)
                plain = [flavour(brecs[vnum], name)]
                if vnum in rrecs:
                    plain.append(flavour(rrecs[vnum], name))
                if vnum in orecs:
                    plain.append(flavour(orecs[vnum], name))
                if all(text != p for p in plain):
                    overlay["text"].setdefault(name, {})[str(vnum)] = text
    for name in ("RESETS", "SHOPS", "SPECIALS"):
        if name not in seas:
            continue
        base_set = {l.strip() for l in base.get(name, [])}
        keep = []
        for line in seas[name][1:]:
            if line.strip() in base_set or not line.strip() or line.lstrip().startswith("*"):
                continue
            if vnums_in(line) & seasonal_only:
                keep.append(line)
        if keep:
            overlay[name.lower()] = keep
    return overlay


# ------------------------------------------------------------------- main

def overlay_path(base: str, tag: str) -> Path:
    return DATA / f"{base}_{tag}.json"


def variant_path(base: str, tag: str) -> Path:
    return AREA / f"{base}_{tag}.are"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if a variant file differs from what the overlay builds")
    ap.add_argument("--extract", action="store_true", help="bootstrap: write the overlays from the current variant files")
    ap.add_argument("--source-dir", type=Path, help="with --extract: the directory holding the hand-kept variant files to read the overlays out of")
    ap.add_argument("--old-base-dir", type=Path, help="with --extract: the base files as they stood when the variants were copied, if known; text equal to them is not flavour either")
    args = ap.parse_args(argv)

    if args.extract:
        if args.source_dir is None:
            ap.error("--extract needs --source-dir")
        DATA.mkdir(parents=True, exist_ok=True)
        for base, tag in VARIANTS:
            sibling = "xmas" if tag == "halloween" else "halloween"
            ov = extract(read(AREA / f"{base}.are"), read(args.source_dir / f"{base}_{tag}.are"),
                         read(args.source_dir / f"{base}_{sibling}.are"),
                         read(args.old_base_dir / f"{base}.are") if args.old_base_dir else None)
            overlay_path(base, tag).write_text(json.dumps(ov, indent=1, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
            n_text = sum(len(v) for v in ov["text"].values())
            n_rec = sum(len(v) for v in ov["records"].values())
            print(f"{base}_{tag}: {n_text} flavoured records, {n_rec} seasonal-only records, "
                  f"{len(ov.get('resets', []))} resets, {len(ov.get('shops', []))} shops, "
                  f"{len(ov.get('specials', []))} specials")
        return 0

    stale = 0
    for base, tag in VARIANTS:
        base_lines = read(AREA / f"{base}.are")
        overlay = json.loads(overlay_path(base, tag).read_text(encoding="utf-8"))
        # The builder must be the identity with an empty overlay, or it is
        # rewriting records it has no business touching.
        if build(base_lines, {}) != base_lines:
            print(f"{base}: the builder does not reproduce the base file with an empty overlay", file=sys.stderr)
            return 2
        text = "\n".join(build(base_lines, overlay))
        path = variant_path(base, tag)
        current = path.read_text(encoding="latin-1") if path.exists() else None
        if args.check:
            if current != text:
                print(f"stale: {path.relative_to(ROOT)} (run scripts/build_seasonal_areas.py)")
                stale += 1
        else:
            path.write_text(text, encoding="latin-1")
            print(f"wrote {path.relative_to(ROOT)}{'' if current != text else ' (unchanged)'}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
