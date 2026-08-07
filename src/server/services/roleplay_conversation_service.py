from __future__ import annotations

from typing import Any, Callable

from src.i18n import t
from src.utils.llm import call_llm_with_task_name
from src.utils.strings import to_json_str_with_intent


def build_conversation_history_payload(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for item in messages[-12:]:
        payload.append(
            {
                "role": str(item.get("role", "")),
                "speaker_name": str(item.get("speaker_name", "")),
                "content": str(item.get("content", "")),
            }
        )
    return payload


def build_fallback_conversation_reply(*, target_avatar, last_player_message: str) -> tuple[str, str]:
    if not last_player_message.strip():
        return t("The other party falls silent for a moment and does not reply immediately."), ""
    return t("{target_avatar_name} pauses to think and responds to the topic.", target_avatar_name=target_avatar.name), ""


async def generate_roleplay_conversation_reply(
    *,
    avatar,
    target_avatar,
    messages: list[dict[str, Any]],
    call_llm: Callable[..., Any] = call_llm_with_task_name,
) -> dict[str, str]:
    world = avatar.world
    info = {
        "avatar_name": avatar.name,
        "target_avatar_name": target_avatar.name,
        "world_info": to_json_str_with_intent(world.get_info(avatar=avatar, detailed=True)),
        "avatar_infos": to_json_str_with_intent(
            {
                avatar.name: avatar.get_expanded_info(other_avatar=target_avatar, detailed=True),
                target_avatar.name: target_avatar.get_info(detailed=True),
            }
        ),
        "conversation_history": to_json_str_with_intent(build_conversation_history_payload(messages)),
    }
    # Read at call time: locale/resource configuration may change while the
    # server remains alive.
    from src.utils.config import CONFIG

    template_path = CONFIG.paths.templates / "roleplay_conversation_turn.txt"
    try:
        response = await call_llm("roleplay_conversation_turn", template_path, info)
        payload = response.get(target_avatar.name, {}) if isinstance(response, dict) else {}
        reply = str(payload.get("reply_content", payload.get("conversation_content", "")) or "").strip()
        thinking = str(payload.get("speaker_thinking", payload.get("thinking", "")) or "").strip()
        if reply:
            return {"reply_content": reply, "speaker_thinking": thinking}
    except Exception:
        pass

    last_player_message = str(messages[-1].get("content", "") if messages else "")
    fallback_reply, fallback_thinking = build_fallback_conversation_reply(
        target_avatar=target_avatar,
        last_player_message=last_player_message,
    )
    return {
        "reply_content": fallback_reply,
        "speaker_thinking": fallback_thinking,
    }


def build_fallback_conversation_summary(*, avatar, target_avatar, messages: list[dict[str, Any]]) -> dict[str, str]:
    turns = max(sum(1 for item in messages if item.get("role") == "player"), 1)
    summary = t(
        "{avatar_name} and {target_avatar_name} talked for {turns} turns and both gained a new impression of the topic at hand.",
        avatar_name=avatar.name,
        target_avatar_name=target_avatar.name,
        turns=turns,
    )
    return {
        "summary": summary,
        "relation_hint": "",
        "story_hint": "",
    }


async def summarize_roleplay_conversation(
    *,
    avatar,
    target_avatar,
    messages: list[dict[str, Any]],
    call_llm: Callable[..., Any] = call_llm_with_task_name,
) -> dict[str, str]:
    world = avatar.world
    info = {
        "avatar_name": avatar.name,
        "target_avatar_name": target_avatar.name,
        "world_info": to_json_str_with_intent(world.get_info(avatar=avatar, detailed=True)),
        "avatar_infos": to_json_str_with_intent(
            {
                avatar.name: avatar.get_expanded_info(other_avatar=target_avatar, detailed=True),
                target_avatar.name: target_avatar.get_info(detailed=True),
            }
        ),
        "conversation_history": to_json_str_with_intent(build_conversation_history_payload(messages)),
    }
    from src.utils.config import CONFIG

    template_path = CONFIG.paths.templates / "roleplay_conversation_summary.txt"
    try:
        response = await call_llm("roleplay_conversation_summary", template_path, info)
        if isinstance(response, dict):
            summary = str(response.get("summary", "") or "").strip()
            relation_hint = str(response.get("relation_hint", "") or "").strip()
            story_hint = str(response.get("story_hint", "") or "").strip()
            if summary:
                return {
                    "summary": summary,
                    "relation_hint": relation_hint,
                    "story_hint": story_hint,
                }
    except Exception:
        pass
    return build_fallback_conversation_summary(avatar=avatar, target_avatar=target_avatar, messages=messages)
