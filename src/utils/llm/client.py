"""LLM 客户端核心调用逻辑"""

import json
import urllib.request
import urllib.error
import asyncio
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional

from src.config import get_settings_service
from src.run.log import log_llm_call
from src.utils.config import CONFIG
from .config import LLMMode, LLMConfig, get_task_mode
from .parser import parse_json
from .prompt import build_prompt, load_template
from .exceptions import LLMError, ParseError, ProviderCallError, ProviderFailureKind
from .runtime_mode import is_test_mode_enabled
from .test_mode_fallbacks import TestModeLLMUnavailable, resolve_test_mode_task

# 模块级信号量，懒加载
_SEMAPHORE: Optional[asyncio.Semaphore] = None
_SEMAPHORE_LIMIT: Optional[int] = None
_LLM_FAILURE_HANDLER: Optional[Callable[[str], Awaitable[None] | None]] = None

_QUOTA_ERROR_CODES = {
    "insufficient_quota",
    "quota_exceeded",
    "insufficient_balance",
    "balance_not_enough",
    "balance_not_sufficient",
    "billing_not_active",
    "payment_required",
}
_RATE_LIMIT_ERROR_CODES = {
    "rate_limit_exceeded",
    "rate_limited",
    "too_many_requests",
}
_BILLING_KEYWORDS = (
    "insufficient quota",
    "insufficient_quota",
    "quota exceeded",
    "insufficient balance",
    "insufficient_balance",
    "payment required",
    "billing details",
    "free token quota",
    "余额不足",
    "配额不足",
    "额度不足",
    "额度不够",
)
_BILLING_KEYWORD_HTTP_STATUSES = {400, 402, 403, 429}


class LLMFailureKind(str, Enum):
    CONFIG_REQUIRED = "config_required"
    RATE_LIMITED = "rate_limited"
    TEMPORARY_NETWORK = "temporary_network"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LLMFailureInfo:
    kind: LLMFailureKind
    user_message: str
    http_status: int | None = None
    provider_message: str = ""

    @property
    def is_config_required(self) -> bool:
        return self.kind in {LLMFailureKind.CONFIG_REQUIRED, LLMFailureKind.RATE_LIMITED}


def register_llm_failure_handler(handler: Callable[[str], Awaitable[None] | None] | None) -> None:
    global _LLM_FAILURE_HANDLER
    _LLM_FAILURE_HANDLER = handler


async def _notify_config_required(error_message: str) -> None:
    if _LLM_FAILURE_HANDLER is None:
        return

    result = _LLM_FAILURE_HANDLER(error_message)
    if asyncio.iscoroutine(result):
        await result


def _extract_provider_message(body_str: str) -> str:
    provider_msg = body_str
    try:
        body_json = json.loads(body_str)
        if isinstance(body_json, dict):
            if "error" in body_json and isinstance(body_json["error"], dict):
                provider_msg = body_json["error"].get("message") or body_json["error"].get("msg") or body_str
            elif body_json.get("type") == "error" and "error" in body_json:
                err_obj = body_json["error"]
                if isinstance(err_obj, dict):
                    provider_msg = err_obj.get("message") or body_str
            elif "message" in body_json:
                provider_msg = body_json["message"]
    except Exception:
        pass

    if len(provider_msg) > 200:
        provider_msg = provider_msg[:200] + "..."
    return provider_msg


def _load_provider_body(body_str: str) -> dict | None:
    try:
        body_json = json.loads(body_str)
    except Exception:
        return None
    if isinstance(body_json, dict):
        return body_json
    return None


def _normalize_error_token(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _collect_provider_error_codes(body_str: str) -> set[str]:
    body_json = _load_provider_body(body_str)
    if body_json is None:
        return set()

    values: set[str] = set()

    def collect_from_dict(data: dict) -> None:
        for key in ("code", "type", "error_code", "err_code"):
            value = data.get(key)
            if value is not None:
                values.add(_normalize_error_token(value))

    collect_from_dict(body_json)
    error_obj = body_json.get("error")
    if isinstance(error_obj, dict):
        collect_from_dict(error_obj)

    return {value for value in values if value}


def _has_billing_or_quota_signal(body_str: str, provider_msg: str, http_status: int | None) -> bool:
    error_codes = _collect_provider_error_codes(body_str)
    if error_codes & _QUOTA_ERROR_CODES:
        return True
    if http_status == 429 and error_codes & _RATE_LIMIT_ERROR_CODES:
        return True
    if http_status not in _BILLING_KEYWORD_HTTP_STATUSES:
        return False

    haystack = f"{body_str}\n{provider_msg}".lower()
    return any(keyword in haystack for keyword in _BILLING_KEYWORDS)


def _build_quota_message(
    *,
    code_str: str,
    provider_msg: str,
    base_url: str = "",
) -> str:
    if "longcat.chat" in base_url.lower():
        return (
            f"LongCat API Key 免费 Token 配额不足，请到 LongCat 用量信息页申请提额或更换 Key。"
            f"服务商返回: {provider_msg}"
        )
    return (
        f"额度不足或计费受限({code_str})，请检查账号余额、Token 配额或服务商用量限制。"
        f"服务商返回: {provider_msg}"
    )


def classify_llm_error(error_raw: str | ProviderCallError, *, base_url: str = "") -> LLMFailureInfo:
    if isinstance(error_raw, ProviderCallError):
        if error_raw.kind is ProviderFailureKind.NETWORK:
            return LLMFailureInfo(
                kind=LLMFailureKind.TEMPORARY_NETWORK,
                user_message=f"网络连接失败，请检查 Base URL 是否可达或本地代理设置。(底层错误: {error_raw.message})",
                provider_message=error_raw.message,
            )
        if error_raw.kind is ProviderFailureKind.HTTP:
            return _classify_http_error(
                str(error_raw.status_code or ""),
                error_raw.response_body,
                base_url=base_url,
            )
        return LLMFailureInfo(
            kind=LLMFailureKind.UNKNOWN,
            user_message=f"未知错误: {error_raw.message}",
            provider_message=error_raw.message,
        )

    if error_raw.startswith("NETWORK_ERROR::"):
        reason = error_raw.split("::", 1)[1]
        return LLMFailureInfo(
            kind=LLMFailureKind.TEMPORARY_NETWORK,
            user_message=f"网络连接失败，请检查 Base URL 是否可达或本地代理设置。(底层错误: {reason})",
            provider_message=reason,
        )

    if error_raw.startswith("HTTP_"):
        parts = error_raw.split("::", 1)
        code_str = parts[0].replace("HTTP_", "")
        body_str = parts[1] if len(parts) > 1 else ""
        return _classify_http_error(code_str, body_str, base_url=base_url)

    return LLMFailureInfo(
        kind=LLMFailureKind.UNKNOWN,
        user_message=f"未知错误: {error_raw}",
        provider_message=error_raw,
    )


def _classify_http_error(code_str: str, body_str: str, *, base_url: str) -> LLMFailureInfo:
    provider_msg = _extract_provider_message(body_str)
    try:
        http_status = int(code_str)
    except ValueError:
        http_status = None

    if _has_billing_or_quota_signal(body_str, provider_msg, http_status):
        return LLMFailureInfo(
            kind=LLMFailureKind.RATE_LIMITED,
            http_status=http_status,
            provider_message=provider_msg,
            user_message=_build_quota_message(
                code_str=code_str,
                provider_msg=provider_msg,
                base_url=base_url,
            ),
        )
    if code_str == "401":
            return LLMFailureInfo(
                kind=LLMFailureKind.CONFIG_REQUIRED,
                http_status=http_status,
                provider_message=provider_msg,
                user_message=f"身份验证失败(401)，请检查 API Key 是否填写正确。服务商返回: {provider_msg}",
            )
    if code_str == "403":
            return LLMFailureInfo(
                kind=LLMFailureKind.CONFIG_REQUIRED,
                http_status=http_status,
                provider_message=provider_msg,
                user_message=f"访问被拒绝(403)，可能是模型未授权或 IP 受限。服务商返回: {provider_msg}",
            )
    if code_str == "404":
            return LLMFailureInfo(
                kind=LLMFailureKind.CONFIG_REQUIRED,
                http_status=http_status,
                provider_message=provider_msg,
                user_message=f"找不到服务(404)，请检查 Base URL 是否正确(通常需要以 /v1 结尾)，或模型名是否存在。服务商返回: {provider_msg}",
            )
    if code_str == "429":
            return LLMFailureInfo(
                kind=LLMFailureKind.RATE_LIMITED,
                http_status=http_status,
                provider_message=provider_msg,
                user_message=f"额度超限或请求频繁(429)，请检查账号余额。服务商返回: {provider_msg}",
            )
    if code_str.startswith("5"):
            return LLMFailureInfo(
                kind=LLMFailureKind.PROVIDER_UNAVAILABLE,
                http_status=http_status,
                provider_message=provider_msg,
                user_message=f"服务商内部异常({code_str})，请稍后重试。服务商返回: {provider_msg}",
            )
    return LLMFailureInfo(
        kind=LLMFailureKind.UNKNOWN,
        http_status=http_status,
        provider_message=provider_msg,
        user_message=f"请求失败({code_str})。服务商返回: {provider_msg}",
    )


def _get_semaphore() -> asyncio.Semaphore:
    global _SEMAPHORE, _SEMAPHORE_LIMIT
    if _SEMAPHORE is None:
        limit = get_settings_service().get_llm_runtime_config()[0].max_concurrent_requests
        _SEMAPHORE = asyncio.Semaphore(limit)
        _SEMAPHORE_LIMIT = limit
        return _SEMAPHORE

    limit = get_settings_service().get_llm_runtime_config()[0].max_concurrent_requests
    if _SEMAPHORE_LIMIT != limit:
        _SEMAPHORE = asyncio.Semaphore(limit)
        _SEMAPHORE_LIMIT = limit
    return _SEMAPHORE


def _call_openai(config: LLMConfig, prompt: str) -> str:
    """使用原生 urllib 调用 (OpenAI 兼容接口)"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
        "User-Agent": "CultivationWorldSimulator/1.0"
    }
    data = {
        "model": config.model_name,
        "messages": [{"role": "user", "content": prompt}]
    }

    url = config.base_url
    if not url:
        raise ValueError("Base URL is required for requests mode (OpenAI Compatible)")

    # URL 规范化处理：确保指向 chat/completions
    if "chat/completions" not in url:
        url = url.rstrip("/")
        url = f"{url}/chat/completions"

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise ProviderCallError(
            ProviderFailureKind.HTTP,
            f"HTTP {e.code}: {_extract_provider_message(error_body)}",
            status_code=e.code,
            response_body=error_body,
            provider_message=_extract_provider_message(error_body),
            cause=e,
        ) from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        reason = getattr(e, "reason", str(e))
        raise ProviderCallError(ProviderFailureKind.NETWORK, str(reason), cause=e) from e
    except Exception as e:
        if isinstance(e, ProviderCallError):
            raise
        raise ProviderCallError(ProviderFailureKind.UNKNOWN, str(e), cause=e) from e


def _call_anthropic(config: LLMConfig, prompt: str) -> str:
    """使用原生 urllib 调用 (Anthropic 原生接口)"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config.api_key,
        "anthropic-version": "2023-06-01",
        "User-Agent": "CultivationWorldSimulator/1.0"
    }
    data = {
        "model": config.model_name,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}]
    }

    url = config.base_url
    if not url:
        raise ValueError("Base URL is required for Anthropic API")

    # URL 规范化处理：确保指向 /v1/messages
    if "/messages" not in url:
        url = url.rstrip("/")
        if not url.endswith("/v1"):
            url = f"{url}/v1"
        url = f"{url}/messages"

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
        # Anthropic 响应格式: {"content": [{"type": "text", "text": "..."}]}
        for block in result.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        raise Exception("UNKNOWN_ERROR::Anthropic 响应中未找到 text 内容")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise ProviderCallError(
            ProviderFailureKind.HTTP,
            f"HTTP {e.code}: {_extract_provider_message(error_body)}",
            status_code=e.code,
            response_body=error_body,
            provider_message=_extract_provider_message(error_body),
            cause=e,
        ) from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        reason = getattr(e, "reason", str(e))
        raise ProviderCallError(ProviderFailureKind.NETWORK, str(reason), cause=e) from e
    except Exception as e:
        if isinstance(e, ProviderCallError):
            raise
        raise ProviderCallError(ProviderFailureKind.UNKNOWN, str(e), cause=e) from e


def _call_with_requests(config: LLMConfig, prompt: str) -> str:
    """根据 api_format 分发到对应的调用实现"""
    if config.api_format == "anthropic":
        return _call_anthropic(config, prompt)
    return _call_openai(config, prompt)


async def call_llm(prompt: str, mode: LLMMode = LLMMode.NORMAL) -> str:
    """
    基础 LLM 调用，自动控制并发
    使用 urllib 直接调用 OpenAI 兼容接口
    """
    if is_test_mode_enabled():
        raise TestModeLLMUnavailable("raw_llm_call")

    config = LLMConfig.from_mode(mode)
    semaphore = _get_semaphore()
    
    try:
        async with semaphore:
            result = await asyncio.to_thread(_call_with_requests, config, prompt)
    except Exception as exc:
        failure = classify_llm_error(exc if isinstance(exc, ProviderCallError) else str(exc), base_url=config.base_url)
        if failure.is_config_required:
            await _notify_config_required(failure.user_message)
        raise
    
    log_llm_call(config.model_name, prompt, result)
    return result


async def call_llm_json(
    prompt: str,
    mode: LLMMode = LLMMode.NORMAL,
    max_retries: int | None = None
) -> dict:
    """调用 LLM 并解析为 JSON，带重试"""
    if max_retries is None:
        max_retries = int(getattr(CONFIG.ai, "max_parse_retries", 0))
    
    last_error: ParseError | None = None
    for attempt in range(max_retries + 1):
        response = await call_llm(prompt, mode)
        try:
            return parse_json(response)
        except ParseError as e:
            last_error = e
            if attempt < max_retries:
                continue
            raise LLMError(f"解析失败（重试 {max_retries} 次后）", cause=last_error) from last_error
    
    # This should never be reached, but satisfies type checker.
    raise LLMError("未知错误")


async def call_llm_with_template(
    template_path: Path | str,
    infos: dict,
    mode: LLMMode = LLMMode.NORMAL,
    max_retries: int | None = None
) -> dict:
    """使用模板调用 LLM"""
    template = load_template(template_path)
    prompt = build_prompt(template, infos)
    return await call_llm_json(prompt, mode, max_retries)


async def call_llm_with_task_name(
    task_name: str,
    template_path: Path | str,
    infos: dict,
    max_retries: int | None = None
) -> dict:
    """
    根据任务名称自动选择 LLM 模式并调用
    
    Args:
        task_name: 任务名称，用于在 config.yml 中查找对应的模式
        template_path: 模板路径
        infos: 模板参数
        max_retries: 最大重试次数
        
    Returns:
        dict: LLM 返回的 JSON 数据
    """
    if is_test_mode_enabled():
        return resolve_test_mode_task(task_name, infos)

    mode = get_task_mode(task_name)
    
    return await call_llm_with_template(template_path, infos, mode, max_retries)


def test_connectivity(mode: LLMMode = LLMMode.NORMAL, config: Optional[LLMConfig] = None) -> tuple[bool, str]:
    """
    测试 LLM 服务连通性 (同步版本)
    
    Args:
        mode: 测试使用的模式 (NORMAL/FAST)，如果传入 config 则忽略此参数
        config: 直接使用该配置进行测试
        
    Returns:
        tuple[bool, str]: (是否成功, 错误信息)，成功时错误信息为空字符串
    """
    try:
        if config is None:
            config = LLMConfig.from_mode(mode)
            
        _call_with_requests(config, "Hello, this is a connectivity test. Please reply 'OK'.")
        return True, ""
    except Exception as e:
        return False, classify_llm_error(
            e if isinstance(e, ProviderCallError) else str(e),
            base_url=config.base_url,
        ).user_message
