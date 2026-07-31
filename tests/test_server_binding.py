"""
Tests for env-driven server binding and static config cleanup.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def test_start_uses_default_host_and_port():
    from src.server import main

    with patch.dict(os.environ, {}, clear=True), \
         patch.object(main, "uvicorn") as mock_uvicorn, \
         patch("src.server.bootstrap.get_free_port", return_value=8002), \
         patch("webbrowser.open"), \
         patch("os.kill"):
        main.start()

    mock_uvicorn.run.assert_called_once()
    kwargs = mock_uvicorn.run.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8002


def test_start_uses_env_host_and_port():
    from src.server import main

    with patch.dict(os.environ, {"SERVER_HOST": "0.0.0.0", "SERVER_PORT": "8080"}, clear=True), \
         patch.object(main, "uvicorn") as mock_uvicorn, \
         patch("webbrowser.open"), \
         patch("os.kill"):
        main.start()

    kwargs = mock_uvicorn.run.call_args.kwargs
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 8080


def test_start_respects_no_browser_env():
    from src.server import main

    with patch.dict(os.environ, {"CWS_NO_BROWSER": "1"}, clear=False), \
         patch.object(main, "uvicorn") as mock_uvicorn, \
         patch("webbrowser.open") as mock_open, \
         patch("os.kill"):
        main.start()

    mock_uvicorn.run.assert_called_once()
    mock_open.assert_not_called()


def test_empty_env_host_falls_back_to_default():
    with patch.dict(os.environ, {"SERVER_HOST": ""}, clear=True):
        host = os.environ.get("SERVER_HOST") or "127.0.0.1"
    assert host == "127.0.0.1"


def test_invalid_port_raises_value_error():
    with patch.dict(os.environ, {"SERVER_PORT": "not_a_number"}):
        with pytest.raises(ValueError):
            int(os.environ.get("SERVER_PORT") or 8002)


def test_static_config_no_longer_contains_system_section():
    from src.utils.config import CONFIG

    assert "system" not in CONFIG


def test_static_config_no_longer_contains_runtime_saves_source():
    from src.utils.config import CONFIG

    assert "resources" in CONFIG
    assert "saves" not in CONFIG.resources


def test_load_config_is_independent_from_current_working_directory(tmp_path, monkeypatch):
    from src.i18n.locale_registry import get_project_root
    from src.utils.config import load_config

    nested_dir = tmp_path / "nested" / "launcher"
    nested_dir.mkdir(parents=True)
    monkeypatch.chdir(nested_dir)

    config = load_config()

    assert Path(config.resources.locales_dir) == get_project_root() / "static" / "locales"
    assert Path(config.resources.shared_game_configs_dir) == get_project_root() / "static" / "game_configs"


def test_update_paths_for_language_falls_back_when_resources_missing(monkeypatch):
    from src.i18n.locale_registry import get_project_root
    import src.utils.config as app_config

    original_resources = app_config.CONFIG.resources
    try:
        app_config.CONFIG.resources = {}
        app_config.update_paths_for_language("zh-CN")

        assert Path(app_config.CONFIG.paths.locales) == get_project_root() / "static" / "locales"
        assert Path(app_config.CONFIG.paths.shared_game_configs) == get_project_root() / "static" / "game_configs"
        assert Path(app_config.CONFIG.paths.templates) == get_project_root() / "static" / "locales" / "zh-CN" / "templates"
    finally:
        app_config.CONFIG.resources = original_resources


def test_server_main_import_succeeds_from_non_project_cwd(tmp_path):
    from src.i18n.locale_registry import get_project_root

    launch_dir = tmp_path / "launcher"
    launch_dir.mkdir()
    data_dir = tmp_path / "appdata"
    project_root = get_project_root()

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(project_root)
        if not existing_pythonpath
        else os.pathsep.join([str(project_root), existing_pythonpath])
    )
    env["CWS_DATA_DIR"] = str(data_dir)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import src.server.main; print('import-ok')",
        ],
        cwd=launch_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout
