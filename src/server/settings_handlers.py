from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable


class SettingsServiceProxy:
    """Delegate settings operations to the current cached service at call time."""

    def __init__(self, get_service: Callable[[], Any]):
        self._get_service = get_service

    def get_settings_view(self):
        return self._get_service().get_settings_view()

    def patch_settings(self, req):
        return self._get_service().patch_settings(req)

    def reset_settings(self):
        return self._get_service().reset_settings()

    def get_default_run_config(self):
        return self._get_service().get_default_run_config()

    def get_llm_view(self):
        return self._get_service().get_llm_view()

    def get_llm_runtime_config(self):
        return self._get_service().get_llm_runtime_config()

    def get_llm_test_payload(self, req):
        return self._get_service().get_llm_test_payload(req)

    def update_llm(self, req):
        return self._get_service().update_llm(req)

    def __getattr__(self, name: str):
        return getattr(self._get_service(), name)


def create_settings_handlers(
    *,
    runtime: Any,
    language_manager: Any,
    settings_service: Any,
    model_to_dict: Callable[[Any], dict],
    apply_runtime_content_locale_impl: Callable[..., None],
) -> SimpleNamespace:
    def apply_runtime_content_locale(lang_code: str) -> None:
        apply_runtime_content_locale_impl(
            runtime=runtime,
            language_manager=language_manager,
            lang_code=lang_code,
        )

    def get_settings() -> dict:
        return model_to_dict(settings_service.get_settings_view())

    def patch_settings_model(req):
        updated = settings_service.patch_settings(req)
        next_locale = str(updated.new_game_defaults.content_locale)
        current_locale = str(language_manager)

        if next_locale and next_locale != current_locale:
            apply_runtime_content_locale(next_locale)

        run_config = runtime.get("run_config")
        if isinstance(run_config, dict):
            run_config["content_locale"] = next_locale

        return updated

    def patch_settings(req) -> dict:
        return model_to_dict(patch_settings_model(req))

    def reset_settings_model():
        updated = settings_service.reset_settings()
        next_locale = str(updated.new_game_defaults.content_locale)
        current_locale = str(language_manager)

        if next_locale and next_locale != current_locale:
            apply_runtime_content_locale(next_locale)

        run_config = runtime.get("run_config")
        if isinstance(run_config, dict):
            run_config["content_locale"] = next_locale

        return updated

    def reset_settings() -> dict:
        return model_to_dict(reset_settings_model())

    return SimpleNamespace(
        apply_runtime_content_locale=apply_runtime_content_locale,
        get_settings=get_settings,
        patch_settings_model=patch_settings_model,
        patch_settings=patch_settings,
        reset_settings_model=reset_settings_model,
        reset_settings=reset_settings,
    )
