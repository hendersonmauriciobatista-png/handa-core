# ============================================================
# Execution Result — RESULTADO EXPLÍCITO DA EXECUÇÃO (FASE 3.2.3)
# ============================================================

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    message: str
    executed_at: str = datetime.now(timezone.utc).isoformat()
