import asyncio
from fastapi import HTTPException
import pytest
from unittest.mock import AsyncMock, Mock, patch

from src.server.runtime import DEFAULT_GAME_STATE, GameSessionRuntime
from src.server.services.roleplay_service import submit_roleplay_choice
from src.systems.single_choice import (
    ChoiceSource,
    FallbackMode,
    FallbackPolicy,
    ItemDisposition,
    ItemExchangeKind,
    ItemExchangeRequest,
    RejectMode,
    SingleChoiceRequest,
    decide_single_choice,
    resolve_item_exchange,
)
from src.utils.config import CONFIG


class MockAvatar:
    def __init__(self):
        self.name = "TestAvatar"
        self.id = "avatar_1"
        self.weapon = None
        self.auxiliary = None
        self.technique = None
        self.world = Mock()
        self.world.static_info = {}
        self.world.get_observable_avatars = Mock(return_value=[])
        self.world.event_manager.get_major_events_by_avatar = Mock(return_value=[])
        self.world.event_manager.get_minor_events_by_avatar = Mock(return_value=[])
        self.world.avatar_manager.get_avatar = Mock(side_effect=lambda avatar_id: self if avatar_id == self.id else None)
        self.change_weapon = Mock()
        self.sell_weapon = Mock(return_value=100)
        self.consume_elixir = Mock()
        self.sell_elixir = Mock(return_value=50)
        self.current_action_name = "thinking"
        self.short_term_objective = ""
        self.thinking = ""

    def get_info(self, detailed=False):
        return {"name": self.name}


class MockItem:
    def __init__(self, name):
        self.name = name
        self.realm = Mock()
        self.realm.__str__ = Mock(return_value="TestRealm")

    def get_info(self, detailed=False):
        return f"Info({self.name})"


@pytest.mark.asyncio
async def test_decide_single_choice_accepts_valid_choice():
    avatar = MockAvatar()
    request = SingleChoiceRequest(
        task_name="single_choice",
        template_path=CONFIG.paths.templates / "single_choice.txt",
        avatar=avatar,
        situation="Context",
        options=[],
        fallback_policy=FallbackPolicy(FallbackMode.FIRST_OPTION),
    )
    request.options = [
        Mock(key="ACCEPT", title="Accept", description="Accept new item"),
        Mock(key="REJECT", title="Reject", description="Reject new item"),
    ]

    with patch(
        "src.systems.single_choice.engine.call_llm_with_task_name",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = {"choice": "REJECT", "thinking": "keep old one"}
        decision = await decide_single_choice(request)

    assert decision.selected_key == "REJECT"
    assert decision.source == ChoiceSource.LLM
    assert decision.used_fallback is False


@pytest.mark.asyncio
async def test_decide_single_choice_falls_back_on_invalid_choice():
    avatar = MockAvatar()
    request = SingleChoiceRequest(
        task_name="single_choice",
        template_path=CONFIG.paths.templates / "single_choice.txt",
        avatar=avatar,
        situation="Context",
        options=[
            Mock(key="ACCEPT", title="Accept", description="Accept new item"),
            Mock(key="REJECT", title="Reject", description="Reject new item"),
        ],
        fallback_policy=FallbackPolicy(FallbackMode.PREFERRED_KEY, preferred_key="ACCEPT"),
    )

    with patch(
        "src.systems.single_choice.engine.call_llm_with_task_name",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = {"choice": "UNKNOWN"}
        decision = await decide_single_choice(request)

    assert decision.selected_key == "ACCEPT"
    assert decision.source == ChoiceSource.FALLBACK
    assert decision.used_fallback is True


@pytest.mark.asyncio
async def test_weapon_auto_equip_without_llm():
    avatar = MockAvatar()
    new_weapon = MockItem("NewSword")

    with patch(
        "src.systems.single_choice.engine.call_llm_with_task_name",
        new_callable=AsyncMock,
    ) as mock_llm:
        outcome = await resolve_item_exchange(
            ItemExchangeRequest(
                avatar=avatar,
                new_item=new_weapon,
                kind=ItemExchangeKind.WEAPON,
                scene_intro="Context",
                reject_mode=RejectMode.ABANDON_NEW,
                auto_accept_when_empty=True,
            )
        )

    assert outcome.accepted is True
    assert outcome.action == ItemDisposition.AUTO_ACCEPTED
    assert "获得了TestRealm兵器『NewSword』并装备" in outcome.result_text
    avatar.change_weapon.assert_called_once_with(new_weapon)
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_weapon_swap_accept_sells_old():
    avatar = MockAvatar()
    old_weapon = MockItem("OldSword")
    new_weapon = MockItem("NewSword")
    avatar.weapon = old_weapon

    with patch(
        "src.systems.single_choice.engine.call_llm_with_task_name",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = {"choice": "ACCEPT"}
        outcome = await resolve_item_exchange(
            ItemExchangeRequest(
                avatar=avatar,
                new_item=new_weapon,
                kind=ItemExchangeKind.WEAPON,
                scene_intro="Context",
                reject_mode=RejectMode.SELL_NEW,
                auto_accept_when_empty=False,
            )
        )

    assert outcome.accepted is True
    assert outcome.action == ItemDisposition.REPLACED_OLD
    assert "换上了TestRealm兵器『NewSword』" in outcome.result_text
    avatar.sell_weapon.assert_called_once_with(old_weapon)
    avatar.change_weapon.assert_called_once_with(new_weapon)
    mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_elixir_reject_sells_new():
    avatar = MockAvatar()
    new_elixir = MockItem("PowerPill")

    with patch(
        "src.systems.single_choice.engine.call_llm_with_task_name",
        new_callable=AsyncMock,
    ) as mock_llm:
        mock_llm.return_value = {"choice": "REJECT"}
        outcome = await resolve_item_exchange(
            ItemExchangeRequest(
                avatar=avatar,
                new_item=new_elixir,
                kind=ItemExchangeKind.ELIXIR,
                scene_intro="Context",
                reject_mode=RejectMode.SELL_NEW,
                auto_accept_when_empty=False,
            )
        )

    assert outcome.accepted is False
    assert outcome.action == ItemDisposition.SOLD_NEW
    assert "卖掉了新获得的PowerPill" in outcome.result_text
    avatar.sell_elixir.assert_called_once_with(new_elixir)
    avatar.consume_elixir.assert_not_called()


@pytest.mark.asyncio
async def test_roleplay_choice_waits_for_player_submission_and_resumes():
    avatar = MockAvatar()
    runtime = GameSessionRuntime(
        {
            **DEFAULT_GAME_STATE,
            "roleplay_session": {
                "controlled_avatar_id": None,
                "status": "inactive",
                "pending_request": None,
                "last_prompt_context": None,
            },
        }
    )
    avatar.world.runtime = runtime
    runtime.set_world_and_sim(avatar.world, None)
    runtime.get_roleplay_session()["controlled_avatar_id"] = avatar.id
    runtime.get_roleplay_session()["status"] = "observing"

    old_weapon = MockItem("OldSword")
    new_weapon = MockItem("NewSword")
    avatar.weapon = old_weapon

    task = asyncio.create_task(
        resolve_item_exchange(
            ItemExchangeRequest(
                avatar=avatar,
                new_item=new_weapon,
                kind=ItemExchangeKind.WEAPON,
                scene_intro="Context",
                reject_mode=RejectMode.SELL_NEW,
                auto_accept_when_empty=False,
            )
        )
    )

    session = runtime.get_roleplay_session()
    pending = None
    for _ in range(10):
        await asyncio.sleep(0)
        session = runtime.get_roleplay_session()
        pending = session["pending_request"]
        if session["status"] == "awaiting_choice" and pending is not None:
            break

    assert session["status"] == "awaiting_choice"
    assert pending["type"] == "choice"
    assert len(pending["options"]) == 2

    await submit_roleplay_choice(
        runtime,
        avatar_id=avatar.id,
        request_id=pending["request_id"],
        selected_key="REJECT",
    )
    outcome = await task

    assert outcome.accepted is False
    assert outcome.action == ItemDisposition.SOLD_NEW
    assert outcome.decision.source == ChoiceSource.PLAYER_ROLEPLAY
    assert avatar.sell_weapon.assert_called_once_with(new_weapon) is None


def test_roleplay_choice_conflict_rejects_second_pending_request():
    from src.server.services.roleplay_service import begin_roleplay_choice

    avatar = MockAvatar()
    runtime = GameSessionRuntime(
        {
            **DEFAULT_GAME_STATE,
            "roleplay_session": {
                "controlled_avatar_id": avatar.id,
                "status": "awaiting_choice",
                "pending_request": {
                    "request_id": "existing-choice",
                    "type": "choice",
                    "avatar_id": avatar.id,
                    "title": "已有请求",
                    "description": "desc",
                    "options": [],
                },
                "last_prompt_context": None,
            },
        }
    )

    request = SingleChoiceRequest(
        task_name="single_choice",
        template_path=CONFIG.paths.templates / "single_choice.txt",
        avatar=avatar,
        situation="Context",
        options=[
            Mock(key="ACCEPT", title="Accept", description="Accept new item"),
            Mock(key="REJECT", title="Reject", description="Reject new item"),
        ],
        fallback_policy=FallbackPolicy(FallbackMode.FIRST_OPTION),
    )

    with pytest.raises(HTTPException) as exc_info:
        begin_roleplay_choice(runtime, request=request)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "已有待处理的扮演请求"
