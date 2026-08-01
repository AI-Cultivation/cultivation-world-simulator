from pathlib import Path

from src.run.load_map import load_cultivation_world_map
from src.run.map_presets import list_map_presets
from src.run.map_snapshot import load_map_from_snapshot, serialize_map_snapshot
from src.run.map_source import derive_tile_rows_from_region_rows, read_map_source
from src.run.map_source import load_region_tile_bindings
from tools.map_presets.quality_audit import audit_landmarks, audit_water_region
from src.classes.core.world import World
from src.server.runtime.session import GameSessionRuntime, create_default_game_state
from src.server.services.game_queries import get_world_map
from src.systems.time import Month, Year, create_month_stamp
from src.classes.language import language_manager
from src.i18n import reload_translations


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read_preset_tile_rows(map_id: str) -> list[list[str]]:
    source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / map_id / "map.json")
    return derive_tile_rows_from_region_rows(
        source.region_rows,
        wilderness_tile=source.wilderness_tile,
    )


def _count_pair_edges(tile_rows: list[list[str]], pair: set[str]) -> int:
    height = len(tile_rows)
    width = len(tile_rows[0]) if height else 0
    count = 0
    for y, row in enumerate(tile_rows):
        for x, tile_name in enumerate(row):
            if x + 1 < width and {tile_name, row[x + 1]} == pair:
                count += 1
            if y + 1 < height and {tile_name, tile_rows[y + 1][x]} == pair:
                count += 1
    return count


def _count_checkerboards(tile_rows: list[list[str]], pair: set[str]) -> int:
    height = len(tile_rows)
    width = len(tile_rows[0]) if height else 0
    count = 0
    for y in range(height - 1):
        for x in range(width - 1):
            top_left = tile_rows[y][x]
            top_right = tile_rows[y][x + 1]
            bottom_left = tile_rows[y + 1][x]
            bottom_right = tile_rows[y + 1][x + 1]
            if (
                {top_left, top_right, bottom_left, bottom_right} == pair
                and top_left == bottom_right
                and top_right == bottom_left
            ):
                count += 1
    return count


def _max_edge_run(tile_rows: list[list[str]], x: int = 0) -> int:
    max_run = 0
    current_tile = None
    current_run = 0
    for row in tile_rows:
        tile_name = row[x]
        if tile_name == current_tile:
            current_run += 1
        else:
            max_run = max(max_run, current_run)
            current_tile = tile_name
            current_run = 1
    return max(max_run, current_run)


def test_official_map_presets_load_with_uniform_size():
    presets = list_map_presets()
    assert [preset.id for preset in presets] == ["classic", "island_seas", "mountain_frontier"]

    region_sets = []
    for preset in presets:
        game_map = load_cultivation_world_map(preset.id)
        assert game_map.width == 84
        assert game_map.height == 60
        assert game_map.map_id == preset.id
        assert game_map.map_name == preset.name
        assert game_map.preset_version == preset.version
        assert game_map.regions
        region_sets.append(set(game_map.regions))

    assert all(region_set == region_sets[0] for region_set in region_sets)


def test_region_tile_bindings_cover_all_regions():
    bindings = load_region_tile_bindings()
    game_map = load_cultivation_world_map("classic")

    assert set(game_map.regions).issubset(set(bindings))
    assert bindings[112].tile == "farm"
    assert bindings[201].tile == "mountain"
    assert bindings[201].landmark_asset == "cave"
    assert bindings[301].landmark_asset == "city_301"
    assert bindings[401].landmark_asset == "sect_1"


def test_official_map_visual_shape_guards():
    island_rows = _read_preset_tile_rows("island_seas")
    assert _count_pair_edges(island_rows, {"island", "plain"}) <= 200
    assert _count_checkerboards(island_rows, {"island", "plain"}) == 0

    mountain_rows = _read_preset_tile_rows("mountain_frontier")
    assert _max_edge_run(mountain_rows, x=0) <= 20


def test_official_map_core_quality_guards():
    for map_id in ["classic", "mountain_frontier"]:
        source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / map_id / "map.json")
        issue_codes = {issue.code for issue in audit_water_region(map_id, source.region_rows)}

        assert "disconnected_water_region" not in issue_codes
        assert "water_region_no_sea_outlet" not in issue_codes

    mountain_source = read_map_source(
        PROJECT_ROOT / "static" / "game_configs" / "maps" / "mountain_frontier" / "map.json"
    )
    landmark_issues = [
        issue
        for issue in audit_landmarks("mountain_frontier", mountain_source.region_rows, mountain_source.landmarks)
        if issue.region_id == 406
    ]
    assert "landmark_poor_fit" not in {issue.code for issue in landmark_issues}


def test_map_snapshot_round_trip_restores_tiles_and_regions():
    game_map = load_cultivation_world_map("island_seas")
    snapshot = serialize_map_snapshot(game_map)

    assert snapshot["schema_version"] == 2
    assert snapshot["preset_id"] == "island_seas"
    assert snapshot["width"] == 84
    assert snapshot["height"] == 60
    assert snapshot["wilderness_tile"] == "sea"
    assert len(snapshot["region_rows"]) == 60
    assert snapshot["landmarks"]

    restored = load_map_from_snapshot(snapshot)
    assert restored.map_id == "island_seas"
    assert restored.width == game_map.width
    assert restored.height == game_map.height
    assert set(restored.regions) == set(game_map.regions)

    for y in range(game_map.height):
        for x in range(game_map.width):
            original_tile = game_map.get_tile(x, y)
            restored_tile = restored.get_tile(x, y)
            assert restored_tile.type == original_tile.type
            assert (restored_tile.region.id if restored_tile.region else -1) == (
                original_tile.region.id if original_tile.region else -1
            )


def test_region_first_map_loads_wilderness_and_landmarks():
    game_map = load_cultivation_world_map("island_seas")
    source = read_map_source(PROJECT_ROOT / "static" / "game_configs" / "maps" / "island_seas" / "map.json")

    wilderness_coord = None
    for y, row in enumerate(source.region_rows):
        for x, region_id in enumerate(row):
            if region_id == -1:
                wilderness_coord = (x, y)
                break
        if wilderness_coord:
            break

    assert wilderness_coord is not None
    wilderness_tile = game_map.get_tile(*wilderness_coord)
    assert wilderness_tile.region is None
    assert wilderness_tile.type.value == source.wilderness_tile

    assert game_map.landmarks[301]["asset"] == "city_301"
    assert "x" in game_map.landmarks[301]
    assert "y" in game_map.landmarks[301]


def test_public_map_data_uses_renderable_tile_types():
    for preset in list_map_presets():
        runtime = GameSessionRuntime(create_default_game_state())
        world = World(
            map=load_cultivation_world_map(preset.id),
            month_stamp=create_month_stamp(Year(1), Month.JANUARY),
        )
        runtime.set_world_and_sim(world, None)

        response = get_world_map(runtime, sects_by_id={}, render_config={})
        tile_types = {tile_type for row in response["data"] for tile_type in row}

        assert "CAVE" not in tile_types
        assert "RUIN" not in tile_types
        assert "SECT" not in tile_types


def test_public_map_region_coordinates_use_landmarks():
    runtime = GameSessionRuntime(create_default_game_state())
    game_map = load_cultivation_world_map("island_seas")
    world = World(
        map=game_map,
        month_stamp=create_month_stamp(Year(1), Month.JANUARY),
    )
    runtime.set_world_and_sim(world, None)

    response = get_world_map(runtime, sects_by_id={}, render_config={})
    city = next(region for region in response["regions"] if region["id"] == 301)

    assert city["x"] == game_map.landmarks[301]["x"]
    assert city["y"] == game_map.landmarks[301]["y"]


def test_map_region_overrides_are_applied_to_region_details():
    game_map = load_cultivation_world_map("classic")
    region = game_map.regions[101]

    assert region.name == "东南平原"
    assert "河渠与海风" in region.desc


def test_map_presets_are_localized():
    original_language = str(language_manager)
    try:
        language_manager.set_language("en-US")
        reload_translations()
        presets = {preset.id: preset.to_dict() for preset in list_map_presets()}
        assert presets["classic"]["name"] == "Central Nine Provinces"
        assert presets["island_seas"]["name"] == "Azure Isles"
        assert presets["mountain_frontier"]["size_label"] == "Medium"
    finally:
        language_manager.set_language(original_language)
        reload_translations()


def test_map_presets_can_be_localized_for_specific_locale_without_switching_global_language():
    original_language = str(language_manager)
    try:
        language_manager.set_language("zh-CN")
        reload_translations()

        presets = {preset.id: preset.to_dict(locale="fr-FR") for preset in list_map_presets()}

        assert str(language_manager) == "zh-CN"
        assert presets["classic"]["name"] == "Les Neuf Provinces Centrales"
        assert presets["island_seas"]["desc"] == (
            "Les mers ouvertes divisent les îles, donnant au monde un sentiment d'espace plus large."
        )
        assert presets["mountain_frontier"]["size_label"] == "Moyen"
    finally:
        language_manager.set_language(original_language)
        reload_translations()
