# ============================================================
# core/learning/recommendation_engine.py
# LC-3 — Recommendation Engine
# Engine observador oficial v1.0
# ============================================================

from typing import Dict, List, Optional

from core.learning.models import ShadowAnalysisReport


class LearningRecommendationEngine:
    """
    Motor observador de recomendações do LC-3.

    Responsabilidades:
    - ler o relatório do shadow analyzer
    - detectar padrões fortes e fracos
    - gerar recomendações textuais
    - não alterar parâmetros do sistema
    """

    def _to_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _to_int(self, value, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _safe_list(self, value) -> List:
        if isinstance(value, list):
            return value
        return []

    def generate(self, report: Optional[ShadowAnalysisReport]) -> Dict:
        if report is None:
            return {
                "status": "NO_REPORT",
                "recommendations": ["Nenhum relatório disponível para análise."],
                "confidence": 0.0,
            }

        report_dict = report.to_dict()

        total_samples = self._to_int(report_dict.get("total_samples", 0), default=0)
        overall_win_rate = self._to_float(
            report_dict.get("overall_win_rate", 0.0), default=0.0
        )
        overall_avg_pnl_usdc = self._to_float(
            report_dict.get("overall_avg_pnl_usdc", 0.0), default=0.0
        )

        best_patterns = self._safe_list(report_dict.get("best_patterns"))
        worst_patterns = self._safe_list(report_dict.get("worst_patterns"))

        recommendations: List[str] = []
        confidence = 0.0

        # ========================================================
        # BASE INSUFICIENTE
        # ========================================================
        if total_samples < 3:
            recommendations.append(
                "Base insuficiente para recomendação robusta. Continuar observando trades fechados."
            )
            return {
                "status": "LOW_DATA",
                "recommendations": recommendations,
                "confidence": 0.2,
            }

        # ========================================================
        # LEITURA GERAL
        # ========================================================
        if overall_win_rate >= 0.60 and overall_avg_pnl_usdc > 0:
            recommendations.append(
                "Desempenho geral positivo. Manter estratégia atual sob observação."
            )
            confidence += 0.25

        elif overall_win_rate < 0.45 and overall_avg_pnl_usdc <= 0:
            recommendations.append(
                "Desempenho geral fraco. Revisar padrões de entrada e saída antes de aumentar exposição."
            )
            confidence += 0.25

        else:
            recommendations.append(
                "Desempenho misto. Recomendado manter coleta e observar consistência dos padrões."
            )
            confidence += 0.15

        # ========================================================
        # MELHORES PADRÕES
        # ========================================================
        for pattern in best_patterns[:3]:
            pattern_key = str(pattern.get("pattern_key", "UNKNOWN"))
            win_rate = self._to_float(pattern.get("win_rate", 0.0), default=0.0)
            avg_pnl_usdc = self._to_float(pattern.get("avg_pnl_usdc", 0.0), default=0.0)
            total_trades = self._to_int(pattern.get("total_trades", 0), default=0)

            if total_trades >= 2 and win_rate >= 0.60 and avg_pnl_usdc > 0:
                recommendations.append(
                    f"Padrão favorável detectado: {pattern_key} | "
                    f"win_rate={win_rate:.2f} | avg_pnl={avg_pnl_usdc:.2f} USDC"
                )
                confidence += 0.10

        # ========================================================
        # PIORES PADRÕES
        # ========================================================
        for pattern in worst_patterns[:3]:
            pattern_key = str(pattern.get("pattern_key", "UNKNOWN"))
            win_rate = self._to_float(pattern.get("win_rate", 0.0), default=0.0)
            avg_pnl_usdc = self._to_float(pattern.get("avg_pnl_usdc", 0.0), default=0.0)
            total_trades = self._to_int(pattern.get("total_trades", 0), default=0)

            if total_trades >= 2 and (win_rate <= 0.40 or avg_pnl_usdc < 0):
                recommendations.append(
                    f"Padrão fraco detectado: {pattern_key} | "
                    f"win_rate={win_rate:.2f} | avg_pnl={avg_pnl_usdc:.2f} USDC"
                )
                confidence += 0.10

        # ========================================================
        # AJUSTE FINAL DE CONFIANÇA
        # ========================================================
        confidence = min(round(confidence, 4), 1.0)

        return {
            "status": "OK",
            "recommendations": recommendations,
            "confidence": confidence,
        }
