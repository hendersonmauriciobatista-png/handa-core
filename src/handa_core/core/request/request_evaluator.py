from h_a.core.request.request_model import Request
from h_a.core.request.request_types import RequestStatus


class RequestEvaluator:
    """
    Avalia requests SEM executar ações.
    Apenas decide status e motivo.
    """

    def __init__(self, policy):
        self.policy = policy

    def evaluate(self, request: Request) -> Request:
        if request.system_phase != "FASE_3_1":
            return request.__class__(
                **{**request.__dict__,
                   "status": RequestStatus.REJECTED,
                   "decision_reason": "INVALID_SYSTEM_PHASE"}
            )

        if getattr(self.policy, "state", None) and getattr(self.policy.state, "global_lock", False):
            return request.__class__(
                **{**request.__dict__,
                   "status": RequestStatus.REJECTED,
                   "decision_reason": "GLOBAL_LOCK_ACTIVE"}
            )

        return request.__class__(
            **{**request.__dict__,
               "status": RequestStatus.APPROVED,
               "decision_reason": "REQUEST_ACCEPTED (NO_EXECUTION)"}
        )
