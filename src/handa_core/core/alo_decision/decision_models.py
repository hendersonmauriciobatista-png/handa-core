# ============================================================
# core/alo_decision/decision_models.py
# H&A - ALO Decision Models
# Estruturas base para a camada de decisão do ALO
# ============================================================

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================
# MODO DA CAMADA
# ============================================================


class AloDecisionMode(str, Enum):
    OBSERVER = "OBSERVER"
    ADVISORY = "ADVISORY"
    ACTIVE = "ACTIVE"


# ============================================================
# INPUT DA DECISÃO
# ============================================================


@dataclass
class AloDecisionInput:
    symbol: str

    # ===== CONTEXTO DE MERCADO =====
    trend: str = ""
    momentum: str = ""
    market_state: str = ""
    volume_state: str = ""

    # ===== INDICADORES =====
    rsi: float = 0.0
    volume_ratio: float = 0.0
    price: float = 0.0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    market_score: float = 0.0

    # ===== CONTEXTO MACRO =====
    mqii_state: str = ""
    mqii_score: float = 0.0
    liquidity_score: float = 0.0
    liquidity_label: str = ""

    # ===== CONTEXTO DE APRENDIZADO =====
    profile_exists: bool = False
    total_events: int = 0
    execution_count: int = 0
    non_execution_count: int = 0
    structural_block_count: int = 0
    quality_filter_count: int = 0
    low_score_count: int = 0
    loss_count: int = 0
    win_count: int = 0
    block_bias: float = 0.0
    confidence_score: float = 0.0

    # ===== CONTEXTO OPERACIONAL =====
    slot_id: Optional[int] = None
    available_capital: float = 0.0
    base_capital: float = 0.0

    # ===== PAYLOAD BRUTO OPCIONAL =====
    raw_profile: Dict[str, Any] = field(default_factory=dict)
    raw_analysis: Dict[str, Any] = field(default_factory=dict)
    raw_snapshot: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# RESULTADO DA DECISÃO
# ============================================================


@dataclass
class AloDecisionResult:
    mode: AloDecisionMode = AloDecisionMode.OBSERVER

    # ===== DECISÃO BASE =====
    should_block: bool = False

    # ===== AJUSTES FUTUROS =====
    confidence_adjustment: float = 0.0
    capital_adjustment: float = 1.0

    # ===== OBSERVABILIDADE =====
    labels: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    # ===== METADADOS =====
    observer_only: bool = True
    block_suggested: bool = False
    confidence_suggested: float = 0.0
    capital_suggested: float = 1.0

    # ===== DEBUG =====
    score_components: Dict[str, float] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value if isinstance(self.mode, Enum) else str(self.mode),
            "should_block": bool(self.should_block),
            "confidence_adjustment": float(self.confidence_adjustment),
            "capital_adjustment": float(self.capital_adjustment),
            "labels": list(self.labels),
            "reasons": list(self.reasons),
            "observer_only": bool(self.observer_only),
            "block_suggested": bool(self.block_suggested),
            "confidence_suggested": float(self.confidence_suggested),
            "capital_suggested": float(self.capital_suggested),
            "score_components": dict(self.score_components),
            "diagnostics": dict(self.diagnostics),
        }
