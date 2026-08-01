from __future__ import annotations

from src.classes.ai import llm_ai
from src.classes.core.avatar import Avatar
from src.classes.event import Event, is_null_event
from src.config.providers import StaticConfigProvider
from src.run.log import get_logger
from src.sim.runtime_capabilities import get_decision_boundary_gateway


async def phase_decide_actions(world, living_avatars: list[Avatar]) -> None:
    gateway = get_decision_boundary_gateway(world)
    if gateway is not None:
        gateway.before_ai_decision(world)
    controlled_avatar_id = gateway.get_controlled_avatar_id() if gateway is not None else ""

    # 只给“既没在执行动作，也没有待执行计划”的角色补决策，
    # 避免 LLM 覆盖已经排好的行动链。
    avatars_to_decide = [
        avatar
        for avatar in living_avatars
        if avatar.current_action is None and not avatar.has_plans()
        and str(getattr(avatar, "id", "")) != controlled_avatar_id
    ]
    if not avatars_to_decide:
        return

    decide_results = await llm_ai.decide(world, avatars_to_decide)
    for avatar, result in decide_results.items():
        action_name_params_pairs, avatar_thinking, short_term_objective, _event = result
        avatar.load_decide_result_chain(
            action_name_params_pairs,
            avatar_thinking,
            short_term_objective,
        )


def phase_commit_next_plans(living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    for avatar in living_avatars:
        if avatar.current_action is None:
            # 这里仅负责把已存在的计划推进到 current_action，
            # 不参与“该计划从哪来”的决策逻辑。
            start_event = avatar.commit_next_plan()
            if start_event is not None and not is_null_event(start_event):
                events.append(start_event)
    return events


async def _tick_action_round(avatars: list[Avatar], log_label: str) -> tuple[list[Event], set[Avatar]]:
    # 单轮动作执行。返回本轮事件，以及需要在同月继续补跑的角色。
    # 之所以要单独拆出来，是为了把“首轮执行”和“后续重试轮”复用同一套异常处理。
    events: list[Event] = []
    avatars_needing_retry: set[Avatar] = set()

    for avatar in avatars:
        try:
            new_events = await avatar.tick_action()
            if new_events:
                events.extend(new_events)

            if getattr(avatar, "_new_action_set_this_step", False):
                avatars_needing_retry.add(avatar)
        except Exception as exc:
            get_logger().logger.error(
                "Avatar %s(%s) %s failed: %s",
                avatar.name,
                avatar.id,
                log_label,
                exc,
                exc_info=True,
            )
            if hasattr(avatar, "_new_action_set_this_step"):
                avatar._new_action_set_this_step = False

    return events, avatars_needing_retry


async def phase_execute_actions(living_avatars: list[Avatar]) -> list[Event]:
    events: list[Event] = []
    max_local_rounds = StaticConfigProvider.current().max_action_rounds_per_turn()

    # 第一轮先让所有在执行动作的角色各跑一次。
    round_events, avatars_needing_retry = await _tick_action_round(
        living_avatars,
        "tick_action",
    )
    events.extend(round_events)

    round_count = 1
    # 某些动作会在 tick 内无缝接上新的 current_action。
    # 这类角色会在同一个月内继续补跑，但要受全局上限保护，避免死循环。
    while avatars_needing_retry and round_count < max_local_rounds:
        current_avatars = list(avatars_needing_retry)
        round_events, avatars_needing_retry = await _tick_action_round(
            current_avatars,
            "retry tick_action",
        )
        events.extend(round_events)
        round_count += 1

    return events
