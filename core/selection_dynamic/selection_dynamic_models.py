# =============================================================================
# core/selection_dynamic/selection_dynamic_models.py
# H&A — Selection Dynamic Models
# =============================================================================

from dataclasses import dataclass

from core.selection_dynamic.policy_modes import SelectionPolicyMode


@dataclass
class DynamicMarketContext:
    mqii_state: str
    liquidity_score: float
    approved_count: int
    uptrend_count: int
    avg_volume_ratio: float


@dataclass
class DynamicSelectionResult:
    mode: SelectionPolicyMode
    approved: bool
    reason: str
    min_score_required: float