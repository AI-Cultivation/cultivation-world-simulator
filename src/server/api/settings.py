from __future__ import annotations

from inspect import isawaitable
from typing import Awaitable, Callable

from fastapi import APIRouter, HTTPException

from src.config import AppSettingsPatch, LLMSettingsUpdate
from src.utils.llm.connectivity import check_llm_profile_connectivity
from src.utils.llm.validation import is_llm_runtime_configured


def create_settings_router(
    *,
    model_to_dict: Callable[[object], dict],
    get_settings_view: Callable[[], object],
    patch_settings: Callable[[AppSettingsPatch], object],
    reset_settings: Callable[[], object],
    get_llm_view: Callable[[], object],
    get_llm_runtime_config: Callable[[], tuple[object, str]],
    get_llm_failure_state: Callable[[], tuple[bool, str]] | None = None,
    get_llm_test_payload: Callable[[LLMSettingsUpdate], tuple[object, str, str]],
    test_connectivity: Callable[..., tuple[bool, str]],
    update_llm: Callable[[LLMSettingsUpdate], object | Awaitable[object]],
    on_llm_updated: Callable[[], Awaitable[None]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/settings")
    def get_settings():
        return model_to_dict(get_settings_view())

    @router.patch("/api/settings")
    def patch_settings_endpoint(req: AppSettingsPatch):
        updated = patch_settings(req)
        return model_to_dict(updated)

    @router.post("/api/settings/reset")
    def reset_settings_endpoint():
        updated = reset_settings()
        return model_to_dict(updated)

    @router.get("/api/settings/llm")
    def get_llm_settings():
        return model_to_dict(get_llm_view())

    @router.get("/api/settings/llm/status")
    def get_llm_status():
        profile, api_key = get_llm_runtime_config()
        configured = is_llm_runtime_configured(profile, api_key)
        requires_config = False
        last_failure = ""
        if get_llm_failure_state is not None:
            requires_config, last_failure = get_llm_failure_state()
        return {
            "configured": configured,
            "requires_config": bool(requires_config),
            "last_failure": last_failure or "",
        }

    @router.post("/api/settings/llm/test")
    def test_llm_connection(req: LLMSettingsUpdate):
        try:
            profile, api_key, fast_api_key = get_llm_test_payload(req)
            success, error_msg = check_llm_profile_connectivity(
                profile=profile,
                api_key=api_key,
                fast_api_key=fast_api_key,
                test_connectivity=test_connectivity,
            )
            if success:
                return {"status": "ok", "message": "连接成功"}
            raise HTTPException(status_code=400, detail=error_msg)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"测试出错: {str(exc)}")

    @router.put("/api/settings/llm")
    async def save_llm_config(req: LLMSettingsUpdate):
        try:
            updated = update_llm(req)
            if isawaitable(updated):
                updated = await updated
            await on_llm_updated()
            return {"status": "ok", "message": "配置已保存", "config": model_to_dict(updated)}
        except Exception as exc:
            import traceback

            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"保存失败: {str(exc)}")

    return router
