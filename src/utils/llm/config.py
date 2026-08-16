"""LLM 配置管理"""

from enum import Enum
from dataclasses import dataclass

from src.config import get_settings_service
from src.utils.config import CONFIG

class LLMMode(str, Enum):
    """LLM 调用模式"""
    NORMAL = "normal"
    FAST = "fast"
    DEFAULT = "default"


@dataclass(frozen=True)
class LLMConfig:
    """LLM 配置数据类"""
    model_name: str
    api_key: str
    base_url: str
    api_format: str = "openai"  # "openai" 或 "anthropic"

    @classmethod
    def from_mode(cls, mode: LLMMode) -> 'LLMConfig':
        """
        根据模式创建配置，从 CONFIG 读取

        Args:
            mode: LLM 调用模式

        Returns:
            LLMConfig: 配置对象
        """
        profile, api_key = get_settings_service().get_llm_runtime_config()
        base_url = profile.base_url
        api_key_value = api_key
        # Profiles saved before api_format was introduced use the OpenAI-compatible API.
        api_format = getattr(profile, "api_format", "openai") or "openai"

        # 根据模式选择模型
        model_name = ""
        if mode == LLMMode.FAST:
            model_name = profile.fast_model_name
            if profile.use_separate_fast_config:
                base_url = profile.fast_base_url
                api_key_value = get_settings_service().get_secrets().fast_api_key
                api_format = getattr(profile, "fast_api_format", "openai") or "openai"
        else:
            # NORMAL or DEFAULT fallback
            model_name = profile.model_name

        return cls(
            model_name=model_name,
            api_key=api_key_value,
            base_url=base_url,
            api_format=api_format,
        )


def get_task_mode(task_name: str) -> LLMMode:
    """
    根据任务名称获取 LLM 模式
    """
    # 从 CONFIG 读取全局模式
    profile, _ = get_settings_service().get_llm_runtime_config()
    global_mode = (profile.mode or "default").lower()
    
    if global_mode == "normal":
        return LLMMode.NORMAL
    elif global_mode == "fast":
        return LLMMode.FAST
    
    # Default 模式：根据 task_name 从细粒度配置中获取
    # 如果配置了 default_modes，则根据任务名称返回对应模式
    default_modes = getattr(CONFIG.llm, "default_modes", {})
    if default_modes and task_name in default_modes:
        task_mode = default_modes[task_name].lower()
        if task_mode == "fast":
            return LLMMode.FAST
        else:
            return LLMMode.NORMAL
    
    # 如果没有配置，默认返回 NORMAL
    return LLMMode.NORMAL
