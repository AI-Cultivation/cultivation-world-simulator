from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import HTTPException

from src.classes.emotions import EmotionType
from src.i18n import t
from src.server.services.roleplay_action_display import build_roleplay_action_chain_display
from src.server.services.roleplay_conversation_service import (
    generate_roleplay_conversation_reply as _conversation_reply_service,
    summarize_roleplay_conversation as _conversation_summary_service,
)
from src.server.services.roleplay_history import append_interaction_history as _append_interaction_history
from src.server.services.roleplay_prompt_builder import build_prompt_context as _build_prompt_context
from src.server.services.roleplay_state import RoleplayStatus
from src.server.services.roleplay_state_machine import (
    ensure_no_pending_request,
    require_controlled_avatar,
    require_pending_request,
    require_status,
    set_awaiting_choice,
    set_conversing,
    set_observing as _set_observing,
    set_submitting,
    set_waiting_decision as _set_waiting_decision,
)
from src.utils.llm import call_llm_with_task_name


_MAX_INTERACTION_HISTORY = 24


def get_roleplay_session(runtime) -> dict[str, Any]:
    raw_session = runtime.get_roleplay_session()
    session = {key: value for key, value in raw_session.items() if not str(key).startswith("_")}
    pending = session.get("pending_request")
    if isinstance(pending, dict):
        session["pending_request"] = dict(pending)
    conversation_session = session.get("conversation_session")
    if isinstance(conversation_session, dict):
        session["conversation_session"] = dict(conversation_session)
    history = session.get("interaction_history")
    if isinstance(history, list):
        copied_history: list[dict[str, Any]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            copied_item = dict(item)
            actions = copied_item.get("actions")
            if isinstance(actions, list):
                copied_item["actions"] = [
                    {
                        **dict(action),
                        "tokens": [dict(token) for token in action.get("tokens", []) if isinstance(token, dict)],
                    }
                    for action in actions
                    if isinstance(action, dict)
                ]
            copied_history.append(copied_item)
        session["interaction_history"] = copied_history
    return session


def _append_interaction_history(runtime, record: dict[str, Any]) -> None:
    from src.server.services.roleplay_history import append_interaction_history

    append_interaction_history(runtime, record, max_items=_MAX_INTERACTION_HISTORY)


def _find_choice_option_text(pending: dict[str, Any], selected_key: str) -> str:
    options = pending.get("options")
    if isinstance(options, list):
        for option in options:
            if not isinstance(option, dict):
                continue
            if str(option.get("key") or "") != str(selected_key):
                continue
            title = str(option.get("title") or "").strip()
            description = str(option.get("description") or "").strip()
            if title and description:
                return f"{title}：{description}"
            if title:
                return title
            if description:
                return description
    return str(selected_key)


def _build_choice_prompt_text(*, title: str, description: str) -> str:
    clean_title = str(title or "").strip()
    clean_description = str(description or "").strip()
    if clean_description:
        return clean_description
    return clean_title


def _get_choice_option_variant(option) -> str:
    metadata = getattr(option, "metadata", None)
    if not isinstance(metadata, dict):
        return "default"
    raw_variant = str(metadata.get("display_variant") or metadata.get("variant") or "").strip().lower()
    if raw_variant in {"accept", "reject", "default"}:
        return raw_variant
    return "default"


def clear_roleplay_session(runtime) -> None:
    runtime.clear_roleplay_session()


def is_player_controlled_choice_target(*, avatar) -> bool:
    return is_player_controlled_avatar(avatar=avatar)


def is_player_controlled_avatar(*, avatar) -> bool:
    from src.sim.runtime_capabilities import get_decision_boundary_gateway

    gateway = get_decision_boundary_gateway(getattr(avatar, "world", None))
    if gateway is None:
        return False
    return gateway.controls_avatar(str(getattr(avatar, "id", "")))


def _require_world(runtime):
    world = runtime.get("world")
    if world is None:
        raise HTTPException(status_code=503, detail=t("World is not initialized yet"))
    return world


def _find_avatar_or_raise(world, avatar_id: str):
    avatar = world.avatar_manager.get_avatar(avatar_id)
    if avatar is None:
        raise HTTPException(status_code=404, detail=t("Target avatar does not exist"))
    return avatar


def finish_roleplay_choice_wait(runtime, *, avatar_id: str, selected_key: str | None = None) -> dict[str, Any]:
    session = runtime.get_roleplay_session()
    if str(session.get("status") or "") == "inactive":
        return dict(session)
    if str(session.get("controlled_avatar_id") or "") not in ("", str(avatar_id)):
        return dict(session)
    prompt_context = {
        **(session.get("last_prompt_context") or {}),
    }
    if selected_key is not None:
        prompt_context["last_selected_key"] = str(selected_key)
    return _set_observing(runtime, avatar_id=avatar_id, prompt_context=prompt_context)


def begin_roleplay_choice(
    runtime,
    *,
    request,
) -> asyncio.Future:
    avatar = request.avatar
    session = runtime.get_roleplay_session()
    ensure_no_pending_request(session)

    request_id = str(getattr(request, "request_id", "") or f"roleplay-choice-{avatar.id}-{int(time.time() * 1000)}")
    request.request_id = request_id
    request_title = str(getattr(request, "title", "") or t("{avatar_name} needs to make a choice", avatar_name=avatar.name))
    request_description = str(getattr(request, "description", "") or getattr(request, "situation", "") or "")
    options = [
        {
            "key": str(option.key),
            "title": str(option.title),
            "description": str(option.description),
            "variant": _get_choice_option_variant(option),
        }
        for option in getattr(request, "options", [])
    ]
    prompt_context = {
        **_build_prompt_context(avatar),
        "choice_title": request_title,
        "choice_description": request_description,
    }
    choice_future = asyncio.get_running_loop().create_future()
    set_awaiting_choice(
        runtime,
        avatar=avatar,
        request_id=request_id,
        title=request_title,
        description=request_description,
        options=options,
        prompt_context=prompt_context,
        choice_future=choice_future,
        request_model=request,
    )
    choice_prompt_text = _build_choice_prompt_text(title=request_title, description=request_description)
    if choice_prompt_text:
        _append_interaction_history(
            runtime,
            {
                "type": "choice_prompt",
                "text": choice_prompt_text,
            },
        )
    return choice_future


async def _generate_roleplay_conversation_reply(*, avatar, target_avatar, messages: list[dict[str, Any]]) -> dict[str, str]:
    return await _conversation_reply_service(
        avatar=avatar,
        target_avatar=target_avatar,
        messages=messages,
        call_llm=call_llm_with_task_name,
    )


async def _summarize_roleplay_conversation(*, avatar, target_avatar, messages: list[dict[str, Any]]) -> dict[str, str]:
    return await _conversation_summary_service(
        avatar=avatar,
        target_avatar=target_avatar,
        messages=messages,
        call_llm=call_llm_with_task_name,
    )


def begin_roleplay_conversation(runtime, *, avatar, target_avatar) -> dict[str, Any]:
    session = runtime.get_roleplay_session()
    existing = session.get("conversation_session")
    if isinstance(existing, dict):
        if (
            str(existing.get("avatar_id") or "") == str(avatar.id)
            and str(existing.get("target_avatar_id") or "") == str(target_avatar.id)
            and str(existing.get("status") or "") in {"awaiting_player", "awaiting_continue", "completed"}
        ):
            return dict(session)
    ensure_no_pending_request(session)

    request_id = f"roleplay-conversation-{avatar.id}-{target_avatar.id}-{int(time.time() * 1000)}"
    title = t("{avatar_name} is talking with {target_avatar_name}", avatar_name=avatar.name, target_avatar_name=target_avatar.name)
    description = t(
        "World paused and waiting for you to continue speaking as {avatar_name} with {target_avatar_name}.",
        avatar_name=avatar.name,
        target_avatar_name=target_avatar.name,
    )
    messages: list[dict[str, Any]] = []
    return set_conversing(
        runtime,
        avatar=avatar,
        target_avatar=target_avatar,
        request_id=request_id,
        title=title,
        description=description,
        messages=messages,
        prompt_context={
            **_build_prompt_context(avatar),
            "target_avatar_id": str(target_avatar.id),
            "target_avatar_name": target_avatar.name,
            "conversation_title": title,
        },
    )


def start_roleplay(runtime, *, avatar_id: str) -> dict[str, Any]:
    world = _require_world(runtime)
    avatar = _find_avatar_or_raise(world, avatar_id)
    session = runtime.get_roleplay_session()
    current_avatar_id = session.get("controlled_avatar_id")
    if current_avatar_id and str(current_avatar_id) != str(avatar_id):
        raise HTTPException(status_code=409, detail=t("There is already another avatar under roleplay control"))

    prompt_context = _build_prompt_context(avatar)
    if avatar.current_action is None and not avatar.has_plans():
        return _set_waiting_decision(runtime, avatar=avatar, prompt_context=prompt_context)
    return _set_observing(runtime, avatar_id=str(avatar.id), prompt_context=prompt_context)


def stop_roleplay(runtime, *, avatar_id: str | None = None) -> dict[str, Any]:
    session = runtime.get_roleplay_session()
    current_avatar_id = session.get("controlled_avatar_id")
    if avatar_id and current_avatar_id and str(current_avatar_id) != str(avatar_id):
        raise HTTPException(status_code=409, detail=t("Roleplay target does not match"))
    runtime.clear_roleplay_session()
    return get_roleplay_session(runtime)


def maybe_request_roleplay_decision(world) -> bool:
    from src.sim.runtime_capabilities import DecisionBoundaryResult, get_decision_boundary_gateway

    gateway = get_decision_boundary_gateway(world)
    if gateway is None:
        return False
    return gateway.before_ai_decision(world) == DecisionBoundaryResult.WAITING_FOR_PLAYER


def _prepare_roleplay_decision(runtime, *, avatar_id: str, request_id: str, command_text: str) -> dict[str, Any]:
    from src.classes.actions import get_action_infos_str
    from src.classes.core.avatar.info_presenter import get_avatar_ai_context

    world = _require_world(runtime)
    avatar = _find_avatar_or_raise(world, avatar_id)
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}

    require_controlled_avatar(session, avatar_id)
    require_status(session, RoleplayStatus.AWAITING_DECISION, "The current request is not waiting for a roleplay command")
    require_pending_request(pending, request_id, "Roleplay request does not exist or has expired")
    if not str(command_text or "").strip():
        raise HTTPException(status_code=400, detail=t("Please enter a roleplay command"))

    set_submitting(session)
    command_text = str(command_text).strip()
    _append_interaction_history(
        runtime,
        {
            "type": "command",
            "text": command_text,
        },
    )

    observed = world.get_observable_avatars(avatar)
    info = {
        "avatar_name": avatar.name,
        "avatar_info": avatar.get_expanded_info(co_region_avatars=observed, detailed=True),
        "avatar_ai_context": {
            **get_avatar_ai_context(avatar, co_region_avatars=observed),
            "player_command": command_text,
            "decision_mode": "player_roleplay",
        },
        "world_info": world.get_info(avatar=avatar, detailed=True),
        "world_lore": world.world_lore.text,
        "general_action_infos": get_action_infos_str(avatar),
        "player_command": command_text,
    }
    return {
        "avatar_id": str(avatar.id),
        "avatar_name": avatar.name,
        "request_id": request_id,
        "command_text": command_text,
        "info": info,
    }


def _commit_roleplay_decision(runtime, *, prepared: dict[str, Any], response: Any) -> dict[str, Any]:
    world = _require_world(runtime)
    avatar = _find_avatar_or_raise(world, prepared["avatar_id"])
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}
    require_controlled_avatar(session, prepared["avatar_id"])
    require_status(session, RoleplayStatus.SUBMITTING, "The roleplay request is no longer being submitted")
    require_pending_request(pending, prepared["request_id"], "Roleplay request does not exist or has expired")

    command_text = prepared["command_text"]
    avatar_name = prepared["avatar_name"]
    payload = response.get(avatar_name, {}) if isinstance(response, dict) else {}
    raw_pairs = payload.get("action_name_params_pairs", [])
    pairs = []
    for item in raw_pairs:
        if isinstance(item, list) and len(item) == 2:
            pairs.append((item[0], item[1] or {}))
        elif isinstance(item, dict) and "action_name" in item and "action_params" in item:
            pairs.append((item["action_name"], item["action_params"] or {}))

    if not pairs:
        session["status"] = RoleplayStatus.AWAITING_DECISION.value
        runtime.set_roleplay_auto_paused(True)
        _append_interaction_history(
            runtime,
            {
                "type": "error",
                "text": t("Failed to generate a valid action plan from this command"),
            },
        )
        raise HTTPException(status_code=422, detail=t("Failed to generate a valid action plan from this command"))

    avatar_thinking = str(payload.get("avatar_thinking", payload.get("thinking", "")) or command_text)
    short_term_objective = str(payload.get("short_term_objective", "") or command_text)
    raw_emotion = str(payload.get("current_emotion", "") or "")
    try:
        avatar.emotion = EmotionType(raw_emotion)
    except ValueError:
        pass

    avatar.load_decide_result_chain(pairs, avatar_thinking, short_term_objective)
    _append_interaction_history(
        runtime,
        {
            "type": "action_chain",
            "actions": build_roleplay_action_chain_display(pairs),
        },
    )
    _set_observing(
        runtime,
        avatar_id=str(avatar.id),
        prompt_context={
            **_build_prompt_context(avatar),
            "last_player_command": command_text,
        },
    )
    return {
        "status": "ok",
        "message": t("Roleplay command submitted"),
        "planned_action_count": len(pairs),
    }


def _restore_roleplay_decision_wait(runtime, *, avatar_id: str, request_id: str) -> None:
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}
    if (
        str(session.get("controlled_avatar_id") or "") == str(avatar_id)
        and str(session.get("status") or "") == RoleplayStatus.SUBMITTING.value
        and str(pending.get("request_id") or "") == str(request_id)
    ):
        session["status"] = RoleplayStatus.AWAITING_DECISION.value
        runtime.set_roleplay_auto_paused(True)


async def submit_roleplay_decision(runtime, *, avatar_id: str, request_id: str, command_text: str) -> dict[str, Any]:
    """Submit a decision without holding the mutation lock during LLM I/O."""
    prepared = await runtime.run_mutation(
        _prepare_roleplay_decision,
        runtime,
        avatar_id=avatar_id,
        request_id=request_id,
        command_text=command_text,
    )
    try:
        from src.utils.config import CONFIG as current_config

        response = await call_llm_with_task_name(
            "action_decision",
            current_config.paths.templates / "ai.txt",
            prepared["info"],
        )
    except Exception:
        await runtime.run_mutation(
            _restore_roleplay_decision_wait,
            runtime,
            avatar_id=avatar_id,
            request_id=request_id,
        )
        raise
    return await runtime.run_mutation(_commit_roleplay_decision, runtime, prepared=prepared, response=response)


async def submit_roleplay_choice(runtime, *, avatar_id: str, request_id: str, selected_key: str) -> dict[str, Any]:
    world = _require_world(runtime)
    _find_avatar_or_raise(world, avatar_id)
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}

    require_controlled_avatar(session, avatar_id)
    require_status(session, RoleplayStatus.AWAITING_CHOICE, "The current request is not waiting for a roleplay choice")
    require_pending_request(pending, request_id, "Roleplay request does not exist or has expired")

    choice_future = session.get("_choice_future")
    if choice_future is None:
        raise HTTPException(status_code=409, detail=t("Roleplay choice state is invalid, please trigger it again"))
    if hasattr(choice_future, "done") and choice_future.done():
        raise HTTPException(status_code=409, detail=t("This roleplay choice has already been handled"))

    set_submitting(session)
    _append_interaction_history(
        runtime,
        {
            "type": "choice",
            "text": _find_choice_option_text(pending, str(selected_key)),
        },
    )
    choice_future.set_result(str(selected_key))
    return {
        "status": "ok",
        "message": t("Roleplay choice submitted"),
        "selected_key": str(selected_key),
    }


def _prepare_roleplay_conversation_turn(runtime, *, avatar_id: str, request_id: str, message: str) -> dict[str, Any]:
    world = _require_world(runtime)
    avatar = _find_avatar_or_raise(world, avatar_id)
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}
    conversation_session = session.get("conversation_session") or {}

    require_controlled_avatar(session, avatar_id)
    require_status(session, RoleplayStatus.CONVERSING, "The current request is not in a roleplay conversation")
    require_pending_request(pending, request_id, "Roleplay conversation request does not exist or has expired")
    if str(conversation_session.get("request_id") or "") != str(request_id):
        raise HTTPException(status_code=404, detail=t("Roleplay conversation session does not exist or has expired"))
    if not str(message or "").strip():
        raise HTTPException(status_code=400, detail=t("Please enter dialogue content"))

    target_avatar = _find_avatar_or_raise(world, str(conversation_session.get("target_avatar_id") or ""))
    set_submitting(session)

    messages = list(conversation_session.get("messages") or [])
    player_message = {
        "id": f"msg-player-{int(time.time() * 1000)}",
        "role": "player",
        "speaker_avatar_id": str(avatar.id),
        "speaker_name": avatar.name,
        "content": str(message).strip(),
        "created_at": time.time(),
    }
    messages.append(player_message)
    _append_interaction_history(
        runtime,
        {
            "type": "conversation_player",
            "text": player_message["content"],
        },
    )

    return {
        "avatar_id": str(avatar.id),
        "target_avatar_id": str(target_avatar.id),
        "request_id": request_id,
        "messages": messages,
        "player_message": player_message,
    }


def _commit_roleplay_conversation_turn(runtime, *, prepared: dict[str, Any], reply_payload: dict[str, str]) -> dict[str, Any]:
    world = _require_world(runtime)
    avatar = _find_avatar_or_raise(world, prepared["avatar_id"])
    target_avatar = _find_avatar_or_raise(world, prepared["target_avatar_id"])
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}
    conversation_session = session.get("conversation_session") or {}
    require_controlled_avatar(session, prepared["avatar_id"])
    require_status(session, RoleplayStatus.SUBMITTING, "The roleplay request is no longer being submitted")
    require_pending_request(pending, prepared["request_id"], "Roleplay conversation request does not exist or has expired")
    if str(conversation_session.get("request_id") or "") != str(prepared["request_id"]):
        raise HTTPException(status_code=404, detail=t("Roleplay conversation session does not exist or has expired"))

    messages = list(prepared["messages"])
    player_message = prepared["player_message"]
    reply_text = str(reply_payload.get("reply_content", "") or "").strip()
    ai_thinking = str(reply_payload.get("speaker_thinking", "") or "").strip()
    reply_message = {
        "id": f"msg-target-{int(time.time() * 1000)}",
        "role": "assistant",
        "speaker_avatar_id": str(target_avatar.id),
        "speaker_name": target_avatar.name,
        "content": reply_text,
        "created_at": time.time(),
    }
    messages.append(reply_message)
    _append_interaction_history(
        runtime,
        {
            "type": "conversation_assistant",
            "text": reply_text,
        },
    )

    conversation_session["messages"] = messages
    conversation_session["status"] = "awaiting_player"
    conversation_session["last_ai_thinking"] = ai_thinking
    pending["messages"] = list(messages)
    session["pending_request"] = pending
    session["conversation_session"] = conversation_session
    session["status"] = RoleplayStatus.CONVERSING.value
    session["last_prompt_context"] = {
        **(session.get("last_prompt_context") or {}),
        "last_player_message": player_message["content"],
        "last_target_reply": reply_text,
    }
    target_avatar.thinking = ai_thinking
    runtime.set_roleplay_auto_paused(True)
    return {
        "status": "ok",
        "message": t("Conversation updated"),
        "messages": list(messages),
        "reply": reply_text,
    }


def _restore_roleplay_conversation_wait(runtime, *, avatar_id: str, request_id: str) -> None:
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}
    if (
        str(session.get("controlled_avatar_id") or "") == str(avatar_id)
        and str(session.get("status") or "") == RoleplayStatus.SUBMITTING.value
        and str(pending.get("request_id") or "") == str(request_id)
    ):
        session["status"] = RoleplayStatus.CONVERSING.value
        runtime.set_roleplay_auto_paused(True)


async def submit_roleplay_conversation_turn(runtime, *, avatar_id: str, request_id: str, message: str) -> dict[str, Any]:
    """Send one turn while allowing unrelated world mutations during LLM I/O."""
    prepared = await runtime.run_mutation(
        _prepare_roleplay_conversation_turn,
        runtime,
        avatar_id=avatar_id,
        request_id=request_id,
        message=message,
    )
    try:
        reply_payload = await _generate_roleplay_conversation_reply(
            avatar=_find_avatar_or_raise(_require_world(runtime), prepared["avatar_id"]),
            target_avatar=_find_avatar_or_raise(_require_world(runtime), prepared["target_avatar_id"]),
            messages=prepared["messages"],
        )
    except Exception:
        await runtime.run_mutation(
            _restore_roleplay_conversation_wait,
            runtime,
            avatar_id=avatar_id,
            request_id=request_id,
        )
        raise
    return await runtime.run_mutation(
        _commit_roleplay_conversation_turn,
        runtime,
        prepared=prepared,
        reply_payload=reply_payload,
    )


def _prepare_end_roleplay_conversation(runtime, *, avatar_id: str, request_id: str) -> dict[str, Any]:
    world = _require_world(runtime)
    avatar = _find_avatar_or_raise(world, avatar_id)
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}
    conversation_session = session.get("conversation_session") or {}

    require_controlled_avatar(session, avatar_id)
    require_status(session, RoleplayStatus.CONVERSING, "The current request is not in a roleplay conversation")
    require_pending_request(pending, request_id, "Roleplay conversation request does not exist or has expired")
    if str(conversation_session.get("request_id") or "") != str(request_id):
        raise HTTPException(status_code=404, detail=t("Roleplay conversation session does not exist or has expired"))

    target_avatar = _find_avatar_or_raise(world, str(conversation_session.get("target_avatar_id") or ""))
    messages = list(conversation_session.get("messages") or [])
    set_submitting(session)
    return {
        "avatar_id": str(avatar.id),
        "target_avatar_id": str(target_avatar.id),
        "request_id": request_id,
        "messages": messages,
    }


def _commit_end_roleplay_conversation(runtime, *, prepared: dict[str, Any], summary_payload: dict[str, str]) -> dict[str, Any]:
    world = _require_world(runtime)
    avatar = _find_avatar_or_raise(world, prepared["avatar_id"])
    target_avatar = _find_avatar_or_raise(world, prepared["target_avatar_id"])
    session = runtime.get_roleplay_session()
    pending = session.get("pending_request") or {}
    conversation_session = session.get("conversation_session") or {}
    require_controlled_avatar(session, prepared["avatar_id"])
    require_status(session, RoleplayStatus.SUBMITTING, "The roleplay request is no longer being submitted")
    require_pending_request(pending, prepared["request_id"], "Roleplay conversation request does not exist or has expired")
    if str(conversation_session.get("request_id") or "") != str(prepared["request_id"]):
        raise HTTPException(status_code=404, detail=t("Roleplay conversation session does not exist or has expired"))

    summary_text = str(summary_payload.get("summary", "") or "").strip()
    _append_interaction_history(
        runtime,
        {
            "type": "conversation_summary",
            "text": summary_text,
        },
    )

    conversation_session["status"] = "completed"
    conversation_session["last_summary"] = dict(summary_payload)
    session["conversation_session"] = conversation_session
    session["pending_request"] = None
    session["status"] = RoleplayStatus.OBSERVING.value
    session["last_prompt_context"] = {
        **(session.get("last_prompt_context") or {}),
        "last_conversation_summary": summary_text,
        "target_avatar_name": target_avatar.name,
    }
    runtime.set_roleplay_auto_paused(False)
    return {
        "status": "ok",
        "message": t("Conversation ended"),
        "summary": summary_text,
        "relation_hint": str(summary_payload.get("relation_hint", "") or ""),
        "story_hint": str(summary_payload.get("story_hint", "") or ""),
    }


async def end_roleplay_conversation(runtime, *, avatar_id: str, request_id: str) -> dict[str, Any]:
    prepared = await runtime.run_mutation(
        _prepare_end_roleplay_conversation,
        runtime,
        avatar_id=avatar_id,
        request_id=request_id,
    )
    try:
        summary_payload = await _summarize_roleplay_conversation(
            avatar=_find_avatar_or_raise(_require_world(runtime), prepared["avatar_id"]),
            target_avatar=_find_avatar_or_raise(_require_world(runtime), prepared["target_avatar_id"]),
            messages=prepared["messages"],
        )
    except Exception:
        await runtime.run_mutation(
            _restore_roleplay_conversation_wait,
            runtime,
            avatar_id=avatar_id,
            request_id=request_id,
        )
        raise
    return await runtime.run_mutation(
        _commit_end_roleplay_conversation,
        runtime,
        prepared=prepared,
        summary_payload=summary_payload,
    )
