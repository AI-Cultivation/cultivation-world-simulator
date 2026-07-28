from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.config import AppSettingsPatch, LLMSettingsUpdate, get_data_paths, get_settings_service
from src.config import settings_service as settings_service_module
from src.i18n.locale_registry import get_default_locale, get_fallback_locale


def test_settings_service_creates_defaults_in_data_root():
    service = get_settings_service()
    settings = service.get_settings_view()
    paths = get_data_paths()

    assert settings.schema_version == 2
    assert settings.ui.locale == get_default_locale()
    assert paths.settings_file.exists()
    assert paths.secrets_file.exists()
    assert paths.saves_dir.exists()
    assert settings.new_game_defaults.test_mode is False


def test_settings_service_existing_read_does_not_rewrite_files(monkeypatch):
    service = get_settings_service()
    service.get_settings_view()

    monkeypatch.setattr(
        service,
        "_save_settings",
        lambda _settings: (_ for _ in ()).throw(AssertionError("read should not write settings")),
    )
    monkeypatch.setattr(
        service,
        "_save_secrets",
        lambda _secrets: (_ for _ in ()).throw(AssertionError("read should not write secrets")),
    )

    settings = service.get_settings_view()
    profile, _ = service.get_llm_runtime_config()

    assert settings.schema_version == 2
    assert profile.model_name == settings.llm.profile.model_name


def test_atomic_write_json_retries_transient_replace_error(tmp_path, monkeypatch):
    target = tmp_path / "settings.json"
    original_replace = settings_service_module.Path.replace
    calls = {"count": 0}

    def flaky_replace(self, target_path):
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError("simulated Windows file lock")
        return original_replace(self, target_path)

    monkeypatch.setattr(settings_service_module, "_REPLACE_RETRY_DELAYS", (0,))
    monkeypatch.setattr(settings_service_module.time, "sleep", lambda _delay: None)
    monkeypatch.setattr(settings_service_module.Path, "replace", flaky_replace)

    settings_service_module._atomic_write_json(target, {"ok": True})

    assert calls["count"] == 2
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert not list(tmp_path.glob("*.tmp"))


def test_settings_service_updates_llm_secret_without_exposing_key():
    service = get_settings_service()
    updated = service.update_llm(
        LLMSettingsUpdate(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model_name="model-a",
            fast_model_name="model-b",
            mode="default",
            max_concurrent_requests=12,
            clear_api_key=False,
        )
    )

    profile, api_key = service.get_llm_runtime_config()

    assert updated.has_api_key is True
    assert profile.base_url == "https://api.example.com/v1"
    assert api_key == "secret-key"
    assert "secret-key" not in get_data_paths().settings_file.read_text(encoding="utf-8")
    assert "secret-key" in get_data_paths().secrets_file.read_text(encoding="utf-8")


def test_settings_service_trims_llm_profile_and_secret():
    service = get_settings_service()
    service.update_llm(
        LLMSettingsUpdate(
            base_url=" https://api.example.com/v1 ",
            api_key=" secret-key ",
            model_name=" model-a ",
            fast_model_name=" model-b ",
            mode=" default ",
            max_concurrent_requests=12,
            clear_api_key=False,
            api_format=" openai ",
        )
    )

    profile, api_key = service.get_llm_runtime_config()

    assert profile.base_url == "https://api.example.com/v1"
    assert profile.model_name == "model-a"
    assert profile.fast_model_name == "model-b"
    assert profile.mode == "default"
    assert profile.api_format == "openai"
    assert api_key == "secret-key"


def test_llm_settings_update_rejects_invalid_concurrency():
    with pytest.raises(ValidationError):
        LLMSettingsUpdate(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model_name="model-a",
            fast_model_name="model-b",
            mode="default",
            max_concurrent_requests=0,
            clear_api_key=False,
            api_format="openai",
        )


def test_settings_service_applies_default_llm_seed_on_first_create(monkeypatch):
    monkeypatch.setenv("CWS_DEFAULT_LLM_BASE_URL", "https://api.longcat.example/openai")
    monkeypatch.setenv("CWS_DEFAULT_LLM_MODEL", "LongCat-Flash-Chat")
    monkeypatch.setenv("CWS_DEFAULT_LLM_FAST_MODEL", "LongCat-Flash-Lite")
    monkeypatch.setenv("CWS_DEFAULT_LLM_API_KEY", "seed-key")

    service = get_settings_service()
    settings = service.get_settings_view()
    profile, api_key = service.get_llm_runtime_config()

    assert settings.llm.profile.has_api_key is True
    assert profile.base_url == "https://api.longcat.example/openai"
    assert profile.model_name == "LongCat-Flash-Chat"
    assert api_key == "seed-key"
    assert "seed-key" not in get_data_paths().settings_file.read_text(encoding="utf-8")


def test_settings_service_seed_does_not_override_existing_user_config(monkeypatch):
    service = get_settings_service()
    service.update_llm(
        LLMSettingsUpdate(
            base_url="https://api.user.example/v1",
            api_key="user-key",
            model_name="user-model",
            fast_model_name="user-fast",
            mode="default",
            max_concurrent_requests=10,
            clear_api_key=False,
        )
    )

    monkeypatch.setenv("CWS_DEFAULT_LLM_BASE_URL", "https://api.longcat.example/openai")
    monkeypatch.setenv("CWS_DEFAULT_LLM_MODEL", "LongCat-Flash-Chat")
    monkeypatch.setenv("CWS_DEFAULT_LLM_FAST_MODEL", "LongCat-Flash-Lite")
    monkeypatch.setenv("CWS_DEFAULT_LLM_API_KEY", "seed-key")

    profile, api_key = service.get_llm_runtime_config()

    assert profile.base_url == "https://api.user.example/v1"
    assert profile.model_name == "user-model"
    assert api_key == "user-key"


def test_settings_reset_does_not_reapply_default_llm_seed(monkeypatch):
    monkeypatch.setenv("CWS_DEFAULT_LLM_BASE_URL", "https://api.longcat.example/openai")
    monkeypatch.setenv("CWS_DEFAULT_LLM_MODEL", "LongCat-Flash-Chat")
    monkeypatch.setenv("CWS_DEFAULT_LLM_FAST_MODEL", "LongCat-Flash-Lite")
    monkeypatch.setenv("CWS_DEFAULT_LLM_API_KEY", "seed-key")

    service = get_settings_service()
    assert service.get_settings_view().llm.profile.has_api_key is True

    reset = service.reset_settings()
    profile, api_key = service.get_llm_runtime_config()

    assert reset.llm.profile.has_api_key is False
    assert profile.base_url == ""
    assert api_key == ""


def test_patch_settings_updates_audio_and_new_game_defaults():
    service = get_settings_service()
    fallback_locale = get_fallback_locale()
    updated = service.patch_settings(
        AppSettingsPatch(
            ui={"audio": {"bgm_volume": 0.7}},
            new_game_defaults={"init_npc_num": 20, "content_locale": fallback_locale},
        )
    )

    assert updated.ui.audio.bgm_volume == 0.7
    assert updated.new_game_defaults.init_npc_num == 20
    assert updated.new_game_defaults.content_locale == fallback_locale


def test_patch_settings_syncs_content_locale_with_ui_locale():
    service = get_settings_service()
    fallback_locale = get_fallback_locale()

    updated = service.patch_settings(
        AppSettingsPatch(
            ui={"locale": fallback_locale},
        )
    )

    assert updated.ui.locale == fallback_locale
    assert updated.new_game_defaults.content_locale == fallback_locale


def test_settings_api_and_start_game(monkeypatch):
    from src.server import main
    default_locale = get_default_locale()
    fallback_locale = get_fallback_locale()

    monkeypatch.setattr(main, "init_game_async", AsyncMock())

    def fake_create_task(coro):
        coro.close()
        return None

    monkeypatch.setattr(main.asyncio, "create_task", fake_create_task)

    settings_res = main.get_settings()
    assert settings_res["ui"]["locale"] == default_locale

    patch_res = main.patch_settings(
        AppSettingsPatch(
            simulation={"auto_save_enabled": True},
            new_game_defaults={"content_locale": fallback_locale},
        )
    )
    assert patch_res["simulation"]["auto_save_enabled"] is True

    start_res = asyncio.run(
        main.start_game(
            main.GameStartRequest(
                content_locale=fallback_locale,
                init_npc_num=18,
                sect_num=4,
                npc_awakening_rate_per_month=0.02,
                world_lore="A fractured world",
            )
        )
    )
    assert start_res["status"] == "ok"
    assert main.game_instance["run_config"]["content_locale"] == fallback_locale
    assert main.game_instance["run_config"]["init_npc_num"] == 18


def test_runtime_run_config_comes_only_from_settings_defaults(monkeypatch):
    from src.server import main

    service = get_settings_service()
    service.patch_settings(
        AppSettingsPatch(
            new_game_defaults={
                "content_locale": get_fallback_locale(),
                "init_npc_num": 22,
                "sect_num": 5,
                "npc_awakening_rate_per_month": 0.03,
                "world_lore": "Fresh defaults",
            }
        )
    )

    monkeypatch.setitem(main.game_instance, "run_config", None)
    runtime = main.get_runtime_run_config()

    assert runtime.content_locale == get_fallback_locale()
    assert runtime.init_npc_num == 22
    assert runtime.sect_num == 5
    assert runtime.npc_awakening_rate_per_month == 0.03
    assert runtime.world_lore == "Fresh defaults"


def test_main_patch_settings_syncs_runtime_locale_and_run_config(monkeypatch):
    from src.server import main

    applied_locales: list[str] = []

    monkeypatch.setattr(main, "apply_runtime_content_locale", lambda lang_code: applied_locales.append(lang_code))
    monkeypatch.setattr(main, "language_manager", "zh-CN")
    monkeypatch.setitem(main.game_instance, "run_config", {"content_locale": "zh-CN"})

    res = main.patch_settings(
        AppSettingsPatch(
            ui={"locale": get_fallback_locale()},
        )
    )

    assert res["ui"]["locale"] == get_fallback_locale()
    assert res["new_game_defaults"]["content_locale"] == get_fallback_locale()
    assert applied_locales == [get_fallback_locale()]
    assert main.game_instance["run_config"]["content_locale"] == get_fallback_locale()


def test_settings_patch_api_returns_200_when_router_serializes_model(monkeypatch):
    from src.server import main

    applied_locales: list[str] = []

    monkeypatch.setattr(main, "apply_runtime_content_locale", lambda lang_code: applied_locales.append(lang_code))
    monkeypatch.setattr(main, "language_manager", "zh-CN")
    monkeypatch.setitem(main.game_instance, "run_config", {"content_locale": "zh-CN"})

    client = TestClient(main.app)
    response = client.patch(
        "/api/settings",
        json={
            "ui": {
                "locale": get_fallback_locale(),
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ui"]["locale"] == get_fallback_locale()
    assert payload["new_game_defaults"]["content_locale"] == get_fallback_locale()
    assert applied_locales == [get_fallback_locale()]


def test_health_api_is_available_before_game_start():
    from src.server import main

    client = TestClient(main.app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_settings_reset_api_returns_200_when_router_serializes_model(monkeypatch):
    from src.server import main

    applied_locales: list[str] = []

    monkeypatch.setattr(main, "apply_runtime_content_locale", lambda lang_code: applied_locales.append(lang_code))
    monkeypatch.setattr(main, "language_manager", "en-US")
    monkeypatch.setitem(main.game_instance, "run_config", {"content_locale": "en-US"})

    client = TestClient(main.app)
    response = client.post("/api/settings/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ui"]["locale"] == get_default_locale()
    assert payload["new_game_defaults"]["content_locale"] == get_default_locale()
    assert applied_locales == [get_default_locale()]


def test_llm_status_api_reports_runtime_failure(monkeypatch):
    from src.server import main

    monkeypatch.setitem(main.game_instance, "llm_check_failed", True)
    monkeypatch.setitem(main.game_instance, "llm_error_message", "身份验证失败")

    client = TestClient(main.app)
    response = client.get("/api/settings/llm/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_config"] is True
    assert payload["last_failure"] == "身份验证失败"


def test_llm_status_api_treats_local_openai_endpoint_as_configured_without_key():
    from src.server import main

    service = get_settings_service()
    service.update_llm(
        LLMSettingsUpdate(
            base_url="http://localhost:11434/v1",
            api_key="",
            model_name="qwen3:8b",
            fast_model_name="qwen3:8b",
            mode="default",
            max_concurrent_requests=4,
            clear_api_key=False,
            api_format="openai",
        )
    )

    client = TestClient(main.app)
    response = client.get("/api/settings/llm/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True


def test_llm_status_api_requires_key_for_remote_endpoint():
    from src.server import main

    service = get_settings_service()
    service.update_llm(
        LLMSettingsUpdate(
            base_url="https://api.example.com/v1",
            api_key="",
            model_name="model-a",
            fast_model_name="model-b",
            mode="default",
            max_concurrent_requests=4,
            clear_api_key=False,
            api_format="openai",
        )
    )

    client = TestClient(main.app)
    response = client.get("/api/settings/llm/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False


def test_llm_settings_api_updates_config_without_exposing_secret():
    from src.server import main

    client = TestClient(main.app)
    response = client.put(
        "/api/settings/llm",
        json={
            "base_url": "https://api.example.com/v1",
            "api_key": "api-route-secret",
            "model_name": "model-a",
            "fast_model_name": "model-b",
            "mode": "default",
            "max_concurrent_requests": 4,
            "clear_api_key": False,
            "api_format": "openai",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["config"]["base_url"] == "https://api.example.com/v1"
    assert payload["config"]["has_api_key"] is True
    assert "api-route-secret" not in response.text

    status_response = client.get("/api/settings/llm/status")
    assert status_response.status_code == 200
    assert status_response.json()["configured"] is True


def test_llm_api_uses_saved_secret_when_testing(monkeypatch):
    from src.server import main

    service = get_settings_service()
    service.update_llm(
        LLMSettingsUpdate(
            base_url="https://api.example.com/v1",
            api_key="stored-secret",
            model_name="model-a",
            fast_model_name="model-b",
            mode="default",
            max_concurrent_requests=10,
            clear_api_key=False,
        )
    )

    captured = {}

    def fake_test_connectivity(config):
        captured["api_key"] = config.api_key
        return True, ""

    monkeypatch.setattr(main, "test_connectivity", fake_test_connectivity)
    res = main.test_llm_connection(
        LLMSettingsUpdate(
            base_url="https://api.example.com/v1",
            api_key="",
            model_name="model-a",
            fast_model_name="model-b",
            mode="default",
            max_concurrent_requests=10,
            clear_api_key=False,
        )
    )

    assert res["status"] == "ok"
    assert captured["api_key"] == "stored-secret"
