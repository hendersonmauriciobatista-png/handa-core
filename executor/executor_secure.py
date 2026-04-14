# ============================================================
# Executor Seguro — EXECUÇÃO CONTROLADA (FASE 3.2.3)
# ============================================================

from typing import Set

from h_a.core.action.action_context import ActionContext
from h_a.core.action.action_intent import ActionIntent
from policy.action_decision import ActionDecision
from executor.execution_result import ExecutionResult
from executor.executor_log import ExecutorLogger


class ExecutorError(Exception):
    pass


class ExecutorSecure:
    """
    Executor obediente:
    - Só executa se decision.allowed == True
    - Não decide
    - Não altera policy
    - Anti-replay por request_id
    """

    def __init__(
        self,
        safe_stop_controller,
        ui_mode_controller,
        auto_controller,
        logger: ExecutorLogger | None = None,
    ):
        self.safe_stop_controller = safe_stop_controller
        self.ui_mode_controller = ui_mode_controller
        self.auto_controller = auto_controller
        self.logger = logger or ExecutorLogger()
        self._consumed_requests: Set[str] = set()

    def execute(self, decision: ActionDecision, context: ActionContext) -> ExecutionResult:
        # 1) Checagens obrigatórias
        if not decision.allowed:
            raise ExecutorError("DECISION_NOT_ALLOWED")

        if decision.request_id in self._consumed_requests:
            raise ExecutorError("REQUEST_ALREADY_CONSUMED")

        if decision.request_id != context.request_id:
            raise ExecutorError("REQUEST_CONTEXT_MISMATCH")

        # 2) Log pré-execução
        self.logger.log({
            "event": "EXECUTION_START",
            "request_id": decision.request_id,
            "action_intent": decision.action_intent.value,
            "decision_reason": decision.reason,
        })

        # 3) Execução explícita por intent
        try:
            if decision.action_intent == ActionIntent.SAFE_STOP:
                self.safe_stop_controller.trigger()

            elif decision.action_intent == ActionIntent.CLEAR_SAFE_STOP:
                self.safe_stop_controller.clear()

            elif decision.action_intent == ActionIntent.SET_UI_MODE:
                self.ui_mode_controller.apply()

            elif decision.action_intent == ActionIntent.ENABLE_AUTO_INTENT:
                self.auto_controller.enable()

            else:
                raise ExecutorError("INTENT_NOT_SUPPORTED")

            # marcar como consumido (anti-replay)
            self._consumed_requests.add(decision.request_id)

            # log pós-execução
            self.logger.log({
                "event": "EXECUTION_SUCCESS",
                "request_id": decision.request_id,
                "action_intent": decision.action_intent.value,
            })

            return ExecutionResult(
                success=True,
                message="EXECUTION_SUCCESS"
            )

        except Exception as exc:
            self.logger.log({
                "event": "EXECUTION_FAILED",
                "request_id": decision.request_id,
                "action_intent": decision.action_intent.value,
                "error": str(exc),
            })
            raise
