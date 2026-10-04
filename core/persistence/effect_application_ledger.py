"""Durable, non-operational Effect Application Ledger foundation."""

from __future__ import annotations

import hashlib
import json
import base64
from datetime import datetime, timezone
from uuid import uuid4
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Optional

from psycopg2.extras import Json
from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from core.execution.operational_effect_adapter import (
    EffectType,
    LogicalBindingLookupDisposition,
    LogicalBindingLookupResult,
    LogicalEffectBinding,
    LogicalEffectIdentity,
)


SCHEMA = "handa_live"
CAPABILITY_FIELDS = {
    "issuer_id", "key_id", "issuer_epoch", "subject_id",
    "effect_request_id", "application_attempt_id", "allowed_classification",
    "recovery_policy_version", "evidence_digest", "issued_at", "expires_at",
    "nonce", "signature",
}
RECOVERY_CLASSIFICATIONS = {"APPLIED", "FAILED_WITHOUT_EFFECT", "OUTCOME_UNKNOWN"}


class EffectApplicationLedgerError(RuntimeError):
    """Raised when a ledger contract transition is invalid."""


@dataclass(frozen=True)
class ApplicationState:
    effect_request_id: str
    state: str
    applied_effect_id: Optional[str] = None
    application_attempt_id: Optional[str] = None


class EffectApplicationLedger:
    """Own only durable ledger state; never performs an operational effect."""

    def __init__(self, connection: Any, trusted_issuers: Optional[Mapping[str, Mapping[str, Any]]] = None):
        self._connection = connection
        self._connection.autocommit = False
        self._trusted_issuers = dict(trusted_issuers or {})

    @contextmanager
    def _transaction(self) -> Iterator[Any]:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute("BEGIN")
                yield cursor
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            raise

    @contextmanager
    def transaction_scope(self) -> Iterator[Any]:
        """Expose the ledger's transaction boundary to a domain coordinator."""
        with self._transaction() as cursor:
            yield cursor

    @contextmanager
    def _transaction_or_cursor(self, shared_cursor: Any = None) -> Iterator[Any]:
        if shared_cursor is not None:
            with nullcontext(shared_cursor) as cursor:
                yield cursor
            return
        with self._transaction() as cursor:
            yield cursor

    def create_effect_request(
        self,
        *,
        effect_request_id: str,
        effect_type: str,
        intent_id: str,
        reconciliation_context_id: str,
        authority_decision_id: str,
        decision_sequence: int,
        authority_contract_version: str,
    ) -> ApplicationState:
        with self._transaction() as cursor:
            self._validate_authority_binding(
                cursor,
                intent_id,
                reconciliation_context_id,
                authority_decision_id,
                decision_sequence,
            )
            try:
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.effect_request
                    (effect_request_id, effect_type, intent_id,
                     reconciliation_context_id, current_state)
                    VALUES (%s, %s, %s, %s, 'AUTHORIZED')
                    """,
                    (effect_request_id, effect_type, intent_id, reconciliation_context_id),
                )
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.authority_binding
                    (effect_request_id, authority_decision_id, intent_id,
                     reconciliation_context_id, decision_sequence,
                     authority_contract_version)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        effect_request_id,
                        authority_decision_id,
                        intent_id,
                        reconciliation_context_id,
                        decision_sequence,
                        authority_contract_version,
                    ),
                )
                self._event(
                    cursor,
                    effect_request_id,
                    None,
                    "AUTHORIZED",
                    "AUTHORITY_ACCEPTED",
                    "effect authority accepted",
                    None,
                    None,
                )
            except Exception as exc:
                raise EffectApplicationLedgerError(
                    "effect request creation rejected"
                ) from exc
        return self.get_effect_request(effect_request_id)

    def claim_application(
        self,
        effect_request_id: str,
        *,
        application_attempt_id: str,
        claimant_id: str = "worker",
        cursor: Any = None,
    ) -> ApplicationState:
        with self._transaction_or_cursor(cursor) as transaction_cursor:
            request = self._locked_request(transaction_cursor, effect_request_id)
            if request["current_state"] != "AUTHORIZED":
                raise EffectApplicationLedgerError("request is not claimable")
            binding = self._binding(transaction_cursor, effect_request_id)
            self._validate_freshness(transaction_cursor, request, binding)
            transaction_cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.application_attempt
                (application_attempt_id, effect_request_id, attempt_state,
                 claimant_id)
                VALUES (%s, %s, 'APPLYING', %s)
                """,
                (application_attempt_id, effect_request_id, claimant_id),
            )
            transaction_cursor.execute(
                f"""
                SELECT 1
                """
            )
            self._event(
                transaction_cursor,
                effect_request_id,
                "AUTHORIZED",
                "APPLYING",
                "CLAIMED",
                "application claim",
                application_attempt_id,
                None,
            )
            transaction_cursor.execute(
                f"""
                UPDATE {SCHEMA}.effect_request
                SET current_state='APPLYING', current_attempt_id=%s,
                    updated_at=CURRENT_TIMESTAMP
                WHERE effect_request_id=%s
                """,
                (application_attempt_id, effect_request_id),
            )
            if cursor is not None:
                return self._application_state_from_cursor(transaction_cursor, effect_request_id)
        return self.get_application_state(effect_request_id)

    def mark_applied(
        self,
        effect_request_id: str,
        *,
        application_attempt_id: str,
        receipt: Mapping[str, Any],
        evidence_ids: Iterable[str] = (),
        cursor: Any = None,
    ) -> ApplicationState:
        application_boundary_reached = False
        try:
            with self._transaction_or_cursor(cursor) as transaction_cursor:
                request = self._locked_request(transaction_cursor, effect_request_id)
                self._require_attempt(request, application_attempt_id, "APPLYING")
                receipt_id, payload_hash = self._receipt_fields(receipt)
                applied_effect_id = uuid4().hex
                transaction_cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.applied_effect
                    (applied_effect_id, effect_request_id,
                     application_attempt_id, receipt_id, receipt_schema_version,
                     producer_id, payload_hash, receipt_payload, evidence_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        applied_effect_id,
                        effect_request_id,
                        application_attempt_id,
                        receipt_id,
                        str(receipt["schema_version"]),
                        str(receipt["producer_id"]),
                        payload_hash,
                        Json(dict(receipt["payload"])),
                        list(evidence_ids),
                    ),
                )
                application_boundary_reached = True
                self._finish(
                    transaction_cursor,
                    effect_request_id,
                    application_attempt_id,
                    "APPLIED",
                    "application applied",
                )
                if cursor is not None:
                    return self._application_state_from_cursor(transaction_cursor, effect_request_id)
        except Exception as exc:
            if application_boundary_reached and cursor is None:
                self._record_outcome_unknown_after_boundary(
                    effect_request_id,
                    application_attempt_id,
                    "application boundary failed before durable APPLIED projection",
                )
                raise EffectApplicationLedgerError(
                    "application outcome is unknown"
                ) from exc
            raise
        return self.get_application_state(effect_request_id)

    def mark_failed_without_effect(
        self,
        effect_request_id: str,
        *,
        application_attempt_id: str,
        evidence: Iterable[Mapping[str, Any]],
        reason: str = "positive non-mutation proof",
    ) -> ApplicationState:
        evidence = tuple(evidence)
        self._require_nonmutation_evidence(evidence)
        with self._transaction() as cursor:
            request = self._locked_request(cursor, effect_request_id)
            self._require_attempt(request, application_attempt_id, "APPLYING")
            self._finish(
                cursor,
                effect_request_id,
                application_attempt_id,
                "FAILED_WITHOUT_EFFECT",
                reason,
                evidence=evidence,
            )
        return self.get_application_state(effect_request_id)

    def mark_outcome_unknown(
        self,
        effect_request_id: str,
        *,
        application_attempt_id: str,
        reason: str,
        evidence: Iterable[Mapping[str, Any]] = (),
    ) -> ApplicationState:
        with self._transaction() as cursor:
            request = self._locked_request(cursor, effect_request_id)
            self._require_attempt(request, application_attempt_id, "APPLYING")
            self._finish(
                cursor,
                effect_request_id,
                application_attempt_id,
                "OUTCOME_UNKNOWN",
                reason,
                evidence=tuple(evidence),
            )
        return self.get_application_state(effect_request_id)

    def recover_application(
        self,
        effect_request_id: str,
        *,
        recovery_authority_id: str,
        recovery_policy_version: str,
        classification: str,
        evidence: Iterable[Mapping[str, Any]],
        receipt: Optional[Mapping[str, Any]] = None,
        application_attempt_id: Optional[str] = None,
        recovery_capability: Optional[Mapping[str, Any]] = None,
        recovery_subject_id: Optional[str] = None,
    ) -> ApplicationState:
        evidence = tuple(evidence)
        if not recovery_authority_id or not recovery_policy_version:
            raise EffectApplicationLedgerError("recovery authority is required")
        if classification not in RECOVERY_CLASSIFICATIONS:
            raise EffectApplicationLedgerError("invalid recovery classification")
        if not evidence:
            raise EffectApplicationLedgerError("recovery evidence is required")
        if classification == "APPLIED" and receipt is None:
            raise EffectApplicationLedgerError("applied recovery requires receipt")
        if classification == "FAILED_WITHOUT_EFFECT":
            self._require_nonmutation_evidence(evidence)
        with self._transaction() as cursor:
            request = self._locked_request(cursor, effect_request_id)
            if request["current_state"] != "OUTCOME_UNKNOWN":
                raise EffectApplicationLedgerError("request is not recoverable")
            previous = request["current_state"]
            attempt_id = application_attempt_id or request["current_attempt_id"]
            issuer_id, policy_version = self._validate_recovery_capability(
                cursor,
                request,
                attempt_id,
                classification,
                evidence,
                recovery_capability,
                recovery_subject_id,
            )
            self._consume_capability(cursor, recovery_capability)
            if classification == "APPLIED":
                receipt_id, payload_hash = self._receipt_fields(receipt)
                cursor.execute(
                    f"""
                    INSERT INTO {SCHEMA}.applied_effect
                    (applied_effect_id, effect_request_id,
                     application_attempt_id, receipt_id, receipt_schema_version,
                     producer_id, payload_hash, receipt_payload, evidence_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4().hex,
                        effect_request_id,
                        attempt_id,
                        receipt_id,
                        str(receipt["schema_version"]),
                        str(receipt["producer_id"]),
                        payload_hash,
                        Json(dict(receipt["payload"])),
                        [item.get("evidence_id") for item in evidence],
                    ),
                )
            if attempt_id is not None:
                cursor.execute(
                    f"""
                    UPDATE {SCHEMA}.application_attempt
                    SET attempt_state=%s, completed_at=CURRENT_TIMESTAMP
                    WHERE application_attempt_id=%s
                      AND effect_request_id=%s
                    """,
                    (classification, attempt_id, effect_request_id),
                )
            self._event(
                cursor,
                effect_request_id,
                previous,
                classification,
                "RECOVERY",
                "recovery classification",
                attempt_id,
                issuer_id,
                policy_version,
                evidence,
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.effect_request
                SET current_state=%s, updated_at=CURRENT_TIMESTAMP
                WHERE effect_request_id=%s
                """,
                (classification, effect_request_id),
            )
        return self.get_application_state(effect_request_id)

    def get_effect_request(self, effect_request_id: str) -> ApplicationState:
        return self.get_application_state(effect_request_id)

    @contextmanager
    def _read_cursor(self, cursor: Any = None) -> Iterator[Any]:
        if cursor is not None:
            with nullcontext(cursor) as read_cursor:
                yield read_cursor
            return
        with self._connection.cursor() as read_cursor:
            try:
                yield read_cursor
            finally:
                self._connection.rollback()

    def lookup_logical_binding(
        self,
        *,
        logical_identity: LogicalEffectIdentity,
        effect_type: EffectType,
        authority_decision_id: str,
        reconciliation_context_id: str,
        decision_sequence: int,
        authority_contract_version: str,
        cursor: Any = None,
    ) -> LogicalBindingLookupResult:
        """Read the canonical binding evidence for one logical effect."""

        with self._read_cursor(cursor) as read_cursor:
            read_cursor.execute(
                f"""
                SELECT er.effect_request_id,
                       er.intent_id,
                       er.logical_effect_id,
                       er.effect_type,
                       er.reconciliation_context_id,
                       ab.authority_decision_id,
                       ab.intent_id,
                       ab.reconciliation_context_id,
                       ab.decision_sequence,
                       ab.authority_contract_version
                FROM {SCHEMA}.effect_request er
                LEFT JOIN {SCHEMA}.authority_binding ab
                  ON ab.effect_request_id = er.effect_request_id
                WHERE er.intent_id=%s
                  AND er.logical_effect_id=%s
                """,
                (
                    logical_identity.intent_id,
                    logical_identity.logical_effect_id,
                ),
            )
            row = read_cursor.fetchone()

        if row is None:
            return LogicalBindingLookupResult(
                disposition=LogicalBindingLookupDisposition.NOT_FOUND,
                binding=None,
            )

        if row[5] is None:
            raise EffectApplicationLedgerError(
                "authority binding is missing for logical effect"
            )

        if row[1] != row[6] or row[4] != row[7]:
            raise EffectApplicationLedgerError(
                "DURABLE_DATA_CONTRADICTION: duplicated logical binding fields disagree"
            )

        try:
            stored_effect_type = EffectType(row[3])
        except ValueError as exc:
            raise EffectApplicationLedgerError(
                "logical binding effect type is outside the governed vocabulary"
            ) from exc

        binding = LogicalEffectBinding(
            logical_identity=LogicalEffectIdentity(row[1], row[2]),
            effect_request_id=row[0],
            effect_type=stored_effect_type,
            authority_decision_id=row[5],
            reconciliation_context_id=row[7],
            decision_sequence=row[8],
            authority_contract_version=row[9],
        )
        expected_effect_type = EffectType(effect_type)
        matches = (
            binding.logical_identity == logical_identity
            and binding.effect_type is expected_effect_type
            and binding.authority_decision_id == authority_decision_id
            and binding.reconciliation_context_id == reconciliation_context_id
            and binding.decision_sequence == decision_sequence
            and binding.authority_contract_version == authority_contract_version
        )
        disposition = (
            LogicalBindingLookupDisposition.FOUND_VALID_BINDING
            if matches
            else LogicalBindingLookupDisposition.FOUND_CONFLICTING_BINDING
        )
        return LogicalBindingLookupResult(disposition=disposition, binding=binding)

    def get_application_state(self, effect_request_id: str) -> ApplicationState:
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT effect_request_id, current_state,
                           current_attempt_id,
                           (SELECT applied_effect_id FROM {SCHEMA}.applied_effect a
                            WHERE a.effect_request_id=e.effect_request_id)
                    FROM {SCHEMA}.effect_request e
                    WHERE effect_request_id=%s
                    """,
                    (effect_request_id,),
                )
                row = cursor.fetchone()
        finally:
            self._connection.rollback()
        if row is None:
            raise EffectApplicationLedgerError("effect request does not exist")
        return ApplicationState(row[0], row[1], row[3], row[2])

    @staticmethod
    def _application_state_from_cursor(cursor: Any, effect_request_id: str) -> ApplicationState:
        cursor.execute(
            f"""
            SELECT effect_request_id, current_state, current_attempt_id,
                   (SELECT applied_effect_id FROM {SCHEMA}.applied_effect a
                    WHERE a.effect_request_id=e.effect_request_id)
            FROM {SCHEMA}.effect_request e
            WHERE effect_request_id=%s
            """,
            (effect_request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise EffectApplicationLedgerError("effect request does not exist")
        return ApplicationState(row[0], row[1], row[3], row[2])

    def _locked_request(self, cursor: Any, effect_request_id: str) -> Mapping[str, Any]:
        cursor.execute(
            f"""
            SELECT effect_request_id, intent_id, reconciliation_context_id,
                   current_state, current_attempt_id
            FROM {SCHEMA}.effect_request
            WHERE effect_request_id=%s
            FOR UPDATE
            """,
            (effect_request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise EffectApplicationLedgerError("effect request does not exist")
        return dict(zip(
            ("effect_request_id", "intent_id", "reconciliation_context_id",
             "current_state", "current_attempt_id"), row
        ))

    def _binding(self, cursor: Any, effect_request_id: str) -> Mapping[str, Any]:
        cursor.execute(
            f"""
            SELECT authority_decision_id, intent_id, reconciliation_context_id,
                   decision_sequence, authority_contract_version
            FROM {SCHEMA}.authority_binding
            WHERE effect_request_id=%s
            """,
            (effect_request_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise EffectApplicationLedgerError("authority binding is missing")
        return dict(zip(
            ("authority_decision_id", "intent_id", "reconciliation_context_id",
             "decision_sequence", "authority_contract_version"), row
        ))

    @staticmethod
    def _validate_authority_binding(
        cursor: Any,
        intent_id: str,
        context_id: str,
        decision_id: str,
        decision_sequence: int,
    ) -> None:
        cursor.execute(
            f"""
            SELECT 1 FROM {SCHEMA}.semantic_decision
            WHERE decision_id=%s AND intent_id=%s AND context_id=%s
              AND decision_sequence=%s
            """,
            (decision_id, intent_id, context_id, decision_sequence),
        )
        if cursor.fetchone() is None:
            raise EffectApplicationLedgerError("authority identity is invalid")

    @staticmethod
    def _validate_freshness(cursor: Any, request: Mapping[str, Any], binding: Mapping[str, Any]) -> None:
        cursor.execute(
            f"""
            SELECT current_decision_id FROM {SCHEMA}.order_intent
            WHERE intent_id=%s
            """,
            (request["intent_id"],),
        )
        row = cursor.fetchone()
        if row is not None and row[0] not in (None, binding["authority_decision_id"]):
            raise EffectApplicationLedgerError("stale authority decision")
        cursor.execute(
            f"""
            SELECT 1 FROM {SCHEMA}.semantic_decision
            WHERE context_id=%s AND intent_id=%s
              AND decision_sequence>%s
              AND (authority_state='BLOCKED' OR contradiction_result IS NOT NULL)
            LIMIT 1
            """,
            (
                binding["reconciliation_context_id"],
                binding["intent_id"],
                binding["decision_sequence"],
            ),
        )
        if cursor.fetchone() is not None:
            raise EffectApplicationLedgerError("later contradiction blocks claim")
        cursor.execute(
            f"""
            SELECT 1 FROM {SCHEMA}.semantic_decision
            WHERE context_id=%s AND intent_id=%s
              AND decision_sequence>%s
            LIMIT 1
            """,
            (
                binding["reconciliation_context_id"],
                binding["intent_id"],
                binding["decision_sequence"],
            ),
        )
        if cursor.fetchone() is not None:
            raise EffectApplicationLedgerError("newer semantic decision invalidates claim")

    @staticmethod
    def _require_attempt(request: Mapping[str, Any], attempt_id: str, state: str) -> None:
        if request["current_state"] != state or request["current_attempt_id"] != attempt_id:
            raise EffectApplicationLedgerError("application attempt is not current")

    @staticmethod
    def _require_nonmutation_evidence(evidence: Iterable[Mapping[str, Any]]) -> None:
        values = tuple(evidence)
        valid = {"TRANSACTION_ROLLBACK", "NO_CALL_STARTED", "AUTHORITATIVE_NO_EFFECT"}
        if not values or any(item.get("proof_type") not in valid for item in values):
            raise EffectApplicationLedgerError("positive non-mutation proof is required")

    def _validate_recovery_capability(
        self,
        cursor: Any,
        request: Mapping[str, Any],
        attempt_id: str,
        classification: str,
        evidence: Iterable[Mapping[str, Any]],
        capability: Optional[Mapping[str, Any]],
        recovery_subject_id: Optional[str],
    ) -> tuple[str, str]:
        if capability is None or set(capability) != CAPABILITY_FIELDS:
            raise EffectApplicationLedgerError("recovery capability is required")
        values = dict(capability)
        issuer = self._trusted_issuers.get(values["issuer_id"])
        if issuer is None:
            raise EffectApplicationLedgerError("unknown recovery issuer")
        if issuer.get("key_id") != values["key_id"]:
            raise EffectApplicationLedgerError("issuer/key binding is invalid")
        if values["issuer_epoch"] != issuer.get("issuer_epoch") or values["issuer_epoch"] in set(issuer.get("revoked_epochs", ())):
            raise EffectApplicationLedgerError("recovery issuer epoch is revoked or stale")
        if values["subject_id"] not in set(issuer.get("subjects", ())):
            raise EffectApplicationLedgerError("recovery subject is not governed")
        if recovery_subject_id != values["subject_id"]:
            raise EffectApplicationLedgerError("recovery subject binding is invalid")
        if values["effect_request_id"] != request["effect_request_id"]:
            raise EffectApplicationLedgerError("recovery request binding is invalid")
        if values["application_attempt_id"] != attempt_id:
            raise EffectApplicationLedgerError("recovery attempt binding is invalid")
        if values["allowed_classification"] != classification:
            raise EffectApplicationLedgerError("recovery classification is not allowed")
        policy_version = values["recovery_policy_version"]
        if policy_version not in set(issuer.get("policy_versions", ())):
            raise EffectApplicationLedgerError("recovery policy version is invalid")
        evidence_payload = self._canonical_json(list(evidence))
        expected_digest = hashlib.sha256(evidence_payload).hexdigest()
        if values["evidence_digest"] != expected_digest:
            raise EffectApplicationLedgerError("recovery evidence digest mismatch")
        now = datetime.now(timezone.utc)
        issued_at = self._parse_timestamp(values["issued_at"])
        expires_at = self._parse_timestamp(values["expires_at"])
        if not issued_at <= now < expires_at:
            raise EffectApplicationLedgerError("recovery capability is outside its validity window")
        try:
            public_key = ECC.import_key(base64.b64decode(issuer["public_key"]))
            verifier = eddsa.new(public_key, "rfc8032")
            verifier.verify(self._canonical_capability_payload(values), base64.b64decode(values["signature"]))
        except Exception as exc:
            raise EffectApplicationLedgerError("recovery capability signature is invalid") from exc
        return values["issuer_id"], policy_version

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if not isinstance(value, str):
            raise EffectApplicationLedgerError("recovery capability timestamp is invalid")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise EffectApplicationLedgerError("recovery capability timestamp is invalid") from exc
        if parsed.tzinfo is None:
            raise EffectApplicationLedgerError("recovery capability timestamp must be timezone-aware")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _canonical_json(value: Any) -> bytes:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")

    @classmethod
    def _canonical_capability_payload(cls, capability: Mapping[str, Any]) -> bytes:
        return cls._canonical_json({key: capability[key] for key in sorted(CAPABILITY_FIELDS - {"signature"})})

    @staticmethod
    def _consume_capability(cursor: Any, capability: Mapping[str, Any]) -> None:
        try:
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.recovery_capability_consumption
                (issuer_id, key_id, issuer_epoch, nonce,
                 effect_request_id, application_attempt_id)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    capability["issuer_id"], capability["key_id"],
                    capability["issuer_epoch"], capability["nonce"],
                    capability["effect_request_id"], capability["application_attempt_id"],
                ),
            )
        except Exception as exc:
            raise EffectApplicationLedgerError("recovery capability was already consumed") from exc

    @staticmethod
    def _receipt_fields(receipt: Mapping[str, Any]) -> tuple[str, str]:
        required = {"receipt_id", "schema_version", "producer_id", "payload"}
        if not required <= set(receipt):
            raise EffectApplicationLedgerError("receipt identity is incomplete")
        payload = json.dumps(receipt["payload"], sort_keys=True, separators=(",", ":"))
        return str(receipt["receipt_id"]), hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _event(
        cursor: Any,
        effect_request_id: str,
        previous_state: Optional[str],
        next_state: Optional[str],
        event_kind: str,
        reason: str,
        attempt_id: Optional[str],
        recovery_authority_id: Optional[str],
        recovery_policy_version: Optional[str] = None,
        evidence: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        cursor.execute(
            f"""
            SELECT COALESCE(MAX(event_sequence), 0) + 1
            FROM {SCHEMA}.lifecycle_event
            WHERE effect_request_id=%s
            """,
            (effect_request_id,),
        )
        event_sequence = cursor.fetchone()[0]
        cursor.execute(
            f"""
            INSERT INTO {SCHEMA}.lifecycle_event
            (effect_request_id, event_sequence, previous_state, next_state, event_kind,
             reason, application_attempt_id, recovery_authority_id,
             recovery_policy_version, evidence_ids)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                effect_request_id,
                event_sequence,
                previous_state,
                next_state,
                event_kind,
                reason,
                attempt_id,
                recovery_authority_id,
                recovery_policy_version,
                [item.get("evidence_id") for item in evidence],
            ),
        )
        if recovery_authority_id is not None:
            cursor.execute(
                f"""
                INSERT INTO {SCHEMA}.recovery_event
                (effect_request_id, application_attempt_id,
                 previous_state, resulting_state, recovery_authority_id,
                 recovery_policy_version, evidence_ids, reason)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    effect_request_id,
                    attempt_id,
                    previous_state,
                    next_state,
                    recovery_authority_id,
                    recovery_policy_version,
                    [item.get("evidence_id") for item in evidence],
                    reason,
                ),
            )

    def _finish(
        self,
        cursor: Any,
        effect_request_id: str,
        attempt_id: str,
        state: str,
        reason: str,
        evidence: Iterable[Mapping[str, Any]] = (),
    ) -> None:
        cursor.execute(
            f"""
            UPDATE {SCHEMA}.application_attempt
            SET attempt_state=%s, completed_at=CURRENT_TIMESTAMP
            WHERE application_attempt_id=%s AND effect_request_id=%s
            """,
            (state, attempt_id, effect_request_id),
        )
        self._event(
            cursor,
            effect_request_id,
            "APPLYING",
            state,
            state,
            reason,
            attempt_id,
            None,
            evidence=evidence,
        )
        cursor.execute(
            f"""
            UPDATE {SCHEMA}.effect_request
            SET current_state=%s, updated_at=CURRENT_TIMESTAMP
            WHERE effect_request_id=%s
            """,
            (state, effect_request_id),
        )

    def _record_outcome_unknown_after_boundary(
        self, effect_request_id: str, attempt_id: str, reason: str
    ) -> None:
        with self._transaction() as cursor:
            request = self._locked_request(cursor, effect_request_id)
            if request["current_state"] != "APPLYING":
                return
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.application_attempt
                SET attempt_state='OUTCOME_UNKNOWN', completed_at=CURRENT_TIMESTAMP
                WHERE application_attempt_id=%s AND effect_request_id=%s
                """,
                (attempt_id, effect_request_id),
            )
            self._event(
                cursor,
                effect_request_id,
                "APPLYING",
                "OUTCOME_UNKNOWN",
                "OUTCOME_UNKNOWN",
                reason,
                attempt_id,
                None,
                evidence=({"evidence_id": attempt_id, "proof_type": "APPLICATION_BOUNDARY_UNCERTAIN"},),
            )
            cursor.execute(
                f"""
                UPDATE {SCHEMA}.effect_request
                SET current_state='OUTCOME_UNKNOWN', updated_at=CURRENT_TIMESTAMP
                WHERE effect_request_id=%s
                """,
                (effect_request_id,),
            )
