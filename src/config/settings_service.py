from __future__ import annotations

import json
import os
import shutil
import threading
import time
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .data_paths import get_data_paths
from .settings_schema import (
    AppSettings,
    AppSettingsPatch,
    AppSettingsView,
    AudioSettings,
    LLMConfigView,
    LLMProfile,
    LLMSecrets,
    LLMSettingsUpdate,
    NewGameDefaults,
    RunConfig,
)
from src.i18n.locale_registry import get_default_locale

_SETTINGS_WRITE_LOCK = threading.RLock()
_REPLACE_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4)


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _is_transient_replace_error(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    with _SETTINGS_WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(
            f".{path.name}.{os.getpid()}.{threading.get_ident()}.{time.monotonic_ns()}.tmp"
        )
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            for delay in (*_REPLACE_RETRY_DELAYS, None):
                try:
                    tmp_path.replace(path)
                    return
                except OSError as exc:
                    if delay is None or not _is_transient_replace_error(exc):
                        raise
                    time.sleep(delay)
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass


class SettingsService:
    def __init__(self) -> None:
        self.paths = get_data_paths()

    def build_default_new_game_defaults(self) -> NewGameDefaults:
        return NewGameDefaults(
            content_locale=get_default_locale(),
            init_npc_num=9,
            sect_num=3,
            npc_awakening_rate_per_month=0.01,
            world_lore="",
            world_secret_id="none",
        )

    def _build_default_llm_seed(self) -> tuple[LLMProfile, str] | None:
        base_url = os.environ.get("CWS_DEFAULT_LLM_BASE_URL", "").strip()
        model_name = os.environ.get("CWS_DEFAULT_LLM_MODEL", "").strip()
        fast_model_name = os.environ.get("CWS_DEFAULT_LLM_FAST_MODEL", "").strip()
        api_key = os.environ.get("CWS_DEFAULT_LLM_API_KEY", "").strip()

        if not (base_url and model_name and fast_model_name and api_key):
            return None

        max_concurrent_raw = os.environ.get("CWS_DEFAULT_LLM_MAX_CONCURRENT_REQUESTS", "").strip()
        try:
            max_concurrent = int(max_concurrent_raw) if max_concurrent_raw else 10
        except ValueError:
            max_concurrent = 10

        return (
            LLMProfile(
                base_url=base_url,
                model_name=model_name,
                fast_model_name=fast_model_name,
                mode=os.environ.get("CWS_DEFAULT_LLM_MODE", "default").strip() or "default",
                max_concurrent_requests=max_concurrent,
                has_api_key=True,
                api_format=os.environ.get("CWS_DEFAULT_LLM_API_FORMAT", "openai").strip() or "openai",
            ),
            api_key,
        )

    def build_default_app_settings(self, *, apply_llm_seed: bool = True) -> AppSettings:
        llm_profile = LLMProfile()
        if apply_llm_seed:
            seed = self._build_default_llm_seed()
            if seed is not None:
                llm_profile = seed[0]

        return AppSettings(
            schema_version=2,
            ui={
                "locale": get_default_locale(),
                "audio": AudioSettings(),
            },
            simulation={
                "auto_save_enabled": False,
                "max_auto_saves": 5,
            },
            llm={
                "profile": llm_profile,
            },
            new_game_defaults=self.build_default_new_game_defaults(),
        )

    def _load_model(self, path: Path, model_cls, default_model):
        if not path.exists():
            return default_model, True

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return model_cls(**data), False
        except (OSError, json.JSONDecodeError, ValidationError):
            backup = self.paths.incompatible_dir / f"{path.stem}.corrupt{path.suffix}"
            try:
                shutil.copy2(path, backup)
            except OSError:
                pass
            return default_model, True

    def _save_settings(self, settings: AppSettings) -> None:
        _atomic_write_json(self.paths.settings_file, _model_to_dict(settings))

    def _save_secrets(self, secrets: LLMSecrets) -> None:
        _atomic_write_json(self.paths.secrets_file, _model_to_dict(secrets))

    def get_settings(self) -> AppSettings:
        settings, should_persist = self._load_model(
            self.paths.settings_file,
            AppSettings,
            self.build_default_app_settings(),
        )
        if should_persist:
            self._save_settings(settings)
        return settings

    def get_secrets(self) -> LLMSecrets:
        secrets, should_persist = self._load_model(self.paths.secrets_file, LLMSecrets, LLMSecrets())
        if not should_persist:
            return secrets
        seed = self._build_default_llm_seed()
        if seed is not None:
            settings = self.get_settings()
            seed_profile, seed_key = seed
            if settings.llm.profile == seed_profile:
                secrets.api_key = seed_key
        self._save_secrets(secrets)
        return secrets

    def get_settings_view(self) -> AppSettingsView:
        settings = self.get_settings()
        secrets = self.get_secrets()
        payload = _model_to_dict(settings)
        payload["llm"]["profile"]["has_api_key"] = bool(secrets.api_key)
        return AppSettingsView(**payload)

    def patch_settings(self, patch: AppSettingsPatch) -> AppSettingsView:
        settings = self.get_settings()
        payload = _model_to_dict(settings)
        patch_payload = {
            key: value
            for key, value in _model_to_dict(patch).items()
            if value is not None
        }

        if patch_payload.get("ui"):
            ui_patch = patch_payload["ui"]
            if ui_patch.get("locale") is not None:
                payload["ui"]["locale"] = ui_patch["locale"]
                if not (
                    patch_payload.get("new_game_defaults")
                    and patch_payload["new_game_defaults"].get("content_locale") is not None
                ):
                    payload["new_game_defaults"]["content_locale"] = ui_patch["locale"]
            if ui_patch.get("audio"):
                audio_patch = ui_patch["audio"]
                if audio_patch.get("bgm_volume") is not None:
                    payload["ui"]["audio"]["bgm_volume"] = audio_patch["bgm_volume"]
                if audio_patch.get("sfx_volume") is not None:
                    payload["ui"]["audio"]["sfx_volume"] = audio_patch["sfx_volume"]

        if patch_payload.get("simulation"):
            sim_patch = patch_payload["simulation"]
            if sim_patch.get("auto_save_enabled") is not None:
                payload["simulation"]["auto_save_enabled"] = sim_patch["auto_save_enabled"]
            if sim_patch.get("max_auto_saves") is not None:
                payload["simulation"]["max_auto_saves"] = sim_patch["max_auto_saves"]

        if patch_payload.get("new_game_defaults"):
            draft_patch = patch_payload["new_game_defaults"]
            for key, value in draft_patch.items():
                if value is not None:
                    payload["new_game_defaults"][key] = value

        updated = AppSettings(**payload)
        self._save_settings(updated)
        return self.get_settings_view()

    def reset_settings(self) -> AppSettingsView:
        defaults = self.build_default_app_settings(apply_llm_seed=False)
        self._save_settings(defaults)
        self._save_secrets(LLMSecrets())
        return self.get_settings_view()

    def get_llm_view(self) -> LLMConfigView:
        return LLMConfigView(**_model_to_dict(self.get_settings_view().llm.profile))

    def _normalize_llm_profile_payload(self, update: LLMSettingsUpdate) -> dict[str, Any]:
        return {
            "base_url": update.base_url.strip(),
            "model_name": update.model_name.strip(),
            "fast_model_name": update.fast_model_name.strip(),
            "mode": update.mode.strip() or "default",
            "max_concurrent_requests": update.max_concurrent_requests,
            "api_format": update.api_format.strip() or "openai",
            "use_separate_fast_config": update.use_separate_fast_config,
            "fast_base_url": update.fast_base_url.strip(),
            "fast_api_format": update.fast_api_format.strip() or "openai",
        }

    def _normalize_llm_api_key(self, api_key: str | None) -> str | None:
        if api_key is None:
            return None
        return api_key.strip()

    def update_llm(self, update: LLMSettingsUpdate) -> LLMConfigView:
        settings = self.get_settings()
        secrets = self.get_secrets()
        profile_payload = self._normalize_llm_profile_payload(update)
        candidate_key = self._normalize_llm_api_key(update.api_key)

        profile = LLMProfile(
            base_url=profile_payload["base_url"],
            model_name=profile_payload["model_name"],
            fast_model_name=profile_payload["fast_model_name"],
            mode=profile_payload["mode"],
            max_concurrent_requests=profile_payload["max_concurrent_requests"],
            has_api_key=settings.llm.profile.has_api_key,
            api_format=profile_payload["api_format"],
            use_separate_fast_config=profile_payload["use_separate_fast_config"],
            fast_base_url=profile_payload["fast_base_url"],
            fast_api_format=profile_payload["fast_api_format"],
            has_fast_api_key=settings.llm.profile.has_fast_api_key,
        )

        if update.clear_api_key:
            secrets.api_key = ""
        elif candidate_key:
            secrets.api_key = candidate_key

        candidate_fast_key = self._normalize_llm_api_key(update.fast_api_key)
        if update.clear_fast_api_key:
            secrets.fast_api_key = ""
        elif candidate_fast_key:
            secrets.fast_api_key = candidate_fast_key

        profile.has_api_key = bool(secrets.api_key)
        profile.has_fast_api_key = bool(secrets.fast_api_key)
        settings.llm.profile = profile

        self._save_settings(settings)
        self._save_secrets(secrets)
        return self.get_llm_view()

    def get_llm_runtime_config(self) -> tuple[LLMProfile, str]:
        settings = self.get_settings()
        secrets = self.get_secrets()
        return settings.llm.profile, secrets.api_key

    def get_llm_test_payload(self, update: LLMSettingsUpdate) -> tuple[LLMProfile, str, str]:
        secrets = self.get_secrets()
        profile_payload = self._normalize_llm_profile_payload(update)
        candidate_key = self._normalize_llm_api_key(update.api_key)
        if not candidate_key:
            candidate_key = secrets.api_key
        if update.clear_api_key:
            candidate_key = ""
        candidate_fast_key = self._normalize_llm_api_key(update.fast_api_key)
        if not candidate_fast_key:
            candidate_fast_key = secrets.fast_api_key
        if update.clear_fast_api_key:
            candidate_fast_key = ""
        profile = LLMProfile(
            base_url=profile_payload["base_url"],
            model_name=profile_payload["model_name"],
            fast_model_name=profile_payload["fast_model_name"],
            mode=profile_payload["mode"],
            max_concurrent_requests=profile_payload["max_concurrent_requests"],
            has_api_key=bool(candidate_key),
            api_format=profile_payload["api_format"],
            use_separate_fast_config=profile_payload["use_separate_fast_config"],
            fast_base_url=profile_payload["fast_base_url"],
            fast_api_format=profile_payload["fast_api_format"],
            has_fast_api_key=bool(candidate_fast_key),
        )
        return profile, candidate_key, candidate_fast_key

    def get_new_game_defaults(self) -> NewGameDefaults:
        return deepcopy(self.get_settings().new_game_defaults)

    def get_default_run_config(self) -> RunConfig:
        return RunConfig(**_model_to_dict(self.get_new_game_defaults()))


@lru_cache(maxsize=1)
def get_settings_service() -> SettingsService:
    return SettingsService()


def reset_settings_service_cache() -> None:
    get_settings_service.cache_clear()
