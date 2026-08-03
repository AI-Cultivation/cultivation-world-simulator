from __future__ import annotations

from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_package_scripts_assert_no_sensitive_configs():
    package_dir = get_project_root() / "tools" / "package"
    scripts = [
        package_dir / "pack_github.ps1",
        package_dir / "desktop" / "pack.ps1",
        package_dir / "compress.ps1",
    ]

    for script in scripts:
        content = script.read_text(encoding="utf-8")
        assert "Assert-NoSensitiveConfigs" in content
        assert "local_config.yml" in content
        assert "settings.json" in content
        assert "secrets.json" in content


def test_desktop_packaging_contract():
    project_root = get_project_root()
    script = project_root / "tools" / "package" / "desktop" / "pack.ps1"
    content = script.read_text(encoding="utf-8")

    assert "CWS_DESKTOP_BACKEND_DIR" in content
    assert "CWS_DESKTOP_SEED_FILE" in content
    assert "desktop_content_root.txt" in content
    assert "npm run dist:desktop" in content
    assert "Assert-NoSensitiveConfigs" in content
    assert "[ValidateSet(\"generic\", \"epic\")][string]$Distribution = \"generic\"" in content
    assert "desktop-distribution.json" in content
    assert "eos-runtime.json" in content
    assert "EPIC_EOS_CLIENT_SECRET" in content
    assert "CWS_DESKTOP_DISTRIBUTION_MANIFEST" in content
    assert "CWS_DESKTOP_EOS_RUNTIME_FILE" in content
    assert "CWS_DESKTOP_EOS_HELPER_DIR" in content
    assert "CWS_DEFAULT_LLM_API_KEY" in content
    assert "desktop_seed.env" in content
    assert "AICultivationSimulator_Backend" in content
    assert "Publish Steam: powershell ./tools/package/publish_steam.ps1 -NoBuild" in content
    assert "Prepare Epic:  powershell ./tools/package/publish_epic.ps1 -NoBuild" in content
    assert 'Remove-Item -Path $DestWeb -Recurse -Force' in content

    wrapper = project_root / "tools" / "package" / "pack_desktop.ps1"
    wrapper_content = wrapper.read_text(encoding="utf-8")
    assert "desktop\\pack.ps1" in wrapper_content
    assert "[ValidateSet(\"generic\", \"epic\")][string]$Distribution = \"generic\"" in wrapper_content
    assert "-Distribution" in wrapper_content


def test_desktop_sandboxed_preload_is_commonjs():
    project_root = get_project_root()
    main = (project_root / "desktop" / "src" / "main.ts").read_text(encoding="utf-8")

    assert "'preload.cjs'" in main
    assert (project_root / "desktop" / "src" / "preload.cts").exists()
    assert not (project_root / "desktop" / "src" / "preload.ts").exists()


def test_steam_frontend_build_avoids_fragile_vendor_chunks():
    project_root = get_project_root()
    config = project_root / "web" / "vite.config.ts"
    content = config.read_text(encoding="utf-8")

    assert "return 'game-panels'" in content
    assert "vendor-vue" not in content
    assert "vendor-ui" not in content


def test_publish_steam_wraps_desktop_build():
    project_root = get_project_root()
    script = project_root / "tools" / "package" / "publish_steam.ps1"
    content = script.read_text(encoding="utf-8")

    assert "pack_desktop.ps1" in content
    assert "desktop_content_root.txt" in content
    assert "steam\\publish.ps1" in content
    assert "-ContentRoot" in content
    assert "[string]$BuildVersion" in content
    assert "-BuildDesc" in content
    assert "[switch]$Preview" in content
    assert "[switch]$NoBuild" in content
    assert not (project_root / "tools" / "package" / "pack_upload_steam.cmd").exists()
    assert not (project_root / "tools" / "package" / "pack_upload_steam.sh").exists()
    assert not (project_root / "tools" / "package" / "pack_upload_steam.ps1").exists()


def test_publish_epic_placeholder_wraps_desktop_build():
    project_root = get_project_root()
    script = project_root / "tools" / "package" / "publish_epic.ps1"
    content = script.read_text(encoding="utf-8")

    assert "pack_desktop.ps1" in content
    assert "desktop_content_root.txt" in content
    assert "epic\\publish.ps1" in content
    assert "-ContentRoot" in content
    assert "-BuildVersion" in content
    assert "[switch]$Preview" in content
    assert "[switch]$NoBuild" in content
    assert "[switch]$RequireUpload" in content
    assert "[ValidateSet(\"dev\", \"live\")][string]$EosEnv = \"live\"" in content
    assert "-Distribution\", \"epic\"" in content
    assert "-EosEnv" in content
    assert not (project_root / "tools" / "package" / "pack_upload_epic.ps1").exists()


def test_epic_eos_runtime_example_contains_placeholders_only():
    project_root = get_project_root()
    example = project_root / "tools" / "package" / "epic" / "eos_runtime.env.example"
    content = example.read_text(encoding="utf-8")

    assert "EPIC_EOS_PRODUCT_ID=" in content
    assert "EPIC_EOS_CLIENT_SECRET=" in content
    assert "712509d46fa64aa6ab328156929cdafe" not in content
    assert "xyza7891zYKHr1OV4M9DmHsIGuPTOY3P" not in content
    assert "2553c1ee5efc43e6bffb221c7d7acb3b" not in content
    assert "d58d8d54f87a456b83aa7af2a73a1e68" not in content


def test_publish_github_wraps_existing_release_pipeline():
    project_root = get_project_root()
    script = project_root / "tools" / "package" / "publish_github.ps1"
    content = script.read_text(encoding="utf-8")

    assert "pack_github.ps1" in content
    assert "compress.ps1" in content
    assert "release.ps1" in content
    assert "[switch]$NoBuild" in content
    assert "[switch]$Preview" in content
    assert "eos_runtime.env" not in content
    assert "CWS_DESKTOP_EOS" not in content


def test_epic_upload_script_wraps_build_patch_tool():
    project_root = get_project_root()
    script = project_root / "tools" / "package" / "epic" / "publish.ps1"
    content = script.read_text(encoding="utf-8")

    assert "[Parameter(Mandatory = $true)][string]$ContentRoot" in content
    assert "[string]$BuildVersion" in content
    assert "[switch]$Preview" in content
    assert "epic_config.env" in content
    assert "[switch]$RequireUpload" in content
    assert "EPIC_BUILD_PATCH_TOOL_PATH" in content
    assert "EPIC_CLIENT_SECRET_ENV_VAR" in content
    assert "ClientSecretEnvVar" in content
    assert "-mode=UploadBinary" in content
    assert "-BuildRoot=$ContentRoot" in content
    assert "-AppLaunch=$AppLaunch" in content
    assert "Add -RequireUpload to upload" in content


def test_steam_upload_script_supports_electron_parameters():
    project_root = get_project_root()
    script = project_root / "tools" / "package" / "steam" / "publish.ps1"
    content = script.read_text(encoding="utf-8")

    assert "[Parameter(Mandatory = $true)][string]$ContentRoot" in content
    assert "[string]$BuildDesc" in content
    assert "[string]$Branch" in content
    assert "[switch]$Preview" in content
    assert "SET_LIVE_BRANCH" in content
    assert "tmp\\${tag}_steam" not in content


def test_desktop_cursor_command_exists():
    project_root = get_project_root()
    command = project_root / ".cursor" / "commands" / "pack_desktop.md"
    content = command.read_text(encoding="utf-8")

    assert "pack_desktop.ps1" in content
    assert "desktop_content_root.txt" in content


def test_epic_cursor_command_exists_for_build_patch_tool():
    project_root = get_project_root()
    command = project_root / ".cursor" / "commands" / "publish_epic.md"
    content = command.read_text(encoding="utf-8")

    assert "publish_epic.ps1" in content
    assert "epic/publish.ps1" in content
    assert "BuildPatchTool" in content
    assert "RequireUpload" in content


def test_publish_commands_exist():
    project_root = get_project_root()

    github = (project_root / ".cursor" / "commands" / "publish_github.md").read_text(encoding="utf-8")
    steam = (project_root / ".cursor" / "commands" / "publish_steam.md").read_text(encoding="utf-8")

    assert "publish_github.ps1" in github
    assert "publish_steam.ps1" in steam


def test_package_task_entry_lists_and_dispatches_known_tasks():
    project_root = get_project_root()
    script = project_root / "tools" / "package" / "task.ps1"
    content = script.read_text(encoding="utf-8")

    assert "[switch]$List" in content
    assert '[ValidateSet("pack", "publish")]' in content
    assert '[ValidateSet("github", "desktop", "steam", "epic")]' in content
    assert "pack_github.ps1" in content
    assert "pack_desktop.ps1" in content
    assert "publish_github.ps1" in content
    assert "publish_steam.ps1" in content
    assert "publish_epic.ps1" in content


def test_github_pack_and_compress_write_markers_and_next_steps():
    project_root = get_project_root()
    pack = (project_root / "tools" / "package" / "pack_github.ps1").read_text(encoding="utf-8")
    compress = (project_root / "tools" / "package" / "compress.ps1").read_text(encoding="utf-8")

    assert "github_build_dir.txt" in pack
    assert "publish_github.ps1 -NoBuild" in pack
    assert "github_zip_path.txt" in compress
    assert "publish_github.ps1 -NoBuild" in compress


def test_default_steam_cursor_command_does_not_use_legacy_pack_script():
    project_root = get_project_root()
    command = project_root / ".cursor" / "commands" / "pack_desktop.md"
    content = command.read_text(encoding="utf-8")

    assert "powershell ./tools/package/pack_steam.ps1" not in content


def test_legacy_steam_pack_script_removed():
    project_root = get_project_root()
    assert not (project_root / "tools" / "package" / "pack_steam.ps1").exists()
    assert not (project_root / "tools" / "package" / "pack_steam_electron.ps1").exists()
    assert not (project_root / ".cursor" / "commands" / "pack_to_steam_electron.md").exists()
    assert not (project_root / ".cursor" / "commands" / "pack_to_steam.md").exists()
    assert not (project_root / ".cursor" / "commands" / "pack_to_epic.md").exists()
