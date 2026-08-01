from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.i18n import t
from .mutual_action import MutualAction
from src.classes.event import Event, NULL_EVENT
from src.utils.config import CONFIG
from src.classes.action_runtime import ActionResult, ActionStatus
from src.classes.relation.relation_delta_service import RelationDeltaService
from src.classes.story_event_service import StoryEventKind, StoryEventService

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


class Conversation(MutualAction):
    """交谈：两名角色在同一区域进行交流。

    - 可由"攀谈"触发，或直接发起
    - 仅当双方处于同一 Region 时可启动
    - LLM 负责生成对话内容
    - 会将对话内容与后续故事写入事件系统
    """
    
    # 多语言 ID
    ACTION_NAME_ID = "conversation_action_name"
    DESC_ID = "conversation_description"
    REQUIREMENTS_ID = "conversation_requirements"
    
    # 不需要翻译的常量
    EMOJI = "🗣️"
    PARAMS = {"target_avatar": "AvatarName"}
    RESPONSE_ACTIONS: list[str] = []  # Conversation 自动触发，不需要对方决策
    RESPONSE_EVENT_STYLE = "none"

    def _get_template_path(self) -> Path:
        # 使用专门的 conversation.txt 模板
        return CONFIG.paths.templates / "conversation.txt"

    def _build_prompt_infos(self, target_avatar: "Avatar") -> dict:
        avatar_name_1 = self.avatar.name
        avatar_name_2 = target_avatar.name
        
        # avatar1 使用 expanded_info（包含详细信息和共同事件），避免重复
        expanded_info = self.avatar.get_expanded_info(other_avatar=target_avatar, detailed=True)
        
        avatar_infos = {
            avatar_name_1: expanded_info,
            avatar_name_2: target_avatar.get_info(detailed=True),
        }
        
        # 获取后续计划
        p1 = self.avatar.get_planned_actions_str()
        p2 = target_avatar.get_planned_actions_str()
        planned_actions_str = {
            avatar_name_1: p1,
            avatar_name_2: p2,
        }
        return {
            "avatar_infos": avatar_infos,
            "avatar_name_1": avatar_name_1,
            "avatar_name_2": avatar_name_2,
            "planned_actions": planned_actions_str,
        }

    def _can_start(self, target: "Avatar") -> tuple[bool, str]:
        """交谈无额外检查条件"""
        return True, ""

    # 覆盖 start：自定义事件消息
    def start(self, target_avatar: "Avatar|str", **kwargs) -> Event:
        # 记录开始时间
        self._start_month_stamp = self.world.month_stamp
        
        # Conversation 动作不仅返回 NULL_EVENT 以避免生成“开始交谈”的冗余事件（防止与对话内容事件时序显示混乱），
        # 同时也无需手动 add_event，因为我们希望侧边栏和历史记录都只显示最终的对话内容。
        
        return NULL_EVENT

    def _handle_response_result(self, target: "Avatar", result: dict) -> ActionResult:
        """
        处理 LLM 返回的对话结果，包括对话内容和关系变化。
        Conversation 不需要响应事件（RESPONSE_ACTIONS 为空），直接生成内容。
        """
        thinking = str(result.get("thinking", "")).strip()
        conversation_content = str(result.get("conversation_content", "")).strip()
        target.thinking = thinking

        # 使用开始时间戳
        month_stamp = self._start_month_stamp if self._start_month_stamp is not None else self.world.month_stamp

        events_to_return = []

        # 记录对话内容
        if conversation_content:
            content = t("{avatar1} conversation with {avatar2}: {content}",
                       avatar1=self.avatar.name, avatar2=target.name, content=conversation_content)
            content_event = Event(
                month_stamp, 
                content, 
                related_avatars=[self.avatar.id, target.id]
            )
            self._conversation_result_text = content
            self._conversation_target = target
            events_to_return.append(content_event)
        return ActionResult(status=ActionStatus.COMPLETED, events=events_to_return)

    def step(self, target_avatar: "Avatar|str", **kwargs) -> ActionResult:
        """玩家扮演时转入 runtime 对话会话，否则复用原有异步 LLM 对话逻辑。"""
        target = self._get_target_avatar(target_avatar)
        if target is None or self._is_dead_avatar(target):
            return ActionResult(status=ActionStatus.FAILED, events=[])

        from src.sim.runtime_capabilities import get_decision_boundary_gateway

        gateway = get_decision_boundary_gateway(self.world)
        if gateway is None:
            return super().step(target_avatar=target_avatar)
        if not gateway.controls_avatar(str(self.avatar.id)):
            return super().step(target_avatar=target_avatar)

        session = gateway.get_session()
        conversation_session = session.get("conversation_session") or {}
        is_matching_session = (
            str(conversation_session.get("avatar_id") or "") == str(self.avatar.id)
            and str(conversation_session.get("target_avatar_id") or "") == str(target.id)
        )

        if is_matching_session and str(conversation_session.get("status") or "") == "completed":
            summary_payload = conversation_session.get("last_summary") or {}
            summary_text = str(summary_payload.get("summary", "") or "").strip()
            relation_hint = str(summary_payload.get("relation_hint", "") or "").strip()
            story_hint = str(summary_payload.get("story_hint", "") or "").strip()
            target.thinking = str(conversation_session.get("last_ai_thinking", "") or "")
            events_to_return = []
            if summary_text:
                event = Event(
                    self._start_month_stamp if self._start_month_stamp is not None else self.world.month_stamp,
                    summary_text,
                    related_avatars=[self.avatar.id, target.id],
                )
                self._conversation_result_text = summary_text
                self._conversation_relation_hint = relation_hint
                self._conversation_story_hint = story_hint
                self._conversation_target = target
                events_to_return.append(event)
            session["conversation_session"] = None
            session["pending_request"] = None
            if str(session.get("status") or "") != "inactive":
                session["status"] = "observing"
            return ActionResult(status=ActionStatus.COMPLETED, events=events_to_return)

        if not is_matching_session:
            gateway.begin_conversation(avatar=self.avatar, target_avatar=target)

        return ActionResult(status=ActionStatus.RUNNING, events=[])

    async def finish(self, target_avatar: "Avatar|str") -> list[Event]:
        target = getattr(self, "_conversation_target", None) or self._get_target_avatar(target_avatar)
        result_text = getattr(self, "_conversation_result_text", "")
        relation_hint = str(getattr(self, "_conversation_relation_hint", "") or "").strip()
        story_hint = str(getattr(self, "_conversation_story_hint", "") or "").strip()
        if target is None or not result_text:
            return []

        relation_resolution_text = result_text
        if relation_hint:
            relation_resolution_text = f"{result_text}\n[relation_hint={relation_hint}]"

        a_to_b, b_to_a = await RelationDeltaService.resolve_event_text_delta(
            action_key="conversation",
            avatar_a=self.avatar,
            avatar_b=target,
            event_text=relation_resolution_text,
        )
        RelationDeltaService.apply_bidirectional_delta(self.avatar, target, a_to_b, b_to_a)

        story_event = await StoryEventService.maybe_create_story(
            kind=StoryEventKind.DAILY_SOCIAL,
            month_stamp=self.world.month_stamp,
            start_text=result_text,
            result_text=result_text,
            actors=[self.avatar, target],
            related_avatar_ids=[self.avatar.id, target.id],
            prompt=story_hint,
            allow_relation_changes=False,
        )
        return [story_event] if story_event is not None else []
