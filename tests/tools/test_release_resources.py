from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image


def load_release_resources_module():
    module_path = Path(__file__).resolve().parents[2] / "tools" / "package" / "release_resources.py"
    spec = importlib.util.spec_from_file_location("release_resources", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_package_size_report_module():
    module_path = Path(__file__).resolve().parents[2] / "tools" / "package" / "package_size_report.py"
    spec = importlib.util.spec_from_file_location("package_size_report", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prepare_release_resources_excludes_source_only_asset_files(tmp_path):
    project_root = tmp_path / "project"
    assets = project_root / "assets"
    public = project_root / "web" / "public"
    (assets / "saves").mkdir(parents=True)
    (assets / "avatars").mkdir()
    (assets / "yao").mkdir()
    (public / "bgm").mkdir(parents=True)
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(assets / "avatars" / "portrait.png")
    Image.new("RGBA", (512, 512), (0, 0, 0, 0)).save(assets / "yao" / "portrait.png")
    (assets / "saves" / "save.json").write_text("{}", encoding="utf-8")
    (assets / "screenshot.gif").write_bytes(b"docs-only")
    (assets / "screenshot.png").write_bytes(b"docs-only")
    (assets / "splash.png").write_bytes(b"runtime")
    (public / "bgm" / "theme.mp3").write_bytes(b"audio")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        """
{
  "version": 1,
  "assets": {
    "source": "assets",
    "exclude": ["saves", "screenshot.gif", "screenshot.png"],
    "resize": {"avatars": 384, "yao": 384}
  },
  "public": {"source": "web/public", "exclude": []}
}
""".strip(),
        encoding="utf-8",
    )

    module = load_release_resources_module()
    output = tmp_path / "release"
    report = module.prepare_release_resources(
        project_root=project_root,
        output_dir=output,
        manifest_path=manifest,
    )

    assert (output / "assets" / "avatars" / "portrait.png").exists()
    assert (output / "assets" / "splash.png").exists()
    assert not (output / "assets" / "saves").exists()
    assert not (output / "assets" / "screenshot.gif").exists()
    assert not (output / "assets" / "screenshot.png").exists()
    assert (output / "public" / "bgm" / "theme.mp3").exists()
    with Image.open(output / "assets" / "avatars" / "portrait.png") as portrait:
        assert portrait.size == (384, 384)
        assert portrait.mode == "RGBA"
    with Image.open(output / "assets" / "yao" / "portrait.png") as portrait:
        assert portrait.size == (384, 384)
        assert portrait.mode == "RGBA"
    assert report["groups"]["assets"]["excluded"] == ["saves", "screenshot.gif", "screenshot.png"]
    assert report["groups"]["assets"]["resize"] == {"avatars": 384, "yao": 384}
    assert report["groups"]["assets"]["source_bytes"] >= report["groups"]["assets"]["bytes"]

    markdown_report = tmp_path / "release-report.md"
    module.write_markdown_report(report, markdown_report)
    assert "Release Resource Report" in markdown_report.read_text(encoding="utf-8")


def test_package_size_report_writes_markdown(tmp_path):
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "app.bin").write_bytes(b"payload")

    module = load_package_size_report_module()
    report = module.build_report(package_root)
    markdown_report = tmp_path / "package-report.md"
    module.write_markdown_report(report, markdown_report)

    assert report["total_bytes"] == len(b"payload")
    assert "Package Size Report" in markdown_report.read_text(encoding="utf-8")
