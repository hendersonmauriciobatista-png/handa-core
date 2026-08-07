# ============================================================
# Action Resolver — REQUEST -> ACTION INTENT (FASE 3.2.1)
# ============================================================

from h_a.core.request.request_model import Request
from h_a.core.request.request_types import RequestType, RequestStatus
from h_a.core.action.action_intent import ActionIntent
from h_a.core.action.action_context import ActionContext


class ActionResolverError(Exception):
    pass


class ActionResolver:
    """
    Tradução segura de Request APPROVED para ActionIntent.
    - Não executa
    - Não usa payload
    - Mapeamento explícito
    """

    _MAP = {
        RequestType.REQUEST_SAFE_STOP: ActionIntent.SAFE_STOP,
        RequestType.REQUEST_CLEAR_SAFE_STOP: ActionIntent.CLEAR_SAFE_STOP,
        RequestType.REQUEST_SET_UI_MODE: ActionIntent.SET_UI_MODE,
        RequestType.REQUEST_ENABLE_AUTO_INTENT: ActionIntent.ENABLE_AUTO_INTENT,
    }

    def resolve(self, request: Request) -> ActionContext:
        if request.status != RequestStatus.APPROVED:
            raise ActionResolverError("REQUEST_NOT_APPROVED")

        if request.type not in self._MAP:
            raise ActionResolverError("REQUEST_TYPE_NOT_SUPPORTED")

        intent = self._MAP[request.type]

        return ActionContext(
            request_id=request.request_id,
            action_intent=intent,
            origin=request.origin,
        )
