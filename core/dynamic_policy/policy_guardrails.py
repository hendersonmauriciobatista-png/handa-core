# =============================================================================
# core/dynamic_policy/policy_guardrails.py
# H&A — Dynamic Policy Guardrails (NPD-H&A v1)
# =============================================================================

from core.dynamic_policy.policy_models import DynamicPolicy


class PolicyGuardrails:
    """
    Impede o NPD de sair dos limites seguros definidos pelo H&A.
    """

    # -------------------------------------------------------------------------
    # LIMITES DE ENTRADA
    # -------------------------------------------------------------------------
    MIN_RSI_FLOOR = 45.0
    MIN_RSI_CEIL = 60.0

    MAX_RSI_FLOOR = 60.0
    MAX_RSI_CEIL = 80.0

    MIN_VOLUME_RATIO_FLOOR = 1.00
    MIN_VOLUME_RATIO_CEIL = 2.50

    MIN_EMA_SPREAD_FLOOR = 0.0003
    MIN_EMA_SPREAD_CEIL = 0.0050

    SIDEWAYS_MIN_RSI_FLOOR = 45.0
    SIDEWAYS_MIN_RSI_CEIL = 60.0

    SIDEWAYS_MIN_VOLUME_FLOOR = 1.10
    SIDEWAYS_MIN_VOLUME_CEIL = 2.50

    SIDEWAYS_MIN_SPREAD_FLOOR = 0.0005
    SIDEWAYS_MIN_SPREAD_CEIL = 0.0035

    # -------------------------------------------------------------------------
    # LIMITES DE RISCO
    # -------------------------------------------------------------------------
    MIN_RR_FLOOR = 1.05
    MIN_RR_CEIL = 2.50

    EXPECTED_PROFIT_FLOOR = 0.0040   # 0.40%
    EXPECTED_PROFIT_CEIL = 0.0100    # 1.00%

    STOP_LOSS_FLOOR = 0.0030         # 0.30%
    STOP_LOSS_CEIL = 0.0060          # 0.60%

    # -------------------------------------------------------------------------
    # LIMITES DE OPERAÇÃO
    # -------------------------------------------------------------------------
    CAPITAL_MULTIPLIER_FLOOR = 0.25
    CAPITAL_MULTIPLIER_CEIL = 1.00

    MAX_ACTIVE_SLOTS_FLOOR = 1
    MAX_ACTIVE_SLOTS_CEIL = 4

    REJECTION_COOLDOWN_FLOOR = 0
    REJECTION_COOLDOWN_CEIL = 6

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _clamp(value, min_value, max_value):
        return max(min_value, min(value, max_value))

    # -------------------------------------------------------------------------
    # APLICAÇÃO DOS LIMITES
    # -------------------------------------------------------------------------

    @classmethod
    def apply(cls, policy: DynamicPolicy) -> DynamicPolicy:
        return DynamicPolicy(
            # -----------------------------------------------------
            # ENTRADA
            # -----------------------------------------------------
            min_rsi=cls._clamp(policy.min_rsi, cls.MIN_RSI_FLOOR, cls.MIN_RSI_CEIL),
            max_rsi=cls._clamp(policy.max_rsi, cls.MAX_RSI_FLOOR, cls.MAX_RSI_CEIL),
            min_volume_ratio=cls._clamp(
                policy.min_volume_ratio,
                cls.MIN_VOLUME_RATIO_FLOOR,
                cls.MIN_VOLUME_RATIO_CEIL,
            ),
            min_ema_spread=cls._clamp(
                policy.min_ema_spread,
                cls.MIN_EMA_SPREAD_FLOOR,
                cls.MIN_EMA_SPREAD_CEIL,
            ),
            allow_sideways=bool(policy.allow_sideways),
            sideways_min_rsi=cls._clamp(
                policy.sideways_min_rsi,
                cls.SIDEWAYS_MIN_RSI_FLOOR,
                cls.SIDEWAYS_MIN_RSI_CEIL,
            ),
            sideways_min_volume=cls._clamp(
                policy.sideways_min_volume,
                cls.SIDEWAYS_MIN_VOLUME_FLOOR,
                cls.SIDEWAYS_MIN_VOLUME_CEIL,
            ),
            sideways_min_spread=cls._clamp(
                policy.sideways_min_spread,
                cls.SIDEWAYS_MIN_SPREAD_FLOOR,
                cls.SIDEWAYS_MIN_SPREAD_CEIL,
            ),

            # -----------------------------------------------------
            # RISCO
            # -----------------------------------------------------
            min_rr=cls._clamp(policy.min_rr, cls.MIN_RR_FLOOR, cls.MIN_RR_CEIL),
            expected_profit_pct=cls._clamp(
                policy.expected_profit_pct,
                cls.EXPECTED_PROFIT_FLOOR,
                cls.EXPECTED_PROFIT_CEIL,
            ),
            stop_loss_pct=cls._clamp(
                policy.stop_loss_pct,
                cls.STOP_LOSS_FLOOR,
                cls.STOP_LOSS_CEIL,
            ),

            # -----------------------------------------------------
            # OPERAÇÃO
            # -----------------------------------------------------
            capital_multiplier=cls._clamp(
                policy.capital_multiplier,
                cls.CAPITAL_MULTIPLIER_FLOOR,
                cls.CAPITAL_MULTIPLIER_CEIL,
            ),
            max_active_slots=int(
                cls._clamp(
                    policy.max_active_slots,
                    cls.MAX_ACTIVE_SLOTS_FLOOR,
                    cls.MAX_ACTIVE_SLOTS_CEIL,
                )
            ),
            rejection_cooldown=int(
                cls._clamp(
                    policy.rejection_cooldown,
                    cls.REJECTION_COOLDOWN_FLOOR,
                    cls.REJECTION_COOLDOWN_CEIL,
                )
            ),
        )