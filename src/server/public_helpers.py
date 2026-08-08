from __future__ import annotations

import hashlib
import os
import re

from src.config import RunConfig, get_settings_service
from src.classes.custom_content import CustomContentRegistry
from src.run.data_loader import reload_all_static_data


def model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def get_runtime_run_config(runtime) -> RunConfig:
    run_config = runtime.get("run_config")
    if run_config:
        return RunConfig(**run_config)
    return get_settings_service().get_default_run_config()


def reset_runtime_custom_content() -> None:
    CustomContentRegistry.reset()


def apply_runtime_content_locale(*, runtime, language_manager, lang_code: str) -> None:
    from src.utils.config import update_paths_for_language
    from src.utils.df import reload_game_configs

    language_manager.set_language(lang_code)
    update_paths_for_language(lang_code)
    reload_game_configs()
    reload_all_static_data()

    world = runtime.get_world()
    if world:
        from src.run.data_loader import fix_runtime_references

        fix_runtime_references(world)


def scan_avatar_assets(*, assets_path: str) -> dict[str, dict[str, list[int]]]:
    def get_ids(base_dir: str, gender: str) -> list[int]:
        directory = os.path.join(base_dir, gender)
        if not os.path.exists(directory):
            return []
        ids: list[int] = []
        for name in os.listdir(directory):
            index_dir = os.path.join(directory, name)
            if not os.path.isdir(index_dir):
                continue
            try:
                avatar_id = int(name)
            except ValueError:
                continue
            if os.path.exists(os.path.join(index_dir, "qi_refining.png")):
                ids.append(avatar_id)
        return sorted(ids)

    avatar_assets: dict[str, dict[str, list[int]]] = {}
    human_base = os.path.join(assets_path, "avatars")
    avatar_assets["human"] = {
        "male": get_ids(human_base, "male"),
        "female": get_ids(human_base, "female"),
    }

    yao_base = os.path.join(assets_path, "yao")
    if os.path.exists(yao_base):
        for race_id in os.listdir(yao_base):
            race_dir = os.path.join(yao_base, race_id)
            if not os.path.isdir(race_dir):
                continue
            avatar_assets[race_id] = {
                "male": get_ids(race_dir, "male"),
                "female": get_ids(race_dir, "female"),
            }

    human_assets = avatar_assets["human"]
    print(
        f"Loaded avatar assets: {len(human_assets['male'])} human males, "
        f"{len(human_assets['female'])} human females, "
        f"{max(0, len(avatar_assets) - 1)} yao race libraries"
    )
    return avatar_assets


def _get_avatar_asset_bucket(*, avatar_assets: dict, avatar) -> list[int]:
    race_id = getattr(getattr(avatar, "race", None), "id", "human") if avatar is not None else "human"
    gender_val = getattr(getattr(avatar, "gender", None), "value", "male") if avatar is not None else "male"
    gender_key = "female" if gender_val == "female" else "male"

    race_assets = avatar_assets.get(race_id) or avatar_assets.get("human", {})
    return list(race_assets.get(gender_key, []))


def resolve_avatar_pic_id(*, avatar_assets: dict, avatar) -> int:
    if avatar is None:
        return 1
    custom_pic_id = getattr(avatar, "custom_pic_id", None)
    if custom_pic_id is not None:
        return custom_pic_id

    available = _get_avatar_asset_bucket(avatar_assets=avatar_assets, avatar=avatar)
    if not available:
        return 1

    hash_bytes = hashlib.md5(str(getattr(avatar, "id", "")).encode("utf-8")).digest()
    hash_int = int.from_bytes(hash_bytes[:4], byteorder="little")
    idx = hash_int % len(available)
    return available[idx]


def resolve_avatar_action_emoji(avatar) -> str:
    if not avatar:
        return ""
    curr = getattr(avatar, "current_action", None)
    if not curr:
        return ""
    act_instance = getattr(curr, "action", None)
    if not act_instance:
        return ""
    return getattr(act_instance, "EMOJI", "")


def validate_save_name(name: str) -> bool:
    if not name or len(name) > 50:
        return False
    return bool(re.match(r"^[\w\u4e00-\u9fff]+$", name))
