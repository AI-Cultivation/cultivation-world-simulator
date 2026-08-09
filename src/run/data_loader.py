"""Compatibility facade for the static catalog lifecycle."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.run.log import get_logger
from src.run.static_catalog import static_catalog

if TYPE_CHECKING:
    from src.classes.core.world import World


def reload_all_static_data():
    logger = get_logger().logger
    logger.info("[DataLoader] 开始重置静态游戏数据...")
    snapshot = static_catalog.reload()
    logger.info("[DataLoader] 静态数据重置完成，generation=%s。", snapshot.generation)
    return snapshot


def fix_runtime_references(world: "World"):
    report = static_catalog.rebind_world(world)
    get_logger().logger.info(
        "[DataLoader] 已修复 %s 个角色的静态引用，缺失=%s。",
        report.avatars_seen,
        list(report.missing_references),
    )
    return report
