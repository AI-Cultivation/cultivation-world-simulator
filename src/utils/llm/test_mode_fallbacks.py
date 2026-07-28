"""Deterministic structured LLM results used by rule-based test runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class TestModeLLMError(RuntimeError):
    """Base error for an LLM operation intentionally unavailable in test mode."""

    __test__ = False


class TestModeUnsupportedLLMTask(TestModeLLMError):
    __test__ = False
    def __init__(self, task_name: str):
        super().__init__(f"No rule fallback is registered for LLM task: {task_name}")
        self.task_name = task_name


class TestModeLLMUnavailable(TestModeLLMError):
    __test__ = False
    def __init__(self, feature: str):
        super().__init__(f"LLM feature is unavailable in rule-based test mode: {feature}")
        self.feature = feature


def _action_decision(infos: Mapping[str, Any]) -> dict[str, Any]:
    avatar_name = str(infos.get("avatar_name", ""))
    return {
        avatar_name: {
            "action_name_params_pairs": [],
            "avatar_thinking": "",
            "short_term_objective": "",
            "current_emotion": "emotion_calm",
        }
    }


def resolve_test_mode_task(task_name: str, infos: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic, parser-safe result without loading prompts or networking."""
    if task_name == "action_decision":
        return _action_decision(infos)
    if task_name == "backstory":
        return {"backstory": ""}
    if task_name == "long_term_objective":
        return {"long_term_objective": ""}
    if task_name == "nickname":
        return {"nickname": "", "thinking": "", "reason": ""}
    if task_name == "story_teller":
        return {"story": ""}
    if task_name == "relation_resolver":
        return {"changed": False}
    if task_name == "relation_delta":
        return {"delta_a_to_b": 0, "delta_b_to_a": 0}
    if task_name == "single_choice":
        # The domain resolver turns an invalid choice into its configured legal fallback.
        return {"choice": "", "thinking": ""}
    if task_name == "sect_thinker":
        return {"sect_thinking": ""}
    if task_name in {"sect_decider", "interaction_feedback", "fate_revelation", "random_minor_event"}:
        return {}
    if task_name.startswith("world_lore_"):
        raise TestModeLLMUnavailable("world_lore_rewrite")
    if task_name in {"custom_content_generation", "roleplay_conversation_turn", "roleplay_conversation_summary"}:
        raise TestModeLLMUnavailable(task_name)
    raise TestModeUnsupportedLLMTask(task_name)


def registered_test_mode_tasks() -> frozenset[str]:
    return frozenset({
        "action_decision", "backstory", "long_term_objective", "nickname", "story_teller",
        "relation_resolver", "relation_delta", "single_choice", "sect_thinker", "sect_decider",
        "interaction_feedback", "fate_revelation", "random_minor_event",
        "custom_content_generation", "roleplay_conversation_turn", "roleplay_conversation_summary",
    })
