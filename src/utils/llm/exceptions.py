"""LLM 相关异常定义。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LLMError(Exception):
    """LLM 相关错误的基类"""
    
    def __init__(self, message: str, *, cause: Exception | None = None, **context):
        super().__init__(message)
        self.cause = cause
        self.context = context


class ParseError(LLMError):
    """JSON 解析失败"""
    
    def __init__(self, message: str, *, raw_text: str = ""):
        super().__init__(message, raw_text=raw_text)
        self.raw_text = raw_text


class ConfigError(LLMError):
    """配置错误"""
    pass


class ProviderFailureKind(str, Enum):
    """Transport-level failures before an LLM response can be consumed."""

    HTTP = "http"
    NETWORK = "network"
    INVALID_RESPONSE = "invalid_response"
    UNKNOWN = "unknown"


@dataclass
class ProviderCallError(Exception):
    """Structured provider failure retained across the transport boundary."""

    kind: ProviderFailureKind
    message: str
    status_code: int | None = None
    response_body: str = ""
    provider_message: str = ""
    cause: Exception | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

