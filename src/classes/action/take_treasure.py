from __future__ import annotations

import random

from src.classes.action import InstantAction
from src.classes.action.param_options import ParamOptionSource
from src.classes.action_runtime import ActionResult, ActionStatus
from src.classes.event import Event
from src.classes.poi import TreasurePOI, restore_equipment_item
from src.i18n import t
from src.systems.cultivation import Realm
from src.systems.single_choice import (
    ItemDisposition,
    ItemExchangeKind,
    ItemExchangeRequest,
    RejectMode,
    resolve_item_exchange,
)
from src.systems.treasure import _config_value


REALM_RANK = {
    Realm.Qi_Refinement.value: 1,
    Realm.Foundation_Establishment.value: 2,
    Realm.Core_Formation.value: 3,
    Realm.Nascent_Soul.value: 4,
}


class TakeTreasure(InstantAction):
    ACTION_NAME_ID = "take_treasure_action_name"
    DESC_ID = "take_treasure_description"
    REQUIREMENTS_ID = "take_treasure_requirements"

    EMOJI = "💎"
    PARAMS = {"poi_id": "poi_id"}
    PARAM_OPTION_SOURCES = {"poi_id": ParamOptionSource.KNOWN_TREASURE_POI_ID}
    IS_MAJOR = True

    def __init__(self, avatar, world):
        super().__init__(avatar, world)
        self._last_event: Event | None = None
        self._pending_payload: dict | None = None
        self._pending_item = None

    def _get_treasure(self, poi_id: str) -> TreasurePOI | None:
        manager = getattr(self.world, "poi_manager", None)
        poi = manager.get(str(poi_id)) if manager is not None else None
        return poi if isinstance(poi, TreasurePOI) else None

    def _realm_delta(self, treasure: TreasurePOI) -> int:
        avatar_realm = getattr(getattr(self.avatar, "cultivation_progress", None), "realm", None)
        avatar_rank = REALM_RANK.get(getattr(avatar_realm, "value", ""), 1)
        treasure_rank = REALM_RANK.get(treasure.treasure_realm, 1)
        return avatar_rank - treasure_rank

    def _success_rate(self, treasure: TreasurePOI) -> float:
        return max(0.05, min(0.95, 0.45 + self._realm_delta(treasure) * 0.15))

    def can_start(self, poi_id: str) -> tuple[bool, str]:
        treasure = self._get_treasure(poi_id)
        if treasure is None:
            return False, t("Cannot resolve treasure: {poi}", poi=poi_id)
        if treasure.is_expired(int(self.world.month_stamp)):
            return False, t("Treasure has faded away")
        if not treasure.is_known_by(self.avatar):
            return False, t("Treasure is unknown")
        if treasure.treasure_payload is None:
            return False, t("Treasure has already been claimed")
        if self.avatar.pos_x != treasure.x or self.avatar.pos_y != treasure.y:
            return False, t("Must be at the treasure to claim it")
        return True, ""

    def _execute(self, poi_id: str) -> None:
        self._last_event = None
        self._pending_payload = None
        self._pending_item = None
        treasure = self._get_treasure(poi_id)
        if treasure is None or treasure.treasure_payload is None:
            return
        treasure.attempt_count += 1
        if random.random() <= self._success_rate(treasure):
            item = restore_equipment_item(treasure.treasure_payload)
            if item is not None:
                self._pending_payload = dict(treasure.treasure_payload)
                self._pending_item = item
                return
            self._last_event = Event(
                self.world.month_stamp,
                t("{avatar} found that the treasure at {treasure} had decayed beyond use.", avatar=self.avatar.name, treasure=treasure.name),
                related_avatars=[self.avatar.id],
            )
            return

        content = t("{avatar} failed to claim {treasure}.", avatar=self.avatar.name, treasure=treasure.name)
        if random.random() < float(_config_value("backlash_probability", 0.10)):
            damage = max(1, int(getattr(self.avatar.hp, "max", 100) * float(_config_value("backlash_hp_ratio", 0.12))))
            self.avatar.hp.reduce(damage)
            content = t(
                "{avatar} triggered the treasure's restriction at {treasure} and was injured for {damage} HP.",
                avatar=self.avatar.name,
                treasure=treasure.name,
                damage=damage,
            )
        self._last_event = Event(self.world.month_stamp, content, related_avatars=[self.avatar.id], is_major=False)

    def step(self, **params) -> ActionResult:
        self._execute(**params)
        return ActionResult(status=ActionStatus.COMPLETED, events=[])

    async def finish(self, poi_id: str) -> list[Event]:
        if self._last_event is not None:
            return [self._last_event]
        if self._pending_payload is None or self._pending_item is None:
            return []
        treasure = self._get_treasure(poi_id)
        if treasure is None:
            return []
        try:
            kind = ItemExchangeKind(self._pending_payload["kind"])
        except ValueError:
            return []
        outcome = await resolve_item_exchange(ItemExchangeRequest(
            avatar=self.avatar,
            new_item=self._pending_item,
            kind=kind,
            scene_intro=t("{avatar} successfully claimed {item} from {treasure}.", avatar=self.avatar.name, item=self._pending_item.name, treasure=treasure.name),
            reject_mode=RejectMode.LEAVE_AT_SOURCE,
            auto_accept_when_empty=True,
        ))
        accepted_actions = {ItemDisposition.AUTO_ACCEPTED, ItemDisposition.REPLACED_OLD}
        if outcome.accepted and outcome.action in accepted_actions:
            self.world.poi_manager.remove(treasure.id)
        return [Event(
            self.world.month_stamp,
            t("{avatar} claimed {item} from {treasure}. {result}", avatar=self.avatar.name, item=self._pending_item.name, treasure=treasure.name, result=outcome.result_text),
            related_avatars=[self.avatar.id],
            is_major=outcome.accepted,
        )]

    def can_possibly_start(self) -> bool:
        manager = getattr(self.world, "poi_manager", None)
        if manager is None:
            return False
        current_month = int(self.world.month_stamp)
        return any(
            poi.x == self.avatar.pos_x and poi.y == self.avatar.pos_y
            and not poi.is_expired(current_month) and getattr(poi, "treasure_payload", None) is not None
            for poi in manager.get_known_by(self.avatar, kind="treasure")
        )
