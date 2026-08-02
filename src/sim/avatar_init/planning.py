from __future__ import annotations
from ._shared import *  # noqa: F403


def _roll_race():
    # Keep the package-level hook patchable for deterministic generation tests.
    from . import roll_avatar_race

    return roll_avatar_race()

@dataclass
class MortalPlan:
    gender: Optional[Gender] = None
    race: Race = field(default_factory=lambda: get_race("human"))
    sect: Optional[Sect] = None
    surname: Optional[str] = None
    parent_avatar: Optional[Avatar] = None
    master_avatar: Optional[Avatar] = None
    level: int = 1
    pos_x: int = 0
    pos_y: int = 0


@dataclass
class PopulationPlan:
    sects: List[Optional[Sect]]
    genders: List[Optional[Gender]]
    races: List[Race]
    surnames: List[Optional[str]]
    relations: Dict[Tuple[int, int], Relation]
    friendliness: Dict[Tuple[int, int], int] = field(default_factory=dict)


@dataclass(frozen=True)
class ConstraintEdge:
    stronger: int
    weaker: int
    min_gap: int
    relation_key: Tuple[int, int]


def _topological_sort(node_count: int, edges: list[ConstraintEdge]) -> list[int] | None:
    incoming = [0] * node_count
    outgoing: dict[int, list[int]] = {idx: [] for idx in range(node_count)}
    for edge in edges:
        if edge.stronger == edge.weaker:
            return None
        outgoing.setdefault(edge.stronger, []).append(edge.weaker)
        incoming[edge.weaker] += 1

    queue = [idx for idx in range(node_count) if incoming[idx] == 0]
    order: list[int] = []
    head = 0
    while head < len(queue):
        node = queue[head]
        head += 1
        order.append(node)
        for nxt in outgoing.get(node, []):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                queue.append(nxt)

    if len(order) != node_count:
        return None
    return order


def _solve_constrained_values(
    node_count: int,
    *,
    min_value: int,
    max_values: list[int],
    edges: list[ConstraintEdge],
) -> tuple[list[int], list[ConstraintEdge]]:
    active_edges = list(edges)

    while True:
        order = _topological_sort(node_count, active_edges)
        if order is None:
            if not active_edges:
                break
            active_edges.pop()
            continue

        upper_bounds = list(max_values)
        impossible_edge: ConstraintEdge | None = None

        for node in order:
            node_upper = upper_bounds[node]
            if node_upper < min_value:
                incoming = [edge for edge in active_edges if edge.weaker == node]
                impossible_edge = incoming[0] if incoming else None
                break
            for edge in active_edges:
                if edge.stronger != node:
                    continue
                candidate = node_upper - edge.min_gap
                if candidate < upper_bounds[edge.weaker]:
                    upper_bounds[edge.weaker] = candidate
                    if upper_bounds[edge.weaker] < min_value:
                        impossible_edge = edge
                        break
            if impossible_edge is not None:
                break

        if impossible_edge is not None:
            active_edges = [edge for edge in active_edges if edge != impossible_edge]
            continue

        assigned = [min_value] * node_count
        outgoing: dict[int, list[ConstraintEdge]] = {idx: [] for idx in range(node_count)}
        for edge in active_edges:
            outgoing.setdefault(edge.stronger, []).append(edge)

        impossible_outgoing: ConstraintEdge | None = None
        for node in reversed(order):
            lower_bound = min_value
            for edge in outgoing.get(node, []):
                lower_bound = max(lower_bound, assigned[edge.weaker] + edge.min_gap)
            if lower_bound > upper_bounds[node]:
                impossible_outgoing = max(
                    outgoing.get(node, []),
                    key=lambda edge: assigned[edge.weaker] + edge.min_gap,
                    default=None,
                )
                break
            assigned[node] = random.randint(lower_bound, upper_bounds[node])

        if impossible_outgoing is not None:
            active_edges = [edge for edge in active_edges if edge != impossible_outgoing]
            continue

        return assigned, active_edges

    return [random.randint(min_value, max(min_value, upper)) for upper in max_values], []

class MortalPlanner:
    """
    负责单个角色的前期规划（宗门、性别、关系、出生点等）。
    """

    @staticmethod
    def plan(
        world: World,
        name: str,
        age: Age,
        *,
        existed_sects: Optional[List[Sect]] = None,
        existing_avatars: Optional[List[Avatar]] = None,
        level: int = 1,
        allow_relations: bool = True,
    ) -> MortalPlan:
        plan = MortalPlan(level=level)
        plan.race = _roll_race()

        plan.gender = random_gender()
        plan.pos_x = random.randint(0, world.map.width - 1)
        plan.pos_y = random.randint(0, world.map.height - 1)

        if existing_avatars is None:
            existing_avatars = world.avatar_manager.get_living_avatars()
        else:
            existing_avatars = [av for av in existing_avatars if not av.is_dead]

        if existed_sects is None:
            try:
                from src.classes.core.sect import sects_by_id as _sects_by_id
                existed_sects = list(_sects_by_id.values())
            except Exception:
                existed_sects = []

        if random.random() < NEW_MORTAL_SECT_PROB:
            accepted_sects = [sect for sect in (existed_sects or []) if sect.accepts_race(plan.race)]
            picked = PopulationPlanner._pick_sects_balanced(accepted_sects, 1)
            plan.sect = picked[0] if picked else None

        if allow_relations and existing_avatars:
            if random.random() < NEW_MORTAL_PARENT_PROB:
                candidates: list[Avatar] = [
                    av
                    for av in existing_avatars
                    if av.age.age >= age.age + PARENT_MIN_DIFF
                    and getattr(getattr(av, "race", None), "id", "human") == plan.race.id
                ]
                if candidates:
                    parent = random.choice(candidates)
                    plan.parent_avatar = parent
                    if not name:
                        if parent.gender is Gender.MALE:
                            plan.surname = pick_surname_for_sect(plan.sect or parent.sect)
                        else:
                            mom_surname = pick_surname_for_sect(plan.sect or parent.sect)
                            for _ in range(5):
                                s = pick_surname_for_sect(plan.sect)
                                if s != mom_surname:
                                    plan.surname = s
                                    break
            if plan.sect is not None and random.random() < NEW_MORTAL_MASTER_PROB:
                same_sect = [av for av in existing_avatars if av.sect is plan.sect]
                if same_sect:
                    stronger = [
                        av
                        for av in same_sect
                        if av.cultivation_progress.level >= plan.level + MASTER_LEVEL_MIN_DIFF
                    ]
                    if stronger:
                        plan.master_avatar = random.choice(stronger)

        return plan


class PopulationPlanner:
    """
    负责批量角色的宗门/关系规划。
    """

    @staticmethod
    def plan_group(n: int, existed_sects: Optional[List[Sect]]) -> PopulationPlan:
        from . import (
            FAMILY_PAIR_CAP_DIV as family_pair_cap_div,
            FAMILY_TRIGGER_PROB as family_trigger_prob,
            LOVERS_PAIR_CAP_DIV as lovers_pair_cap_div,
            LOVERS_TRIGGER_PROB as lovers_trigger_prob,
            MASTER_PAIR_PROB as master_pair_prob,
        )

        n = int(max(0, n))
        use_sects = bool(existed_sects)
        planned_sect: list[Optional[Sect]] = [None] * n
        if n == 0:
            return PopulationPlan(planned_sect, [None] * 0, [], [None] * 0, {}, {})

        planned_race: list[Race] = [_roll_race() for _ in range(n)]

        if use_sects and existed_sects:
            sect_member_target = int(n * SECT_MEMBER_RATIO)
            counts: dict[int, int] = {sect.id: 0 for sect in existed_sects}
            for idx in range(sect_member_target):
                planned_sect[idx] = PopulationPlanner._pick_sect_for_race(existed_sects, planned_race[idx], counts)
            paired = list(zip(planned_sect, list(range(n))))
            random.shuffle(paired)
            planned_sect = [p[0] for p in paired]

        planned_gender: list[Optional[Gender]] = [None] * n
        planned_surname: list[Optional[str]] = [None] * n
        planned_relations: dict[tuple[int, int], Relation] = {}

        # — 家庭 —
        unused_indices = list(range(n))
        random.shuffle(unused_indices)
        family_groups: list[list[int]] = []

        family_groups_budget = max(0, n // family_pair_cap_div)
        for _ in range(family_groups_budget):
            if random.random() >= family_trigger_prob or len(unused_indices) < 2:
                continue

            max_family_size = min(len(unused_indices), FAMILY_CHILDREN_MAX + 1)
            if max_family_size < 2:
                break

            family_size = random.randint(2, max_family_size)
            members = [unused_indices.pop() for _ in range(family_size)]
            parent_idx = members[0]
            child_indices = members[1:]
            family_groups.append(members)

            if random.random() < FATHER_CHILD_PROB:
                surname = pick_surname_for_sect(planned_sect[parent_idx] or planned_sect[child_indices[0]])
                planned_gender[parent_idx] = Gender.MALE
                planned_surname[parent_idx] = surname
                for child_idx in child_indices:
                    planned_surname[child_idx] = surname
                    planned_relations[(parent_idx, child_idx)] = Relation.IS_CHILD_OF
            else:
                planned_gender[parent_idx] = Gender.FEMALE
                mom_surname = pick_surname_for_sect(planned_sect[parent_idx])
                planned_surname[parent_idx] = mom_surname
                child_surname: Optional[str] = None
                for _ in range(5):
                    candidate = pick_surname_for_sect(planned_sect[parent_idx])
                    if candidate != mom_surname:
                        child_surname = candidate
                        break
                if child_surname is None:
                    child_surname = pick_surname_for_sect(planned_sect[parent_idx])
                for child_idx in child_indices:
                    planned_surname[child_idx] = child_surname
                    planned_relations[(parent_idx, child_idx)] = Relation.IS_CHILD_OF

        if use_sects and existed_sects:
            for family in family_groups:
                PopulationPlanner._rebalance_family_sects(planned_sect, family, existed_sects)

        leftover = unused_indices[:]

        # — 道侣 —
        random.shuffle(leftover)
        lovers_budget = max(0, n // lovers_pair_cap_div)
        i = 0
        while i + 1 < len(leftover) and lovers_budget > 0:
            if random.random() < lovers_trigger_prob:
                a = leftover[i]
                b = leftover[i + 1]
                if (a, b) not in planned_relations and (b, a) not in planned_relations:
                    if planned_gender[a] is None and planned_gender[b] is None:
                        planned_gender[a] = Gender.MALE if random.random() < 0.5 else Gender.FEMALE
                        planned_gender[b] = Gender.FEMALE if planned_gender[a] is Gender.MALE else Gender.MALE
                    elif planned_gender[a] is None:
                        planned_gender[a] = Gender.MALE if planned_gender[b] is Gender.FEMALE else Gender.FEMALE
                    elif planned_gender[b] is None:
                        planned_gender[b] = Gender.MALE if planned_gender[a] is Gender.FEMALE else Gender.FEMALE
                    if planned_gender[a] != planned_gender[b]:
                        planned_relations[(a, b)] = Relation.IS_LOVER_OF
                lovers_budget -= 1
            i += 2

        # — 师徒（同宗门）—
        if use_sects and existed_sects:
            members_by_sect: dict[int, list[int]] = {s.id: [] for s in existed_sects}
            for idx, sect in enumerate(planned_sect):
                if sect is not None:
                    members_by_sect.setdefault(sect.id, []).append(idx)
            for members in members_by_sect.values():
                random.shuffle(members)
                j = 0
                while j + 1 < len(members):
                    if random.random() < master_pair_prob:
                        master, apprentice = members[j], members[j + 1]
                        if (master, apprentice) not in planned_relations and (apprentice, master) not in planned_relations:
                            planned_relations[(master, apprentice)] = Relation.IS_DISCIPLE_OF
                    j += 2

        for idx in range(n):
            if planned_gender[idx] is None:
                planned_gender[idx] = random_gender()

        return PopulationPlan(planned_sect, planned_gender, planned_race, planned_surname, planned_relations, {})

    @staticmethod
    def _pick_sects_balanced(existed_sects: List[Sect], k: int) -> list[Optional[Sect]]:
        if not existed_sects or k <= 0:
            return []
        counts: dict[int, int] = {s.id: 0 for s in existed_sects}
        chosen: list[Optional[Sect]] = []
        for _ in range(k):
            min_count = min(counts.values()) if counts else 0
            candidates = [s for s in existed_sects if counts.get(s.id, 0) == min_count]
            s = random.choice(candidates)
            counts[s.id] = counts.get(s.id, 0) + 1
            chosen.append(s)
        return chosen

    @staticmethod
    def _pick_sect_for_race(
        existed_sects: List[Sect],
        race: Race,
        current_counts: dict[int, int],
    ) -> Optional[Sect]:
        candidates = [sect for sect in existed_sects if sect.accepts_race(race)]
        if not candidates:
            return None
        min_count = min(current_counts.get(sect.id, 0) for sect in candidates)
        tied = [sect for sect in candidates if current_counts.get(sect.id, 0) == min_count]
        sect = random.choice(tied)
        current_counts[sect.id] = current_counts.get(sect.id, 0) + 1
        return sect

    @staticmethod
    def _pick_different_sect(
        existed_sects: List[Sect],
        current_counts: dict[int, int],
        banned_sect_ids: set[int],
    ) -> Optional[Sect]:
        candidates = [sect for sect in existed_sects if sect.id not in banned_sect_ids]
        if not candidates:
            return None
        min_count = min(current_counts.get(sect.id, 0) for sect in candidates)
        tied = [sect for sect in candidates if current_counts.get(sect.id, 0) == min_count]
        return random.choice(tied)

    @staticmethod
    def _rebalance_family_sects(
        planned_sect: list[Optional[Sect]],
        family: list[int],
        existed_sects: List[Sect],
    ) -> None:
        if not family:
            return

        family_counts: dict[int, int] = {}
        for idx in family:
            sect = planned_sect[idx]
            if sect is not None:
                family_counts[sect.id] = family_counts.get(sect.id, 0) + 1

        if len(family) == 1:
            return

        parent_idx = family[0]
        parent_sect = planned_sect[parent_idx]
        global_counts: dict[int, int] = {sect.id: 0 for sect in existed_sects}
        for sect in planned_sect:
            if sect is not None:
                global_counts[sect.id] = global_counts.get(sect.id, 0) + 1

        if parent_sect is not None and family_counts.get(parent_sect.id, 0) > FAMILY_SAME_SECT_CAP:
            family_counts[parent_sect.id] = 1

        for idx in family[1:]:
            current = planned_sect[idx]
            if current is not None and family_counts.get(current.id, 0) > FAMILY_SAME_SECT_CAP:
                family_counts[current.id] -= 1
                global_counts[current.id] = max(0, global_counts.get(current.id, 0) - 1)
                current = None

            roll = random.random()
            chosen = current
            if parent_sect is not None and family_counts.get(parent_sect.id, 0) < FAMILY_SAME_SECT_CAP and roll < FAMILY_PARENT_SECT_FOLLOW_PROB:
                chosen = parent_sect
            elif roll < FAMILY_PARENT_SECT_FOLLOW_PROB + FAMILY_OTHER_SECT_PROB:
                banned = {
                    sect_id
                    for sect_id, count in family_counts.items()
                    if count >= FAMILY_SAME_SECT_CAP
                }
                replacement = PopulationPlanner._pick_different_sect(existed_sects, global_counts, banned)
                chosen = replacement
            else:
                chosen = None

            previous = planned_sect[idx]
            if previous is not None and previous is not chosen:
                family_counts[previous.id] = max(0, family_counts.get(previous.id, 0) - 1)
                global_counts[previous.id] = max(0, global_counts.get(previous.id, 0) - 1)

            planned_sect[idx] = chosen
            if chosen is not None:
                family_counts[chosen.id] = family_counts.get(chosen.id, 0) + 1
                global_counts[chosen.id] = global_counts.get(chosen.id, 0) + 1
