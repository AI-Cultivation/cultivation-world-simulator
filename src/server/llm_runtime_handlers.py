from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from src.utils.llm.connectivity import check_llm_profile_connectivity


def create_llm_runtime_handlers(
    *,
    runtime: Any,
    manager: Any,
    settings_service: Any,
    create_llm_updated_handler: Callable[..., Any],
    test_connectivity_impl: Callable[..., tuple[bool, str]],
) -> SimpleNamespace:
    def test_connectivity(config):
        return test_connectivity_impl(config=config)

    def test_llm_connection(req) -> dict:
        profile, api_key = settings_service.get_llm_test_payload(req)
        success, error_msg = check_llm_profile_connectivity(
            profile=profile,
            api_key=api_key,
            test_connectivity=test_connectivity,
        )
        if success:
            return {"status": "ok", "message": "连接成功"}
        return {"status": "error", "message": error_msg}

    handle_llm_updated = create_llm_updated_handler(
        runtime=runtime,
        manager=manager,
    )

    async def handle_global_llm_failure(error_message: str) -> None:
        failed, current_error = runtime.get_llm_failure_state()
        if failed and current_error == error_message:
            return

        runtime.set_llm_check_state(failed=True, error_message=error_message)
        runtime.set_paused(True)
        await manager.broadcast(
            {
                "type": "llm_config_required",
                "error": error_message,
            }
        )

    return SimpleNamespace(
        test_connectivity=test_connectivity,
        test_llm_connection=test_llm_connection,
        handle_llm_updated=handle_llm_updated,
        handle_global_llm_failure=handle_global_llm_failure,
    )
