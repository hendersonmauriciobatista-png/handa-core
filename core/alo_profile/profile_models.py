# ============================================================
# core/alo_profile/profile_models.py
# Modelos de perfil persistente do ALO por ativo
# ============================================================

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AloSymbolProfile:
    symbol: str

    # =========================
    # ESTATÍSTICAS DE TRADE
    # =========================
    total_trades: int = 0
    wins: int = 0
    losses: int = 0

    # =========================
    # ESTATÍSTICAS DE NÃO-EXECUÇÃO
    # =========================
    non_execution_count: int = 0
    structural_rejections: int = 0
    technical_rejections: int = 0
    macro_block_count: int = 0

    # =========================
    # MEMÓRIA CURTA / CONTEXTO
    # =========================
    recent_results: List[float] = field(default_factory=list)
    recent_reasons: List[str] = field(default_factory=list)

    # =========================
    # PENALIDADES / BIASES
    # =========================
    lateral_penalty: float = 0.0
    false_breakout_penalty: float = 0.0

    confidence_bias: float = 0.0
    capital_bias: float = 1.0
    block_bias: float = 0.0

    # =========================
    # METADADOS
    # =========================
    last_market_state: str = ""
    last_update: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AloSymbolProfile":
        return cls(
            symbol=str(data.get("symbol", "")).upper(),
            total_trades=int(data.get("total_trades", 0) or 0),
            wins=int(data.get("wins", 0) or 0),
            losses=int(data.get("losses", 0) or 0),
            non_execution_count=int(data.get("non_execution_count", 0) or 0),
            structural_rejections=int(data.get("structural_rejections", 0) or 0),
            technical_rejections=int(data.get("technical_rejections", 0) or 0),
            macro_block_count=int(data.get("macro_block_count", 0) or 0),
            recent_results=list(data.get("recent_results", []) or []),
            recent_reasons=list(data.get("recent_reasons", []) or []),
            lateral_penalty=float(data.get("lateral_penalty", 0.0) or 0.0),
            false_breakout_penalty=float(
                data.get("false_breakout_penalty", 0.0) or 0.0
            ),
            confidence_bias=float(data.get("confidence_bias", 0.0) or 0.0),
            capital_bias=float(data.get("capital_bias", 1.0) or 1.0),
            block_bias=float(data.get("block_bias", 0.0) or 0.0),
            last_market_state=str(data.get("last_market_state", "") or ""),
            last_update=str(data.get("last_update", _utc_now_iso()) or _utc_now_iso()),
        )


@dataclass
class AloProfileEvaluation:
    symbol: str
    profile_label: str = "NEUTRAL"
    should_block: bool = False
    confidence_adjustment: float = 0.0
    capital_adjustment: float = 1.0
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
