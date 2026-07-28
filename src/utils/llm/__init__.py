"""
LLM 调用模块

提供三个核心 API：
- call_llm: 基础调用，返回原始文本
- call_llm_json: 调用并解析为 JSON
- call_llm_with_template: 使用模板调用（最常用）
"""

from .client import (
    call_llm, 
    call_llm_json, 
    call_llm_with_template, 
    call_llm_with_task_name,
    test_connectivity
)
from .config import LLMMode, get_task_mode
from .exceptions import LLMError, ParseError, ConfigError
from .runtime_mode import is_test_mode_enabled, is_world_test_mode, llm_test_mode_scope

__all__ = [
    "call_llm",
    "call_llm_json", 
    "call_llm_with_template",
    "call_llm_with_task_name",
    "test_connectivity",
    "LLMMode",
    "get_task_mode",
    "LLMError",
    "ParseError",
    "ConfigError",
    "is_test_mode_enabled",
    "is_world_test_mode",
    "llm_test_mode_scope",
]
