# ============================================================
# core/alo_decision/constitutional_layer.py
# H&A - ALO Constitutional Layer
# Camada constitucional do ALO
# ============================================================

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class ConstitutionalAlignment(str, Enum):
    ALIGNED = "ALIGNED"
    OVERPROTECTION = "DESALINHADO_POR_EXCESSO_DE_PROTECAO"
    EXCESSIVE_RISK = "DESALINHADO_POR_RISCO_EXCESSIVO"
    FRAGMENTED_GOVERNANCE = "DESALINHADO_POR_GOVERNANCA_FRAGMENTADA"
    UNDEFINED = "UNDEFINED"


@dataclass
class ConstitutionalAssessment:
    alignment: ConstitutionalAlignment
    reason: str
    details: Dict[str, Any]


class ALOConstitutionalLayer:
    """
    Camada constitucional do ALO.

    Responsabilidade:
    - interpretar princípios constitucionais do H&A;
    - avaliar alinhamento contextual;
    - detectar excesso de proteção;
    - detectar risco excessivo;
    - detectar governança fragmentada.

    Esta camada NÃO executa trade.
    Esta camada NÃO substitui Selection.
    Esta camada NÃO substitui Decision.
    """

    def __init__(self) -> None:
        self.principles = {
            "capital_preservation": True,
            "sustainable_profit": True,
            "avoid_operational_paralysis": True,
            "avoid_irresponsible_risk": True,
            "alo_contextual_sovereignty": True,
        }

    def assess_context(self, context: Dict[str, Any]) -> ConstitutionalAssessment:
        """
        Avalia se o contexto atual está alinhado com a Constituição H&A.
        """

        if not isinstance(context, dict):
            return ConstitutionalAssessment(
                alignment=ConstitutionalAlignment.UNDEFINED,
                reason="Contexto inválido para avaliação constitucional.",
                details={"context_type": str(type(context))},
            )

        protection_blocks = int(context.get("protection_blocks", 0) or 0)
        approved_setups = int(context.get("approved_setups", 0) or 0)
        premium_setups = int(context.get("premium_setups", 0) or 0)
        risk_flags = int(context.get("risk_flags", 0) or 0)
        governance_sources = int(context.get("governance_sources", 1) or 1)

        if governance_sources > 1:
            return ConstitutionalAssessment(
                alignment=ConstitutionalAlignment.FRAGMENTED_GOVERNANCE,
                reason="Mais de uma célula aparenta exercer soberania contextual global.",
                details=context,
            )

        if protection_blocks > 0 and premium_setups > 0 and approved_setups == 0:
            return ConstitutionalAssessment(
                alignment=ConstitutionalAlignment.OVERPROTECTION,
                reason="Proteção excessiva detectada: setups premium existem, mas todos foram bloqueados.",
                details=context,
            )

        if risk_flags >= 3:
            return ConstitutionalAssessment(
                alignment=ConstitutionalAlignment.EXCESSIVE_RISK,
                reason="Risco excessivo detectado: múltiplos alertas de risco no contexto.",
                details=context,
            )

        return ConstitutionalAssessment(
            alignment=ConstitutionalAlignment.ALIGNED,
            reason="Contexto alinhado aos princípios constitucionais do H&A.",
            details=context,
        )
