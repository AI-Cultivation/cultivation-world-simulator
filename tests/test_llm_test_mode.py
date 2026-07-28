from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.utils.llm.client import call_llm, call_llm_with_task_name
from src.utils.llm.runtime_mode import is_test_mode_enabled, llm_test_mode_scope
from src.utils.llm.test_mode_fallbacks import TestModeLLMUnavailable, TestModeUnsupportedLLMTask


@pytest.mark.asyncio
async def test_task_call_uses_rule_fallback_without_provider_request():
    with patch("src.utils.llm.client._call_with_requests", new_callable=AsyncMock) as provider:
        with llm_test_mode_scope(True):
            result = await call_llm_with_task_name("relation_delta", "unused-template.txt", infos={})

    assert result == {"delta_a_to_b": 0, "delta_b_to_a": 0}
    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_task_fails_closed_without_provider_request():
    with patch("src.utils.llm.client._call_with_requests", new_callable=AsyncMock) as provider:
        with llm_test_mode_scope(True), pytest.raises(TestModeUnsupportedLLMTask):
            await call_llm_with_task_name("new_unregistered_task", "unused-template.txt", infos={})

    provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_raw_llm_call_is_unavailable_in_test_mode():
    with llm_test_mode_scope(True), pytest.raises(TestModeLLMUnavailable):
        await call_llm("should not be sent")


def test_scope_resets_after_exit():
    assert not is_test_mode_enabled()
    with llm_test_mode_scope(True):
        assert is_test_mode_enabled()
    assert not is_test_mode_enabled()
