from __future__ import annotations
from ._shared import *  # noqa: F403
from ._shared import _apply_structural_initial_friendliness

class RelationApplier:
    """
    负责将规划关系写入 Avatar 实例。
    """

    @staticmethod
    def apply(
        avatars_by_index: List[Optional[Avatar]],
        relations: dict[tuple[int, int], Relation],
        friendliness: Optional[dict[tuple[int, int], int]] = None,
    ) -> None:
        for (a, b), relation in relations.items():
            if a >= len(avatars_by_index) or b >= len(avatars_by_index):
                continue
            av_a = avatars_by_index[a]
            av_b = avatars_by_index[b]
            if av_a is None or av_b is None or av_a is av_b:
                continue
            av_a.set_relation(av_b, relation)
            _apply_structural_initial_friendliness(av_a, av_b, relation)

        if not friendliness:
            return

        for (a, b), value in friendliness.items():
            if a >= len(avatars_by_index) or b >= len(avatars_by_index):
                continue
            av_a = avatars_by_index[a]
            av_b = avatars_by_index[b]
            if av_a is None or av_b is None or av_a is av_b:
                continue
            set_friendliness(av_a, av_b, value)


class SectRankAssigner:
    """
    负责宗门职位的分配，保证掌门唯一。
    """

    @staticmethod
    def assign_one(avatar: Avatar, world: World) -> None:
        if avatar.sect is None:
            avatar.sect_rank = None
            return

        from src.classes.sect_ranks import get_rank_from_realm, sect_has_patriarch, SectRank

        rank = get_rank_from_realm(avatar.cultivation_progress.realm)
        if rank == SectRank.Patriarch and sect_has_patriarch(avatar):
            rank = SectRank.Elder
        avatar.sect_rank = rank

    @staticmethod
    def assign_batch(avatars: List[Avatar], world: World) -> None:
        from src.classes.sect_ranks import get_rank_from_realm, SectRank

        for avatar in avatars:
            if avatar is None:
                continue
            if avatar.sect is None:
                avatar.sect_rank = None
            else:
                avatar.sect_rank = get_rank_from_realm(avatar.cultivation_progress.realm)

        sect_nascent_souls: Dict[int, List[Avatar]] = {}
        for avatar in avatars:
            if avatar is None or avatar.sect is None:
                continue
            if avatar.sect_rank == SectRank.Patriarch:
                sect_id = avatar.sect.id
                if sect_id not in sect_nascent_souls:
                    sect_nascent_souls[sect_id] = []
                sect_nascent_souls[sect_id].append(avatar)

        existing_patriarchs: Dict[int, bool] = {}
        for other in world.avatar_manager.avatars.values():
            if other.sect is not None and other.sect_rank == SectRank.Patriarch:
                existing_patriarchs[other.sect.id] = True

        for sect_id, candidates in sect_nascent_souls.items():
            if existing_patriarchs.get(sect_id, False):
                for avatar in candidates:
                    avatar.sect_rank = SectRank.Elder
            else:
                candidates.sort(key=lambda av: av.cultivation_progress.level, reverse=True)
                for avatar in candidates[1:]:
                    avatar.sect_rank = SectRank.Elder
