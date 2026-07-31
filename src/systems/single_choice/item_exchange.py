from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, TYPE_CHECKING

from src.i18n import t
from src.utils.config import CONFIG

from .models import (
    ChoiceSource,
    FallbackMode,
    FallbackPolicy,
    SingleChoiceDecision,
    SingleChoiceOption,
    SingleChoiceOutcome,
    SingleChoiceRequest,
)
from .scenario import SingleChoiceScenario

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


class ItemExchangeKind(Enum):
    WEAPON = "weapon"
    AUXILIARY = "auxiliary"
    TECHNIQUE = "technique"
    ELIXIR = "elixir"


class RejectMode(Enum):
    ABANDON_NEW = "abandon_new"
    SELL_NEW = "sell_new"
    LEAVE_AT_SOURCE = "leave_at_source"


class ItemDisposition(Enum):
    AUTO_ACCEPTED = "auto_accepted"
    REPLACED_OLD = "replaced_old"
    CONSUMED_NEW = "consumed_new"
    SOLD_NEW = "sold_new"
    ABANDONED_NEW = "abandoned_new"
    LEFT_AT_SOURCE = "left_at_source"


@dataclass(slots=True)
class ItemExchangeSpec:
    kind: ItemExchangeKind
    label: str
    action_verb: str
    done_verb: str
    replace_verb: str
    get_current: Callable[["Avatar"], Any | None]
    accept_new: Callable[["Avatar", Any], Any]
    sell_item: Callable[["Avatar", Any], int] | None


@dataclass(slots=True)
class ItemExchangeRequest:
    avatar: "Avatar"
    new_item: Any
    kind: ItemExchangeKind
    scene_intro: str
    reject_mode: RejectMode
    auto_accept_when_empty: bool = True
    fallback_policy: FallbackPolicy = field(
        default_factory=lambda: FallbackPolicy(FallbackMode.FIRST_OPTION)
    )


@dataclass(slots=True)
class ItemExchangeOutcome(SingleChoiceOutcome):
    kind: ItemExchangeKind
    accepted: bool
    action: ItemDisposition
    current_item_before: Any | None
    current_item_after: Any | None
    sold_price: int | None
    new_item: Any


def _get_item_exchange_spec(kind: ItemExchangeKind) -> ItemExchangeSpec:
    if kind == ItemExchangeKind.WEAPON:
        return ItemExchangeSpec(
            kind=kind,
            label=t("item_label_weapon"),
            action_verb=t("item_verb_equip"),
            done_verb=t("item_verb_equipped"),
            replace_verb=t("item_verb_replace"),
            get_current=lambda avatar: avatar.weapon,
            accept_new=lambda avatar, item: avatar.change_weapon(item),
            sell_item=lambda avatar, item: avatar.sell_weapon(item),
        )

    if kind == ItemExchangeKind.AUXILIARY:
        return ItemExchangeSpec(
            kind=kind,
            label=t("item_label_auxiliary"),
            action_verb=t("item_verb_equip"),
            done_verb=t("item_verb_equipped"),
            replace_verb=t("item_verb_replace"),
            get_current=lambda avatar: avatar.auxiliary,
            accept_new=lambda avatar, item: avatar.change_auxiliary(item),
            sell_item=lambda avatar, item: avatar.sell_auxiliary(item),
        )

    if kind == ItemExchangeKind.TECHNIQUE:
        return ItemExchangeSpec(
            kind=kind,
            label=t("item_label_technique"),
            action_verb=t("item_verb_practice"),
            done_verb=t("item_verb_switched"),
            replace_verb=t("item_verb_replace"),
            get_current=lambda avatar: avatar.technique,
            accept_new=lambda avatar, item: setattr(avatar, "technique", item),
            sell_item=None,
        )

    if kind == ItemExchangeKind.ELIXIR:
        return ItemExchangeSpec(
            kind=kind,
            label=t("item_label_elixir"),
            action_verb=t("item_verb_consume"),
            done_verb=t("item_verb_consumed"),
            replace_verb=t("item_verb_replace"),
            get_current=lambda avatar: None,
            accept_new=lambda avatar, item: avatar.consume_elixir(item),
            sell_item=lambda avatar, item: avatar.sell_elixir(item),
        )

    raise ValueError(t("Unsupported item type: {item_type}", item_type=kind.value))


def _get_item_grade(item: Any) -> str:
    return str(getattr(item, "realm", getattr(item, "grade", None)))


def _build_item_exchange_options(
    request: ItemExchangeRequest,
    spec: ItemExchangeSpec,
    current_item: Any | None,
) -> list[SingleChoiceOption]:
    new_name = request.new_item.name
    old_name = current_item.name if current_item else ""

    accept_desc = t(
        "{action} new {label}『{new_name}』",
        action=spec.action_verb,
        label=spec.label,
        new_name=new_name,
    )
    if current_item and spec.sell_item is not None:
        accept_desc += t(", sell old {label}『{old_name}』", label=spec.label, old_name=old_name)
    elif current_item:
        accept_desc += t(
            ", {replace} old {label}『{old_name}』",
            replace=spec.replace_verb,
            label=spec.label,
            old_name=old_name,
        )

    reject_desc = t("Abandon『{new_name}』", new_name=new_name)
    if request.reject_mode == RejectMode.SELL_NEW and spec.sell_item is not None:
        reject_desc = t(
            "Sell new {label}『{new_name}』for spirit stones, keep current status",
            label=spec.label,
            new_name=new_name,
        )
    elif current_item:
        reject_desc += t(", keep current『{old_name}』", old_name=old_name)
    if request.reject_mode == RejectMode.LEAVE_AT_SOURCE:
        reject_desc = t("Leave『{new_name}』where it was found", new_name=new_name)

    return [
        SingleChoiceOption(
            key="ACCEPT",
            title=t("Accept new item"),
            description=accept_desc,
            metadata={"display_variant": "accept"},
        ),
        SingleChoiceOption(
            key="REJECT",
            title=t("Reject new item"),
            description=reject_desc,
            metadata={"display_variant": "reject"},
        ),
    ]


def _build_item_exchange_situation(
    request: ItemExchangeRequest,
    spec: ItemExchangeSpec,
    current_item: Any | None,
) -> str:
    new_info = request.new_item.get_info(detailed=True)
    description = t("New {label}: {info}", label=spec.label, info=new_info)

    if current_item:
        old_info = current_item.get_info(detailed=True)
        description = t(
            "Current {label}: {old_info}\n{new_desc}",
            label=spec.label,
            old_info=old_info,
            new_desc=description,
        )
        if spec.sell_item is not None:
            description += t(
                "\n(Selecting {replace} will sell old {label})",
                replace=spec.replace_verb,
                label=spec.label,
            )

    return f"{request.scene_intro}\n{description}"


class ItemExchangeScenario(SingleChoiceScenario[ItemExchangeOutcome]):
    def __init__(self, request: ItemExchangeRequest):
        self.request = request
        self.spec = _get_item_exchange_spec(request.kind)
        self.current_item = self.spec.get_current(request.avatar)

    def should_auto_accept(self) -> bool:
        return self.current_item is None and self.request.auto_accept_when_empty

    def build_request(self) -> SingleChoiceRequest:
        if self.should_auto_accept():
            return SingleChoiceRequest(
                task_name="single_choice",
                template_path=CONFIG.paths.templates / "single_choice.txt",
                avatar=self.request.avatar,
                situation=self.request.scene_intro,
                options=[
                    SingleChoiceOption(
                        key="ACCEPT",
                        title=t("Accept new item"),
                        description=t("Automatically accept the new item."),
                        metadata={"display_variant": "accept"},
                    )
                ],
                fallback_policy=FallbackPolicy(FallbackMode.PREFERRED_KEY, preferred_key="ACCEPT"),
                title=self.request.scene_intro,
                description=self.request.scene_intro,
            )

        return SingleChoiceRequest(
            task_name="single_choice",
            template_path=CONFIG.paths.templates / "single_choice.txt",
            avatar=self.request.avatar,
            situation=_build_item_exchange_situation(self.request, self.spec, self.current_item),
            options=_build_item_exchange_options(self.request, self.spec, self.current_item),
            fallback_policy=self.request.fallback_policy,
            title=self.request.scene_intro,
            description=self.request.scene_intro,
        )

    async def apply_decision(self, decision: SingleChoiceDecision) -> ItemExchangeOutcome:
        avatar = self.request.avatar
        new_item = self.request.new_item
        current_item = self.current_item
        grade = _get_item_grade(new_item)

        if self.should_auto_accept():
            self.spec.accept_new(avatar, new_item)
            return ItemExchangeOutcome(
                decision=decision,
                result_text=t(
                    "{avatar_name} obtained {grade} {label}『{item_name}』and {action}.",
                    avatar_name=avatar.name,
                    grade=grade,
                    label=self.spec.label,
                    item_name=new_item.name,
                    action=self.spec.action_verb,
                ),
                kind=self.request.kind,
                accepted=True,
                action=ItemDisposition.AUTO_ACCEPTED,
                current_item_before=None,
                current_item_after=new_item,
                sold_price=None,
                new_item=new_item,
            )

        if decision.selected_key == "ACCEPT":
            if current_item is not None and self.spec.sell_item is not None:
                self.spec.sell_item(avatar, current_item)
            self.spec.accept_new(avatar, new_item)
            action = ItemDisposition.CONSUMED_NEW if self.request.kind == ItemExchangeKind.ELIXIR else ItemDisposition.REPLACED_OLD
            current_after = None if self.request.kind == ItemExchangeKind.ELIXIR else new_item
            return ItemExchangeOutcome(
                decision=decision,
                result_text=t(
                    "{avatar_name} {done} {grade} {label}『{item_name}』.",
                    avatar_name=avatar.name,
                    done=self.spec.done_verb,
                    grade=grade,
                    label=self.spec.label,
                    item_name=new_item.name,
                ),
                kind=self.request.kind,
                accepted=True,
                action=action,
                current_item_before=current_item,
                current_item_after=current_after,
                sold_price=None,
                new_item=new_item,
            )

        if self.request.reject_mode == RejectMode.SELL_NEW and self.spec.sell_item is not None:
            sold_price = self.spec.sell_item(avatar, new_item)
            return ItemExchangeOutcome(
                decision=decision,
                result_text=t(
                    "{avatar_name} sold newly obtained {item_name}, gained {price} spirit stones.",
                    avatar_name=avatar.name,
                    item_name=new_item.name,
                    price=sold_price,
                ),
                kind=self.request.kind,
                accepted=False,
                action=ItemDisposition.SOLD_NEW,
                current_item_before=current_item,
                current_item_after=current_item,
                sold_price=sold_price,
                new_item=new_item,
            )

        if self.request.reject_mode == RejectMode.LEAVE_AT_SOURCE:
            return ItemExchangeOutcome(
                decision=decision,
                result_text=t(
                    "{avatar_name} left {item_name} where it was found.",
                    avatar_name=avatar.name,
                    item_name=new_item.name,
                ),
                kind=self.request.kind,
                accepted=False,
                action=ItemDisposition.LEFT_AT_SOURCE,
                current_item_before=current_item,
                current_item_after=current_item,
                sold_price=None,
                new_item=new_item,
            )

        return ItemExchangeOutcome(
            decision=decision,
            result_text=t(
                "{avatar_name} abandoned {item_name}.",
                avatar_name=avatar.name,
                item_name=new_item.name,
            ),
            kind=self.request.kind,
            accepted=False,
            action=ItemDisposition.ABANDONED_NEW,
            current_item_before=current_item,
            current_item_after=current_item,
            sold_price=None,
            new_item=new_item,
        )


async def resolve_item_exchange(request: ItemExchangeRequest) -> ItemExchangeOutcome:
    from .engine import resolve_single_choice

    scenario = ItemExchangeScenario(request)
    if scenario.should_auto_accept():
        return await scenario.apply_decision(
            SingleChoiceDecision(
                selected_key="ACCEPT",
                thinking="",
                source=ChoiceSource.FALLBACK,
                raw_response=None,
                used_fallback=False,
            )
        )
    return await resolve_single_choice(scenario)
