from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def build_report(root: Path) -> dict:
    top_level = []
    for item in sorted(root.iterdir()):
        size = _directory_size(item) if item.is_dir() else item.stat().st_size
        top_level.append({"name": item.name, "bytes": size})

    hashes: dict[tuple[int, str], list[str]] = defaultdict(list)
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        import hashlib

        digest = hashlib.sha256(item.read_bytes()).hexdigest()
        hashes[(item.stat().st_size, digest)].append(item.relative_to(root).as_posix())

    duplicate_bytes = sum(size * (len(paths) - 1) for (size, _), paths in hashes.items() if len(paths) > 1)
    return {
        "root": str(root),
        "total_bytes": _directory_size(root),
        "top_level": sorted(top_level, key=lambda item: item["bytes"], reverse=True),
        "duplicate_bytes": duplicate_bytes,
    }


def write_markdown_report(report: dict, output_path: Path) -> None:
    rows = [
        "# Package Size Report",
        "",
        f"Total size: {report['total_bytes'] / 1024 / 1024:.2f} MiB",
        f"Duplicate file bytes: {report['duplicate_bytes'] / 1024 / 1024:.2f} MiB",
        "",
        "| Top-level item | MiB |",
        "| --- | ---: |",
    ]
    rows.extend(f"| {item['name']} | {item['bytes'] / 1024 / 1024:.2f} |" for item in report["top_level"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a JSON package size inventory.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()
    report = build_report(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        write_markdown_report(report, args.markdown_output)
    print(f"Package size report: {args.output}")


if __name__ == "__main__":
    main()
