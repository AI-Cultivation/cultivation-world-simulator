from __future__ import annotations
from typing import TYPE_CHECKING
from src.i18n import t
from .manager import _get_manager
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar

def get_opportunity_context_text(avatar: "Avatar") -> str:
    manager = _get_manager(avatar.world)
    record = manager.get_for_avatar(avatar.id)
    if record is None:
        return ""
    remaining = max(0, int(record.expires_month) - int(avatar.world.month_stamp))
    years = remaining // 12
    months = remaining % 12
    if years > 0 and months > 0:
        remaining_text = t("{years} years and {months} months", years=years, months=months)
    elif years > 0:
        remaining_text = t("{years} years", years=years)
    else:
        remaining_text = t("{months} months", months=months)
    return t("Opportunity sense: {hint} This sense may last about {remaining}.", hint=record.hint_text, remaining=remaining_text)
