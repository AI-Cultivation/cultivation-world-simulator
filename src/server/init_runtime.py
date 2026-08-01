from __future__ import annotations

from src.utils.llm.client import test_connectivity
from src.utils.llm.config import LLMConfig, LLMMode
from src.utils.llm.validation import llm_requires_api_key


INIT_PHASE_NAMES = {
    0: "scanning_assets",
    1: "loading_map",
    2: "shaping_world_lore",
    3: "initializing_sects",
    4: "generating_avatars",
    5: "preparing_character_profiles",
    6: "generating_initial_events",
}

INIT_PROGRESS_MAP = {
    0: 0,
    1: 10,
    2: 25,
    3: 40,
    4: 55,
    5: 70,
    6: 85,
}


def check_llm_connectivity() -> tuple[bool, str]:
    """Check whether configured NORMAL/FAST LLM endpoints are reachable."""
    try:
        normal_config = LLMConfig.from_mode(LLMMode.NORMAL)
        fast_config = LLMConfig.from_mode(LLMMode.FAST)

        if not normal_config.base_url:
            return False, "LLM 配置不完整：请填写 Base URL"
        if not normal_config.model_name:
            return False, "LLM 配置不完整：请填写智能模型名称"
        if (
            llm_requires_api_key(
                base_url=normal_config.base_url,
                api_format=normal_config.api_format,
            )
            and not normal_config.api_key
        ):
            return False, "LLM 配置不完整：请填写 API Key"

        same_model = (
            normal_config.model_name == fast_config.model_name
            and normal_config.base_url == fast_config.base_url
            and normal_config.api_key == fast_config.api_key
        )

        if same_model:
            print(f"Testing LLM connectivity (Single Model): {normal_config.model_name}")
            success, error = test_connectivity(LLMMode.NORMAL, normal_config)
            if not success:
                return False, f"连接失败：{error}"
            return True, ""

        print(f"Testing normal model connectivity: {normal_config.model_name}")
        success, error = test_connectivity(LLMMode.NORMAL, normal_config)
        if not success:
            return False, f"智能模型连接失败：{error}"

        print(f"Testing fast model connectivity: {fast_config.model_name}")
        success, error = test_connectivity(LLMMode.FAST, fast_config)
        if not success:
            return False, f"快速模型连接失败：{error}"

        return True, ""
    except Exception as exc:
        return False, f"连通性检测异常：{exc}"


def update_init_progress(*, runtime, phase: int, phase_name: str = "") -> None:
    """Update initialization phase/progress on the shared runtime state."""
    resolved_name = phase_name or INIT_PHASE_NAMES.get(phase, "")
    runtime.set_initialization_progress(
        phase=phase,
        phase_name=resolved_name,
        progress=INIT_PROGRESS_MAP.get(phase, phase * 14),
    )
    print(
        f"[Init] Phase {phase}: "
        f"{runtime.get('init_phase_name', resolved_name)} "
        f"({runtime.get('init_progress', 0)}%)"
    )
