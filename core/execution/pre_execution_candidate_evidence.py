"""Authority-neutral BUY evidence derived from the existing decision output."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from core.decision.decision_engine import BuySignal, MarketSnapshot
from core.execution.authority_digest import (
    market_snapshot_digest,
    strategy_decision_digest,
    upstream_evidence_digest,
)


DECISION_ENGINE_EVIDENCE_SOURCE_COMPONENT = "decision-engine-buy-signal"
DECISION_ENGINE_EVIDENCE_PROFILE_VERSION = "buy-signal-evidence-v1"


def _normalize_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    if not symbol:
        raise ValueError("symbol is required")
    return symbol


def _normalize_timestamp(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("produced_at must be datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class PreExecutionCandidateEvidence:
    candidate_id: str
    source_component: str
    source_contract_version: str
    symbol: str
    side: str
    reason_codes: tuple[str, ...]
    market_snapshot_digest: str
    strategy_decision_digest: str
    produced_at: datetime

    def __post_init__(self) -> None:
        symbol = _normalize_symbol(self.symbol)
        if self.source_component != DECISION_ENGINE_EVIDENCE_SOURCE_COMPONENT:
            raise ValueError("source_component is internally governed")
        if self.source_contract_version != DECISION_ENGINE_EVIDENCE_PROFILE_VERSION:
            raise ValueError("source_contract_version is internally governed")
        if self.side != "BUY":
            raise ValueError("the current evidence profile is BUY-only")
        if not self.reason_codes or any(not str(reason).strip() for reason in self.reason_codes):
            raise ValueError("reason_codes must contain non-empty values")
        produced_at = _normalize_timestamp(self.produced_at)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "reason_codes", tuple(str(reason) for reason in self.reason_codes))
        object.__setattr__(self, "produced_at", produced_at)
        expected_id = f"candidate-{self.evidence_digest}"
        if self.candidate_id != expected_id:
            raise ValueError("candidate_id must be derived from canonical evidence")

    @property
    def evidence_digest(self) -> str:
        return upstream_evidence_digest(
            source_component=self.source_component,
            source_contract_version=self.source_contract_version,
            symbol=self.symbol,
            side=self.side,
            reason_codes=self.reason_codes,
            market_snapshot_digest_value=self.market_snapshot_digest,
            strategy_decision_digest_value=self.strategy_decision_digest,
            produced_at=self.produced_at,
        )

    @classmethod
    def from_buy_signal(
        cls, snapshot: MarketSnapshot, signal: BuySignal
    ) -> "PreExecutionCandidateEvidence":
        snapshot_symbol = _normalize_symbol(snapshot.pair)
        signal_symbol = _normalize_symbol(signal.pair)
        if snapshot_symbol != signal_symbol:
            raise ValueError("snapshot and BuySignal symbols must match")

        reason_codes = tuple(str(reason) for reason in (signal.reasons or ()))
        if not reason_codes:
            raise ValueError("BuySignal must contain reason evidence")
        market_digest = market_snapshot_digest(snapshot)
        strategy_digest = strategy_decision_digest(
            symbol=signal_symbol,
            reason_codes=reason_codes,
            confidence=float(signal.confidence),
        )
        produced_at = _normalize_timestamp(signal.timestamp)
        unsigned = {
            "source_component": DECISION_ENGINE_EVIDENCE_SOURCE_COMPONENT,
            "source_contract_version": DECISION_ENGINE_EVIDENCE_PROFILE_VERSION,
            "symbol": signal_symbol,
            "side": "BUY",
            "reason_codes": reason_codes,
            "market_snapshot_digest": market_digest,
            "strategy_decision_digest": strategy_digest,
            "produced_at": produced_at,
        }
        evidence_digest = upstream_evidence_digest(**{
            "source_component": unsigned["source_component"],
            "source_contract_version": unsigned["source_contract_version"],
            "symbol": unsigned["symbol"],
            "side": unsigned["side"],
            "reason_codes": unsigned["reason_codes"],
            "market_snapshot_digest_value": unsigned["market_snapshot_digest"],
            "strategy_decision_digest_value": unsigned["strategy_decision_digest"],
            "produced_at": unsigned["produced_at"],
        })
        return cls(candidate_id=f"candidate-{evidence_digest}", **unsigned)
