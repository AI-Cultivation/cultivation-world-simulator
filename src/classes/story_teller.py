from __future__ import annotations

from typing import Dict, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar

from src.utils.config import CONFIG
from src.utils.llm import call_llm_with_task_name
from src.i18n.story_styles import get_random_story_style


class StoryTeller:
    """
    故事生成器：基于模板与 LLM，将给定事件扩展为简短的小故事。
    """
    
    TEMPLATE_SINGLE_FILE = "story_single.txt"
    TEMPLATE_DUAL_FILE = "story_dual.txt"
    TEMPLATE_GATHERING_FILE = "story_gathering.txt"

    @staticmethod
    def _get_template_path(filename: str) -> Path:
        """获取当前语言环境下的模板路径"""
        return CONFIG.paths.templates / filename

    @staticmethod
    def _build_avatar_infos(*actors: "Avatar") -> Dict[str, dict]:
        """
        构建角色信息字典。
        - 双人故事：第一个角色使用 expanded_info（包含共同事件），第二个使用普通 info
        - 单人故事：使用 expanded_info
        """
        non_null = [a for a in actors if a is not None]
        avatar_infos: Dict[str, dict] = {}
        
        if len(non_null) >= 2:
            avatar_infos[non_null[0].name] = non_null[0].get_expanded_info(other_avatar=non_null[1], detailed=True)
            avatar_infos[non_null[1].name] = non_null[1].get_info(detailed=True)
        elif non_null:
            avatar_infos[non_null[0].name] = non_null[0].get_expanded_info(detailed=True)
        
        return avatar_infos

    @staticmethod
    def _build_template_data(event: str, res: str, avatar_infos: Dict[str, dict], prompt: str, *actors: "Avatar") -> dict:
        """构建模板渲染所需的数据字典"""
        
        # 默认空关系列表
        avatar_name_1 = ""
        avatar_name_2 = ""
        
        world_info = actors[0].world.static_info
        
        # 如果有两个有效角色，计算可能的关系
        non_null = [a for a in actors if a is not None]
        if len(non_null) >= 2:
            avatar_name_1 = non_null[0].name
            avatar_name_2 = non_null[1].name

        return {
            "world_info": world_info,
            "world_lore": actors[0].world.world_lore.text if actors else "",
            "avatar_infos": avatar_infos,
            "avatar_name_1": avatar_name_1,
            "avatar_name_2": avatar_name_2,
            "event": event,
            "res": res,
            "style": get_random_story_style(),
            "story_prompt": prompt,
        }

    @staticmethod
    def _make_fallback_story(event: str, res: str, style: str) -> str:
        """生成降级文案"""
        # 不再显示 style，避免出戏
        return f"{event}。{res}。"

    @staticmethod
    async def tell_story(event: str, res: str, *actors: "Avatar", prompt: str = "", allow_relation_changes: bool = False) -> str:
        """
        生成小故事（异步版本）。
        根据 allow_relation_changes 参数选择模板：
        - True: 使用 story_dual.txt（双人故事模板，需要至少2个角色）
        - False: 使用 story_single.txt（通用故事模板）
        
        Args:
            event: 事件描述
            res: 结果描述
            *actors: 参与的角色（1-2个）
            prompt: 可选的故事提示词
            allow_relation_changes:
                历史命名，当前仅用于切换双人/单人故事模板，
                并不会直接写回角色关系。
        """
        non_null = [a for a in actors if a is not None]
        
        # 历史命名沿用中；当前语义只是“是否使用双人故事模板”。
        is_dual = allow_relation_changes and len(non_null) >= 2
        
        template_file = StoryTeller.TEMPLATE_DUAL_FILE if is_dual else StoryTeller.TEMPLATE_SINGLE_FILE
        template_path = StoryTeller._get_template_path(template_file)
        
        avatar_infos = StoryTeller._build_avatar_infos(*actors)
        infos = StoryTeller._build_template_data(event, res, avatar_infos, prompt, *actors)
        
        # 移除了 try-except 块，允许异常向上冒泡，以便 Fail Fast
        data = await call_llm_with_task_name("story_teller", template_path, infos)
        story = data.get("story", "").strip()

        if story:
            return story
        
        return StoryTeller._make_fallback_story(event, res, infos["style"])

    @staticmethod
    async def tell_gathering_story(
        gathering_info: str,
        events_text: str,
        details_text: str,
        related_avatars: list["Avatar"],
        prompt: str = ""
    ) -> str:
        """
        生成聚会/拍卖会等多人事件的故事。
        通用接口，适配 story_gathering.txt 模板。
        
        Args:
            gathering_info: 事件本身的设定信息（如地点、背景、规则等）
            events_text: 发生的具体事件/交互记录
            details_text: 详细信息（包括角色信息、物品信息等）
            related_avatars: 参与的角色列表（主要用于获取世界背景信息）
            prompt: 额外提示词
        """
        if not related_avatars:
            return events_text

        # 使用第一个角色的世界信息
        world_info = related_avatars[0].world.static_info
            
        infos = {
            "world_info": world_info,
            "world_lore": related_avatars[0].world.world_lore.text,
            "gathering_info": gathering_info,
            "events": events_text,
            "details": details_text,
            "style": get_random_story_style(),
            "story_prompt": prompt
        }
        
        # 增加 token 上限以支持长故事
        template_path = StoryTeller._get_template_path(StoryTeller.TEMPLATE_GATHERING_FILE)
        data = await call_llm_with_task_name("story_teller", template_path, infos)
        story = data.get("story", "").strip()
        
        if story:
            return story
            
        return events_text


__all__ = ["StoryTeller"]
