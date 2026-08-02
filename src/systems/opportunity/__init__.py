from .context import get_opportunity_context_text
from .config import _get_cfg_value, _opportunity_probability, _weighted_choice_from_mapping
from .manager import _get_manager
from .models import OpportunityManager, OpportunityOutcome, OpportunityRecord, OpportunityTargetType
from .outcomes import _load_boon_records, _pick_equipment, _pick_outcome
from .persistence import load_opportunities, serialize_opportunities
from .phases import phase_check_opportunities, phase_generate_opportunities, try_generate_opportunity

__all__ = [
    "OpportunityManager",
    "OpportunityOutcome",
    "OpportunityRecord",
    "OpportunityTargetType",
    "get_opportunity_context_text",
    "load_opportunities",
    "phase_check_opportunities",
    "phase_generate_opportunities",
    "serialize_opportunities",
    "try_generate_opportunity",
]
