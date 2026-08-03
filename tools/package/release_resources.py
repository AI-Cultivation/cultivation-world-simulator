from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_MANIFEST = Path(__file__).with_name("release_resources.json")


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"Unsupported release resource manifest version: {data.get('version')}")
    for group in ("assets", "public"):
        config = data.get(group)
        if not isinstance(config, dict) or not isinstance(config.get("source"), str):
            raise ValueError(f"Manifest group '{group}' must define a source directory")
        if not isinstance(config.get("exclude", []), list):
            raise ValueError(f"Manifest group '{group}' excludes must be a list")
        if not isinstance(config.get("resize", {}), dict):
            raise ValueError(f"Manifest group '{group}' resize rules must be an object")
    return data


def _matches_exclusion(relative_path: Path, patterns: list[str]) -> bool:
    normalized = relative_path.as_posix()
    return any(
        fnmatch.fnmatch(normalized, pattern)
        or normalized.startswith(f"{pattern.rstrip('/')}/")
        for pattern in patterns
    )


def _file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _resize_limit(relative_path: Path, resize_rules: dict[str, int]) -> int | None:
    if not relative_path.parts:
        return None
    limit = resize_rules.get(relative_path.parts[0])
    return int(limit) if limit else None


def _copy_release_file(
    source_file: Path,
    target_file: Path,
    png_cache_dir: Path,
    resize_limit: int | None,
) -> None:
    if source_file.suffix.lower() != ".png":
        shutil.copy2(source_file, target_file)
        return

    cache_variant = f"{_file_digest(source_file)}-{resize_limit or 'original'}.png"
    cache_file = png_cache_dir / cache_variant
    if cache_file.exists():
        shutil.copy2(cache_file, target_file)
        return

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with Image.open(source_file) as image:
            if resize_limit and max(image.size) > resize_limit:
                scale = resize_limit / max(image.size)
                target_size = tuple(round(value * scale) for value in image.size)
                image = image.resize(target_size, Image.Resampling.NEAREST)
            image.save(cache_file, format="PNG", optimize=True)
        shutil.copy2(cache_file, target_file)
    except OSError:
        cache_file.unlink(missing_ok=True)
        # Preserve malformed source bytes so packaged validation reports the
        # asset problem instead of hiding it behind a staging failure.
        shutil.copy2(source_file, target_file)


def _copy_group(
    source: Path,
    destination: Path,
    exclusions: list[str],
    resize_rules: dict[str, int],
    png_cache_dir: Path,
) -> tuple[int, int, int]:
    if not source.is_dir():
        raise FileNotFoundError(f"Release resource source directory does not exist: {source}")

    files = 0
    source_bytes = 0
    output_bytes = 0
    for source_file in source.rglob("*"):
        if not source_file.is_file():
            continue
        relative_path = source_file.relative_to(source)
        if _matches_exclusion(relative_path, exclusions):
            continue
        target_file = destination / relative_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        _copy_release_file(
            source_file,
            target_file,
            png_cache_dir,
            _resize_limit(relative_path, resize_rules),
        )
        files += 1
        source_bytes += source_file.stat().st_size
        output_bytes += target_file.stat().st_size
    return files, source_bytes, output_bytes


def prepare_release_resources(*, project_root: Path, output_dir: Path, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    png_cache_dir = project_root / "tmp" / "release_resource_png_cache"

    groups: dict[str, dict[str, Any]] = {}
    for group_name in ("assets", "public"):
        config = manifest[group_name]
        source = project_root / config["source"]
        destination = output_dir / group_name
        files, source_bytes, output_bytes = _copy_group(
            source,
            destination,
            list(config.get("exclude", [])),
            {key: int(value) for key, value in config.get("resize", {}).items()},
            png_cache_dir,
        )
        groups[group_name] = {
            "source": str(source),
            "destination": str(destination),
            "files": files,
            "source_bytes": source_bytes,
            "bytes": output_bytes,
            "optimized_bytes_saved": source_bytes - output_bytes,
            "excluded": list(config.get("exclude", [])),
            "resize": dict(config.get("resize", {})),
        }

    total_bytes = sum(group["bytes"] for group in groups.values())
    source_bytes = sum(group["source_bytes"] for group in groups.values())
    return {
        "manifest": str(manifest_path),
        "output": str(output_dir),
        "png_cache": str(png_cache_dir),
        "groups": groups,
        "source_bytes": source_bytes,
        "total_bytes": total_bytes,
        "optimized_bytes_saved": source_bytes - total_bytes,
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], output_path: Path) -> None:
    rows = [
        "# Release Resource Report",
        "",
        "| Group | Files | Source MiB | Staged MiB | Saved MiB |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, group in report["groups"].items():
        rows.append(
            "| {name} | {files} | {source:.2f} | {staged:.2f} | {saved:.2f} |".format(
                name=name,
                files=group["files"],
                source=group["source_bytes"] / 1024 / 1024,
                staged=group["bytes"] / 1024 / 1024,
                saved=group["optimized_bytes_saved"] / 1024 / 1024,
            )
        )
    rows.extend(
        [
            "",
            f"Total staged size: {report['total_bytes'] / 1024 / 1024:.2f} MiB",
            f"PNG optimization savings: {report['optimized_bytes_saved'] / 1024 / 1024:.2f} MiB",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare shared release resources for packaged distributions.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--markdown-report", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    report = prepare_release_resources(
        project_root=args.project_root.resolve(),
        output_dir=args.output.resolve(),
        manifest_path=args.manifest.resolve(),
    )
    write_report(report, args.report.resolve())
    if args.markdown_report:
        write_markdown_report(report, args.markdown_report.resolve())
    print(f"Prepared release resources: {args.output}")
    print(f"Release resource report: {args.report}")


if __name__ == "__main__":
    main()
