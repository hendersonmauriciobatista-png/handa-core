import random
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    score: float
    approved: bool
    reason: str


class MarketAnalyzer:
    """
    Analisa o mercado e gera um score de entrada.
    Versão MOCK (estrutura final).
    """

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold

    def analyze(self, slot_id: int) -> AnalysisResult:
        """
        Retorna um score de 0.0 a 1.0
        """

        # =========================
        # MOCK DE INDICADORES
        # =========================
        ema_score = random.uniform(0.0, 1.0)
        rsi_score = random.uniform(0.0, 1.0)
        volume_score = random.uniform(0.0, 1.0)

        # Peso dos indicadores
        score = (
            0.4 * ema_score +
            0.3 * rsi_score +
            0.3 * volume_score
        )

        approved = score >= self.threshold

        return AnalysisResult(
            score=round(score, 3),
            approved=approved,
            reason="EMA/RSI/VOLUME"
        )
