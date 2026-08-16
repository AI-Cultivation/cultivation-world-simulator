from __future__ import annotations

from types import SimpleNamespace

from src.server import init_runtime
from src.utils.llm.connectivity import check_llm_profile_connectivity
from src.utils.llm.config import LLMConfig, LLMMode
from src.utils.llm.validation import (
    is_local_llm_endpoint,
    llm_requires_api_key,
)


def test_local_llm_endpoint_detection_accepts_loopback_urls():
    assert is_local_llm_endpoint("http://localhost:11434/v1") is True
    assert is_local_llm_endpoint("http://127.0.0.1:11434/v1") is True
    assert is_local_llm_endpoint("https://api.example.com/v1") is False


def test_api_key_requirement_depends_on_endpoint_and_format():
    assert llm_requires_api_key(base_url="http://localhost:11434/v1", api_format="openai") is False
    assert llm_requires_api_key(base_url="https://api.example.com/v1", api_format="openai") is True
    assert llm_requires_api_key(base_url="http://localhost:11434/v1", api_format="anthropic") is True


def test_init_llm_check_allows_local_ollama_without_api_key(monkeypatch):
    configs = {
        LLMMode.NORMAL: LLMConfig(
            base_url="http://localhost:11434/v1",
            api_key="",
            model_name="qwen3:8b",
            api_format="openai",
        ),
        LLMMode.FAST: LLMConfig(
            base_url="http://localhost:11434/v1",
            api_key="",
            model_name="qwen3:8b",
            api_format="openai",
        ),
    }
    captured = {}

    monkeypatch.setattr(init_runtime.LLMConfig, "from_mode", classmethod(lambda _cls, mode: configs[mode]))

    def fake_test_connectivity(mode, config):
        captured["api_key"] = config.api_key
        return True, ""

    monkeypatch.setattr(init_runtime, "test_connectivity", fake_test_connectivity)

    success, error = init_runtime.check_llm_connectivity()

    assert success is True
    assert error == ""
    assert captured["api_key"] == ""


def test_init_llm_check_still_requires_api_key_for_remote_endpoint(monkeypatch):
    configs = {
        LLMMode.NORMAL: LLMConfig(
            base_url="https://api.example.com/v1",
            api_key="",
            model_name="model-a",
            api_format="openai",
        ),
        LLMMode.FAST: LLMConfig(
            base_url="https://api.example.com/v1",
            api_key="",
            model_name="model-b",
            api_format="openai",
        ),
    }

    monkeypatch.setattr(init_runtime.LLMConfig, "from_mode", classmethod(lambda _cls, mode: configs[mode]))

    success, error = init_runtime.check_llm_connectivity()

    assert success is False
    assert "API Key" in error


def test_profile_connectivity_checks_normal_and_fast_models():
    profile = SimpleNamespace(
        base_url="https://api.example.com/v1",
        model_name="normal-model",
        fast_model_name="fast-model",
        api_format="openai",
    )
    tested_models = []

    def fake_test_connectivity(*, config):
        tested_models.append(config.model_name)
        return True, ""

    success, error = check_llm_profile_connectivity(
        profile=profile,
        api_key="secret",
        test_connectivity=fake_test_connectivity,
    )

    assert success is True
    assert error == ""
    assert tested_models == ["normal-model", "fast-model"]


def test_profile_connectivity_tests_same_model_once():
    profile = SimpleNamespace(
        base_url="https://api.example.com/v1",
        model_name="same-model",
        fast_model_name="same-model",
        api_format="openai",
    )
    tested_models = []

    def fake_test_connectivity(*, config):
        tested_models.append(config.model_name)
        return True, ""

    success, error = check_llm_profile_connectivity(
        profile=profile,
        api_key="secret",
        test_connectivity=fake_test_connectivity,
    )

    assert success is True
    assert error == ""
    assert tested_models == ["same-model"]


def test_profile_connectivity_supports_separate_local_fast_service_without_key():
    profile = SimpleNamespace(
        base_url="https://api.qwen.example/v1",
        model_name="qwen-plus",
        fast_model_name="qwen3:8b",
        api_format="openai",
        use_separate_fast_config=True,
        fast_base_url="http://localhost:11434/v1",
        fast_api_format="openai",
    )
    tested_configs = []

    def fake_test_connectivity(*, config):
        tested_configs.append(config)
        return True, ""

    success, error = check_llm_profile_connectivity(
        profile=profile,
        api_key="qwen-key",
        fast_api_key="",
        test_connectivity=fake_test_connectivity,
    )

    assert success is True
    assert error == ""
    assert [(config.base_url, config.model_name, config.api_key) for config in tested_configs] == [
        ("https://api.qwen.example/v1", "qwen-plus", "qwen-key"),
        ("http://localhost:11434/v1", "qwen3:8b", ""),
    ]


def test_profile_connectivity_labels_fast_model_failure():
    profile = SimpleNamespace(
        base_url="https://api.example.com/v1",
        model_name="normal-model",
        fast_model_name="fast-model",
        api_format="openai",
    )

    def fake_test_connectivity(*, config):
        if config.model_name == "fast-model":
            return False, "model not found"
        return True, ""

    success, error = check_llm_profile_connectivity(
        profile=profile,
        api_key="secret",
        test_connectivity=fake_test_connectivity,
    )

    assert success is False
    assert error == "快速模型连接失败：model not found"
