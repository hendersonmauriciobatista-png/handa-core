import random
import time
from dataclasses import dataclass
from typing import Literal


# =================================================
# SIGNAL ENVELOPE (V1)
# =================================================
MarketRegime = Literal["TREND", "RANGE", "CHAOTIC"]
SignalStrength = Literal["LOW", "MEDIUM", "HIGH"]
RiskFlag = Literal["OK", "CAUTION", "BLOCK"]
ExecutionWindow = Literal["OPEN", "WAIT", "CLOSED"]
TradeIntent = Literal["NONE", "PLAN", "EXECUTE", "ABORT"]
SlotState = Literal[
    "IDLE",
    "ANALYZING",
    "ANALYZED",
    "TRADE_PLANNED",
    "TRADING",
    "DONE",
]


@dataclass
class SignalEnvelope:
    source: Literal["MOCK", "BINANCE_LIVE"]
    timestamp: float
    symbol: str

    market_regime: MarketRegime
    signal_strength: SignalStrength
    confidence_score: int

    risk_flag: RiskFlag
    execution_window: ExecutionWindow

    trade_intent: TradeIntent
    slot_state: SlotState


# =================================================
# MOCK SIGNAL GENERATOR v1
# =================================================
class MockSignalGenerator:
    """
    Gera sinais MOCK coerentes no tempo.
    NÃO simula preço.
    Simula apenas decisão e contexto.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self._last_regime = None
        self._last_strength = None
        self._last_update = 0.0

    # -------------------------
    # API PRINCIPAL
    # -------------------------
    def generate(self, slot_state: SlotState) -> SignalEnvelope:
        now = time.time()

        # evita flickering
        if now - self._last_update < random.uniform(2, 5):
            return self._reuse_last(slot_state)

        market_regime = self._pick_market_regime()
        signal_strength = self._pick_signal_strength(market_regime)
        confidence = self._pick_confidence(signal_strength)

        risk_flag = self._pick_risk(market_regime)
        execution_window = self._pick_execution_window(risk_flag)

        trade_intent = self._decide_intent(
            slot_state,
            signal_strength,
            confidence,
            risk_flag,
            execution_window,
        )

        envelope = SignalEnvelope(
            source="MOCK",
            timestamp=now,
            symbol=self.symbol,
            market_regime=market_regime,
            signal_strength=signal_strength,
            confidence_score=confidence,
            risk_flag=risk_flag,
            execution_window=execution_window,
            trade_intent=trade_intent,
            slot_state=slot_state,
        )

        self._cache(envelope)
        return envelope

    # =================================================
    # DECISÕES INTERNAS
    # =================================================
    def _decide_intent(
        self,
        slot_state: SlotState,
        strength: SignalStrength,
        confidence: int,
        risk: RiskFlag,
        window: ExecutionWindow,
    ) -> TradeIntent:

        if risk == "BLOCK" or window == "CLOSED":
            return "ABORT"

        if slot_state == "ANALYZED":
            if strength == "HIGH" and confidence >= 70 and window == "OPEN":
                return "PLAN"
            return "NONE"

        if slot_state == "TRADE_PLANNED":
            if window == "OPEN" and confidence >= 75:
                return "EXECUTE"
            if window == "WAIT":
                return "PLAN"
            return "ABORT"

        return "NONE"

    # =================================================
    # GERADORES DE CONTEXTO
    # =================================================
    def _pick_market_regime(self) -> MarketRegime:
        if self._last_regime and random.random() < 0.7:
            return self._last_regime
        return random.choices(
            ["TREND", "RANGE", "CHAOTIC"],
            weights=[0.45, 0.35, 0.20],
        )[0]

    def _pick_signal_strength(self, regime: MarketRegime) -> SignalStrength:
        if regime == "TREND":
            return random.choices(
                ["HIGH", "MEDIUM", "LOW"], weights=[0.5, 0.3, 0.2]
            )[0]
        if regime == "RANGE":
            return random.choices(
                ["MEDIUM", "LOW", "HIGH"], weights=[0.5, 0.3, 0.2]
            )[0]
        return random.choices(
            ["LOW", "MEDIUM", "HIGH"], weights=[0.5, 0.3, 0.2]
        )[0]

    def _pick_confidence(self, strength: SignalStrength) -> int:
        if strength == "HIGH":
            return random.randint(70, 95)
        if strength == "MEDIUM":
            return random.randint(45, 75)
        return random.randint(20, 55)

    def _pick_risk(self, regime: MarketRegime) -> RiskFlag:
        if regime == "CHAOTIC":
            return random.choices(
                ["BLOCK", "CAUTION", "OK"], weights=[0.4, 0.4, 0.2]
            )[0]
        return random.choices(
            ["OK", "CAUTION"], weights=[0.75, 0.25]
        )[0]

    def _pick_execution_window(self, risk: RiskFlag) -> ExecutionWindow:
        if risk == "BLOCK":
            return "CLOSED"
        return random.choices(
            ["OPEN", "WAIT", "CLOSED"], weights=[0.5, 0.35, 0.15]
        )[0]

    # =================================================
    # CACHE / STABILITY
    # =================================================
    def _cache(self, envelope: SignalEnvelope):
        self._last_regime = envelope.market_regime
        self._last_strength = envelope.signal_strength
        self._last_update = envelope.timestamp

    def _reuse_last(self, slot_state: SlotState) -> SignalEnvelope:
        return SignalEnvelope(
            source="MOCK",
            timestamp=time.time(),
            symbol=self.symbol,
            market_regime=self._last_regime or "RANGE",
            signal_strength=self._last_strength or "LOW",
            confidence_score=random.randint(30, 60),
            risk_flag="CAUTION",
            execution_window="WAIT",
            trade_intent="NONE",
            slot_state=slot_state,
        )
