# ============================================================
# Action Decision — DECISÃO IMUTÁVEL (FASE 3.2.2)
# ============================================================

from dataclasses import dataclass
from datetime import datetime, timezone
from h_a.core.action.action_intent import ActionIntent


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    reason: str
    request_id: str
    action_intent: ActionIntent
    decided_at: str = datetime.now(timezone.utc).isoformat()
