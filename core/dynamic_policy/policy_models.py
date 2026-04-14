# =============================================================================
# core/dynamic_policy/policy_models.py
# H&A — Dynamic Policy Models (NPD-H&A v1)
# =============================================================================

from dataclasses import dataclass
from typing import Optional


# =============================================================================
# INPUT — CONTEXTO DE MERCADO
# =============================================================================

@dataclass
class MarketContext:
    pair: str
    price: float
    rsi: float
    ema_fast: float
    ema_slow: float
    volume_ratio: float
    atr: float


# =============================================================================
# INPUT — ESTADO DO SISTEMA
# =============================================================================

@dataclass
class SystemContext:
    balance: float
    active_slots: int
    max_slots: int
    drawdown_pct: float
    loss_streak: int
    win_rate_recent: float


# =============================================================================
# INPUT — FEEDBACK LC-1
# =============================================================================

@dataclass
class LC1Feedback:
    pair_win_rate: float = 0.5
    pair_loss_streak: int = 0
    avg_profit_pct: float = 0.0
    avg_loss_pct: float = 0.0
    sample_size: int = 0


# =============================================================================
# OUTPUT — POLICY DINÂMICA
# =============================================================================

@dataclass
class DynamicPolicy:

    # ---------------------------------------------------------
    # ENTRADA
    # ---------------------------------------------------------
    min_rsi: float
    max_rsi: float
    min_volume_ratio: float
    min_ema_spread: float

    allow_sideways: bool
    sideways_min_rsi: float
    sideways_min_volume: float
    sideways_min_spread: float

    # ---------------------------------------------------------
    # RISCO
    # ---------------------------------------------------------
    min_rr: float
    expected_profit_pct: float
    stop_loss_pct: float

    # ---------------------------------------------------------
    # OPERAÇÃO
    # ---------------------------------------------------------
    capital_multiplier: float
    max_active_slots: int
    rejection_cooldown: int


# =============================================================================
# RESULTADO SIMPLIFICADO (DEBUG / LOG)
# =============================================================================

@dataclass
class PolicyDebugInfo:
    regime: str
    atr_pct: float
    ema_spread: float
    notes: Optional[str] = None