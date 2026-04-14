# ============================================================
# Policy Gate Final — ÚLTIMO VETO ANTES DA EXECUÇÃO (FASE 3.2.2)
# ============================================================

from datetime import datetime, timezone, timedelta
from typing import Dict

from h_a.core.action.action_context import ActionContext
from h_a.core.action.action_intent import ActionIntent
from policy.action_decision import ActionDecision


class PolicyGate:
    """
    Gate final de decisão.
    - Revalida estado atual (TOCTOU safe)
    - Não executa ações
    - Não altera estado
    - Retorna decisão estruturada
    """

    # Cooldown explícito por intent
    _COOLDOWNS: Dict[ActionIntent, timedelta] = {
        ActionIntent.SAFE_STOP: timedelta(seconds=0),
        ActionIntent.CLEAR_SAFE_STOP: timedelta(seconds=10),
        ActionIntent.SET_UI_MODE: timedelta(seconds=5),
        ActionIntent.ENABLE_AUTO_INTENT: timedelta(seconds=10),
    }

    def __init__(self, policy):
        """
        policy.state esperado:
          - system_phase : str
          - global_lock : bool
          - safe_stop_active : bool
          - engine_running : bool
          - live_prepared : bool
          - last_action_at : Dict[ActionIntent, datetime]
        """
        self.policy = policy

    def decide(self, ctx: ActionContext) -> ActionDecision:
        now = datetime.now(timezone.utc)

        # 1) Fase do sistema
        if getattr(self.policy.state, "system_phase", None) != "FASE_3_2":
            return ActionDecision(
                allowed=False,
                reason="INVALID_SYSTEM_PHASE",
                request_id=ctx.request_id,
                action_intent=ctx.action_intent,
            )

        # 2) Global lock (tempo real)
        if getattr(self.policy.state, "global_lock", False):
            return ActionDecision(
                allowed=False,
                reason="GLOBAL_LOCK_ACTIVE",
                request_id=ctx.request_id,
                action_intent=ctx.action_intent,
            )

        # 3) Cooldown humano
        last_at = getattr(self.policy.state, "last_action_at", {}).get(ctx.action_intent)
        cooldown = self._COOLDOWNS.get(ctx.action_intent, timedelta(seconds=0))
        if last_at and (now - last_at) < cooldown:
            return ActionDecision(
                allowed=False,
                reason="COOLDOWN_ACTIVE",
                request_id=ctx.request_id,
                action_intent=ctx.action_intent,
            )

        # 4) Permissões explícitas por intent
        if ctx.action_intent == ActionIntent.SAFE_STOP:
            return ActionDecision(
                allowed=True,
                reason="SAFE_STOP_ALLOWED",
                request_id=ctx.request_id,
                action_intent=ctx.action_intent,
            )

        if ctx.action_intent == ActionIntent.CLEAR_SAFE_STOP:
            if not getattr(self.policy.state, "safe_stop_active", False):
                return ActionDecision(
                    allowed=False,
                    reason="SAFE_STOP_NOT_ACTIVE",
                    request_id=ctx.request_id,
                    action_intent=ctx.action_intent,
                )
            return ActionDecision(
                allowed=True,
                reason="CLEAR_SAFE_STOP_ALLOWED",
                request_id=ctx.request_id,
                action_intent=ctx.action_intent,
            )

        if ctx.action_intent == ActionIntent.SET_UI_MODE:
            if getattr(self.policy.state, "engine_running", False):
                return ActionDecision(
                    allowed=False,
                    reason="ENGINE_RUNNING",
                    request_id=ctx.request_id,
                    action_intent=ctx.action_intent,
                )
            return ActionDecision(
                allowed=True,
                reason="SET_UI_MODE_ALLOWED",
                request_id=ctx.request_id,
                action_intent=ctx.action_intent,
            )

        if ctx.action_intent == ActionIntent.ENABLE_AUTO_INTENT:
            if not getattr(self.policy.state, "live_prepared", False):
                return ActionDecision(
                    allowed=False,
                    reason="LIVE_NOT_PREPARED",
                    request_id=ctx.request_id,
                    action_intent=ctx.action_intent,
                )
            return ActionDecision(
                allowed=True,
                reason="ENABLE_AUTO_ALLOWED",
                request_id=ctx.request_id,
                action_intent=ctx.action_intent,
            )

        # 5) Falha segura
        return ActionDecision(
            allowed=False,
            reason="INTENT_NOT_SUPPORTED",
            request_id=ctx.request_id,
            action_intent=ctx.action_intent,
        )
