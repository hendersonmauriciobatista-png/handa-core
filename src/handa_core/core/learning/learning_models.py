# ============================================================
# H&A — LEARNING MODELS
# Estruturas de dados do Adaptive Learning Observer (ALO)
# ============================================================

from dataclasses import dataclass, field
from typing import Dict


# ============================================================
# SYMBOL LEARNING PROFILE
# ============================================================


@dataclass
class SymbolLearningProfile:
    symbol: str

    # =========================
    # CONTADORES
    # =========================
    attempts: int = 0
    approvals: int = 0
    rejections: int = 0

    # =========================
    # MOTIVOS DE REJEIÇÃO
    # =========================
    rejection_reasons: Dict[str, int] = field(default_factory=dict)

    # =========================
    # SCORE
    # =========================
    confidence_score: float = 0.0

    # =========================
    # STATUS
    # =========================
    status: str = "UNKNOWN"

    # ============================================================
    # UPDATE METHODS
    # ============================================================

    def register_attempt(self):
        self.attempts += 1

    def register_approval(self):
        self.approvals += 1

    def register_rejection(self, reason: str):
        self.rejections += 1

        if not reason:
            reason = "UNKNOWN"

        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1

    # ============================================================
    # CALCULATIONS
    # ============================================================

    def calculate_score(self):
        if self.attempts == 0:
            self.confidence_score = 0.0
            return

        self.confidence_score = self.approvals / self.attempts

    def update_status(self):
        score = self.confidence_score

        if score > 0.6:
            self.status = "HIGH_CONFIDENCE"
        elif score > 0.3:
            self.status = "MEDIUM_CONFIDENCE"
        else:
            self.status = "LOW_CONFIDENCE"

    def get_dominant_rejection_reason(self) -> str:
        if not self.rejection_reasons:
            return "NONE"

        return max(self.rejection_reasons, key=self.rejection_reasons.get)
