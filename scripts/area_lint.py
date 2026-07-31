from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from webadmin.area_health import build_area_health
from webadmin.area_parser import AreaParser


FAIL_LEVELS = {
    "none": set(),
    "critical": {"critical"},
    "warning": {"critical", "warning"},
    "info": {"critical", "warning", "info"},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint ToC area data.")
    parser.add_argument("--area-path", type=Path, default=REPO_ROOT / "area")
    parser.add_argument("--json", action="store_true", help="Emit full JSON result.")
    parser.add_argument(
        "--fail-on",
        choices=sorted(FAIL_LEVELS),
        default="critical",
        help="Exit non-zero when issues at this severity or higher are found.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of text issues to print when not using --json.",
    )
    args = parser.parse_args()

    area_parser = AreaParser(args.area_path)
    area_parser.parse_all()
    result = build_area_health(area_parser, args.area_path)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        summary = result["summary"]
        counts = summary["by_severity"]
        print(
            "Area health: "
            f"{summary['areas']} areas, {summary['mobiles']} mobs, "
            f"{summary['objects']} objects, {summary['rooms']} rooms"
        )
        print(
            "Issues: "
            f"{counts['critical']} critical, {counts['warning']} warning, "
            f"{counts['info']} info"
        )
        for issue in result["issues"][: max(0, args.limit)]:
            where = issue.get("area_file", "-")
            vnum = issue.get("vnum")
            suffix = f" #{vnum}" if vnum is not None else ""
            print(f"[{issue['severity']}] {issue['code']} {where}{suffix}: {issue['message']}")
        if len(result["issues"]) > args.limit:
            print(f"... {len(result['issues']) - args.limit} more issues omitted")

    fail_severities = FAIL_LEVELS[args.fail_on]
    if any(issue["severity"] in fail_severities for issue in result["issues"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
