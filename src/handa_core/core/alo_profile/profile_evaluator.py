# ============================================================
# core/alo_profile/profile_evaluator.py
# Avaliador operacional do perfil persistente do ALO
# ============================================================

from typing import Optional

from core.alo_profile.profile_models import AloProfileEvaluation, AloSymbolProfile


class AloProfileEvaluator:
    def __init__(self):
        pass

    def _safe_str(self, value) -> str:
        return str(value or "").strip()

    def _winrate(self, profile: AloSymbolProfile) -> float:
        if profile.total_trades <= 0:
            return 0.0
        return profile.wins / max(profile.total_trades, 1)

    def evaluate(
        self,
        profile: Optional[AloSymbolProfile],
        market_state: str = "",
    ) -> AloProfileEvaluation:
        if not isinstance(profile, AloSymbolProfile):
            return AloProfileEvaluation(
                symbol="UNKNOWN",
                profile_label="NEUTRAL",
                should_block=False,
                confidence_adjustment=0.0,
                capital_adjustment=1.0,
                reason="PROFILE_INVALID",
            )

        symbol = self._safe_str(profile.symbol).upper() or "UNKNOWN"
        market_state_upper = self._safe_str(
            market_state or profile.last_market_state
        ).upper()

        evaluation = AloProfileEvaluation(
            symbol=symbol,
            profile_label="NEUTRAL",
            should_block=False,
            confidence_adjustment=0.0,
            capital_adjustment=1.0,
            reason="NEUTRAL_PROFILE",
        )

        total_trades = int(profile.total_trades or 0)
        total_losses = int(profile.losses or 0)
        total_wins = int(profile.wins or 0)
        winrate = self._winrate(profile)

        lateral_penalty = float(profile.lateral_penalty or 0.0)
        false_breakout_penalty = float(profile.false_breakout_penalty or 0.0)
        block_bias = float(profile.block_bias or 0.0)

        # =========================================================
        # 1. POUCA AMOSTRA = NEUTRO
        # =========================================================
        if total_trades < 3 and profile.non_execution_count < 5:
            evaluation.profile_label = "OBSERVATION"
            evaluation.reason = "LOW_SAMPLE"
            return evaluation

        # =========================================================
        # 2. BLOQUEIOS NEGATIVOS FORTES
        # =========================================================
        if block_bias >= 1.5:
            evaluation.profile_label = "BLOCKED"
            evaluation.should_block = True
            evaluation.confidence_adjustment = -0.30
            evaluation.capital_adjustment = 0.50
            evaluation.reason = "HIGH_BLOCK_BIAS"
            return evaluation

        if total_trades >= 4 and total_losses >= 4 and winrate <= 0.20:
            evaluation.profile_label = "UNSTABLE"
            evaluation.should_block = True
            evaluation.confidence_adjustment = -0.25
            evaluation.capital_adjustment = 0.60
            evaluation.reason = "PERSISTENT_LOSS_PROFILE"
            return evaluation

        # =========================================================
        # 3. PENALIDADE ESPECÍFICA PARA MERCADO LATERAL
        # =========================================================
        if "LATERAL" in market_state_upper and lateral_penalty >= 0.60:
            evaluation.profile_label = "LATERAL_RISK"
            evaluation.should_block = True
            evaluation.confidence_adjustment = -0.20
            evaluation.capital_adjustment = 0.70
            evaluation.reason = "LATERAL_MARKET_PENALTY"
            return evaluation

        # =========================================================
        # 4. FALSO BREAKOUT / SAÍDAS RUINS
        # =========================================================
        if false_breakout_penalty >= 0.80:
            evaluation.profile_label = "FALSE_BREAKOUT_RISK"
            evaluation.should_block = False
            evaluation.confidence_adjustment = -0.15
            evaluation.capital_adjustment = 0.75
            evaluation.reason = "FALSE_BREAKOUT_PATTERN"
            return evaluation

        # =========================================================
        # 5. PERFIL POSITIVO MODERADO
        # =========================================================
        if total_trades >= 5 and total_wins >= 3 and winrate >= 0.60:
            evaluation.profile_label = "TRUSTED"
            evaluation.should_block = False
            evaluation.confidence_adjustment = 0.08
            evaluation.capital_adjustment = 1.10
            evaluation.reason = "CONSISTENT_POSITIVE_PROFILE"
            return evaluation

        # =========================================================
        # 6. PERFIL FRACO, MAS NÃO BLOQUEADO
        # =========================================================
        if total_trades >= 3 and winrate < 0.40:
            evaluation.profile_label = "WEAK"
            evaluation.should_block = False
            evaluation.confidence_adjustment = -0.10
            evaluation.capital_adjustment = 0.85
            evaluation.reason = "LOW_WINRATE_PROFILE"
            return evaluation

        # =========================================================
        # 7. PADRÃO FINAL NEUTRO
        # =========================================================
        evaluation.profile_label = "NEUTRAL"
        evaluation.should_block = False
        evaluation.confidence_adjustment = 0.0
        evaluation.capital_adjustment = 1.0
        evaluation.reason = "NEUTRAL_PROFILE"
        return evaluation
