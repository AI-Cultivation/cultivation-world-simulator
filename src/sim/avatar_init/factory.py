from __future__ import annotations
from ._shared import *  # noqa: F403
from ._shared import (
    _apply_structural_initial_friendliness,
    _assign_initial_goldfinger,
    _assign_initial_official_status,
    _assign_initial_sect_contribution,
    _create_random_innate_lifespan,
    _get_initial_age_max_for_realm,
    _mark_dead_if_lifespan_exhausted,
    _plan_group_initial_friendliness,
    _roll_cultivation_start_month,
)
from .planning import ConstraintEdge, MortalPlanner, PopulationPlan, PopulationPlanner, _solve_constrained_values
from .relations import RelationApplier, SectRankAssigner

class AvatarFactory:
    """
    根据规划产出 Avatar，对装备、宗门职位和关系进行统一处理。
    """

    @staticmethod
    def build_from_plan(
        world: World,
        current_month_stamp: MonthStamp,
        *,
        name: str,
        age: Age,
        plan: MortalPlan,
        attach_relations: bool = True,
        overrides: Optional[Dict[str, object]] = None,
        allow_random_goldfinger: bool = True,
    ) -> Avatar:
        if name:
            final_name = name
        else:
            if plan.surname:
                final_name = get_random_name_with_surname(plan.gender, plan.surname, plan.sect)
            else:
                final_name = get_random_name_for_race(plan.gender, plan.race, plan.sect)

        birth_month_stamp = current_month_stamp - age.age * 12 + random.randint(0, 11)

        avatar = Avatar(
            world=world,
            name=final_name,
            id=get_avatar_id(),
            birth_month_stamp=MonthStamp(birth_month_stamp),
            age=age,
            gender=plan.gender,
            cultivation_progress=CultivationProgress(plan.level),
            pos_x=plan.pos_x,
            pos_y=plan.pos_y,
            sect=plan.sect,
            race=plan.race,
        )

        avatar.magic_stone = MagicStone(50)
        avatar.tile = world.map.get_tile(avatar.pos_x, avatar.pos_y)

        # 确定出生地
        parents_list = []
        if plan.parent_avatar:
            parents_list.append(plan.parent_avatar)
        avatar.born_region_id = get_born_region_id(world, parents=parents_list, sect=plan.sect, race=plan.race)

        # 在构造 Avatar 实例后计算并赋值：
        if avatar.cultivation_start_month_stamp is None:
            avatar.cultivation_start_month_stamp = _roll_cultivation_start_month(
                MonthStamp(birth_month_stamp),
                current_month_stamp,
            )

        SectRankAssigner.assign_one(avatar, world)
        _assign_initial_sect_contribution(avatar)
        EquipmentAllocator.assign_weapon(avatar)
        EquipmentAllocator.assign_auxiliary(avatar)

        if attach_relations:
            if plan.parent_avatar is not None:
                plan.parent_avatar.acknowledge_child(avatar)
            if plan.master_avatar is not None:
                plan.master_avatar.accept_disciple(avatar)
                _apply_structural_initial_friendliness(plan.master_avatar, avatar, Relation.IS_DISCIPLE_OF)
            from src.classes.relation.relations import update_second_degree_relations

            if plan.parent_avatar is not None:
                update_second_degree_relations(plan.parent_avatar)
            if plan.master_avatar is not None:
                update_second_degree_relations(plan.master_avatar)
            update_second_degree_relations(avatar)

        if avatar.technique is not None:
            mapped = attribute_to_root(avatar.technique.attribute)
            if mapped is not None:
                avatar.root = mapped

        if overrides:
            AvatarFactory._apply_overrides(avatar, overrides)

        if allow_random_goldfinger:
            _assign_initial_goldfinger(avatar)

        _mark_dead_if_lifespan_exhausted(avatar, current_month_stamp)

        return avatar

    @staticmethod
    def build_group(
        world: World,
        current_month_stamp: MonthStamp,
        population_plan: PopulationPlan,
    ) -> dict[str, Avatar]:
        planned_sect = population_plan.sects
        planned_gender = population_plan.genders
        planned_race = population_plan.races
        planned_surname = population_plan.surnames
        planned_relations = population_plan.relations
        n = len(planned_sect)
        width, height = world.map.width, world.map.height

        constrained_relations = dict(planned_relations)
        level_edges: list[ConstraintEdge] = []
        for (a, b), rel in constrained_relations.items():
            if rel is Relation.IS_CHILD_OF:
                level_edges.append(ConstraintEdge(a, b, PARENT_LEVEL_MIN_DIFF, (a, b)))
            elif rel is Relation.IS_DISCIPLE_OF:
                level_edges.append(ConstraintEdge(a, b, MASTER_LEVEL_MIN_DIFF, (a, b)))

        levels, valid_level_edges = _solve_constrained_values(
            n,
            min_value=LEVEL_MIN,
            max_values=[LEVEL_MAX for _ in range(n)],
            edges=level_edges,
        )
        valid_level_relation_keys = {edge.relation_key for edge in valid_level_edges}
        for (a, b), rel in list(constrained_relations.items()):
            if rel in (Relation.IS_CHILD_OF, Relation.IS_DISCIPLE_OF) and (a, b) not in valid_level_relation_keys:
                constrained_relations.pop((a, b), None)

        age_edges = [
            ConstraintEdge(a, b, PARENT_MIN_DIFF, (a, b))
            for (a, b), rel in constrained_relations.items()
            if rel is Relation.IS_CHILD_OF
        ]
        age_max_values = [
            _get_initial_age_max_for_realm(CultivationProgress(levels[i]).realm)
            for i in range(n)
        ]
        for edge in age_edges:
            age_max_values[edge.stronger] = min(age_max_values[edge.stronger], PARENT_AGE_CAP)

        ages, valid_age_edges = _solve_constrained_values(
            n,
            min_value=AGE_MIN,
            max_values=age_max_values,
            edges=age_edges,
        )
        valid_age_relation_keys = {edge.relation_key for edge in valid_age_edges}
        for (a, b), rel in list(constrained_relations.items()):
            if rel is Relation.IS_CHILD_OF and (a, b) not in valid_age_relation_keys:
                constrained_relations.pop((a, b), None)

        avatars_by_index: list[Avatar] = [None] * n  # type: ignore
        avatars_by_id: dict[str, Avatar] = {}

        for i in range(n):
            gender = planned_gender[i] or random_gender()
            race = planned_race[i] if i < len(planned_race) else get_race("human")
            sect = planned_sect[i]
            if sect is not None and not sect.accepts_race(race):
                sect = None

            if planned_surname[i]:
                name = get_random_name_with_surname(gender, planned_surname[i] or "", sect)
            else:
                name = get_random_name_for_race(gender, race, sect)

            level = levels[i]
            cultivation_progress = CultivationProgress(level)
            age_years = ages[i]
            age = Age(
                age_years,
                cultivation_progress.realm,
                innate_max_lifespan=_create_random_innate_lifespan(),
            )

            x, y = random.randint(0, width - 1), random.randint(0, height - 1)
            birth_month_stamp = current_month_stamp - age_years * 12 + random.randint(0, 11)

            avatar = Avatar(
                world=world,
                name=name,
                id=get_avatar_id(),
                birth_month_stamp=MonthStamp(birth_month_stamp),
                age=age,
                gender=gender,
                cultivation_progress=cultivation_progress,
                pos_x=x,
                pos_y=y,
                root=random.choice(list(Root)),
                sect=sect,
                race=race,
            )

            avatar.magic_stone = MagicStone(50)
            avatar.tile = world.map.get_tile(x, y)

            avatar.born_region_id = get_born_region_id(world, parents=[], sect=sect, race=race)

            # 在构造 Avatar 实例后计算并赋值：
            if avatar.cultivation_start_month_stamp is None:
                avatar.cultivation_start_month_stamp = _roll_cultivation_start_month(
                    MonthStamp(birth_month_stamp),
                    current_month_stamp,
                )

            if sect is not None:
                avatar.alignment = sect.alignment
                avatar.technique = get_technique_by_sect(sect)

            EquipmentAllocator.assign_weapon(avatar)
            EquipmentAllocator.assign_auxiliary(avatar)

            if avatar.technique is not None:
                mapped = attribute_to_root(avatar.technique.attribute)
                if mapped is not None:
                    avatar.root = mapped

            _assign_initial_official_status(avatar)
            _assign_initial_goldfinger(avatar)

            _mark_dead_if_lifespan_exhausted(avatar, current_month_stamp)

            avatars_by_index[i] = avatar
            avatars_by_id[avatar.id] = avatar

        SectRankAssigner.assign_batch(avatars_by_index, world)
        for avatar in avatars_by_index:
            if avatar is not None:
                _assign_initial_sect_contribution(avatar)
        planned_friendliness = _plan_group_initial_friendliness(avatars_by_index, constrained_relations)
        RelationApplier.apply(avatars_by_index, constrained_relations, planned_friendliness)

        for i, avatar in enumerate(avatars_by_index):
            if avatar is None:
                continue
            parents = [
                avatars_by_index[p_idx]
                for (p_idx, c_idx), rel in constrained_relations.items()
                if rel is Relation.IS_CHILD_OF and c_idx == i and avatars_by_index[p_idx] is not None
            ]
            avatar.born_region_id = get_born_region_id(world, parents=parents, sect=avatar.sect, race=avatar.race)

        from src.classes.relation.relations import update_second_degree_relations

        for avatar in avatars_by_index:
            if avatar is not None:
                update_second_degree_relations(avatar)

        return avatars_by_id

    @staticmethod
    def _apply_overrides(avatar: Avatar, overrides: Dict[str, object]) -> None:
        technique = overrides.get("technique")
        if isinstance(technique, Technique):
            avatar.technique = technique
            mapped = attribute_to_root(technique.attribute)
            if mapped is not None:
                avatar.root = mapped

        weapon = overrides.get("weapon")
        if isinstance(weapon, Weapon):
            avatar.weapon = weapon

        auxiliary = overrides.get("auxiliary")
        if isinstance(auxiliary, Auxiliary):
            avatar.auxiliary = auxiliary

        goldfinger = overrides.get("goldfinger")
        if isinstance(goldfinger, Goldfinger):
            avatar.goldfinger = goldfinger
            avatar.goldfinger_state = {}

        personas = overrides.get("personas")
        if isinstance(personas, list) and personas:
            avatar.personas = personas  # type: ignore[assignment]

        appearance = overrides.get("appearance")
        if isinstance(appearance, int):
            avatar.appearance = get_appearance_by_level(appearance)


def create_random_mortal(world: World, current_month_stamp: MonthStamp, name: str, age: Age, level: int = 1) -> Avatar:
    """
    创建一个完全随机的新修士，包含可能的亲属/师徒关系。
    """
    plan = MortalPlanner.plan(world, name=name, age=age, level=level, allow_relations=True)
    return AvatarFactory.build_from_plan(world, current_month_stamp, name=name, age=age, plan=plan)


def make_avatars(
    world: World,
    count: int = 12,
    current_month_stamp: MonthStamp = MonthStamp(100 * 12),
    existed_sects: Optional[List[Sect]] = None,
) -> dict[str, Avatar]:
    population_plan = PopulationPlanner.plan_group(count, existed_sects)
    random_avatars = AvatarFactory.build_group(world, current_month_stamp, population_plan)
    return random_avatars

# —— 指定参数创建：支持传入字符串并解析为对象 ——
