# ============================================================
# Action Context — CONTEXTO IMUTÁVEL (FASE 3.2.1)
# ============================================================

from dataclasses import dataclass
from datetime import datetime, timezone

from h_a.core.action.action_intent import ActionIntent


@dataclass(frozen=True)
class ActionContext:
    request_id: str
    action_intent: ActionIntent
    origin: str
    resolved_at: str = datetime.now(timezone.utc).isoformat()
