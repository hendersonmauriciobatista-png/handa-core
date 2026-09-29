"""Semantic persistence contract for governed LIVE order evidence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Optional

from psycopg2.extras import Json

from core.execution.live_order_models import LiveOrderIntent
from core.persistence.persistence_coordinator import PersistenceCoordinator
from core.persistence.transaction_context import (
    ImmutablePage,
    ImmutableRow,
    InvalidCapabilityRequest,
    Predicate,
    PredicateOperator,
    ResourceScope,
    ResourceSpec,
)


LIVE_SCHEMA = "handa_live"


def live_order_resource_scope() -> ResourceScope:
    """Return the exact structured resource scope for the published schema."""

    order_intent = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="order_intent",
        readable_columns=frozenset(
            {
                "intent_id", "venue", "account_scope", "client_order_id",
                "slot_id", "symbol", "side", "requested_quote_amount",
                "requested_base_qty", "policy_context",
                "submission_lifecycle_state", "execution_certainty",
                "reconciliation_state", "exchange_order_id",
                "current_version", "current_context_id", "current_decision_id",
                "recorded_at",
            }
        ),
        writable_columns=frozenset(
            {
                "intent_id", "venue", "account_scope", "client_order_id",
                "slot_id", "symbol", "side", "requested_quote_amount",
                "requested_base_qty", "policy_context",
                "submission_lifecycle_state", "execution_certainty",
                "reconciliation_state", "exchange_order_id",
                "current_version", "current_context_id", "current_decision_id",
            }
        ),
        key_columns=frozenset({"intent_id"}),
        ordering_columns=("intent_id",),
        version_column="current_version",
    )
    submission_attempt = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="submission_attempt",
        readable_columns=frozenset(
            {
                "attempt_id", "intent_id", "attempt_sequence", "venue",
                "context_id",
                "account_scope", "client_order_id",
                "submission_lifecycle_state", "exchange_order_id",
                "transport_status", "transport_error", "recorded_at",
                "observed_at", "exchange_event_time",
            }
        ),
        writable_columns=frozenset(
            {
                "attempt_id", "intent_id", "attempt_sequence", "venue",
                "context_id",
                "account_scope", "client_order_id",
                "submission_lifecycle_state", "exchange_order_id",
                "transport_status", "transport_error", "observed_at",
                "exchange_event_time",
            }
        ),
        key_columns=frozenset({"attempt_id"}),
        ordering_columns=("attempt_sequence", "attempt_id"),
    )
    exchange_evidence = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="exchange_evidence",
        readable_columns=frozenset(
            {
                "evidence_id", "intent_id", "attempt_id", "evidence_sequence",
                "symbol", "exchange_order_id", "exchange_status",
                "raw_snapshot", "recorded_at", "observed_at",
                "exchange_event_time", "client_order_id_observed", "order_type",
                "time_in_force", "orig_qty", "orig_quote_order_qty", "executed_qty",
                "cumulative_quote_qty", "observation_class", "observation_source",
            }
        ),
        writable_columns=frozenset(
            {
                "evidence_id", "intent_id", "attempt_id", "evidence_sequence",
                "symbol", "exchange_order_id", "exchange_status",
                "raw_snapshot", "observed_at", "exchange_event_time",
                "client_order_id_observed", "order_type", "time_in_force", "orig_qty",
                "orig_quote_order_qty", "executed_qty", "cumulative_quote_qty",
                "observation_class", "observation_source",
            }
        ),
        key_columns=frozenset({"evidence_id"}),
        ordering_columns=("evidence_sequence", "evidence_id"),
    )
    trade_effect = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="trade_effect",
        readable_columns=frozenset(
            {
                "symbol", "exchange_order_id", "exchange_trade_id",
                "evidence_id", "intent_id", "price", "gross_base_qty",
                "quote_qty", "commission_amount", "commission_asset",
                "recorded_at", "exchange_event_time",
            }
        ),
        writable_columns=frozenset(
            {
                "symbol", "exchange_order_id", "exchange_trade_id",
                "evidence_id", "intent_id", "price", "gross_base_qty",
                "quote_qty", "commission_amount", "commission_asset",
                "exchange_event_time",
            }
        ),
        key_columns=frozenset(
            {"symbol", "exchange_order_id", "exchange_trade_id"}
        ),
        ordering_columns=(
            "recorded_at", "symbol", "exchange_order_id", "exchange_trade_id"
        ),
    )
    normalized_evidence = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="normalized_evidence",
        readable_columns=frozenset(
            {
                "normalized_revision_id", "evidence_id", "intent_id",
                "revision_sequence", "exchange_status", "normalized_status",
                "provenance", "normalized_payload", "recorded_at",
            }
        ),
        writable_columns=frozenset(
            {
                "normalized_revision_id", "evidence_id", "intent_id",
                "revision_sequence", "exchange_status", "normalized_status",
                "provenance", "normalized_payload",
            }
        ),
        key_columns=frozenset({"normalized_revision_id"}),
        ordering_columns=("revision_sequence", "normalized_revision_id"),
    )
    reconciliation = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="reconciliation",
        readable_columns=frozenset(
            {
                "reconciliation_id", "intent_id", "decision_sequence",
                "reconciliation_state", "execution_certainty",
                "decision_reason", "recorded_at", "resolved_at",
            }
        ),
        writable_columns=frozenset(
            {
                "reconciliation_id", "intent_id", "decision_sequence",
                "reconciliation_state", "execution_certainty",
                "decision_reason", "resolved_at",
            }
        ),
        key_columns=frozenset({"reconciliation_id"}),
        ordering_columns=("decision_sequence", "reconciliation_id"),
    )
    reconciliation_context = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="reconciliation_context",
        readable_columns=frozenset({
            "context_id", "intent_id", "context_sequence", "context_state",
            "created_at", "closed_at", "closure_reason", "predecessor_context_id",
            "predecessor_intent_id",
        }),
        writable_columns=frozenset({
            "context_id", "intent_id", "context_sequence", "context_state",
            "closed_at", "closure_reason", "predecessor_context_id",
            "predecessor_intent_id",
        }),
        key_columns=frozenset({"context_id"}),
        ordering_columns=("context_sequence", "context_id"),
    )
    semantic_decision = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="semantic_decision",
        readable_columns=frozenset({
            "decision_id", "context_id", "intent_id", "reconciliation_id",
            "decision_sequence", "evaluation_time", "decision_scope",
            "authority_state", "execution_occurred", "order_outcome_terminal",
            "execution_extent", "final_partial_outcome", "unknown_reason",
            "contradiction_result", "decision_reason", "evaluated_input_snapshot",
            "authority_contract_version", "decision_schema_version",
            "evidence_normalization_version", "lineage_completeness_status",
            "recorded_at",
        }),
        writable_columns=frozenset({
            "decision_id", "context_id", "intent_id", "reconciliation_id",
            "decision_sequence", "evaluation_time", "decision_scope",
            "authority_state", "execution_occurred", "order_outcome_terminal",
            "execution_extent", "final_partial_outcome", "unknown_reason",
            "contradiction_result", "decision_reason", "evaluated_input_snapshot",
            "authority_contract_version", "decision_schema_version",
            "evidence_normalization_version", "lineage_completeness_status",
        }),
        key_columns=frozenset({"decision_id"}),
        ordering_columns=("decision_sequence", "decision_id"),
    )
    decision_evidence_reference = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="decision_evidence_reference",
        readable_columns=frozenset({
            "reference_id", "decision_id", "intent_id", "evidence_kind",
            "semantic_role", "recorded_at",
        }),
        writable_columns=frozenset({
            "reference_id", "decision_id", "intent_id", "evidence_kind",
            "semantic_role",
        }),
        key_columns=frozenset({"reference_id"}),
        ordering_columns=("recorded_at", "reference_id"),
    )
    decision_exchange_observation_ref = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="decision_exchange_observation_ref",
        readable_columns=frozenset({"reference_id", "evidence_id", "intent_id"}),
        writable_columns=frozenset({"reference_id", "evidence_id", "intent_id"}),
        key_columns=frozenset({"reference_id"}),
        ordering_columns=("reference_id",),
    )
    decision_normalized_revision_ref = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="decision_normalized_revision_ref",
        readable_columns=frozenset({"reference_id", "normalized_revision_id", "intent_id"}),
        writable_columns=frozenset({"reference_id", "normalized_revision_id", "intent_id"}),
        key_columns=frozenset({"reference_id"}),
        ordering_columns=("reference_id",),
    )
    decision_trade_fill_ref = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="decision_trade_fill_ref",
        readable_columns=frozenset({
            "reference_id", "symbol", "exchange_order_id", "exchange_trade_id", "intent_id",
        }),
        writable_columns=frozenset({
            "reference_id", "symbol", "exchange_order_id", "exchange_trade_id", "intent_id",
        }),
        key_columns=frozenset({"reference_id"}),
        ordering_columns=("reference_id",),
    )
    decision_contradiction_basis_ref = ResourceSpec(
        schema=LIVE_SCHEMA,
        table="decision_contradiction_basis_ref",
        readable_columns=frozenset({"reference_id", "basis_reference_id", "intent_id"}),
        writable_columns=frozenset({"reference_id", "basis_reference_id", "intent_id"}),
        key_columns=frozenset({"reference_id"}),
        ordering_columns=("reference_id",),
    )
    return ResourceScope(
        (
            order_intent,
            submission_attempt,
            exchange_evidence,
            trade_effect,
            normalized_evidence,
            reconciliation,
            reconciliation_context,
            semantic_decision,
            decision_evidence_reference,
            decision_exchange_observation_ref,
            decision_normalized_revision_ref,
            decision_trade_fill_ref,
            decision_contradiction_basis_ref,
        )
    )


class LiveOrderStore:
    """Semantic Store using coordinator-owned structured transactions only."""

    def __init__(self, coordinator: PersistenceCoordinator):
        self._coordinator = coordinator

    def create_intent(
        self, intent: LiveOrderIntent, *, venue: str, account_scope: str
    ) -> ImmutableRow:
        values = {
            "intent_id": intent.intent_id,
            "venue": venue,
            "account_scope": account_scope,
            "client_order_id": intent.client_order_id,
            "slot_id": intent.slot_id,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "requested_quote_amount": intent.requested_quote_amount,
            "requested_base_qty": intent.requested_base_qty,
            "policy_context": intent.policy_context,
            "submission_lifecycle_state": "READY_TO_SUBMIT",
            "execution_certainty": None,
            "reconciliation_state": None,
        }
        return self._run(
            lambda context: context.insert_returning(
                "order_intent", values, _ORDER_COLUMNS
            )
        )

    def record_submission_preparation(
        self,
        *,
        intent_id: str,
        attempt_id: str,
        attempt_sequence: int,
        venue: str,
        account_scope: str,
        client_order_id: str,
        expected_version: int,
        context_id: Optional[str] = None,
    ) -> ImmutableRow:
        def operation(context):
            current = context.read_by_key(
                "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
            )
            if current is None or current["submission_lifecycle_state"] != "READY_TO_SUBMIT":
                raise ValueError("submission preparation requires READY_TO_SUBMIT")
            if current["execution_certainty"] is not None:
                raise ValueError("submission preparation requires NULL execution certainty")
            if (
                current["venue"] != venue
                or current["account_scope"] != account_scope
                or current["client_order_id"] != client_order_id
            ):
                raise ValueError(
                    "submission preparation identity does not match persisted intent"
                )
            if context_id is not None:
                context_row = context.read_by_key(
                    "reconciliation_context", {"context_id": context_id}, ("intent_id",)
                )
                if context_row is not None and context_row["intent_id"] != intent_id:
                    raise ValueError("submission attempt context intent mismatch")
            context.insert(
                "submission_attempt",
                {
                    "attempt_id": attempt_id,
                    "intent_id": intent_id,
                    "attempt_sequence": attempt_sequence,
                    "context_id": context_id,
                    "venue": venue,
                    "account_scope": account_scope,
                    "client_order_id": client_order_id,
                    "submission_lifecycle_state": "SUBMISSION_ATTEMPTED",
                },
            )
            return context.update_if_version(
                "order_intent",
                {"intent_id": intent_id},
                expected_version,
                {
                    "submission_lifecycle_state": "SUBMISSION_ATTEMPTED",
                    "execution_certainty": None,
                    "reconciliation_state": None,
                },
                _ORDER_COLUMNS,
            )

        return self._run(operation)

    def record_external_handoff(
        self,
        *,
        intent_id: str,
        expected_version: int,
        reconciliation_state: str = "PENDING",
    ) -> ImmutableRow:
        if reconciliation_state not in {"PENDING", "BLOCKED"}:
            raise InvalidCapabilityRequest(
                "external handoff requires PENDING or BLOCKED reconciliation"
            )

        def operation(context):
            current = context.read_by_key(
                "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
            )
            if current is None or current["submission_lifecycle_state"] != "SUBMISSION_ATTEMPTED":
                raise ValueError("external handoff requires submission preparation")
            if current["execution_certainty"] is not None:
                raise ValueError("external handoff requires NULL execution certainty")
            return context.update_if_version(
                "order_intent",
                {"intent_id": intent_id},
                expected_version,
                {
                    "submission_lifecycle_state": "MAY_HAVE_BEEN_SUBMITTED",
                    "execution_certainty": "UNKNOWN",
                    "reconciliation_state": reconciliation_state,
                },
                _ORDER_COLUMNS,
            )

        return self._run(operation)

    def record_exchange_observation(
        self,
        *,
        evidence_id: str,
        intent_id: str,
        evidence_sequence: int,
        symbol: str,
        raw_snapshot: Mapping[str, Any],
        observed_at: Any,
        attempt_id: Optional[str] = None,
        exchange_order_id: Optional[str] = None,
        exchange_status: Optional[str] = None,
        exchange_event_time: Any = None,
        normalized_revision: Optional[Mapping[str, Any]] = None,
        trade_effects: Sequence[Mapping[str, Any]] = (),
        expected_version: Optional[int] = None,
        client_order_id_observed: Optional[str] = None,
        order_type: Optional[str] = None,
        time_in_force: Optional[str] = None,
        orig_qty: Any = None,
        orig_quote_order_qty: Any = None,
        executed_qty: Any = None,
        cumulative_quote_qty: Any = None,
        observation_class: Optional[str] = None,
        observation_source: Optional[str] = None,
    ) -> None:
        def operation(context):
            context.insert(
                "exchange_evidence",
                {
                    "evidence_id": evidence_id,
                    "intent_id": intent_id,
                    "attempt_id": attempt_id,
                    "evidence_sequence": evidence_sequence,
                    "symbol": symbol,
                    "exchange_order_id": exchange_order_id,
                    "exchange_status": exchange_status,
                    "raw_snapshot": Json(dict(raw_snapshot)),
                    "client_order_id_observed": client_order_id_observed,
                    "order_type": order_type,
                    "time_in_force": time_in_force,
                    "orig_qty": orig_qty,
                    "orig_quote_order_qty": orig_quote_order_qty,
                    "executed_qty": executed_qty,
                    "cumulative_quote_qty": cumulative_quote_qty,
                    "observation_class": observation_class,
                    "observation_source": observation_source,
                    "observed_at": observed_at,
                    "exchange_event_time": exchange_event_time,
                },
            )
            for effect in trade_effects:
                context.insert(
                    "trade_effect",
                    _trade_effect_values(effect, evidence_id, intent_id),
                )
            if normalized_revision is not None:
                context.insert(
                    "normalized_evidence",
                    _normalized_values(normalized_revision, evidence_id, intent_id),
                )
            if exchange_order_id is not None:
                if expected_version is None:
                    raise InvalidCapabilityRequest(
                        "expected_version is required when associating exchange order"
                    )
                current = context.read_by_key(
                    "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
                )
                if current is None:
                    raise ValueError("exchange observation requires an existing intent")
                if (
                    current["exchange_order_id"] is not None
                    and current["exchange_order_id"] != exchange_order_id
                ):
                    raise ValueError("exchange order correlation conflict")
                context.update_if_version(
                    "order_intent",
                    {"intent_id": intent_id},
                    expected_version,
                    {"exchange_order_id": exchange_order_id},
                    _ORDER_COLUMNS,
                )

        self._run(operation)

    def append_normalized_revision(
        self, *, evidence_id: str, intent_id: str, revision: Mapping[str, Any]
    ) -> None:
        self._run(
            lambda context: context.insert(
                "normalized_evidence",
                _normalized_values(revision, evidence_id, intent_id),
            )
        )

    def append_trade_effects(
        self,
        *,
        evidence_id: str,
        intent_id: str,
        effects: Sequence[Mapping[str, Any]],
    ) -> None:
        def operation(context):
            for effect in effects:
                context.insert(
                    "trade_effect",
                    _trade_effect_values(effect, evidence_id, intent_id),
                )

        self._run(operation)

    def associate_exchange_order(
        self,
        *,
        intent_id: str,
        exchange_order_id: str,
        expected_version: int,
    ) -> ImmutableRow:
        def operation(context):
            current = context.read_by_key(
                "order_intent", {"intent_id": intent_id}, _ORDER_COLUMNS
            )
            if current is None:
                raise ValueError("exchange order association requires an existing intent")
            if (
                current["exchange_order_id"] is not None
                and current["exchange_order_id"] != exchange_order_id
            ):
                raise ValueError("exchange order correlation conflict")
            return context.update_if_version(
                "order_intent",
                {"intent_id": intent_id},
                expected_version,
                {"exchange_order_id": exchange_order_id},
                _ORDER_COLUMNS,
            )

        return self._run(operation)

    def append_reconciliation_decision(
        self,
        *,
        reconciliation_id: str,
        intent_id: str,
        decision_sequence: int,
        reconciliation_state: str,
        execution_certainty: str,
        expected_version: int,
        decision_reason: Optional[str] = None,
        resolved_at: Any = None,
    ) -> ImmutableRow:
        _validate_reconciliation_boundary(
            reconciliation_state, execution_certainty
        )

        def operation(context):
            context.insert(
                "reconciliation",
                {
                    "reconciliation_id": reconciliation_id,
                    "intent_id": intent_id,
                    "decision_sequence": decision_sequence,
                    "reconciliation_state": reconciliation_state,
                    "execution_certainty": execution_certainty,
                    "decision_reason": decision_reason,
                    "resolved_at": resolved_at,
                },
            )
            return _update_current_projection(
                context,
                intent_id=intent_id,
                expected_version=expected_version,
                changes={
                    "execution_certainty": execution_certainty,
                    "reconciliation_state": reconciliation_state,
                },
            )

        return self._run(operation)

    def create_reconciliation_context(
        self,
        *,
        context_id: str,
        intent_id: str,
        context_state: str = "ACTIVE",
        predecessor_context_id: Optional[str] = None,
        closure_reason: Optional[str] = None,
        closed_at: Any = None,
    ) -> ImmutableRow:
        def operation(context):
            context_sequence = context.allocate_next_sequence(
                "reconciliation_context",
                "intent_id",
                intent_id,
                "context_sequence",
                "order_intent",
            )
            return context.insert_returning(
                "reconciliation_context",
                {
                    "context_id": context_id,
                    "intent_id": intent_id,
                    "context_sequence": context_sequence,
                    "context_state": context_state,
                    "predecessor_context_id": predecessor_context_id,
                    "predecessor_intent_id": intent_id if predecessor_context_id is not None else None,
                    "closure_reason": closure_reason,
                    "closed_at": closed_at,
                },
                _CONTEXT_COLUMNS,
            )

        return self._run(operation)

    def append_semantic_decision(
        self,
        *,
        decision: Mapping[str, Any],
        evidence_references: Sequence[Mapping[str, Any]] = (),
        expected_version: Optional[int] = None,
    ) -> ImmutableRow:
        """Append one immutable semantic decision and its typed references."""
        required = {
            "decision_id", "context_id", "intent_id",
            "evaluation_time", "decision_scope", "authority_state",
            "execution_occurred", "order_outcome_terminal", "execution_extent",
            "final_partial_outcome", "evaluated_input_snapshot",
            "authority_contract_version", "decision_schema_version",
            "evidence_normalization_version", "lineage_completeness_status",
        }
        missing = sorted(required - set(decision))
        if missing:
            raise InvalidCapabilityRequest(
                f"semantic decision requires {', '.join(missing)}"
            )
        if "decision_sequence" in decision:
            raise InvalidCapabilityRequest(
                "decision_sequence is allocated by governed persistence"
            )

        def operation(context):
            values = dict(decision)
            values["decision_sequence"] = context.allocate_next_sequence(
                "semantic_decision",
                "context_id",
                decision["context_id"],
                "decision_sequence",
                "reconciliation_context",
            )
            for name in (
                "execution_occurred", "order_outcome_terminal", "execution_extent",
                "final_partial_outcome", "unknown_reason", "contradiction_result",
                "evaluated_input_snapshot",
            ):
                if name in values and values[name] is not None:
                    values[name] = Json(values[name])
            result = context.insert_returning(
                "semantic_decision", values, _SEMANTIC_DECISION_COLUMNS
            )
            for reference in evidence_references:
                reference_values = {
                    name: reference[name]
                    for name in (
                        "reference_id", "decision_id", "intent_id", "evidence_kind",
                        "semantic_role",
                    )
                    if name in reference
                }
                _validate_decision_reference(reference_values)
                _validate_authoritative_reference(context, reference, decision)
                context.insert("decision_evidence_reference", reference_values)
                kind = reference_values["evidence_kind"]
                if kind == "EXCHANGE_OBSERVATION":
                    context.insert(
                        "decision_exchange_observation_ref",
                        {
                            "reference_id": reference_values["reference_id"],
                            "evidence_id": reference["evidence_id"],
                            "intent_id": reference_values["intent_id"],
                        },
                    )
                elif kind == "NORMALIZED_REVISION":
                    context.insert(
                        "decision_normalized_revision_ref",
                        {
                            "reference_id": reference_values["reference_id"],
                            "normalized_revision_id": reference["normalized_revision_id"],
                            "intent_id": reference_values["intent_id"],
                        },
                    )
                elif kind == "TRADE_FILL":
                    context.insert(
                        "decision_trade_fill_ref",
                        {
                            "reference_id": reference_values["reference_id"],
                            "symbol": reference["symbol"],
                            "exchange_order_id": reference["exchange_order_id"],
                            "exchange_trade_id": reference["exchange_trade_id"],
                            "intent_id": reference_values["intent_id"],
                        },
                    )
                else:
                    context.insert(
                        "decision_contradiction_basis_ref",
                        {
                            "reference_id": reference_values["reference_id"],
                            "basis_reference_id": reference["basis_reference_id"],
                            "intent_id": reference_values["intent_id"],
                        },
                    )
            if expected_version is not None:
                _update_current_projection(
                    context,
                    intent_id=decision["intent_id"],
                    expected_version=expected_version,
                    changes={
                        "current_context_id": decision["context_id"],
                        "current_decision_id": decision["decision_id"],
                    },
                )
            return result

        return self._run(operation)

    def evaluate_lineage_completeness(
        self, *, references: Sequence[Mapping[str, Any]], required_kinds: Sequence[str]
    ) -> str:
        present = {reference.get("evidence_kind") for reference in references}
        return (
            "LINEAGE_COMPLETE"
            if set(required_kinds) <= present
            else "LINEAGE_INCOMPLETE"
        )

    def find_unresolved(self, *, limit: int, cursor: Optional[str] = None) -> ImmutablePage:
        return self._find_order_page(
            [Predicate("execution_certainty", PredicateOperator.EQ, "UNKNOWN")],
            limit,
            cursor,
        )

    def find_unresolved_by_symbol(
        self, *, symbol: str, limit: int, cursor: Optional[str] = None
    ) -> ImmutablePage:
        return self._find_order_page(
            [
                Predicate("symbol", PredicateOperator.EQ, symbol),
                Predicate("execution_certainty", PredicateOperator.EQ, "UNKNOWN"),
            ],
            limit,
            cursor,
        )

    def find_by_client_namespace(
        self, *, venue: str, account_scope: str, client_order_id: str
    ) -> Optional[ImmutableRow]:
        page = self._find_order_page(
            [
                Predicate("venue", PredicateOperator.EQ, venue),
                Predicate("account_scope", PredicateOperator.EQ, account_scope),
                Predicate("client_order_id", PredicateOperator.EQ, client_order_id),
            ],
            1,
        )
        return page.rows[0] if page.rows else None

    def find_by_exchange_correlation(
        self, *, symbol: str, exchange_order_id: str, limit: int = 100
    ) -> ImmutablePage:
        return self._find_order_page(
            [
                Predicate("symbol", PredicateOperator.EQ, symbol),
                Predicate("exchange_order_id", PredicateOperator.EQ, exchange_order_id),
            ],
            limit,
        )

    def enumerate_evidence(
        self, *, intent_id: str, limit: int, cursor: Optional[str] = None
    ) -> ImmutablePage:
        return self._run(
            lambda context: context.enumerate(
                "exchange_evidence",
                [Predicate("intent_id", PredicateOperator.EQ, intent_id)],
                _EVIDENCE_COLUMNS,
                limit,
                cursor,
            )
        )

    def _find_order_page(
        self,
        predicates: Sequence[Predicate],
        limit: int,
        cursor: Optional[str] = None,
    ) -> ImmutablePage:
        return self._run(
            lambda context: context.enumerate(
                "order_intent", predicates, _ORDER_COLUMNS, limit, cursor
            )
        )

    def _run(self, operation):
        with self._coordinator.transaction() as context:
            return operation(context)


_ORDER_COLUMNS = (
    "intent_id", "venue", "account_scope", "client_order_id", "slot_id",
    "symbol", "side", "requested_quote_amount", "requested_base_qty",
    "policy_context", "submission_lifecycle_state", "execution_certainty",
    "reconciliation_state", "exchange_order_id", "current_version",
    "current_context_id", "current_decision_id",
    "recorded_at",
)

_EVIDENCE_COLUMNS = (
    "evidence_id", "intent_id", "attempt_id", "evidence_sequence", "symbol",
    "exchange_order_id", "exchange_status", "raw_snapshot", "recorded_at",
    "observed_at", "exchange_event_time", "client_order_id_observed",
    "order_type", "time_in_force", "orig_qty", "orig_quote_order_qty",
    "executed_qty", "cumulative_quote_qty", "observation_class",
    "observation_source",
)

_CONTEXT_COLUMNS = (
    "context_id", "intent_id", "context_sequence", "context_state",
    "created_at", "closed_at", "closure_reason", "predecessor_context_id",
    "predecessor_intent_id",
)

_SEMANTIC_DECISION_COLUMNS = (
    "decision_id", "context_id", "intent_id", "reconciliation_id",
    "decision_sequence", "evaluation_time", "decision_scope", "authority_state",
    "execution_occurred", "order_outcome_terminal", "execution_extent",
    "final_partial_outcome", "unknown_reason", "contradiction_result",
    "decision_reason", "evaluated_input_snapshot", "authority_contract_version",
    "decision_schema_version", "evidence_normalization_version",
    "lineage_completeness_status", "recorded_at",
)


def _update_current_projection(
    context, *, intent_id: str, expected_version: int, changes: Mapping[str, Any]
) -> ImmutableRow:
    return context.update_if_version(
        "order_intent",
        {"intent_id": intent_id},
        expected_version,
        changes,
        _ORDER_COLUMNS,
    )


def _validate_decision_reference(reference: Mapping[str, Any]) -> None:
    required = {"reference_id", "decision_id", "intent_id", "evidence_kind", "semantic_role"}
    missing = sorted(required - set(reference))
    if missing:
        raise InvalidCapabilityRequest(
            f"decision evidence reference requires {', '.join(missing)}"
        )
    required_by_kind = {
        "EXCHANGE_OBSERVATION": ("evidence_id",),
        "NORMALIZED_REVISION": ("normalized_revision_id",),
        "TRADE_FILL": ("symbol", "exchange_order_id", "exchange_trade_id"),
        "CONTRADICTION_BASIS": ("basis_reference_id",),
    }
    kind = reference["evidence_kind"]
    if kind not in required_by_kind:
        raise InvalidCapabilityRequest(f"unsupported evidence kind: {kind}")
    missing = [name for name in required_by_kind[kind] if name not in reference]
    if missing:
        raise InvalidCapabilityRequest(
            f"{kind} reference requires {', '.join(missing)}"
        )


def _validate_authoritative_reference(
    context, reference: Mapping[str, Any], decision: Mapping[str, Any]
) -> None:
    if reference["decision_id"] != decision["decision_id"]:
        raise InvalidCapabilityRequest("evidence reference decision identity mismatch")
    if reference["intent_id"] != decision["intent_id"]:
        raise InvalidCapabilityRequest("evidence reference intent identity mismatch")

    kind = reference["evidence_kind"]
    if kind == "EXCHANGE_OBSERVATION":
        owner = context.read_by_key(
            "exchange_evidence", {"evidence_id": reference["evidence_id"]}, ("intent_id",)
        )
    elif kind == "NORMALIZED_REVISION":
        owner = context.read_by_key(
            "normalized_evidence",
            {"normalized_revision_id": reference["normalized_revision_id"]},
            ("intent_id",),
        )
    elif kind == "TRADE_FILL":
        owner = context.read_by_key(
            "trade_effect",
            {
                "symbol": reference["symbol"],
                "exchange_order_id": reference["exchange_order_id"],
                "exchange_trade_id": reference["exchange_trade_id"],
            },
            ("intent_id",),
        )
    else:
        owner = context.read_by_key(
            "decision_evidence_reference",
            {"reference_id": reference["basis_reference_id"]},
            ("decision_id", "intent_id"),
        )
    if owner is not None:
        if kind == "CONTRADICTION_BASIS":
            if (
                owner["decision_id"] != decision["decision_id"]
                or owner["intent_id"] != decision["intent_id"]
            ):
                raise InvalidCapabilityRequest(
                    "contradiction basis identity mismatch"
                )
        elif owner["intent_id"] != decision["intent_id"]:
            raise InvalidCapabilityRequest("authoritative evidence intent mismatch")


def _trade_effect_values(effect, evidence_id: str, intent_id: str):
    required = (
        "symbol", "exchange_order_id", "exchange_trade_id", "price",
        "gross_base_qty", "quote_qty", "commission_amount", "commission_asset",
    )
    missing = [name for name in required if name not in effect]
    if missing:
        raise InvalidCapabilityRequest(
            f"trade effect requires {', '.join(missing)}"
        )
    values = {name: effect[name] for name in required}
    values.update(
        {
            "evidence_id": evidence_id,
            "intent_id": intent_id,
            "exchange_event_time": effect.get("exchange_event_time"),
        }
    )
    return values


def _normalized_values(revision, evidence_id: str, intent_id: str):
    for name in ("normalized_revision_id", "revision_sequence", "normalized_status"):
        if name not in revision:
            raise InvalidCapabilityRequest(f"normalized revision requires {name}")
    return {
        "normalized_revision_id": revision["normalized_revision_id"],
        "evidence_id": evidence_id,
        "intent_id": intent_id,
        "revision_sequence": revision["revision_sequence"],
        "exchange_status": revision.get("exchange_status"),
        "normalized_status": revision["normalized_status"],
        "provenance": Json(dict(revision.get("provenance", {}))),
        "normalized_payload": Json(dict(revision.get("normalized_payload", {}))),
    }


def _validate_reconciliation_boundary(state: str, certainty: str) -> None:
    if certainty == "UNKNOWN" and state not in {"PENDING", "BLOCKED"}:
        raise InvalidCapabilityRequest(
            "UNKNOWN requires PENDING or BLOCKED reconciliation"
        )
    if certainty == "NO_EFFECT_CONFIRMED" and state != "RESOLVED":
        raise InvalidCapabilityRequest(
            "NO_EFFECT_CONFIRMED requires RESOLVED reconciliation"
        )
    if certainty == "EXECUTION_CONFIRMED" and state != "RESOLVED":
        raise InvalidCapabilityRequest(
            "EXECUTION_CONFIRMED requires RESOLVED reconciliation"
        )
    if certainty not in {
        "UNKNOWN", "NO_EFFECT_CONFIRMED", "EXECUTION_CONFIRMED"
    }:
        raise InvalidCapabilityRequest("unsupported execution certainty")
    if state not in {"NOT_REQUIRED", "PENDING", "RESOLVED", "BLOCKED"}:
        raise InvalidCapabilityRequest("unsupported reconciliation state")
