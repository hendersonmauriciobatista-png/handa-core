# =============================================================================
# core/dynamic_policy/dynamic_policy_core.py
# H&A — Dynamic Policy Core (NPD-H&A v1)
# AJUSTE BALANCEADO: MAIS FLEXÍVEL, SEM PERDER PROTEÇÃO
# =============================================================================

from core.dynamic_policy.policy_models import (
    MarketContext,
    SystemContext,
    LC1Feedback,
    DynamicPolicy,
    PolicyDebugInfo,
)
from core.dynamic_policy.policy_guardrails import PolicyGuardrails
from core.dynamic_policy.market_regime_detector import MarketRegimeDetector


class DynamicPolicyCore:
    """
    Núcleo de Política Dinâmica do H&A.

    Responsável por:
    - ler contexto de mercado
    - ler contexto do sistema
    - ler feedback do LC-1
    - montar parâmetros dinâmicos seguros
    """

    def __init__(self):
        self.guardrails = PolicyGuardrails()

    # -------------------------------------------------------------------------
    # API PRINCIPAL
    # -------------------------------------------------------------------------

    def build_policy(
        self,
        market: MarketContext,
        system: SystemContext,
        lc1: LC1Feedback,
    ) -> DynamicPolicy:

        regime = MarketRegimeDetector.detect(market)

        raw_policy = self._build_raw_policy(
            market=market,
            system=system,
            lc1=lc1,
            regime=regime,
        )

        safe_policy = self.guardrails.apply(raw_policy)
        return safe_policy

    def build_debug_info(
        self,
        market: MarketContext,
    ) -> PolicyDebugInfo:

        price = float(market.price or 0.0)
        ema_fast = float(market.ema_fast or 0.0)
        ema_slow = float(market.ema_slow or 0.0)
        atr = float(market.atr or 0.0)

        ema_spread = abs(ema_fast - ema_slow) / price if price > 0 else 0.0
        atr_pct = atr / price if price > 0 else 0.0
        regime = MarketRegimeDetector.detect(market)

        return PolicyDebugInfo(
            regime=regime,
            atr_pct=round(atr_pct, 6),
            ema_spread=round(ema_spread, 6),
            notes="Dynamic policy debug info",
        )

    # -------------------------------------------------------------------------
    # POLICY BASE
    # -------------------------------------------------------------------------

    def _build_raw_policy(
        self,
        market: MarketContext,
        system: SystemContext,
        lc1: LC1Feedback,
        regime: str,
    ) -> DynamicPolicy:

        price = float(market.price or 0.0)
        ema_fast = float(market.ema_fast or 0.0)
        ema_slow = float(market.ema_slow or 0.0)
        volume_ratio = float(market.volume_ratio or 0.0)
        atr = float(market.atr or 0.0)

        ema_spread = abs(ema_fast - ema_slow) / price if price > 0 else 0.0
        atr_pct = atr / price if price > 0 else 0.0

        # -----------------------------------------------------
        # BASE POR REGIME
        # -----------------------------------------------------
        if regime == "TREND_STRONG":
            policy = DynamicPolicy(
                min_rsi=50.0,
                max_rsi=74.0,
                min_volume_ratio=0.95,
                min_ema_spread=0.0005,
                allow_sideways=True,
                sideways_min_rsi=47.0,
                sideways_min_volume=1.10,
                sideways_min_spread=0.0007,
                min_rr=1.10,
                expected_profit_pct=0.0065,
                stop_loss_pct=0.0035,
                capital_multiplier=1.00,
                max_active_slots=4,
                rejection_cooldown=1,
            )

        elif regime == "TREND_WEAK":
            policy = DynamicPolicy(
                min_rsi=50.0,
                max_rsi=72.0,
                min_volume_ratio=0.90,
                min_ema_spread=0.0004,
                allow_sideways=True,
                sideways_min_rsi=47.0,
                sideways_min_volume=1.05,
                sideways_min_spread=0.0006,
                min_rr=1.15,
                expected_profit_pct=0.0055,
                stop_loss_pct=0.0038,
                capital_multiplier=0.90,
                max_active_slots=3,
                rejection_cooldown=2,
            )

        elif regime == "SIDEWAYS_TRADABLE":
            policy = DynamicPolicy(
                min_rsi=47.0,
                max_rsi=66.0,
                min_volume_ratio=0.85,
                min_ema_spread=0.00035,
                allow_sideways=True,
                sideways_min_rsi=46.0,
                sideways_min_volume=1.00,
                sideways_min_spread=0.0005,
                min_rr=1.20,
                expected_profit_pct=0.0050,
                stop_loss_pct=0.0035,
                capital_multiplier=0.75,
                max_active_slots=2,
                rejection_cooldown=2,
            )

        else:  # SIDEWAYS_DEAD / UNKNOWN
            policy = DynamicPolicy(
                min_rsi=53.0,
                max_rsi=68.0,
                min_volume_ratio=1.10,
                min_ema_spread=0.0006,
                allow_sideways=False,
                sideways_min_rsi=50.0,
                sideways_min_volume=1.20,
                sideways_min_spread=0.0008,
                min_rr=1.30,
                expected_profit_pct=0.0045,
                stop_loss_pct=0.0032,
                capital_multiplier=0.45,
                max_active_slots=1,
                rejection_cooldown=3,
            )

        # -----------------------------------------------------
        # AJUSTE POR VOLATILIDADE
        # -----------------------------------------------------
        policy = self._apply_volatility_adjustment(policy, atr_pct)

        # -----------------------------------------------------
        # AJUSTE POR VOLUME
        # -----------------------------------------------------
        policy = self._apply_volume_adjustment(policy, volume_ratio, ema_spread, regime)

        # -----------------------------------------------------
        # AJUSTE POR ESTADO DO SISTEMA
        # -----------------------------------------------------
        policy = self._apply_system_adjustment(policy, system)

        # -----------------------------------------------------
        # AJUSTE POR LC-1
        # -----------------------------------------------------
        policy = self._apply_lc1_adjustment(policy, lc1)

        return policy

    # -------------------------------------------------------------------------
    # AJUSTES
    # -------------------------------------------------------------------------

    def _apply_volatility_adjustment(
        self,
        policy: DynamicPolicy,
        atr_pct: float,
    ) -> DynamicPolicy:

        if atr_pct >= 0.0060:
            policy.min_ema_spread += 0.00015
            policy.sideways_min_spread += 0.00015
            policy.stop_loss_pct += 0.0005
            policy.expected_profit_pct += 0.0005

        elif atr_pct >= 0.0030:
            policy.min_ema_spread += 0.00008
            policy.sideways_min_spread += 0.00008
            policy.stop_loss_pct += 0.0002

        return policy

    def _apply_volume_adjustment(
        self,
        policy: DynamicPolicy,
        volume_ratio: float,
        ema_spread: float,
        regime: str,
    ) -> DynamicPolicy:

        # Mercado muito forte -> libera um pouco
        if volume_ratio >= 2.0 and ema_spread >= 0.0010:
            policy.min_rsi -= 1.0
            policy.min_rr -= 0.05
            policy.expected_profit_pct += 0.0005

        # Volume baixo, mas não morto -> aperta só um pouco
        elif 0.70 <= volume_ratio < 1.00:
            policy.min_rsi += 0.5
            policy.min_rr += 0.03

        # Volume muito baixo -> endurece de verdade
        elif volume_ratio < 0.70:
            policy.min_rsi += 1.5
            policy.min_rr += 0.10
            policy.capital_multiplier -= 0.10

            if regime in ("SIDEWAYS_TRADABLE", "SIDEWAYS_DEAD"):
                policy.allow_sideways = False

        return policy

    def _apply_system_adjustment(
        self,
        policy: DynamicPolicy,
        system: SystemContext,
    ) -> DynamicPolicy:

        # Drawdown alto -> mais conservador
        if system.drawdown_pct >= 3.0:
            policy.min_rsi += 2.0
            policy.min_rr += 0.10
            policy.capital_multiplier -= 0.20
            policy.max_active_slots = min(policy.max_active_slots, 2)
            policy.rejection_cooldown += 1

        elif system.drawdown_pct >= 1.5:
            policy.min_rsi += 1.0
            policy.capital_multiplier -= 0.10
            policy.max_active_slots = min(policy.max_active_slots, 3)

        # Loss streak recente -> proteção
        if system.loss_streak >= 3:
            policy.min_rr += 0.10
            policy.capital_multiplier -= 0.15
            policy.rejection_cooldown += 1

        # Win rate recente boa -> libera um pouco
        if system.win_rate_recent >= 0.65:
            policy.min_rr -= 0.05
            policy.capital_multiplier += 0.05

        return policy

    def _apply_lc1_adjustment(
        self,
        policy: DynamicPolicy,
        lc1: LC1Feedback,
    ) -> DynamicPolicy:

        # Só confia no LC-1 se houver amostra suficiente
        if lc1.sample_size < 5:
            return policy

        if lc1.pair_win_rate >= 0.65:
            policy.min_rr -= 0.05
            policy.expected_profit_pct += 0.0003
            policy.capital_multiplier += 0.05

        elif lc1.pair_win_rate <= 0.35:
            policy.min_rsi += 1.0
            policy.min_rr += 0.10
            policy.capital_multiplier -= 0.10
            policy.rejection_cooldown += 1

        if lc1.pair_loss_streak >= 2:
            policy.capital_multiplier -= 0.10
            policy.rejection_cooldown += 1

        if lc1.avg_profit_pct > abs(lc1.avg_loss_pct):
            policy.expected_profit_pct += 0.0002

        return policy