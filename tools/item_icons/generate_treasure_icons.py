from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from PIL import Image

from tools.item_icons.postprocess import (
    clean_chroma_background,
    pixelate_icon,
    split_contact_sheet,
    suppress_chroma_spill,
)
from tools.item_icons.utils.fal_client import FalImageConfig, generate_to_file


ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "tools" / "img_gen" / "image_api.env"
CHROMA_KEY = (255, 0, 255)


TREASURE_PROMPT = """Create a single 3 by 3 contact sheet of nine distinct treasure-chest POI icons
for a pixel-art xianxia cultivation world strategy game.

Canvas/layout:
- Exactly 3 columns by 3 rows, one centered treasure chest per cell.
- Use one perfectly flat solid #ff00ff chroma-key background across the entire image.
- No text, labels, numbers, UI frame, watermark, scenery, floor plane, cast shadows, gradients, or background particles.
- Do not use #ff00ff, magenta outlines, or pink glow inside any chest.
- Keep every chest fully inside its cell with generous padding and a centered silhouette.

Style:
- 32-bit fantasy cultivation RPG pixel art.
- Crisp hard pixel edges, compact readable silhouettes at 64x64, isolated map POI assets rather than inventory illustrations or scenes.
- Subtle top-left highlights and restrained internal spiritual light only.

Nine variants in reading order:
1. ancient jade-bound relic chest
2. gold spirit-lock chest
3. weathered ancient cultivator coffer
4. black demon-pattern treasure chest
5. meteorite-metal treasure chest
6. lost sect sealed lacquer chest
7. spirit-vein crystal chest
8. cracked rune chest
9. restrained radiant celestial casket
"""


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _get_fal_key() -> str:
    configured = _load_env(ENV_PATH) if ENV_PATH.exists() else {}
    return (
        os.environ.get("FAL_KEY")
        or os.environ.get("ITEM_ICON_FAL_KEY")
        or os.environ.get("FAL_API_KEY")
        or configured.get("FAL_KEY")
        or configured.get("ITEM_ICON_FAL_KEY")
        or configured.get("FAL_API_KEY")
        or ""
    )


def _build_preview(icon_paths: list[Path], output_path: Path) -> None:
    icons = [Image.open(path).convert("RGBA") for path in icon_paths]
    icon_size = icons[0].width
    preview = Image.new("RGBA", (icon_size * 3, icon_size * 3), (30, 27, 35, 255))
    for index, icon in enumerate(icons):
        x = (index % 3) * icon_size
        y = (index // 3) * icon_size
        preview.alpha_composite(icon, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview.convert("RGB").save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and process 3x3 treasure POI icons with fal gpt-image-2.")
    parser.add_argument("--work-dir", default="tmp/treasure_icon_generation")
    parser.add_argument("--output-dir", default="web/src/assets/icons/pois")
    args = parser.parse_args()

    api_key = _get_fal_key()
    if not api_key:
        raise RuntimeError("Set FAL_API_KEY, FAL_KEY, or ITEM_ICON_FAL_KEY in tools/img_gen/image_api.env or the environment.")

    work_dir = ROOT / args.work_dir
    raw_path = work_dir / "raw" / "treasure_sheet.png"
    split_dir = work_dir / "split"
    alpha_dir = work_dir / "alpha"
    despill_dir = work_dir / "despill"
    pixel_dir = work_dir / "pixel"
    output_dir = ROOT / args.output_dir

    result = generate_to_file(
        TREASURE_PROMPT,
        raw_path,
        config=FalImageConfig(
            api_key=api_key,
            model="openai/gpt-image-2",
            image_size="square_hd",
            quality="medium",
            output_format="png",
        ),
    )
    print(f"fal request completed: {result.get('request_id') or 'unknown'}")

    split_paths = split_contact_sheet(raw_path, split_dir, columns=3, rows=3, prefix="treasure")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_paths: list[Path] = []
    for index, split_path in enumerate(split_paths, start=1):
        alpha_path = alpha_dir / f"treasure_{index:02d}.png"
        despill_path = despill_dir / alpha_path.name
        pixel_path = pixel_dir / alpha_path.name
        final_path = output_dir / alpha_path.name
        clean_chroma_background(split_path, alpha_path, key_rgb=CHROMA_KEY)
        suppress_chroma_spill(alpha_path, despill_path, spill_rgb=CHROMA_KEY)
        pixelate_icon(despill_path, pixel_path)
        shutil.copy2(pixel_path, final_path)

        icon = Image.open(final_path).convert("RGBA")
        if icon.size != (128, 128):
            raise RuntimeError(f"Unexpected icon dimensions for {final_path}: {icon.size}")
        if any(icon.getpixel(corner)[3] != 0 for corner in ((0, 0), (127, 0), (0, 127), (127, 127))):
            raise RuntimeError(f"Background removal failed for {final_path}: corners are not transparent")
        final_paths.append(final_path)

    preview_path = work_dir / "treasure_icons_preview.png"
    _build_preview(final_paths, preview_path)
    print(f"raw contact sheet: {raw_path}")
    print(f"processed preview: {preview_path}")
    for path in final_paths:
        print(f"icon: {path}")


if __name__ == "__main__":
    main()
