from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Any, Callable

from src.utils.llm.runtime_mode import llm_test_mode_scope


def _create_save_slot(*, config, get_events_db_path) -> tuple[Any, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    save_name = f"save_{timestamp}"
    saves_dir = config.paths.saves
    saves_dir.mkdir(parents=True, exist_ok=True)
    save_path = saves_dir / f"{save_name}.json"
    events_db_path = get_events_db_path(save_path)
    return save_path, events_db_path


def _select_existed_sects(*, sects_by_id, needed_sects: int) -> list[Any]:
    all_sects = list(sects_by_id.values())
    if needed_sects <= 0 or not all_sects:
        return []

    pool = list(all_sects)
    random.shuffle(pool)
    return pool[:needed_sects]


async def _apply_world_lore_if_needed(
    *,
    world,
    run_config,
    world_lore_manager_cls,
    build_world_lore_snapshot,
) -> None:
    world_lore = run_config.world_lore
    if not world_lore or not world_lore.strip():
        return

    world.set_world_lore(world_lore)
    if bool(getattr(run_config, "test_mode", False)):
        world.world_lore_snapshot = build_world_lore_snapshot(world)
        print("Skipping LLM world lore rewrite in rule-based test mode")
        return

    print(f"Reshaping world based on worldview and history: {world_lore[:50]}...")
    try:
        world_lore_mgr = world_lore_manager_cls(world)
        await world_lore_mgr.apply_world_lore(world_lore)
        if not getattr(world, "world_lore_snapshot", None):
            world.world_lore_snapshot = build_world_lore_snapshot(world)
        print("World lore applied")
    except Exception as exc:
        print(f"[Warning] Failed to apply world lore: {exc}")


async def _generate_initial_avatars(
    *,
    world,
    run_config,
    existed_sects,
    make_random_avatars,
) -> dict[Any, Any]:
    target_total_count = int(run_config.init_npc_num)
    if target_total_count <= 0:
        return {}

    def _make_random_sync():
        return make_random_avatars(
            world,
            count=target_total_count,
            current_month_stamp=world.month_stamp,
            existed_sects=existed_sects,
        )

    random_avatars = await asyncio.to_thread(_make_random_sync)
    print(f"Generated {len(random_avatars)} random NPCs")
    return random_avatars


def _resolve_initially_dead_avatars(*, world, avatars: dict[Any, Any]) -> None:
    """Move pre-generated dead avatars through the normal death pipeline.

    Avatar generation can determine that an NPC's rolled lifespan is already
    exhausted.  At this point the NPC has not yet been registered, so the
    generator cannot create its world-facing death artifacts itself.
    """
    from src.classes.death import handle_death
    from src.classes.death_reason import DeathReason, DeathType

    for avatar in avatars.values():
        if getattr(avatar, "is_dead", False):
            handle_death(world, avatar, DeathReason(DeathType.OLD_AGE))


async def _prepare_initial_character_profiles(*, world) -> None:
    from src.sim.simulator_engine.phases import lifecycle

    avatar_manager = getattr(world, "avatar_manager", None)
    if avatar_manager is None:
        return

    if hasattr(avatar_manager, "get_living_avatars"):
        living_avatars = list(avatar_manager.get_living_avatars())
    else:
        living_avatars = list(getattr(avatar_manager, "avatars", {}).values())
    if not living_avatars:
        return

    print("Preparing initial character profiles...")
    objective_results = await asyncio.gather(
        *[lifecycle.process_avatar_long_term_objective(avatar) for avatar in living_avatars],
        return_exceptions=True,
    )
    event_manager = getattr(world, "event_manager", None)
    if event_manager is not None:
        for result in objective_results:
            if isinstance(result, Exception):
                print(f"[Warning] Initial long-term objective generation failed: {result}")
                continue
            if result is not None:
                event_manager.add_event(result)

    backstory_results = await asyncio.gather(
        *[lifecycle.process_avatar_backstory(avatar) for avatar in living_avatars],
        return_exceptions=True,
    )
    for result in backstory_results:
        if isinstance(result, Exception):
            print(f"[Warning] Initial backstory generation failed: {result}")
    print("Initial character profiles prepared")


async def _run_llm_check_background(
    *,
    runtime,
    init_generation: int,
    check_llm_connectivity: Callable[[], tuple[bool, str]],
) -> None:
    if int(runtime.get("init_generation", 0) or 0) != init_generation:
        return
    runtime.set_llm_check_state(pending=True)
    try:
        print("Checking LLM connectivity in background...")
        success, error_msg = await asyncio.to_thread(check_llm_connectivity)
        if int(runtime.get("init_generation", 0) or 0) != init_generation:
            return
        if not success:
            print(f"[Warning] LLM connectivity check failed: {error_msg}")
            runtime.set_llm_check_state(pending=False, failed=True, error_message=error_msg)
        else:
            print("LLM connectivity check passed")
            runtime.set_llm_check_state(pending=False, failed=False, error_message="")
    except Exception as exc:
        if int(runtime.get("init_generation", 0) or 0) != init_generation:
            return
        runtime.set_llm_check_state(
            pending=False,
            failed=True,
            error_message=f"连通性检测异常：{exc}",
        )
        print(f"[Warning] LLM connectivity check failed: {exc}")


async def _generate_initial_events(*, sim) -> None:
    print("Generating initial events...")
    try:
        await sim.step()
        print("Initial events generation completed")
    except Exception as exc:
        print(f"[Warning] Initial events generation failed: {exc}")


async def perform_game_initialization(
    *,
    runtime,
    avatar_assets: dict[str, list[int]],
    assets_path: str,
    config,
    update_init_progress: Callable[[int, str], None],
    reset_runtime_custom_content: Callable[[], None],
    reload_all_static_data: Callable[[], None],
    scan_avatar_assets: Callable[..., dict[str, list[int]]],
    load_cultivation_world_map: Callable[[], Any],
    get_events_db_path,
    get_runtime_run_config: Callable[[Any], Any],
    world_cls,
    create_month_stamp,
    year_cls,
    month_enum,
    generate_dynasty: Callable[[], Any],
    generate_emperor: Callable[[Any, int], Any],
    event_cls,
    translate: Callable[..., str],
    simulator_cls,
    model_to_dict: Callable[[Any], dict[str, Any]],
    world_lore_manager_cls,
    build_world_lore_snapshot: Callable[[Any], Any],
    sects_by_id,
    make_random_avatars,
    check_llm_connectivity: Callable[[], tuple[bool, str]],
) -> None:
    runtime.begin_initialization()
    runtime.clear_roleplay_session()

    async def _do_init():
        update_init_progress(0, "scanning_assets")
        print("Resetting world rule data...")
        reset_runtime_custom_content()
        reload_all_static_data()
        await asyncio.to_thread(
            lambda: avatar_assets.update(scan_avatar_assets(assets_path=assets_path))
        )

        run_config = get_runtime_run_config(runtime)
        with llm_test_mode_scope(bool(getattr(run_config, "test_mode", False))):
            update_init_progress(1, "loading_map")
            game_map = await asyncio.to_thread(
            load_cultivation_world_map,
            getattr(run_config, "map_id", "classic"),
            )

            save_path, events_db_path = _create_save_slot(
            config=config,
            get_events_db_path=get_events_db_path,
            )
            runtime.set_current_save_path(save_path)
            print(f"Events database: {events_db_path}")

            start_year = getattr(config.world, "start_year", 100)
            world = world_cls.create_with_db(
            map=game_map,
            month_stamp=create_month_stamp(year_cls(start_year), month_enum.JANUARY),
            events_db_path=events_db_path,
            start_year=start_year,
            )
            world.runtime = runtime
            world.dynasty = generate_dynasty()
            world.dynasty.current_emperor = generate_emperor(world.dynasty, int(world.month_stamp))
            world.event_manager.add_event(
            event_cls(
                month_stamp=world.month_stamp,
                content=translate(
                    "{dynasty_title} has enthroned a new ruler, and {emperor_name} ascends as emperor.",
                    dynasty_title=world.dynasty.title,
                    emperor_name=world.dynasty.current_emperor.name,
                ),
                is_major=True,
            )
            )

            sim = simulator_cls(world)
            sim.awakening_rate = run_config.npc_awakening_rate_per_month
            world.run_config_snapshot = model_to_dict(run_config)

            update_init_progress(2, "shaping_world_lore")
            await _apply_world_lore_if_needed(
            world=world,
            run_config=run_config,
            world_lore_manager_cls=world_lore_manager_cls,
            build_world_lore_snapshot=build_world_lore_snapshot,
            )

            update_init_progress(3, "initializing_sects")
            existed_sects = _select_existed_sects(
            sects_by_id=sects_by_id,
            needed_sects=int(run_config.sect_num or 0),
            )

            update_init_progress(4, "generating_avatars")
            final_avatars = await _generate_initial_avatars(
            world=world,
            run_config=run_config,
            existed_sects=existed_sects,
            make_random_avatars=make_random_avatars,
            )

            world.avatar_manager.avatars.update(final_avatars)
            _resolve_initially_dead_avatars(world=world, avatars=final_avatars)
            world.existed_sects = existed_sects
            world.sect_context.from_existed_sects(existed_sects)
            from src.systems.world_secret import initialize_world_secret
            initialize_world_secret(world, getattr(run_config, "world_secret_id", "none"))
            runtime.set_world_and_sim(world, sim)

            update_init_progress(5, "preparing_character_profiles")
            await _prepare_initial_character_profiles(world=world)

            update_init_progress(6, "generating_initial_events")
            runtime.set_paused(True)
            await _generate_initial_events(sim=sim)
            runtime.finish_initialization(phase_name="complete")
            runtime.set_initialization_progress(progress=100)
            runtime.set_llm_check_state(
                pending=not bool(getattr(run_config, "test_mode", False)),
                failed=False,
                error_message="",
            )
            init_generation = int(runtime.get("init_generation", 0) or 0)
            if not getattr(run_config, "test_mode", False):
                asyncio.create_task(
                    _run_llm_check_background(
                        runtime=runtime,
                        init_generation=init_generation,
                        check_llm_connectivity=check_llm_connectivity,
                    )
                )
            print("Game world initialization completed!")

    try:
        await runtime.run_mutation(_do_init)
    except Exception as exc:
        import traceback

        traceback.print_exc()
        runtime.fail_initialization(str(exc))
        print(f"[Error] Initialization failed: {exc}")
