"""Disconnected position-effect authority foundation.

This module owns position-effect identity and durable-domain semantics.  It
does not submit orders, release slots, retry submissions, or finalize
financial accounting.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional

from psycopg2.extras import Json


class PositionEffectError(RuntimeError):
    """Raised when a position-effect contract invariant is violated."""


@dataclass(frozen=True)
class Position:
    position_id: str
    intent_id: str
    symbol: str
    quantity: Decimal
    state: str = "ACTIVE"
    lifecycle_version: int = 1

    @property
    def current_quantity(self) -> Decimal:
        return self.quantity


@dataclass(frozen=True)
class PositionEffectResult:
    position_id: str
    effect_type: str
    previous_quantity: Decimal
    applied_quantity: Decimal
    resulting_quantity: Decimal
    state: str
    effect_request_id: str
    execution_extent_identity: str

    @property
    def residual_quantity(self) -> Decimal:
        return self.resulting_quantity

    @property
    def quantity(self) -> Decimal:
        return self.resulting_quantity

    @property
    def status(self) -> str:
        return self.state


class PositionEffectAuthority:
    """Validate and apply isolated position effects.

    The in-memory mode makes domain falsifiers executable without creating a
    second live operational mutation path.  A PostgreSQL implementation may
    use the same contract with the migration-007 relations.
    """

    def __init__(self, connection: Any = None, ledger: Any = None):
        self.connection = connection
        self.ledger = ledger
        self._positions: dict[str, Position] = {}
        self._history: dict[str, list[PositionEffectResult]] = {}
        self._request_results: dict[str, PositionEffectResult] = {}
        self._consumed_extents: dict[str, PositionEffectResult] = {}

    def apply_open(
        self,
        *,
        position_id: str,
        intended_quantity: Any,
        receipt: Mapping[str, Any],
        intent_id: str,
        symbol: str = "",
        effect_request_id: str,
        external_order_id: Optional[str] = None,
        cursor: Any = None,
        **binding: Any,
    ) -> PositionEffectResult:
        if int(binding.get("decision_sequence", 1)) <= 0:
            raise PositionEffectError("stale semantic decision")
        if binding.get("contradiction_state") in {"PRESENT", "CONTRADICTED"}:
            raise PositionEffectError("later contradiction blocks application")
        if cursor is not None:
            return self._apply_open_persistent(
                cursor=cursor,
                position_id=position_id,
                intended_quantity=intended_quantity,
                receipt=receipt,
                intent_id=intent_id,
                symbol=symbol,
                effect_request_id=effect_request_id,
                external_order_id=external_order_id,
                binding=binding,
            )
        if effect_request_id in self._request_results:
            return self._request_results[effect_request_id]
        quantity = self._receipt_quantity(receipt)
        intended = self._decimal(intended_quantity, "intended_quantity")
        if quantity <= 0 or intended <= 0:
            raise PositionEffectError("OPEN requires positive quantity")
        if position_id in self._positions:
            raise PositionEffectError("position identity already exists")
        self._validate_receipt_order(receipt, external_order_id)
        extent = self._extent_identity(receipt)
        self._claim_extent(extent)
        position = Position(position_id, intent_id, symbol, quantity)
        result = PositionEffectResult(
            position_id, "OPEN", Decimal("0"), quantity, quantity, "ACTIVE",
            effect_request_id, extent,
        )
        self._positions[position_id] = position
        self._record(result)
        return result

    def apply_reduction(
        self,
        *,
        position_id: str,
        applied_quantity: Any,
        receipt: Mapping[str, Any],
        effect_request_id: str,
        cursor: Any = None,
        **binding: Any,
    ) -> PositionEffectResult:
        if int(binding.get("decision_sequence", 1)) <= 0:
            raise PositionEffectError("stale semantic decision")
        if binding.get("contradiction_state") in {"PRESENT", "CONTRADICTED"}:
            raise PositionEffectError("later contradiction blocks application")
        if cursor is not None:
            return self._apply_reduction_persistent(
                cursor=cursor,
                position_id=position_id,
                applied_quantity=applied_quantity,
                receipt=receipt,
                effect_request_id=effect_request_id,
                binding=binding,
            )
        if effect_request_id in self._request_results:
            return self._request_results[effect_request_id]
        position = self._positions.get(position_id)
        if position is None or position.state != "ACTIVE":
            raise PositionEffectError("active position is required")
        applied = self._decimal(applied_quantity, "applied_quantity")
        if applied <= 0 or applied >= position.quantity:
            raise PositionEffectError("REDUCE must leave positive residual")
        receipt_quantity = self._receipt_quantity(receipt)
        if receipt_quantity != applied:
            raise PositionEffectError("receipt extent does not match reduction")
        extent = self._extent_identity(receipt)
        self._claim_extent(extent)
        resulting = position.quantity - applied
        result = PositionEffectResult(
            position_id, "REDUCE", position.quantity, applied, resulting, "ACTIVE",
            effect_request_id, extent,
        )
        self._positions[position_id] = Position(
            position.position_id, position.intent_id, position.symbol,
            resulting, "ACTIVE", position.lifecycle_version + 1,
        )
        self._record(result)
        return result

    def apply_close(
        self,
        *,
        position_id: str,
        receipt: Mapping[str, Any],
        effect_request_id: str,
        outcome: str = "RESOLVED",
        cursor: Any = None,
        **binding: Any,
    ) -> PositionEffectResult:
        if int(binding.get("decision_sequence", 1)) <= 0:
            raise PositionEffectError("stale semantic decision")
        if binding.get("contradiction_state") in {"PRESENT", "CONTRADICTED"}:
            raise PositionEffectError("later contradiction blocks application")
        if cursor is not None:
            return self._apply_close_persistent(
                cursor=cursor,
                position_id=position_id,
                receipt=receipt,
                effect_request_id=effect_request_id,
                outcome=outcome,
                binding=binding,
            )
        if effect_request_id in self._request_results:
            return self._request_results[effect_request_id]
        if outcome == "OUTCOME_UNKNOWN":
            raise PositionEffectError("UNKNOWN outcome cannot close position")
        position = self._positions.get(position_id)
        if position is None or position.state != "ACTIVE":
            raise PositionEffectError("active position is required")
        applied = self._receipt_quantity(receipt)
        if applied != position.quantity:
            raise PositionEffectError("CLOSE requires full residual extent")
        extent = self._extent_identity(receipt)
        self._claim_extent(extent)
        result = PositionEffectResult(
            position_id, "CLOSE", position.quantity, applied, Decimal("0"), "CLOSED",
            effect_request_id, extent,
        )
        self._positions[position_id] = Position(
            position.position_id, position.intent_id, position.symbol,
            Decimal("0"), "CLOSED", position.lifecycle_version + 1,
        )
        self._record(result)
        return result

    def get_position(self, position_id: str) -> Position:
        try:
            return self._positions[position_id]
        except KeyError as exc:
            raise PositionEffectError("position does not exist") from exc

    def get_position_history(self, position_id: str) -> tuple[PositionEffectResult, ...]:
        return tuple(self._history.get(position_id, ()))

    def reconcile_local_mutation(
        self, *, effect_request_id: str, mutation_status: str, evidence: Any
    ) -> PositionEffectResult:
        del evidence
        if mutation_status != "UNKNOWN":
            raise PositionEffectError("only ambiguous local mutation is supported")
        return PositionEffectResult(
            "unknown", "OUTCOME_UNKNOWN", Decimal("0"), Decimal("0"), Decimal("0"),
            "OUTCOME_UNKNOWN", effect_request_id, "unknown",
        )

    def _record(self, result: PositionEffectResult) -> None:
        self._request_results[result.effect_request_id] = result
        self._history.setdefault(result.position_id, []).append(result)

    def _apply_open_persistent(
        self, *, cursor: Any, position_id: str, intended_quantity: Any,
        receipt: Mapping[str, Any], intent_id: str, symbol: str,
        effect_request_id: str, external_order_id: Optional[str],
        binding: Mapping[str, Any],
    ) -> PositionEffectResult:
        existing = self._persistent_result(cursor, effect_request_id)
        if existing is not None:
            return existing
        quantity = self._receipt_quantity(receipt)
        intended = self._decimal(intended_quantity, "intended_quantity")
        if quantity <= 0 or intended <= 0:
            raise PositionEffectError("OPEN requires positive quantity")
        self._validate_receipt_order(receipt, external_order_id)
        extent = self._extent_identity(receipt)
        metadata = self._persistent_metadata(cursor, effect_request_id, binding)
        receipt_id = self._persist_receipt(cursor, receipt, effect_request_id, extent)
        cursor.execute(
            """
            INSERT INTO handa_live.position
            (position_id, intent_id, symbol, lifecycle_state, current_quantity,
             open_effect_request_id, position_lifecycle_version)
            VALUES (%s, %s, %s, 'ACTIVE', %s, %s, 1)
            """,
            (position_id, intent_id, symbol, quantity, effect_request_id),
        )
        self._persist_event(
            cursor, position_id=position_id, intent_id=intent_id,
            effect_type="OPEN", effect_request_id=effect_request_id,
            application_attempt_id=metadata["application_attempt_id"],
            receipt=receipt, receipt_id=receipt_id, extent=extent,
            previous=Decimal("0"), applied=quantity, resulting=quantity,
            metadata=metadata,
        )
        return PositionEffectResult(
            position_id, "OPEN", Decimal("0"), quantity, quantity, "ACTIVE",
            effect_request_id, extent,
        )

    def _apply_reduction_persistent(
        self, *, cursor: Any, position_id: str, applied_quantity: Any,
        receipt: Mapping[str, Any], effect_request_id: str,
        binding: Mapping[str, Any],
    ) -> PositionEffectResult:
        existing = self._persistent_result(cursor, effect_request_id)
        if existing is not None:
            return existing
        cursor.execute(
            """
            SELECT intent_id, symbol, lifecycle_state, current_quantity,
                   position_lifecycle_version
            FROM handa_live.position
            WHERE position_id=%s
            FOR UPDATE
            """,
            (position_id,),
        )
        row = cursor.fetchone()
        if row is None or row[2] != "ACTIVE":
            raise PositionEffectError("active position is required")
        intent_id, symbol, state, previous, version = row
        previous = self._decimal(previous, "current_quantity")
        applied = self._decimal(applied_quantity, "applied_quantity")
        if applied <= 0 or applied >= previous:
            raise PositionEffectError("REDUCE must leave positive residual")
        receipt_quantity = self._receipt_quantity(receipt)
        if receipt_quantity != applied:
            raise PositionEffectError("receipt extent does not match reduction")
        extent = self._extent_identity(receipt)
        metadata = self._persistent_metadata(cursor, effect_request_id, binding)
        receipt_id = self._persist_receipt(cursor, receipt, effect_request_id, extent)
        resulting = previous - applied
        self._persist_event(
            cursor, position_id=position_id, intent_id=intent_id,
            effect_type="REDUCE", effect_request_id=effect_request_id,
            application_attempt_id=metadata["application_attempt_id"],
            receipt=receipt, receipt_id=receipt_id, extent=extent,
            previous=previous, applied=applied, resulting=resulting,
            metadata=metadata,
        )
        cursor.execute(
            """
            UPDATE handa_live.position
            SET current_quantity=%s, position_lifecycle_version=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE position_id=%s
            """,
            (resulting, version + 1, position_id),
        )
        return PositionEffectResult(
            position_id, "REDUCE", previous, applied, resulting, state,
            effect_request_id, extent,
        )

    def _apply_close_persistent(
        self, *, cursor: Any, position_id: str, receipt: Mapping[str, Any],
        effect_request_id: str, outcome: str, binding: Mapping[str, Any],
    ) -> PositionEffectResult:
        existing = self._persistent_result(cursor, effect_request_id)
        if existing is not None:
            return existing
        if outcome == "OUTCOME_UNKNOWN":
            raise PositionEffectError("UNKNOWN outcome cannot close position")
        cursor.execute(
            """
            SELECT intent_id, lifecycle_state, current_quantity,
                   position_lifecycle_version
            FROM handa_live.position
            WHERE position_id=%s
            FOR UPDATE
            """,
            (position_id,),
        )
        row = cursor.fetchone()
        if row is None or row[1] != "ACTIVE":
            raise PositionEffectError("active position is required")
        intent_id, state, previous, version = row
        previous = self._decimal(previous, "current_quantity")
        applied = self._receipt_quantity(receipt)
        if applied != previous:
            raise PositionEffectError("CLOSE requires full residual extent")
        extent = self._extent_identity(receipt)
        metadata = self._persistent_metadata(cursor, effect_request_id, binding)
        receipt_id = self._persist_receipt(cursor, receipt, effect_request_id, extent)
        self._persist_event(
            cursor, position_id=position_id, intent_id=intent_id,
            effect_type="CLOSE", effect_request_id=effect_request_id,
            application_attempt_id=metadata["application_attempt_id"],
            receipt=receipt, receipt_id=receipt_id, extent=extent,
            previous=previous, applied=applied, resulting=Decimal("0"),
            metadata=metadata,
        )
        cursor.execute(
            """
            UPDATE handa_live.position
            SET lifecycle_state='CLOSED', current_quantity=0,
                position_lifecycle_version=%s, updated_at=CURRENT_TIMESTAMP
            WHERE position_id=%s
            """,
            (version + 1, position_id),
        )
        return PositionEffectResult(
            position_id, "CLOSE", previous, applied, Decimal("0"), "CLOSED",
            effect_request_id, extent,
        )

    @staticmethod
    def _persistent_result(cursor: Any, effect_request_id: str) -> Optional[PositionEffectResult]:
        cursor.execute(
            """
            SELECT position_id, effect_type, previous_quantity, applied_quantity,
                   resulting_quantity, CASE WHEN resulting_quantity = 0
                       THEN 'CLOSED' ELSE 'ACTIVE' END,
                   effect_request_id, execution_extent_identity
            FROM handa_live.position_effect_event
            WHERE effect_request_id=%s
            """,
            (effect_request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return PositionEffectResult(
            row[0], row[1], Decimal(row[2]), Decimal(row[3]), Decimal(row[4]),
            row[5], row[6], row[7],
        )

    @staticmethod
    def _persistent_metadata(cursor: Any, effect_request_id: str, binding: Mapping[str, Any]):
        cursor.execute(
            """
            SELECT er.current_attempt_id, er.reconciliation_context_id,
                   ab.authority_decision_id, ab.decision_sequence,
                   ab.authority_contract_version
            FROM handa_live.effect_request er
            JOIN handa_live.authority_binding ab
              ON ab.effect_request_id = er.effect_request_id
            WHERE er.effect_request_id=%s
            FOR UPDATE OF er
            """,
            (effect_request_id,),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            raise PositionEffectError("application attempt is required")
        return {
            "application_attempt_id": row[0],
            "reconciliation_context_id": binding.get("reconciliation_context_id", row[1]),
            "semantic_decision_id": binding.get("semantic_decision_id", row[2]),
            "decision_sequence": binding.get("decision_sequence", row[3]),
            "authority_contract_version": binding.get("authority_contract_version", row[4]),
        }

    @classmethod
    def _persist_receipt(cls, cursor, receipt, effect_request_id, extent):
        receipt_id = str(receipt.get("receipt_id") or f"position-receipt-{effect_request_id}")
        payload = json.dumps(dict(receipt), sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        cursor.execute(
            """
            INSERT INTO handa_live.position_receipt
            (receipt_id, external_order_identity, execution_extent_identity,
             executed_base_quantity, executed_quote_quantity, weighted_price,
             external_status, receipt_payload, receipt_digest, normalization_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                receipt_id, str(receipt["order_id"]), extent,
                cls._receipt_quantity(receipt), receipt.get("executed_quote_qty"),
                receipt.get("weighted_price"), str(receipt.get("status", "UNKNOWN")),
                Json(dict(receipt), dumps=lambda value: json.dumps(value, default=str)),
                digest, str(receipt.get("normalization_version", "1")),
            ),
        )
        return receipt_id

    @staticmethod
    def _persist_event(
        cursor, *, position_id, intent_id, effect_type, effect_request_id,
        application_attempt_id, receipt, receipt_id, extent, previous, applied,
        resulting, metadata,
    ):
        cursor.execute(
            """
            SELECT COALESCE(MAX(event_sequence), 0) + 1
            FROM handa_live.position_effect_event
            WHERE position_id=%s
            """,
            (position_id,),
        )
        event_sequence = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO handa_live.position_effect_event
            (position_id, intent_id, effect_type, effect_request_id,
             application_attempt_id, external_order_identity,
             execution_extent_identity, receipt_id, previous_quantity,
             applied_quantity, resulting_quantity, event_sequence,
             reconciliation_context_id, semantic_decision_id, decision_sequence,
             authority_contract_version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                position_id, intent_id, effect_type, effect_request_id,
                application_attempt_id, str(receipt["order_id"]), extent,
                receipt_id, previous, applied, resulting, event_sequence,
                metadata["reconciliation_context_id"], metadata["semantic_decision_id"],
                metadata["decision_sequence"], metadata["authority_contract_version"],
            ),
        )

    def _claim_extent(self, extent: str) -> None:
        if extent in self._consumed_extents:
            raise PositionEffectError("execution extent was already consumed")
        self._consumed_extents[extent] = PositionEffectResult(
            "", "", Decimal("0"), Decimal("0"), Decimal("0"), "", "", extent
        )

    @staticmethod
    def _decimal(value: Any, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise PositionEffectError(f"{field} must be a valid decimal") from exc
        if not result.is_finite():
            raise PositionEffectError(f"{field} must be finite")
        return result

    @classmethod
    def _receipt_quantity(cls, receipt: Mapping[str, Any]) -> Decimal:
        if receipt.get("status") == "UNKNOWN":
            raise PositionEffectError("execution extent is unknown")
        value = receipt.get("executed_base_qty")
        return cls._decimal(value, "executed_base_qty")

    @staticmethod
    def _validate_receipt_order(receipt: Mapping[str, Any], external_order_id: Optional[str]) -> None:
        if external_order_id is not None and str(receipt.get("order_id")) != str(external_order_id):
            raise PositionEffectError("receipt order identity does not match effect")

    @staticmethod
    def _extent_identity(receipt: Mapping[str, Any]) -> str:
        order_id = receipt.get("order_id")
        fills = receipt.get("fills", ())
        if not order_id or not isinstance(fills, (list, tuple)):
            raise PositionEffectError("execution extent identity is incomplete")
        payload = json.dumps(
            {"order_id": str(order_id), "fills": fills},
            sort_keys=True, separators=(",", ":"), default=str,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
