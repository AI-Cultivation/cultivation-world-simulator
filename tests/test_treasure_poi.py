from __future__ import annotations

import pytest

from src.classes.action.param_options import build_param_options
from src.classes.action.take_treasure import TakeTreasure
from src.classes.poi import TreasurePOI, build_equipment_payload
from src.classes.items.weapon import weapons_by_id
from src.systems.cultivation import Realm
from src.systems.single_choice import ItemDisposition, ItemExchangeKind, ItemExchangeOutcome
from src.systems.single_choice.models import ChoiceSource, SingleChoiceDecision
from src.systems.treasure import phase_treasure_lifecycle, try_spawn_treasure


def _weapon_for(realm: Realm):
    return next(weapon for weapon in weapons_by_id.values() if weapon.realm == realm)


def _make_treasure(base_world, dummy_avatar, *, realm=Realm.Foundation_Establishment) -> TreasurePOI:
    weapon = _weapon_for(realm)
    treasure = TreasurePOI(
        id="treasure:test:1",
        x=0,
        y=0,
        name="test treasure",
        created_month=int(base_world.month_stamp),
        expires_month=int(base_world.month_stamp) + 120,
        icon_key="treasure_01",
        treasure_icon_id="treasure_01",
        treasure_source="meteorite_relic",
        treasure_realm=realm.value,
        treasure_payload=build_equipment_payload(weapon),
    )
    treasure.discover(dummy_avatar)
    base_world.poi_manager.add(treasure)
    return treasure


def test_treasure_poi_save_load_and_known_param_option(base_world, dummy_avatar):
    dummy_avatar.world = base_world
    treasure = _make_treasure(base_world, dummy_avatar)

    saved = base_world.poi_manager.to_save_list()
    base_world.poi_manager.load_from_list(saved)
    loaded = base_world.poi_manager.get(treasure.id)

    assert isinstance(loaded, TreasurePOI)
    assert loaded.treasure_source == "meteorite_relic"
    assert loaded.treasure_payload == treasure.treasure_payload
    options = build_param_options(TakeTreasure, dummy_avatar)["poi_id"]
    assert options[0]["value"] == treasure.id


def test_treasure_success_rate_is_realm_only(base_world, dummy_avatar):
    treasure = _make_treasure(base_world, dummy_avatar, realm=Realm.Core_Formation)
    action = TakeTreasure(dummy_avatar, base_world)

    dummy_avatar.cultivation_progress.realm = Realm.Qi_Refinement
    assert action._success_rate(treasure) == pytest.approx(0.15)
    dummy_avatar.cultivation_progress.realm = Realm.Core_Formation
    assert action._success_rate(treasure) == pytest.approx(0.45)
    dummy_avatar.cultivation_progress.realm = Realm.Nascent_Soul
    assert action._success_rate(treasure) == pytest.approx(0.60)
    treasure.treasure_realm = Realm.Nascent_Soul.value
    dummy_avatar.cultivation_progress.realm = Realm.Qi_Refinement
    assert action._success_rate(treasure) == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_take_treasure_accept_removes_poi(monkeypatch, base_world, dummy_avatar):
    dummy_avatar.world = base_world
    dummy_avatar.weapon = None
    dummy_avatar.cultivation_progress.realm = Realm.Foundation_Establishment
    treasure = _make_treasure(base_world, dummy_avatar)
    monkeypatch.setattr("src.classes.action.take_treasure.random.random", lambda: 0.0)

    action = TakeTreasure(dummy_avatar, base_world)
    action.step(poi_id=treasure.id)
    events = await action.finish(poi_id=treasure.id)

    assert base_world.poi_manager.get(treasure.id) is None
    assert dummy_avatar.weapon is not None
    assert events[0].is_major is True


@pytest.mark.asyncio
async def test_take_treasure_rejection_leaves_poi(monkeypatch, base_world, dummy_avatar):
    dummy_avatar.world = base_world
    dummy_avatar.weapon = _weapon_for(Realm.Foundation_Establishment)
    dummy_avatar.cultivation_progress.realm = Realm.Foundation_Establishment
    treasure = _make_treasure(base_world, dummy_avatar)
    monkeypatch.setattr("src.classes.action.take_treasure.random.random", lambda: 0.0)

    async def reject_exchange(request):
        return ItemExchangeOutcome(
            decision=SingleChoiceDecision("REJECT", "", ChoiceSource.FALLBACK, None, True),
            result_text="left at source",
            kind=ItemExchangeKind.WEAPON,
            accepted=False,
            action=ItemDisposition.LEFT_AT_SOURCE,
            current_item_before=dummy_avatar.weapon,
            current_item_after=dummy_avatar.weapon,
            sold_price=None,
            new_item=request.new_item,
        )

    monkeypatch.setattr("src.classes.action.take_treasure.resolve_item_exchange", reject_exchange)
    action = TakeTreasure(dummy_avatar, base_world)
    action.step(poi_id=treasure.id)
    events = await action.finish(poi_id=treasure.id)

    assert base_world.poi_manager.get(treasure.id) is treasure
    assert treasure.treasure_payload is not None
    assert events[0].is_major is False


def test_treasure_failure_and_expiry_keep_then_remove(monkeypatch, base_world, dummy_avatar):
    dummy_avatar.world = base_world
    treasure = _make_treasure(base_world, dummy_avatar)
    monkeypatch.setattr("src.classes.action.take_treasure.random.random", lambda: 1.0)

    action = TakeTreasure(dummy_avatar, base_world)
    action.step(poi_id=treasure.id)
    assert treasure.attempt_count == 1
    assert base_world.poi_manager.get(treasure.id) is treasure

    treasure.expires_month = int(base_world.month_stamp)
    monkeypatch.setattr("src.systems.treasure.try_spawn_treasure", lambda world: None)
    events = phase_treasure_lifecycle(base_world)
    assert base_world.poi_manager.get(treasure.id) is None
    assert len(events) == 1


def test_spawned_treasure_is_limited_to_equipment_realms(monkeypatch, base_world):
    monkeypatch.setattr("src.systems.treasure.random.random", lambda: 0.0)
    treasure = try_spawn_treasure(base_world)

    assert isinstance(treasure, TreasurePOI)
    assert treasure.treasure_realm in {
        Realm.Foundation_Establishment.value,
        Realm.Core_Formation.value,
        Realm.Nascent_Soul.value,
    }
    assert treasure.treasure_payload["kind"] in {"weapon", "auxiliary"}
    assert treasure.expires_month == int(base_world.month_stamp) + 240
