"""Post-claim BUY-only governed MOCK transport gateway."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from core.execution.execution_fact import ExecutionFact, ExternalOrderStatus
from core.execution.mock_capability_venue_adapter import MockVenueRejected
from core.persistence.governed_transport_store import (
    GovernedTransportStore,
    TERMINAL_STATES,
    TransportConflict,
    TransportValidationError,
)


class TransportDisposition(str, Enum):
    SUBMISSION_ACCEPTED = "SUBMISSION_ACCEPTED"
    SUBMISSION_REJECTED = "SUBMISSION_REJECTED"
    SUBMISSION_OUTCOME_UNKNOWN = "SUBMISSION_OUTCOME_UNKNOWN"
    RECOVERY_ACCEPTED = "RECOVERY_ACCEPTED"
    RECOVERY_REJECTED = "RECOVERY_REJECTED"
    RECOVERY_NO_EFFECT_CONFIRMED = "RECOVERY_NO_EFFECT_CONFIRMED"
    RECOVERY_INCONCLUSIVE = "RECOVERY_INCONCLUSIVE"
    TERMINAL_REPLAY = "TERMINAL_REPLAY"
    INVALID_CAPABILITY = "INVALID_CAPABILITY"
    UNSUPPORTED_SIDE = "UNSUPPORTED_SIDE"
    CONFLICT = "CONFLICT"
    CANNOT_TRANSPORT = "CANNOT_TRANSPORT"


@dataclass(frozen=True)
class TransportResult:
    disposition: TransportDisposition
    submission_authorization_id: Optional[str] = None
    transport_state: Optional[str] = None
    execution_fact: Optional[ExecutionFact] = None
    reason: str = ""


class GovernedSubmissionGateway:
    """The only public input is an opaque claimed capability."""

    def __init__(self, store: GovernedTransportStore, adapter):
        self._store = store
        self._adapter = adapter

    def submit(self, capability: Any) -> TransportResult:
        authorization_id = getattr(capability, "submission_authorization_id", None)
        try:
            with self._store.transaction() as context:
                preparation = self._store.prepare_handoff(context, capability)
                authorization_id = preparation.projection["submission_authorization_id"]

            # The handoff transaction is committed before the venue boundary.
            # A creator receives only an ephemeral local first-send grant; it
            # must reacquire the projection lock in a new transaction.
            with self._store.transaction() as context:
                projection = self._store.get_projection(
                    context, authorization_id, for_update=True
                )
                if projection is None:
                    return TransportResult(
                        TransportDisposition.CANNOT_TRANSPORT,
                        authorization_id,
                        reason="transport projection disappeared",
                    )

                if projection["transport_state"] in TERMINAL_STATES:
                    fact = None
                    if projection["transport_state"] == "OBSERVED_ACCEPTED":
                        fact = self._adapter.recover_by_client_order_id(
                            projection["client_order_id"]
                        )
                    return TransportResult(
                        TransportDisposition.TERMINAL_REPLAY,
                        projection["submission_authorization_id"],
                        projection["transport_state"],
                        fact,
                        "durable terminal transport observation",
                    )

                if not preparation.created:
                    return self._recover(context, projection)

                # The creator alone has an ephemeral first-send grant.  The
                # projection lock is held through the MOCK call and transition.
                try:
                    fact = self._adapter.submit_buy(
                        symbol=projection["symbol"],
                        requested_quote_amount=projection["requested_quote_amount"],
                        client_order_id=projection["client_order_id"],
                    )
                    self._require_accepted_fact(fact, projection)
                except MockVenueRejected as exc:
                    updated = self._store.transition(
                        context, projection,
                        event_type="SUBMISSION_REJECTED",
                        state_after="OBSERVED_REJECTED",
                        detail={"reason": str(exc)},
                    )
                    return TransportResult(
                        TransportDisposition.SUBMISSION_REJECTED,
                        updated["submission_authorization_id"],
                        updated["transport_state"],
                        reason=str(exc),
                    )
                except Exception as exc:
                    updated = self._store.transition(
                        context, projection,
                        event_type="SUBMISSION_OUTCOME_UNKNOWN",
                        state_after="OUTCOME_UNKNOWN",
                        detail={"reason": str(exc), "ambiguous": True},
                    )
                    return TransportResult(
                        TransportDisposition.SUBMISSION_OUTCOME_UNKNOWN,
                        updated["submission_authorization_id"],
                        updated["transport_state"],
                        reason=str(exc),
                    )

                updated = self._store.transition(
                    context,
                    projection,
                    event_type="SUBMISSION_ACCEPTED",
                    state_after="OBSERVED_ACCEPTED",
                    external_order_id=fact.external_order_id,
                    observation_identity=fact.observation_identity,
                    detail={"source": "mock-capability-venue"},
                )
                return TransportResult(
                    TransportDisposition.SUBMISSION_ACCEPTED,
                    updated["submission_authorization_id"],
                    updated["transport_state"],
                    fact,
                )
        except TransportConflict as exc:
            return TransportResult(TransportDisposition.CONFLICT, authorization_id, reason=str(exc))
        except TransportValidationError as exc:
            disposition = (
                TransportDisposition.UNSUPPORTED_SIDE
                if "UNSUPPORTED_SIDE" in str(exc)
                else TransportDisposition.INVALID_CAPABILITY
            )
            return TransportResult(disposition, authorization_id, reason=str(exc))
        except Exception as exc:
            return TransportResult(TransportDisposition.CANNOT_TRANSPORT, authorization_id, reason=str(exc))

    def _recover(self, context, projection) -> TransportResult:
        try:
            fact = self._adapter.recover_by_client_order_id(projection["client_order_id"])
        except Exception as exc:
            updated = self._store.transition(
                context, projection,
                event_type="RECOVERY_INCONCLUSIVE",
                state_after="OUTCOME_UNKNOWN",
                detail={"reason": str(exc), "inconclusive": True},
            )
            return TransportResult(
                TransportDisposition.RECOVERY_INCONCLUSIVE,
                updated["submission_authorization_id"],
                updated["transport_state"],
                reason=str(exc),
            )
        if fact is None:
            updated = self._store.transition(
                context, projection,
                event_type="RECOVERY_NO_EFFECT_CONFIRMED",
                state_after="NO_EFFECT_CONFIRMED",
                detail={"reason": "durable MOCK lookup returned NOT_FOUND"},
            )
            return TransportResult(
                TransportDisposition.RECOVERY_NO_EFFECT_CONFIRMED,
                updated["submission_authorization_id"],
                updated["transport_state"],
                reason="durable MOCK lookup returned NOT_FOUND",
            )
        if fact.external_status is ExternalOrderStatus.REJECTED:
            updated = self._store.transition(
                context, projection,
                event_type="RECOVERY_REJECTED",
                state_after="OBSERVED_REJECTED",
                external_order_id=fact.external_order_id,
                observation_identity=fact.observation_identity,
                detail={"source": "mock-capability-recovery"},
            )
            return TransportResult(
                TransportDisposition.RECOVERY_REJECTED,
                updated["submission_authorization_id"],
                updated["transport_state"],
                fact,
            )
        try:
            self._require_accepted_fact(fact, projection)
        except Exception as exc:
            updated = self._store.transition(
                context, projection,
                event_type="RECOVERY_INCONCLUSIVE",
                state_after="OUTCOME_UNKNOWN",
                detail={"reason": str(exc), "inconclusive": True},
            )
            return TransportResult(
                TransportDisposition.RECOVERY_INCONCLUSIVE,
                updated["submission_authorization_id"],
                updated["transport_state"],
                reason=str(exc),
            )
        updated = self._store.transition(
            context, projection,
            event_type="RECOVERY_ACCEPTED",
            state_after="OBSERVED_ACCEPTED",
            external_order_id=fact.external_order_id,
            observation_identity=fact.observation_identity,
            detail={"source": "mock-capability-recovery"},
        )
        return TransportResult(
            TransportDisposition.RECOVERY_ACCEPTED,
            updated["submission_authorization_id"],
            updated["transport_state"],
            fact,
        )

    @staticmethod
    def _require_accepted_fact(fact: ExecutionFact, projection) -> None:
        if not isinstance(fact, ExecutionFact):
            raise RuntimeError("venue adapter returned invalid execution fact")
        if fact.symbol != projection["symbol"] or fact.side != projection["side"]:
            raise RuntimeError("venue fact identity conflicts with transport projection")
        if fact.client_order_id != projection["client_order_id"]:
            raise RuntimeError("venue fact client identity conflicts with transport projection")
        if fact.external_status is ExternalOrderStatus.REJECTED:
            raise MockVenueRejected("venue explicitly rejected submission")
        if fact.external_status is not ExternalOrderStatus.FILLED or not fact.external_order_id:
            raise RuntimeError("venue fact does not prove acceptance")
        if fact.executed_quote_qty != projection["requested_quote_amount"]:
            raise RuntimeError("venue fact changed the authorized quote amount")


__all__ = [
    "GovernedSubmissionGateway", "TransportDisposition", "TransportResult",
]
