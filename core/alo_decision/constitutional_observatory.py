# ============================================================
# core/alo_decision/constitutional_observatory.py
# H&A - ALO Constitutional Observatory
# Observador constitucional do ecossistema H&A
# ============================================================

from typing import Dict, Any, Optional

from core.alo_decision.constitutional_layer import (
    ALOConstitutionalLayer,
    ConstitutionalAssessment,
)


class ALOConstitutionalObservatory:
    """
    Observatory constitucional do H&A.

    Responsabilidade:
    - observar desalinhamentos estruturais;
    - detectar overprotection;
    - detectar governança fragmentada;
    - registrar sinais institucionais;
    - NÃO interferir operacionalmente.

    Esta camada NÃO:
    - bloqueia trade;
    - altera score;
    - modifica Selection;
    - modifica Decision;
    - altera MQII.
    """

    def __init__(self) -> None:
        self.layer = ALOConstitutionalLayer()

    def observe(
        self,
        mqii_snapshot: Optional[Dict[str, Any]] = None,
        selection_snapshot: Optional[Dict[str, Any]] = None,
        decision_snapshot: Optional[Dict[str, Any]] = None,
        radar_snapshot: Optional[Dict[str, Any]] = None,
    ) -> ConstitutionalAssessment:
        """
        Consolida snapshots do sistema e executa avaliação constitucional.
        """

        mqii_snapshot = mqii_snapshot or {}
        selection_snapshot = selection_snapshot or {}
        decision_snapshot = decision_snapshot or {}
        radar_snapshot = radar_snapshot or {}

        approved_setups = int(radar_snapshot.get("approved_count", 0))

        premium_setups = int(selection_snapshot.get("premium_count", 0))

        protection_blocks = int(selection_snapshot.get("blocked_count", 0))

        risk_flags = int(decision_snapshot.get("risk_flags", 0))

        governance_sources = 0

        if mqii_snapshot.get("context_override"):
            governance_sources += 1

        if selection_snapshot.get("context_override"):
            governance_sources += 1

        if decision_snapshot.get("context_override"):
            governance_sources += 1

        if governance_sources <= 0:
            governance_sources = 1

        context = {
            "approved_setups": approved_setups,
            "premium_setups": premium_setups,
            "protection_blocks": protection_blocks,
            "risk_flags": risk_flags,
            "governance_sources": governance_sources,
            "mqii_state": mqii_snapshot.get("state"),
            "selection_mode": selection_snapshot.get("mode"),
            "decision_state": decision_snapshot.get("state"),
        }

        assessment = self.layer.assess_context(context)

        self._log_assessment(assessment)

        return assessment

    def _log_assessment(
        self,
        assessment: ConstitutionalAssessment,
    ) -> None:
        """
        Log institucional do observatório.
        """

        print(
            "[ALO CONSTITUTIONAL] "
            f"alignment={assessment.alignment.value} | "
            f"reason={assessment.reason}"
        )
