from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from plainweave.bindings import SeiBinding
from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.intent_graph import (
    DEFAULT_INTENT_COVERAGE_EXCLUDED_NAMESPACES,
    CorpusEntry,
    IntentCoverage,
    IntentCoverageSurface,
    IntentLevel,
    IntentNode,
    Trace,
)
from plainweave.loomweave_adapter import (
    PUBLIC_SURFACE_TAGS,
    LoomweaveAdapter,
    LoomweaveCatalogEntity,
    LoomweaveIdentityError,
)
from plainweave.models import (
    AcceptanceCriterion,
    Actor,
    Baseline,
    BaselineDiff,
    BaselineDiffItem,
    BaselineMember,
    CodeEntity,
    DossierAcceptanceCriteriaSection,
    DossierAuthoritySummary,
    DossierBaselineExposure,
    DossierBaselineExposureItem,
    DossierComputedGap,
    DossierNextAction,
    DossierPeerFacts,
    DossierRequirementSection,
    DossierTraceSection,
    IntentEdge,
    IntentGoal,
    RequirementDossier,
    RequirementDraft,
    RequirementRecord,
    RequirementVerificationStatus,
    RequirementVersion,
    TraceLink,
    TraceRef,
    VerificationEvidence,
    VerificationMethod,
    VerificationReason,
)
from plainweave.store import connect, read_schema_meta


class PlainweaveService:
    #: Actor kinds permitted to record external/manual attestation authority
    #: (waiver, manual attestation, human-attested evidence). Authority is
    #: derived from the registered ``actors`` record, never from the raw actor
    #: string — a free-form ``--actor human:fake`` is not an attester unless it
    #: has been deliberately registered (an audited ``actor_registered`` event).
    ATTESTER_KINDS = frozenset({"human", "attester"})
    #: All kinds accepted by :meth:`register_actor`.
    ACTOR_KINDS = frozenset({"human", "agent", "attester"})

    def __init__(self, db_path: Path, *, root: Path | None = None) -> None:
        self.db_path = db_path
        self.root = root.resolve() if root is not None else db_path.parent.parent.resolve()

    def register_actor(
        self,
        actor_id: str,
        *,
        kind: str,
        display_name: str | None = None,
        actor: str,
    ) -> Actor:
        """Register (or update) an actor identity in the project registry.

        The registry is the source of truth for attestation authority. It is
        the trust boundary for this local-first store: registration is a
        deliberate, event-logged act, so promoting an actor to a human/attester
        kind leaves an auditable ``actor_registered`` trail rather than being an
        implicit claim smuggled into every evidence call. Registration is also
        the shared actor/owner surface other Weft tools (Filigree, Loomweave)
        bind to.
        """
        self._require_actor(actor)
        if not actor_id:
            raise self._error(ErrorCode.VALIDATION, "actor_id is required")
        if kind not in self.ACTOR_KINDS:
            raise self._error(
                ErrorCode.VALIDATION,
                f"actor kind must be one of {sorted(self.ACTOR_KINDS)}",
            )
        now = self._now()
        with connect(self.db_path) as connection:
            # A registration is privileged if it would *grant* attester authority
            # (target kind) or *modify an actor that already holds it* (so an
            # agent cannot neuter an attester by re-registering them as an agent).
            grants_authority = kind in self.ATTESTER_KINDS
            touches_attester = self._actor_kind(connection, actor_id) in self.ATTESTER_KINDS
            if grants_authority or touches_attester:
                # Privileged. Open only for the genesis grant (no attester exists
                # yet, bootstrap); after that, only an existing registered
                # attester may perform it — so an agent cannot mint a fake human
                # and then attest. Genesis itself is first-come and should be
                # performed out-of-band at project setup; the filesystem remains
                # the ultimate trust boundary.
                attester_exists = self._attester_exists(connection)
                registrant_is_attester = self._actor_kind(connection, actor) in self.ATTESTER_KINDS
                if attester_exists and not registrant_is_attester:
                    raise self._error(
                        ErrorCode.POLICY_REQUIRED,
                        "registering or modifying a human/attester actor requires an existing registered attester",
                    )
            connection.execute(
                """
                insert into actors(actor_id, kind, display_name)
                values (?, ?, ?)
                on conflict(actor_id) do update set
                  kind = excluded.kind,
                  display_name = excluded.display_name
                """,
                (actor_id, kind, display_name),
            )
            self._record_event(
                connection,
                "actor_registered",
                "actor",
                actor_id,
                actor,
                None,
                {"actor_id": actor_id, "kind": kind, "display_name": display_name},
                now,
            )
            connection.commit()
        return Actor(actor_id=actor_id, kind=kind, display_name=display_name)

    def add_verification_method(
        self,
        requirement_id: str,
        *,
        method: str,
        target: str,
        actor: str,
    ) -> VerificationMethod:
        self._require_actor(actor)
        self._validate_verification_method(method)
        if not target:
            raise self._error(ErrorCode.VALIDATION, "verification target is required")
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            if str(requirement["status"]) not in {"approved", "deprecated"} or int(requirement["current_version"]) <= 0:
                raise self._error(ErrorCode.POLICY_REQUIRED, "verification methods require an approved requirement")
            method_id = f"VERM-{self._next_verification_method_number(connection):04d}"
            connection.execute(
                """
                insert into verification_methods(
                  method_id, requirement_id, requirement_version, method_type,
                  target, status, created_by, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    method_id,
                    requirement["requirement_id"],
                    int(requirement["current_version"]),
                    method,
                    target,
                    "active",
                    actor,
                    now,
                ),
            )
            self._record_event(
                connection,
                "verification_method_added",
                "verification_method",
                method_id,
                actor,
                None,
                {"method_id": method_id, "requirement_id": requirement["display_id"], "method": method},
                now,
            )
            connection.commit()
            return self._verification_method_from_row(self._verification_method_row(connection, method_id))

    def record_verification_evidence(
        self,
        method_id: str,
        *,
        status: str,
        evidence_ref: str,
        actor: str,
        payload: dict[str, Any] | None = None,
    ) -> VerificationEvidence:
        self._require_actor(actor)
        self._validate_evidence_status(status)
        if not evidence_ref:
            raise self._error(ErrorCode.VALIDATION, "evidence reference is required")
        now = self._now()
        with connect(self.db_path) as connection:
            method = self._verification_method_row(connection, method_id)
            requirement = self._requirement_row(connection, str(method["requirement_id"]))
            authority = self._evidence_authority(connection, str(method["method_type"]), status, actor)
            evidence_id = f"EVID-{self._next_evidence_number(connection):04d}"
            current_version = int(requirement["current_version"])
            connection.execute(
                """
                insert into verification_evidence(
                  evidence_id, method_id, requirement_id, requirement_version,
                  status, evidence_ref, authority, freshness, recorded_by,
                  recorded_at, payload_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    method_id,
                    requirement["requirement_id"],
                    current_version,
                    status,
                    evidence_ref,
                    authority,
                    "current",
                    actor,
                    now,
                    json.dumps(payload or {}, sort_keys=True),
                ),
            )
            self._record_event(
                connection,
                "verification_evidence_recorded",
                "verification_evidence",
                evidence_id,
                actor,
                None,
                {"evidence_id": evidence_id, "method_id": method_id, "status": status, "authority": authority},
                now,
            )
            connection.commit()
            return self._verification_evidence_from_row(
                self._verification_evidence_row(connection, evidence_id),
                current_version,
            )

    def verification_status(self, requirement_id: str) -> RequirementVerificationStatus:
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            return self._verification_status_for_row(connection, requirement)

    def requirement_dossier(self, requirement_id: str) -> RequirementDossier:
        with connect(self.db_path) as connection:
            requirement_row = self._requirement_row(connection, requirement_id)
            record = self._record_from_row(connection, requirement_row)
            active_draft = self._active_draft_for_row(connection, requirement_row)
            criteria = self._dossier_acceptance_criteria(connection, requirement_row)
            traces = self._dossier_traces(connection, record)
            verification = self._verification_status_for_row(connection, requirement_row)
            baseline_exposure = self._dossier_baseline_exposure(connection, requirement_row, record)
            gaps = self._dossier_computed_gaps(record, active_draft, criteria, traces, verification, baseline_exposure)
            next_actions = self._dossier_next_actions(record, active_draft, gaps, verification)
            current_version = record.current_version_record
            return RequirementDossier(
                {
                    "requirement_id": record.requirement_id,
                    "id": record.id,
                    "stable_id": record.stable_id,
                    "current_version": record.current_version,
                },
                DossierAuthoritySummary(
                    record.status,
                    current_version.version if current_version else None,
                    current_version.statement_hash if current_version else None,
                    active_draft is not None,
                    active_draft.draft_id if active_draft else None,
                    verification.status,
                    len(baseline_exposure.items),
                ),
                DossierRequirementSection(record, current_version, active_draft),
                criteria,
                traces,
                verification,
                baseline_exposure,
                gaps,
                self._dossier_peer_facts(traces),
                next_actions,
            )

    def list_unverified_requirements(self) -> list[RequirementVerificationStatus]:
        return self._list_requirement_statuses({"unverified"})

    def list_stale_requirements(self) -> list[RequirementVerificationStatus]:
        return self._list_requirement_statuses({"stale"})

    def create_baseline(self, name: str, *, actor: str, description: str | None = None) -> Baseline:
        self._require_actor(actor)
        now = self._now()
        with connect(self.db_path) as connection:
            baseline_id = f"BASELINE-{self._next_baseline_number(connection):04d}"
            connection.execute(
                """
                insert into baselines(
                  baseline_id, name, description, locked, created_by, created_at
                ) values (?, ?, ?, ?, ?, ?)
                """,
                (baseline_id, name, description or "", 1, actor, now),
            )
            rows = connection.execute(
                """
                select r.requirement_id, r.display_id, r.stable_id, v.version,
                       v.statement_hash, v.status
                from requirements r
                join requirement_versions v
                  on v.requirement_id = r.requirement_id
                 and v.version = r.current_version
                where r.current_version > 0
                  and r.status in ('approved', 'deprecated')
                  and v.status in ('approved', 'deprecated')
                order by r.display_id
                """
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    insert into baseline_members(
                      baseline_id, requirement_id, version, display_id, stable_id,
                      statement_hash, status_at_baseline
                    ) values (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        baseline_id,
                        row["requirement_id"],
                        row["version"],
                        row["display_id"],
                        row["stable_id"],
                        row["statement_hash"],
                        row["status"],
                    ),
                )
            baseline = self._baseline_from_row(connection, self._baseline_row(connection, baseline_id))
            self._record_event(
                connection,
                "baseline_created",
                "baseline",
                baseline_id,
                actor,
                None,
                {"baseline_id": baseline_id, "name": name, "members": len(baseline.members)},
                now,
            )
            connection.commit()
            return baseline

    def show_baseline(self, baseline_id: str) -> Baseline:
        with connect(self.db_path) as connection:
            return self._baseline_from_row(connection, self._baseline_row(connection, baseline_id))

    def list_baselines(self) -> list[Baseline]:
        with connect(self.db_path) as connection:
            rows = connection.execute("select * from baselines order by baseline_id").fetchall()
            return [self._baseline_from_row(connection, row) for row in rows]

    def diff_baseline(self, baseline_id: str) -> BaselineDiff:
        with connect(self.db_path) as connection:
            self._baseline_row(connection, baseline_id)
            baseline_members = self._baseline_members(connection, baseline_id)
            baseline_by_requirement = {member.requirement_id: member for member in baseline_members}
            items: list[BaselineDiffItem] = []
            summary = {
                "unchanged": 0,
                "changed": 0,
                "missing_current": 0,
                "new_since_baseline": 0,
                "superseded_since_baseline": 0,
            }
            for member in baseline_members:
                requirement = connection.execute(
                    "select * from requirements where requirement_id = ?",
                    (member.requirement_id,),
                ).fetchone()
                current_version = int(requirement["current_version"]) if requirement is not None else None
                current = (
                    self._version_by_number(connection, member.requirement_id, current_version)
                    if current_version
                    else None
                )
                if current is None:
                    status = "missing_current"
                    current_hash = None
                elif current.version != member.version:
                    status = "superseded_since_baseline"
                    current_hash = current.statement_hash
                elif current.statement_hash != member.statement_hash:
                    status = "changed"
                    current_hash = current.statement_hash
                else:
                    status = "unchanged"
                    current_hash = current.statement_hash
                summary[status] += 1
                items.append(
                    BaselineDiffItem(
                        member.requirement_id,
                        member.id,
                        member.stable_id,
                        member.version,
                        current_version,
                        status,
                        member.statement_hash,
                        current_hash,
                    )
                )
            rows = connection.execute(
                """
                select r.requirement_id, r.display_id, r.stable_id, v.version,
                       v.statement_hash
                from requirements r
                join requirement_versions v
                  on v.requirement_id = r.requirement_id
                 and v.version = r.current_version
                where r.current_version > 0
                  and r.status in ('approved', 'deprecated')
                  and v.status in ('approved', 'deprecated')
                order by r.display_id
                """
            ).fetchall()
            for row in rows:
                requirement_id = str(row["requirement_id"])
                if requirement_id in baseline_by_requirement:
                    continue
                summary["new_since_baseline"] += 1
                items.append(
                    BaselineDiffItem(
                        requirement_id,
                        str(row["display_id"]),
                        str(row["stable_id"]),
                        None,
                        int(row["version"]),
                        "new_since_baseline",
                        None,
                        str(row["statement_hash"]),
                    )
                )
            return BaselineDiff(baseline_id, summary, items)

    def create_requirement(
        self,
        title: str,
        statement: str,
        actor: str,
        criticality: str = "medium",
    ) -> RequirementDraft:
        self._require_actor(actor)
        now = self._now()
        with connect(self.db_path) as connection:
            project_key = self._project_key(connection)
            number = self._next_requirement_number(connection)
            requirement_id = f"req-{number}"
            display_id = f"REQ-{project_key}-{number:04d}"
            stable_id = f"plainweave:req:{project_key}:{number:04d}"
            draft_id = f"DRAFT-{number:04d}"
            connection.execute(
                """
                insert into requirements(
                  requirement_id, display_id, stable_id, current_version, active_draft_id,
                  status, type, criticality, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    requirement_id,
                    display_id,
                    stable_id,
                    0,
                    draft_id,
                    "draft",
                    "functional",
                    criticality,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                insert into requirement_drafts(
                  draft_id, requirement_id, base_version, title, statement,
                  draft_revision, created_by, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (draft_id, requirement_id, None, title, statement, 1, actor, now, now),
            )
            self._record_event(
                connection,
                "requirement_created",
                "requirement",
                requirement_id,
                actor,
                None,
                {"id": display_id, "draft_id": draft_id},
                now,
            )
            connection.commit()
        return RequirementDraft(requirement_id, display_id, stable_id, draft_id, None, 1, title, statement, "draft")

    def update_draft(
        self,
        requirement_id: str,
        *,
        actor: str,
        title: str | None = None,
        statement: str | None = None,
        expected_draft_revision: int | None = None,
    ) -> RequirementDraft:
        self._require_actor(actor)
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            draft_id = requirement["active_draft_id"]
            if not isinstance(draft_id, str):
                raise self._error(ErrorCode.POLICY_REQUIRED, "requirement has no active draft")
            draft = self._draft_row(connection, draft_id)
            if expected_draft_revision is not None and int(draft["draft_revision"]) != expected_draft_revision:
                raise self._error(ErrorCode.CONFLICT, "draft revision conflict")
            next_revision = int(draft["draft_revision"]) + 1
            next_title = title if title is not None else str(draft["title"])
            next_statement = statement if statement is not None else str(draft["statement"])
            connection.execute(
                """
                update requirement_drafts
                set title = ?, statement = ?, draft_revision = ?, updated_at = ?
                where draft_id = ?
                """,
                (next_title, next_statement, next_revision, now, draft_id),
            )
            self._record_event(
                connection,
                "requirement_draft_updated",
                "requirement",
                str(requirement["requirement_id"]),
                actor,
                None,
                {"draft_id": draft_id, "draft_revision": next_revision},
                now,
            )
            connection.commit()
            return RequirementDraft(
                str(requirement["requirement_id"]),
                str(requirement["display_id"]),
                str(requirement["stable_id"]),
                draft_id,
                self._optional_int(draft["base_version"]),
                next_revision,
                next_title,
                next_statement,
                "draft",
            )

    def approve_requirement(
        self,
        requirement_id: str,
        *,
        actor: str,
        expected_version: int,
        idempotency_key: str | None = None,
    ) -> RequirementVersion:
        self._require_actor(actor)
        cached = self._idempotent_version(
            idempotency_key,
            operation="approve_requirement",
            request={"expected_version": expected_version},
        )
        if cached is not None:
            if not self._matches_requirement(cached, requirement_id) or expected_version != cached.version - 1:
                raise self._error(ErrorCode.CONFLICT, "idempotency key conflicts with this approval request")
            return cached
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            self._require_current_version(requirement, expected_version)
            draft_id = requirement["active_draft_id"]
            if not isinstance(draft_id, str):
                raise self._error(ErrorCode.POLICY_REQUIRED, "requirement has no active draft")
            draft = self._draft_row(connection, draft_id)
            version_number = int(requirement["current_version"]) + 1
            version = self._insert_version(connection, requirement, draft, version_number, "approved", actor, now)
            connection.execute(
                """
                update requirements
                set current_version = ?, active_draft_id = null, status = ?, updated_at = ?
                where requirement_id = ?
                """,
                (version_number, "approved", now, requirement["requirement_id"]),
            )
            connection.execute(
                "update acceptance_criteria set version = ? where requirement_id = ? and draft_id = ?",
                (version_number, requirement["requirement_id"], draft_id),
            )
            self._record_event(
                connection,
                "requirement_approved",
                "requirement",
                str(requirement["requirement_id"]),
                actor,
                idempotency_key,
                asdict(version),
                now,
            )
            self._store_idempotency(
                connection,
                idempotency_key,
                "approve_requirement",
                str(requirement["requirement_id"]),
                version,
                request={"expected_version": expected_version},
            )
            connection.commit()
            return version

    def supersede_requirement(
        self,
        requirement_id: str,
        *,
        title: str,
        statement: str,
        actor: str,
        expected_version: int,
        idempotency_key: str | None = None,
    ) -> RequirementVersion:
        self._require_actor(actor)
        cached = self._idempotent_version(
            idempotency_key,
            operation="supersede_requirement",
            request={"expected_version": expected_version, "title": title, "statement": statement},
        )
        if cached is not None:
            if not self._matches_requirement(cached, requirement_id) or expected_version != cached.version - 1:
                raise self._error(ErrorCode.CONFLICT, "idempotency key conflicts with this supersede request")
            return cached
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            self._require_current_version(requirement, expected_version)
            next_version = int(requirement["current_version"]) + 1
            statement_hash = self._statement_hash(statement)
            connection.execute(
                """
                insert into requirement_versions(
                  requirement_id, version, title, statement, statement_hash, status,
                  approved_by, approved_at, superseded_by_version
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    requirement["requirement_id"],
                    next_version,
                    title,
                    statement,
                    statement_hash,
                    "approved",
                    actor,
                    now,
                    None,
                ),
            )
            connection.execute(
                """
                update requirement_versions
                set status = ?, superseded_by_version = ?
                where requirement_id = ? and version = ?
                """,
                ("superseded", next_version, requirement["requirement_id"], expected_version),
            )
            connection.execute(
                """
                update requirements
                set current_version = ?, active_draft_id = null, status = ?, updated_at = ?
                where requirement_id = ?
                """,
                (next_version, "approved", now, requirement["requirement_id"]),
            )
            version = RequirementVersion(
                str(requirement["requirement_id"]),
                str(requirement["display_id"]),
                str(requirement["stable_id"]),
                next_version,
                title,
                statement,
                statement_hash,
                "approved",
                actor,
                now,
            )
            self._record_event(
                connection,
                "requirement_superseded",
                "requirement",
                str(requirement["requirement_id"]),
                actor,
                idempotency_key,
                asdict(version),
                now,
            )
            self._store_idempotency(
                connection,
                idempotency_key,
                "supersede_requirement",
                str(requirement["requirement_id"]),
                version,
                request={"expected_version": expected_version, "title": title, "statement": statement},
            )
            connection.commit()
            return version

    def reject_requirement(
        self,
        requirement_id: str,
        *,
        actor: str,
        expected_version: int,
        reason: str,
    ) -> RequirementRecord:
        self._require_actor(actor)
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            self._require_current_version(requirement, expected_version)
            draft_id = requirement["active_draft_id"]
            if not isinstance(draft_id, str):
                raise self._error(ErrorCode.POLICY_REQUIRED, "requirement has no active draft")
            connection.execute(
                """
                update requirements
                set active_draft_id = null, status = ?, updated_at = ?
                where requirement_id = ?
                """,
                ("rejected", now, requirement["requirement_id"]),
            )
            record = self._get_requirement(connection, requirement_id)
            self._record_event(
                connection,
                "requirement_rejected",
                "requirement",
                str(requirement["requirement_id"]),
                actor,
                None,
                {"draft_id": draft_id, "reason": reason},
                now,
            )
            connection.commit()
            return record

    def deprecate_requirement(
        self,
        requirement_id: str,
        *,
        actor: str,
        expected_version: int,
        idempotency_key: str | None = None,
    ) -> RequirementRecord:
        self._require_actor(actor)
        cached = self._idempotent_record(
            idempotency_key,
            operation="deprecate_requirement",
            request={"expected_version": expected_version},
        )
        if cached is not None:
            if not self._matches_record(cached, requirement_id) or expected_version != cached.current_version:
                raise self._error(ErrorCode.CONFLICT, "idempotency key conflicts with this deprecate request")
            return cached
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            self._require_current_version(requirement, expected_version)
            connection.execute(
                "update requirements set status = ?, updated_at = ? where requirement_id = ?",
                ("deprecated", now, requirement["requirement_id"]),
            )
            connection.execute(
                "update requirement_versions set status = ? where requirement_id = ? and version = ?",
                ("deprecated", requirement["requirement_id"], expected_version),
            )
            record = self._get_requirement(connection, requirement_id)
            self._record_event(
                connection,
                "requirement_deprecated",
                "requirement",
                str(requirement["requirement_id"]),
                actor,
                idempotency_key,
                self._record_dict(record),
                now,
            )
            self._store_idempotency(
                connection,
                idempotency_key,
                "deprecate_requirement",
                str(requirement["requirement_id"]),
                record,
                request={"expected_version": expected_version},
            )
            connection.commit()
            return record

    def add_acceptance_criterion(
        self,
        requirement_id: str,
        text: str,
        *,
        actor: str,
        position: int | None = None,
    ) -> AcceptanceCriterion:
        self._require_actor(actor)
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            draft_id = requirement["active_draft_id"]
            if not isinstance(draft_id, str):
                raise self._error(ErrorCode.POLICY_REQUIRED, "acceptance criteria changes require an active draft")
            next_position = position or self._next_criterion_position(
                connection, str(requirement["requirement_id"]), draft_id
            )
            criterion_id = f"AC-{self._next_criterion_number(connection):04d}"
            connection.execute(
                """
                insert into acceptance_criteria(
                  criterion_id, requirement_id, draft_id, version, position,
                  text, status, created_by, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    criterion_id,
                    requirement["requirement_id"],
                    draft_id,
                    None,
                    next_position,
                    text,
                    "active",
                    actor,
                    now,
                ),
            )
            self._record_event(
                connection,
                "acceptance_criterion_added",
                "requirement",
                str(requirement["requirement_id"]),
                actor,
                None,
                {"criterion_id": criterion_id, "draft_id": draft_id},
                now,
            )
            connection.commit()
            return AcceptanceCriterion(
                criterion_id,
                str(requirement["requirement_id"]),
                draft_id,
                None,
                next_position,
                text,
                "active",
                actor,
                now,
            )

    def list_acceptance_criteria(self, requirement_id: str, version: int | None = None) -> list[AcceptanceCriterion]:
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            if version is not None:
                rows = connection.execute(
                    """
                    select * from acceptance_criteria
                    where requirement_id = ? and version = ?
                    order by position, criterion_id
                    """,
                    (requirement["requirement_id"], version),
                ).fetchall()
            else:
                active_draft_id = requirement["active_draft_id"]
                if isinstance(active_draft_id, str):
                    rows = connection.execute(
                        """
                        select * from acceptance_criteria
                        where requirement_id = ? and draft_id = ?
                        order by position, criterion_id
                        """,
                        (requirement["requirement_id"], active_draft_id),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        select * from acceptance_criteria
                        where requirement_id = ? and version = ?
                        order by position, criterion_id
                        """,
                        (requirement["requirement_id"], int(requirement["current_version"])),
                    ).fetchall()
            return [self._criterion_from_row(row) for row in rows]

    def propose_trace_link(
        self,
        from_ref: TraceRef,
        relation: str,
        to_ref: TraceRef,
        *,
        actor: str,
        confidence: float | None = None,
    ) -> TraceLink:
        return self.create_trace_link(
            from_ref,
            relation,
            to_ref,
            actor=actor,
            authority="agent_proposed",
            confidence=confidence,
        )

    def create_trace_link(
        self,
        from_ref: TraceRef,
        relation: str,
        to_ref: TraceRef,
        *,
        actor: str,
        authority: str,
        confidence: float | None = None,
    ) -> TraceLink:
        self._require_actor(actor)
        self._validate_trace_relation(from_ref, relation, to_ref)
        from_ref, target_snapshot = self._normalize_trace_refs(from_ref)
        now = self._now()
        state = "accepted" if authority == "accepted" else "proposed"
        accepted_by = actor if authority == "accepted" else None
        with connect(self.db_path) as connection:
            if state == "accepted":
                self._require_accepted_trace_targets(connection, to_ref)
            link_id = f"LINK-{self._next_link_number(connection):04d}"
            connection.execute(
                """
                insert into trace_links(
                  link_id, state, from_kind, from_id, relation, to_kind, to_id,
                  authority, freshness, confidence, created_by, accepted_by,
                  created_at, updated_at, target_snapshot_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    state,
                    from_ref.kind,
                    from_ref.id,
                    relation,
                    to_ref.kind,
                    to_ref.id,
                    authority,
                    "current",
                    confidence,
                    actor,
                    accepted_by,
                    now,
                    now,
                    json.dumps(target_snapshot, sort_keys=True),
                ),
            )
            self._record_event(
                connection,
                "trace_link_created",
                "trace_link",
                link_id,
                actor,
                None,
                {"link_id": link_id, "state": state, "authority": authority},
                now,
            )
            connection.commit()
            return TraceLink(
                link_id,
                state,
                from_ref,
                relation,
                to_ref,
                authority,
                "current",
                confidence,
                actor,
                accepted_by,
                target_snapshot,
            )

    def accept_trace_link(self, link_id: str, *, actor: str) -> TraceLink:
        return self._transition_trace(link_id, actor=actor, state="accepted", authority="accepted", freshness="current")

    def reject_trace_link(self, link_id: str, *, actor: str, reason: str) -> TraceLink:
        return self._transition_trace(link_id, actor=actor, state="rejected", reason=reason)

    def mark_trace_stale(self, link_id: str, *, actor: str, reason: str) -> TraceLink:
        return self._transition_trace(link_id, actor=actor, state="stale", freshness="stale", reason=reason)

    def mark_trace_orphaned(self, link_id: str, *, actor: str, reason: str) -> TraceLink:
        return self._transition_trace(link_id, actor=actor, state="orphaned", freshness="orphaned", reason=reason)

    def trace_for(self, requirement_id: str | None = None, state: str | None = None) -> list[TraceLink]:
        clauses: list[str] = []
        params: list[object] = []
        if requirement_id is not None:
            clauses.append("(to_id = ? or from_id = ?)")
            params.extend([requirement_id, requirement_id])
        if state is not None:
            clauses.append("state = ?")
            params.append(state)
        where = " where " + " and ".join(clauses) if clauses else ""
        with connect(self.db_path) as connection:
            rows = connection.execute(f"select * from trace_links{where} order by link_id", params).fetchall()
            return [self._trace_from_row(row) for row in rows]

    def create_goal(self, title: str, statement: str, *, actor: str) -> IntentGoal:
        self._require_actor(actor)
        if not title:
            raise self._error(ErrorCode.VALIDATION, "goal title is required")
        if not statement:
            raise self._error(ErrorCode.VALIDATION, "goal statement is required")
        now = self._now()
        with connect(self.db_path) as connection:
            project_key = self._project_key(connection)
            number = self._next_goal_number(connection)
            goal_id = f"goal-{number}"
            display_id = f"GOAL-{project_key}-{number:04d}"
            stable_id = f"plainweave:goal:{project_key}:{number:04d}"
            connection.execute(
                """
                insert into intent_goals(
                  goal_id, display_id, stable_id, title, statement, status,
                  created_by, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (goal_id, display_id, stable_id, title, statement, "active", actor, now, now),
            )
            self._record_event(
                connection,
                "intent_goal_created",
                "intent_goal",
                goal_id,
                actor,
                None,
                {"id": display_id},
                now,
            )
            connection.commit()
            return IntentGoal(goal_id, display_id, stable_id, title, statement, "active", actor, now)

    def link_goal_to_requirement(self, goal_id: str, requirement_id: str, *, actor: str) -> IntentEdge:
        self._require_actor(actor)
        now = self._now()
        with connect(self.db_path) as connection:
            goal = self._goal_row(connection, goal_id)
            requirement = self._requirement_row(connection, requirement_id)
            canonical_goal_id = str(goal["goal_id"])
            canonical_requirement_id = str(requirement["requirement_id"])
            existing = connection.execute(
                """
                select * from intent_edges
                where goal_id = ? and requirement_id = ? and relation = ?
                """,
                (canonical_goal_id, canonical_requirement_id, "justifies"),
            ).fetchone()
            if existing is None:
                edge_id = f"IEDGE-{self._next_intent_edge_number(connection):04d}"
                connection.execute(
                    """
                    insert into intent_edges(
                      edge_id, goal_id, requirement_id, relation, authority,
                      freshness, created_by, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        canonical_goal_id,
                        canonical_requirement_id,
                        "justifies",
                        "accepted",
                        "current",
                        actor,
                        now,
                        now,
                    ),
                )
                self._record_event(
                    connection,
                    "intent_edge_created",
                    "intent_edge",
                    edge_id,
                    actor,
                    None,
                    {"goal_id": canonical_goal_id, "requirement_id": canonical_requirement_id},
                    now,
                )
                connection.commit()
                row = self._intent_edge_row(connection, edge_id)
            else:
                row = existing
            return self._intent_edge_from_row(row)

    def goals_for_requirement(self, requirement_id: str) -> list[tuple[IntentGoal, str]]:
        """Goals that justify a requirement, each paired with its edge freshness.

        Returns every ``justifies`` edge paired with its recorded ``freshness``.
        Edge staleness is not yet written by any code path, so today this value is
        always ``current``; the pairing exists so drifted laddering can surface once
        an edge-staleness signal lands without changing this contract. An empty list
        means the requirement ladders to no strategic goal. Raises ``NOT_FOUND`` when
        the requirement itself does not resolve.
        """
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            canonical_requirement_id = str(requirement["requirement_id"])
            rows = connection.execute(
                """
                select g.*, e.freshness as edge_freshness
                from intent_edges e
                join intent_goals g on g.goal_id = e.goal_id
                where e.requirement_id = ? and e.relation = ?
                order by g.display_id
                """,
                (canonical_requirement_id, "justifies"),
            ).fetchall()
        return [(self._goal_from_row(row), str(row["edge_freshness"])) for row in rows]

    def record_code_entity(
        self,
        entity_id: str,
        *,
        entity_kind: str,
        actor: str,
        display_name: str | None = None,
        content_hash: str | None = None,
        public: bool = True,
        source: str = "loomweave_catalog",
        freshness: str = "current",
    ) -> CodeEntity:
        self._require_actor(actor)
        if not entity_id:
            raise self._error(ErrorCode.VALIDATION, "entity_id is required")
        if not entity_kind:
            raise self._error(ErrorCode.VALIDATION, "entity_kind is required")
        now = self._now()
        with connect(self.db_path) as connection:
            connection.execute(
                """
                insert into code_entities(
                  entity_id, entity_kind, display_name, content_hash, public,
                  source, freshness, recorded_by, recorded_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(entity_id) do update set
                  entity_kind = excluded.entity_kind,
                  display_name = excluded.display_name,
                  content_hash = excluded.content_hash,
                  public = excluded.public,
                  source = excluded.source,
                  freshness = excluded.freshness,
                  recorded_by = excluded.recorded_by,
                  updated_at = excluded.updated_at
                """,
                (
                    entity_id,
                    entity_kind,
                    display_name,
                    content_hash,
                    1 if public else 0,
                    source,
                    freshness,
                    actor,
                    now,
                    now,
                ),
            )
            self._record_event(
                connection,
                "code_entity_recorded",
                "code_entity",
                entity_id,
                actor,
                None,
                {"entity_kind": entity_kind, "source": source, "public": public},
                now,
            )
            connection.commit()
            return self._code_entity_from_row(self._code_entity_row(connection, entity_id))

    def bind_sei_to_requirement(
        self,
        entity_id: str,
        requirement_id: str,
        *,
        actor: str,
        content_hash_at_attach: str | None = None,
        entity_kind: str = "loomweave_entity",
        provenance: dict[str, Any] | None = None,
    ) -> SeiBinding:
        self._require_actor(actor)
        if not entity_id:
            raise self._error(ErrorCode.VALIDATION, "entity_id is required")
        if not entity_kind:
            raise self._error(ErrorCode.VALIDATION, "entity_kind is required")
        now = self._now()
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            canonical_requirement_id = str(requirement["requirement_id"])
            entity = connection.execute("select * from code_entities where entity_id = ?", (entity_id,)).fetchone()
            if entity is None:
                connection.execute(
                    """
                    insert into code_entities(
                      entity_id, entity_kind, display_name, content_hash, public,
                      source, freshness, recorded_by, recorded_at, updated_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entity_id,
                        entity_kind,
                        None,
                        content_hash_at_attach,
                        1,
                        "authoring_time_bind",
                        "unknown" if content_hash_at_attach is None else "current",
                        actor,
                        now,
                        now,
                    ),
                )
            existing = connection.execute(
                """
                select * from entity_associations
                where entity_id = ? and requirement_id = ? and relation = ?
                """,
                (entity_id, canonical_requirement_id, "satisfies"),
            ).fetchone()
            if existing is None:
                association_id = f"EASSOC-{self._next_association_number(connection):04d}"
                connection.execute(
                    """
                    insert into entity_associations(
                      association_id, entity_id, entity_kind, requirement_id, relation,
                      content_hash_at_attach, drift_status, freshness, bound_by, bound_at,
                      provenance_json
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        association_id,
                        entity_id,
                        entity_kind,
                        canonical_requirement_id,
                        "satisfies",
                        content_hash_at_attach,
                        "unknown" if content_hash_at_attach is None else "attached",
                        "unknown" if content_hash_at_attach is None else "current",
                        actor,
                        now,
                        json.dumps(provenance or {}, sort_keys=True),
                    ),
                )
                self._record_event(
                    connection,
                    "sei_binding_created",
                    "entity_association",
                    association_id,
                    actor,
                    None,
                    {"entity_id": entity_id, "requirement_id": canonical_requirement_id},
                    now,
                )
                connection.commit()
                row = self._association_row(connection, association_id)
            else:
                row = existing
            return self._binding_from_row(row)

    def list_sei_bindings(self, requirement_id: str | None = None) -> list[SeiBinding]:
        with connect(self.db_path) as connection:
            params: tuple[object, ...]
            if requirement_id is None:
                rows = connection.execute(
                    "select * from entity_associations order by entity_id, requirement_id"
                ).fetchall()
            else:
                requirement = self._requirement_row(connection, requirement_id)
                params = (str(requirement["requirement_id"]),)
                rows = connection.execute(
                    """
                    select * from entity_associations
                    where requirement_id = ?
                    order by entity_id, requirement_id
                    """,
                    params,
                ).fetchall()
            return [self._binding_from_row(row) for row in rows]

    def is_binding_drifted(self, binding: SeiBinding, current_content_hash: str) -> bool:
        if binding.content_hash_at_attach is None:
            return False
        return binding.content_hash_at_attach != current_content_hash

    def intent_orphans(self, level: IntentLevel) -> list[IntentNode]:
        with connect(self.db_path) as connection:
            if level == IntentLevel.CODE:
                rows = connection.execute(
                    """
                    select c.entity_id
                    from code_entities c
                    left join entity_associations a on a.entity_id = c.entity_id
                    where c.public = 1 and a.association_id is null
                    order by c.entity_id
                    """
                ).fetchall()
                return [IntentNode(IntentLevel.CODE, str(row["entity_id"])) for row in rows]
            if level == IntentLevel.REQUIREMENT:
                rows = connection.execute(
                    """
                    select r.requirement_id
                    from requirements r
                    left join intent_edges e on e.requirement_id = r.requirement_id
                    where r.status in ('draft', 'approved') and e.edge_id is null
                    order by r.display_id
                    """
                ).fetchall()
                return [IntentNode(IntentLevel.REQUIREMENT, str(row["requirement_id"])) for row in rows]
            rows = connection.execute(
                """
                select g.goal_id
                from intent_goals g
                left join intent_edges e on e.goal_id = g.goal_id
                where g.status = 'active' and e.edge_id is null
                order by g.display_id
                """
            ).fetchall()
            return [IntentNode(IntentLevel.GOAL, str(row["goal_id"])) for row in rows]

    def intent_trace(self, node: IntentNode) -> Trace:
        with connect(self.db_path) as connection:
            if node.level == IntentLevel.CODE:
                requirement_ids = self._requirement_ids_for_entity(connection, node.node_id)
                up_nodes = self._dedupe_nodes(
                    [
                        *(IntentNode(IntentLevel.REQUIREMENT, requirement_id) for requirement_id in requirement_ids),
                        *(
                            IntentNode(IntentLevel.GOAL, goal_id)
                            for requirement_id in requirement_ids
                            for goal_id in self._goal_ids_for_requirement(connection, requirement_id)
                        ),
                    ]
                )
                return Trace(node, tuple(up_nodes), ())
            if node.level == IntentLevel.REQUIREMENT:
                requirement = self._requirement_row(connection, node.node_id)
                requirement_id = str(requirement["requirement_id"])
                up_tuple = tuple(
                    IntentNode(IntentLevel.GOAL, goal_id)
                    for goal_id in self._goal_ids_for_requirement(connection, requirement_id)
                )
                down_tuple = tuple(
                    IntentNode(IntentLevel.CODE, entity_id)
                    for entity_id in self._entity_ids_for_requirement(connection, requirement_id)
                )
                return Trace(node, up_tuple, down_tuple)
            goal = self._goal_row(connection, node.node_id)
            goal_id = str(goal["goal_id"])
            requirement_ids = self._requirement_ids_for_goal(connection, goal_id)
            down_nodes = self._dedupe_nodes(
                [
                    *(IntentNode(IntentLevel.REQUIREMENT, requirement_id) for requirement_id in requirement_ids),
                    *(
                        IntentNode(IntentLevel.CODE, entity_id)
                        for requirement_id in requirement_ids
                        for entity_id in self._entity_ids_for_requirement(connection, requirement_id)
                    ),
                ]
            )
            return Trace(node, (), tuple(down_nodes))

    def intent_corpus(self) -> list[CorpusEntry]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                select requirement_id from requirements
                where status in ('draft', 'approved')
                order by display_id
                """
            ).fetchall()
            entries: list[CorpusEntry] = []
            for row in rows:
                requirement_id = str(row["requirement_id"])
                entries.append(
                    CorpusEntry(
                        IntentNode(IntentLevel.REQUIREMENT, requirement_id),
                        tuple(
                            IntentNode(IntentLevel.GOAL, goal_id)
                            for goal_id in self._goal_ids_for_requirement(connection, requirement_id)
                        ),
                        tuple(
                            IntentNode(IntentLevel.CODE, entity_id)
                            for entity_id in self._entity_ids_for_requirement(connection, requirement_id)
                        ),
                    )
                )
            return entries

    def intent_coverage(
        self,
        *,
        exclude_namespaces: Sequence[str] | None = None,
        surface_classes: Sequence[str] | None = None,
    ) -> IntentCoverage:
        """Compute the north-star honestly: the fraction of in-scope public surfaces
        that answer *"why does this exist?"* via ``SEI -> requirement -> goal``.

        The public-surface denominator is enumerated from the local Loomweave catalog
        (the ``PUBLIC_SURFACE_TAGS`` entities), scoped by namespace exclusion (default
        ``scripts.``/``tests.``) and an optional surface-class restriction. A surface is
        justified iff its SEI traces up to a goal; unrecorded or unbound surfaces are the
        honest gap. The reading carries the catalog's ``coverage`` block verbatim and a
        ``denominator_complete`` flag, so a degraded denominator is never presented as a
        complete-surface reading. Advisory only — it emits a fact, not a verdict."""
        active_exclusions = (
            DEFAULT_INTENT_COVERAGE_EXCLUDED_NAMESPACES
            if exclude_namespaces is None
            else tuple(sorted({prefix for prefix in exclude_namespaces if prefix}))
        )
        active_classes = self._validated_surface_classes(surface_classes)

        adapter = self._loomweave_adapter()
        items: list[LoomweaveCatalogEntity] = []
        coverage: dict[str, object] = {}
        adapter_status: dict[str, object] = {}
        adapter_degraded: list[dict[str, object]] = []
        offset = 0
        page_size = 100
        while True:
            page = adapter.list_catalog(limit=page_size, offset=offset)
            if offset == 0:
                coverage = dict(page.coverage)
                adapter_status = dict(page.adapter_status)
                adapter_degraded = [dict(entry) for entry in page.degraded]
            items.extend(page.items)
            if not page.has_more or page.next_offset is None:
                break
            offset = page.next_offset

        justified: list[IntentCoverageSurface] = []
        unjustified: list[IntentCoverageSurface] = []
        excluded_count = 0
        for entity in items:
            entity_classes = tuple(sorted(PUBLIC_SURFACE_TAGS.intersection(entity.tags)))
            if not entity_classes:
                # Modules / untagged entities are pulled into the catalog for context but
                # are not public surfaces; the denominator is the tagged exported API.
                continue
            if active_classes is not None and not set(entity_classes).intersection(active_classes):
                continue
            namespace = self._surface_namespace(entity.locator)
            if any(namespace.startswith(prefix) for prefix in active_exclusions):
                excluded_count += 1
                continue
            goals = self._goal_nodes_for_surface(entity.sei)
            surface = IntentCoverageSurface(entity.locator, entity.sei, entity_classes, bool(goals), goals)
            (justified if surface.justified else unjustified).append(surface)

        numerator = len(justified)
        denominator = numerator + len(unjustified)
        ratio = (numerator / denominator) if denominator else None
        return IntentCoverage(
            numerator=numerator,
            denominator=denominator,
            ratio=ratio,
            denominator_complete=bool(coverage.get("complete", False)),
            coverage=coverage,
            justified=tuple(justified),
            unjustified=tuple(unjustified),
            excluded_namespaces=active_exclusions,
            excluded_count=excluded_count,
            surface_classes=active_classes,
            adapter_status=adapter_status,
            adapter_degraded=tuple(adapter_degraded),
        )

    def _validated_surface_classes(self, surface_classes: Sequence[str] | None) -> tuple[str, ...] | None:
        if surface_classes is None:
            return None
        invalid = sorted({cls for cls in surface_classes if cls not in PUBLIC_SURFACE_TAGS})
        if invalid:
            raise self._error(
                ErrorCode.VALIDATION,
                "surface_classes contains unknown public-surface classes: " + ", ".join(invalid),
            )
        return tuple(sorted(set(surface_classes)))

    def _surface_namespace(self, locator: str) -> str:
        """The qualified-name segment of a ``{plugin}:{kind}:{qualname}`` locator, used
        for namespace scoping. Operates on the catalog locator, never an opaque SEI."""
        parts = locator.split(":", 2)
        return parts[2] if len(parts) == 3 else locator

    def _goal_nodes_for_surface(self, sei: str | None) -> tuple[IntentNode, ...]:
        """A surface is justified iff its SEI ladders up to a goal through a *live*
        requirement (``status in ('draft', 'approved')``) — the same liveness predicate
        :meth:`intent_corpus` and :meth:`intent_orphans` use. A binding whose only
        requirement has been deprecated is no longer live justification, so it is not
        counted; counting a dead obligation would inflate the honest north-star. Returns
        the goal nodes reached (empty when unbound, deprecated, or not laddered).

        This walks the graph directly rather than reusing :meth:`intent_trace`, which
        deliberately keeps surfacing deprecated requirements: trace *explains* the
        neighbourhood, coverage *counts* live justification."""
        if sei is None:
            return ()
        with connect(self.db_path) as connection:
            goal_ids: list[str] = []
            seen: set[str] = set()
            for requirement_id in self._live_requirement_ids_for_entity(connection, sei):
                for goal_id in self._goal_ids_for_requirement(connection, requirement_id):
                    if goal_id not in seen:
                        seen.add(goal_id)
                        goal_ids.append(goal_id)
        return tuple(IntentNode(IntentLevel.GOAL, goal_id) for goal_id in goal_ids)

    def get_requirement(self, requirement_id: str) -> RequirementRecord:
        with connect(self.db_path) as connection:
            return self._get_requirement(connection, requirement_id)

    def search_requirements(self, query: str | None = None) -> list[RequirementRecord]:
        with connect(self.db_path) as connection:
            if query:
                rows = connection.execute(
                    """
                    select distinct r.*
                    from requirements r
                    left join requirement_drafts d on d.requirement_id = r.requirement_id
                    left join requirement_versions v on v.requirement_id = r.requirement_id
                    where r.display_id like ?
                       or r.stable_id like ?
                       or r.requirement_id like ?
                       or d.title like ?
                       or d.statement like ?
                       or v.title like ?
                       or v.statement like ?
                    order by r.display_id
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"),
                ).fetchall()
            else:
                rows = connection.execute("select * from requirements order by display_id").fetchall()
            return [self._record_from_row(connection, row) for row in rows]

    def requirement_preflight_profile(self, requirement_id: str) -> dict[str, object]:
        with connect(self.db_path) as connection:
            row = self._requirement_row(connection, requirement_id)
            criticality = row["criticality"]
            requirement_type = row["type"]
            return {
                "id": str(row["display_id"]),
                "requirement_id": str(row["requirement_id"]),
                "stable_id": str(row["stable_id"]),
                "version": int(row["current_version"]),
                "criticality": str(criticality) if criticality is not None else "unknown",
                "type": str(requirement_type) if requirement_type is not None else "unknown",
            }

    def _get_requirement(self, connection: sqlite3.Connection, requirement_id: str) -> RequirementRecord:
        return self._record_from_row(connection, self._requirement_row(connection, requirement_id))

    def _record_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> RequirementRecord:
        current_version = int(row["current_version"])
        version = (
            self._version_by_number(connection, str(row["requirement_id"]), current_version)
            if current_version
            else None
        )
        return RequirementRecord(
            str(row["requirement_id"]),
            str(row["display_id"]),
            str(row["stable_id"]),
            current_version,
            row["active_draft_id"] if isinstance(row["active_draft_id"], str) else None,
            str(row["status"]),
            version,
        )

    def _active_draft_for_row(
        self,
        connection: sqlite3.Connection,
        requirement: sqlite3.Row,
    ) -> RequirementDraft | None:
        draft_id = requirement["active_draft_id"]
        if not isinstance(draft_id, str):
            return None
        draft = self._draft_row(connection, draft_id)
        return RequirementDraft(
            str(requirement["requirement_id"]),
            str(requirement["display_id"]),
            str(requirement["stable_id"]),
            draft_id,
            self._optional_int(draft["base_version"]),
            int(draft["draft_revision"]),
            str(draft["title"]),
            str(draft["statement"]),
            "draft",
        )

    def _dossier_acceptance_criteria(
        self,
        connection: sqlite3.Connection,
        requirement: sqlite3.Row,
    ) -> DossierAcceptanceCriteriaSection:
        requirement_id = str(requirement["requirement_id"])
        current_version = int(requirement["current_version"])
        current_rows = (
            connection.execute(
                """
                select * from acceptance_criteria
                where requirement_id = ? and version = ?
                order by position, criterion_id
                """,
                (requirement_id, current_version),
            ).fetchall()
            if current_version
            else []
        )
        active_draft_id = requirement["active_draft_id"]
        draft_rows = (
            connection.execute(
                """
                select * from acceptance_criteria
                where requirement_id = ? and draft_id = ? and version is null
                order by position, criterion_id
                """,
                (requirement_id, active_draft_id),
            ).fetchall()
            if isinstance(active_draft_id, str)
            else []
        )
        return DossierAcceptanceCriteriaSection(
            [self._criterion_from_row(row) for row in current_rows],
            [self._criterion_from_row(row) for row in draft_rows],
        )

    def _dossier_traces(self, connection: sqlite3.Connection, record: RequirementRecord) -> DossierTraceSection:
        requirement_refs = {record.requirement_id, record.id, record.stable_id}
        method_refs = self._verification_method_ids_for_requirement(connection, record.requirement_id)
        exact_refs = requirement_refs | method_refs
        ref_patterns = [f"{ref}@%" for ref in requirement_refs]
        exact_placeholders = ",".join("?" for _ in exact_refs)
        pattern_clauses = " or ".join(["from_id like ?"] * len(ref_patterns) + ["to_id like ?"] * len(ref_patterns))
        rows = connection.execute(
            f"""
            select * from trace_links
            where from_id in ({exact_placeholders})
               or to_id in ({exact_placeholders})
               or {pattern_clauses}
            order by link_id
            """,
            [*exact_refs, *exact_refs, *ref_patterns, *ref_patterns],
        ).fetchall()
        incoming: list[TraceLink] = []
        outgoing: list[TraceLink] = []
        by_state: dict[str, int] = {}
        by_relation: dict[str, int] = {}
        items: list[TraceLink] = []
        for row in rows:
            item = self._trace_from_row(row)
            is_incoming = self._trace_ref_matches_requirement(item.to_ref, requirement_refs) or (
                item.to_ref.kind == "verification_method" and item.to_ref.id in method_refs
            )
            is_outgoing = self._trace_ref_matches_requirement(item.from_ref, requirement_refs) or (
                item.from_ref.kind == "verification_method" and item.from_ref.id in method_refs
            )
            if not is_incoming and not is_outgoing:
                continue
            items.append(item)
            if is_incoming:
                incoming.append(item)
            if is_outgoing:
                outgoing.append(item)
            by_state[item.state] = by_state.get(item.state, 0) + 1
            by_relation[item.relation] = by_relation.get(item.relation, 0) + 1
        return DossierTraceSection(
            incoming,
            outgoing,
            dict(sorted(by_state.items())),
            dict(sorted(by_relation.items())),
            items,
        )

    def _trace_ref_matches_requirement(self, trace_ref: TraceRef, requirement_refs: set[str]) -> bool:
        if trace_ref.id in requirement_refs:
            return True
        prefix, separator, _version = trace_ref.id.rpartition("@")
        return trace_ref.kind == "requirement_version" and separator == "@" and prefix in requirement_refs

    def _verification_method_ids_for_requirement(
        self,
        connection: sqlite3.Connection,
        requirement_id: str,
    ) -> set[str]:
        rows = connection.execute(
            """
            select method_id from verification_methods
            where requirement_id = ?
            order by method_id
            """,
            (requirement_id,),
        ).fetchall()
        return {str(row["method_id"]) for row in rows}

    def _dossier_baseline_exposure(
        self,
        connection: sqlite3.Connection,
        requirement: sqlite3.Row,
        record: RequirementRecord,
    ) -> DossierBaselineExposure:
        rows = connection.execute(
            """
            select b.baseline_id, b.name, b.locked, b.created_by, b.created_at,
                   bm.version, bm.statement_hash
            from baseline_members bm
            join baselines b on b.baseline_id = bm.baseline_id
            where bm.requirement_id = ?
            order by b.baseline_id
            """,
            (requirement["requirement_id"],),
        ).fetchall()
        summary = {
            "current": 0,
            "changed": 0,
            "missing_current": 0,
            "superseded_since_baseline": 0,
        }
        items: list[DossierBaselineExposureItem] = []
        current_version = int(requirement["current_version"])
        current = (
            self._version_by_number(connection, str(requirement["requirement_id"]), current_version)
            if current_version
            else None
        )
        for row in rows:
            baseline_version = int(row["version"])
            baseline_hash = str(row["statement_hash"])
            if current is None:
                state = "missing_current"
                current_hash = None
            elif current.version != baseline_version:
                state = "superseded_since_baseline"
                current_hash = current.statement_hash
            elif current.statement_hash != baseline_hash:
                state = "changed"
                current_hash = current.statement_hash
            else:
                state = "current"
                current_hash = current.statement_hash
            summary[state] += 1
            items.append(
                DossierBaselineExposureItem(
                    str(row["baseline_id"]),
                    str(row["name"]),
                    bool(row["locked"]),
                    str(row["created_by"]),
                    str(row["created_at"]),
                    baseline_version,
                    baseline_hash,
                    current.version if current else record.current_version if current_version else None,
                    current_hash,
                    state,
                )
            )
        return DossierBaselineExposure(summary, items)

    def _dossier_computed_gaps(
        self,
        record: RequirementRecord,
        active_draft: RequirementDraft | None,
        criteria: DossierAcceptanceCriteriaSection,
        traces: DossierTraceSection,
        verification: RequirementVerificationStatus,
        baseline_exposure: DossierBaselineExposure,
    ) -> list[DossierComputedGap]:
        gaps: list[DossierComputedGap] = []
        if record.current_version_record is None:
            gaps.append(
                DossierComputedGap(
                    "no_approved_version",
                    "high",
                    "Requirement has no approved current version.",
                    "requirement",
                )
            )
        if active_draft is not None:
            gaps.append(
                DossierComputedGap(
                    "active_draft_pending_review",
                    "medium",
                    "Requirement has an active draft that is not approved.",
                    "requirement",
                )
            )
        if record.current_version > 0 and not criteria.current_version:
            gaps.append(
                DossierComputedGap(
                    "no_acceptance_criteria",
                    "high",
                    "Current approved version has no acceptance criteria.",
                    "acceptance_criteria",
                )
            )
        for reason in verification.reasons:
            if reason.code in {
                "no_verification_method",
                "no_current_evidence",
                "failing_evidence",
                "stale_evidence",
            }:
                gaps.append(DossierComputedGap(reason.code, "high", reason.message, "verification"))
        if any(item.state == "proposed" for item in traces.items):
            gaps.append(
                DossierComputedGap(
                    "proposed_trace_pending_review",
                    "medium",
                    "Requirement has proposed trace links awaiting review.",
                    "traces",
                )
            )
        if any(item.state in {"stale", "orphaned"} for item in traces.items):
            gaps.append(
                DossierComputedGap(
                    "stale_or_orphaned_trace",
                    "high",
                    "Requirement has stale or orphaned trace links.",
                    "traces",
                )
            )
        if any(item.state != "current" for item in baseline_exposure.items):
            gaps.append(
                DossierComputedGap(
                    "baseline_version_drift",
                    "medium",
                    "Requirement differs from at least one containing baseline.",
                    "baseline_exposure",
                )
            )
        return gaps

    def _dossier_next_actions(
        self,
        record: RequirementRecord,
        active_draft: RequirementDraft | None,
        gaps: list[DossierComputedGap],
        verification: RequirementVerificationStatus,
    ) -> list[DossierNextAction]:
        gap_codes = {gap.code for gap in gaps}
        verification_reason_codes = {reason.code for reason in verification.reasons}
        actions: list[DossierNextAction] = []
        if active_draft is not None or "active_draft_pending_review" in gap_codes:
            actions.append(
                DossierNextAction(
                    "approve_or_reject_draft",
                    20,
                    "Review and approve or reject the active draft.",
                    f"plainweave req approve {record.id} --actor human:reviewer "
                    f"--expected-version {record.current_version} --json",
                    ["active_draft_pending_review"],
                )
            )
        if "no_acceptance_criteria" in gap_codes:
            actions.append(
                DossierNextAction(
                    "add_acceptance_criteria",
                    30,
                    "Define acceptance criteria through the proper draft/change flow.",
                    None,
                    ["no_acceptance_criteria"],
                )
            )
        if "no_verification_method" in gap_codes:
            actions.append(
                DossierNextAction(
                    "add_verification_method",
                    40,
                    "Define a verification method for the current version.",
                    f"plainweave verify method add {record.id} --method test "
                    "--target tests/path.py::test_behavior --actor human:reviewer --json",
                    ["no_verification_method"],
                )
            )
        if "no_current_evidence" in gap_codes:
            actions.append(
                DossierNextAction(
                    "record_current_evidence",
                    45,
                    "Record verification evidence for the current version.",
                    None,
                    ["no_current_evidence"],
                )
            )
        if "failing_evidence" in gap_codes:
            actions.append(
                DossierNextAction(
                    "investigate_failing_evidence",
                    50,
                    "Investigate failing verification evidence.",
                    None,
                    ["failing_evidence"],
                )
            )
        if "stale_evidence" in gap_codes:
            actions.append(
                DossierNextAction(
                    "refresh_stale_evidence",
                    60,
                    "Refresh verification evidence for the current version.",
                    None,
                    ["stale_evidence"],
                )
            )
        if "human_waiver" in verification_reason_codes:
            actions.append(
                DossierNextAction(
                    "review_waiver",
                    70,
                    "Review current waiver evidence.",
                    None,
                    ["human_waiver"],
                )
            )
        if "proposed_trace_pending_review" in gap_codes:
            actions.append(
                DossierNextAction(
                    "review_proposed_traces",
                    80,
                    "Review proposed trace links.",
                    None,
                    ["proposed_trace_pending_review"],
                )
            )
        if "stale_or_orphaned_trace" in gap_codes:
            actions.append(
                DossierNextAction(
                    "repair_stale_or_orphaned_traces",
                    85,
                    "Repair stale or orphaned trace links.",
                    None,
                    ["stale_or_orphaned_trace"],
                )
            )
        if "baseline_version_drift" in gap_codes:
            actions.append(
                DossierNextAction(
                    "run_impact_analysis_when_available",
                    90,
                    "Analyze the impact of requirement drift against containing baselines.",
                    None,
                    ["baseline_version_drift"],
                )
            )
        blockers = [
            code
            for code in (
                "no_acceptance_criteria",
                "no_verification_method",
                "no_current_evidence",
                "failing_evidence",
                "stale_evidence",
                "stale_or_orphaned_trace",
            )
            if code in gap_codes
        ]
        if blockers:
            actions.append(
                DossierNextAction(
                    "do_not_treat_as_satisfied",
                    100,
                    "Do not treat this requirement as satisfied until blocking gaps are resolved.",
                    None,
                    blockers,
                )
            )
        return actions

    def _insert_version(
        self,
        connection: sqlite3.Connection,
        requirement: sqlite3.Row,
        draft: sqlite3.Row,
        version_number: int,
        status: str,
        actor: str,
        approved_at: str,
    ) -> RequirementVersion:
        statement = str(draft["statement"])
        version = RequirementVersion(
            str(requirement["requirement_id"]),
            str(requirement["display_id"]),
            str(requirement["stable_id"]),
            version_number,
            str(draft["title"]),
            statement,
            self._statement_hash(statement),
            status,
            actor,
            approved_at,
        )
        connection.execute(
            """
            insert into requirement_versions(
              requirement_id, version, title, statement, statement_hash, status,
              approved_by, approved_at, superseded_by_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version.requirement_id,
                version.version,
                version.title,
                version.statement,
                version.statement_hash,
                version.status,
                version.approved_by,
                version.approved_at,
                None,
            ),
        )
        return version

    def _version_by_number(
        self, connection: sqlite3.Connection, requirement_id: str, version_number: int
    ) -> RequirementVersion | None:
        row = connection.execute(
            """
            select r.display_id, r.stable_id, v.*
            from requirement_versions v
            join requirements r on r.requirement_id = v.requirement_id
            where v.requirement_id = ? and v.version = ?
            """,
            (requirement_id, version_number),
        ).fetchone()
        if row is None:
            return None
        return self._version_from_row(row)

    def _version_from_row(self, row: sqlite3.Row) -> RequirementVersion:
        return RequirementVersion(
            str(row["requirement_id"]),
            str(row["display_id"]),
            str(row["stable_id"]),
            int(row["version"]),
            str(row["title"]),
            str(row["statement"]),
            str(row["statement_hash"]),
            str(row["status"]),
            str(row["approved_by"]),
            str(row["approved_at"]),
        )

    def _requirement_row(self, connection: sqlite3.Connection, requirement_id: str) -> sqlite3.Row:
        row = connection.execute(
            "select * from requirements where display_id = ? or requirement_id = ? or stable_id = ?",
            (requirement_id, requirement_id, requirement_id),
        ).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"requirement not found: {requirement_id}")
        return cast(sqlite3.Row, row)

    def _draft_row(self, connection: sqlite3.Connection, draft_id: str) -> sqlite3.Row:
        row = connection.execute("select * from requirement_drafts where draft_id = ?", (draft_id,)).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"draft not found: {draft_id}")
        return cast(sqlite3.Row, row)

    def _require_current_version(self, requirement: sqlite3.Row, expected_version: int) -> None:
        current_version = int(requirement["current_version"])
        if current_version != expected_version:
            raise self._error(ErrorCode.CONFLICT, "expected version does not match current version")

    def _project_key(self, connection: sqlite3.Connection) -> str:
        metadata = read_schema_meta(connection)
        return metadata["project_key"]

    def _next_requirement_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from requirements").fetchone()[0])
        return count + 1

    def _next_goal_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from intent_goals").fetchone()[0])
        return count + 1

    def _next_intent_edge_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from intent_edges").fetchone()[0])
        return count + 1

    def _next_association_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from entity_associations").fetchone()[0])
        return count + 1

    def _next_criterion_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from acceptance_criteria").fetchone()[0])
        return count + 1

    def _next_criterion_position(self, connection: sqlite3.Connection, requirement_id: str, draft_id: str) -> int:
        value = connection.execute(
            "select max(position) from acceptance_criteria where requirement_id = ? and draft_id = ?",
            (requirement_id, draft_id),
        ).fetchone()[0]
        return int(value) + 1 if value is not None else 1

    def _next_link_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from trace_links").fetchone()[0])
        return count + 1

    def _next_baseline_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from baselines").fetchone()[0])
        return count + 1

    def _next_verification_method_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from verification_methods").fetchone()[0])
        return count + 1

    def _next_evidence_number(self, connection: sqlite3.Connection) -> int:
        count = int(connection.execute("select count(*) from verification_evidence").fetchone()[0])
        return count + 1

    def _baseline_row(self, connection: sqlite3.Connection, baseline_id: str) -> sqlite3.Row:
        row = connection.execute("select * from baselines where baseline_id = ?", (baseline_id,)).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"baseline not found: {baseline_id}")
        return cast(sqlite3.Row, row)

    def _baseline_members(self, connection: sqlite3.Connection, baseline_id: str) -> list[BaselineMember]:
        rows = connection.execute(
            """
            select * from baseline_members
            where baseline_id = ?
            order by display_id, version
            """,
            (baseline_id,),
        ).fetchall()
        return [
            BaselineMember(
                str(row["requirement_id"]),
                str(row["display_id"]),
                str(row["stable_id"]),
                int(row["version"]),
                str(row["statement_hash"]),
                str(row["status_at_baseline"]),
            )
            for row in rows
        ]

    def _baseline_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> Baseline:
        baseline_id = str(row["baseline_id"])
        return Baseline(
            baseline_id,
            str(row["name"]),
            str(row["description"]),
            bool(row["locked"]),
            str(row["created_by"]),
            str(row["created_at"]),
            self._baseline_members(connection, baseline_id),
        )

    def _verification_method_row(self, connection: sqlite3.Connection, method_id: str) -> sqlite3.Row:
        row = connection.execute(
            """
            select r.display_id, vm.*
            from verification_methods vm
            join requirements r on r.requirement_id = vm.requirement_id
            where vm.method_id = ?
            """,
            (method_id,),
        ).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"verification method not found: {method_id}")
        return cast(sqlite3.Row, row)

    def _verification_method_from_row(self, row: sqlite3.Row) -> VerificationMethod:
        return VerificationMethod(
            str(row["method_id"]),
            str(row["display_id"]),
            int(row["requirement_version"]),
            str(row["method_type"]),
            str(row["target"]),
            str(row["status"]),
            str(row["created_by"]),
            str(row["created_at"]),
        )

    def _verification_evidence_row(self, connection: sqlite3.Connection, evidence_id: str) -> sqlite3.Row:
        row = connection.execute(
            """
            select r.display_id, ve.*
            from verification_evidence ve
            join requirements r on r.requirement_id = ve.requirement_id
            where ve.evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"verification evidence not found: {evidence_id}")
        return cast(sqlite3.Row, row)

    def _verification_evidence_from_row(
        self,
        row: sqlite3.Row,
        current_version: int | None = None,
    ) -> VerificationEvidence:
        payload = json.loads(str(row["payload_json"]))
        requirement_version = int(row["requirement_version"])
        freshness = str(row["freshness"])
        if current_version is not None and requirement_version != current_version:
            freshness = "stale"
        return VerificationEvidence(
            str(row["evidence_id"]),
            str(row["method_id"]),
            str(row["display_id"]),
            requirement_version,
            str(row["status"]),
            str(row["evidence_ref"]),
            str(row["authority"]),
            freshness,
            str(row["recorded_by"]),
            str(row["recorded_at"]),
            payload if isinstance(payload, dict) else {},
        )

    def _verification_evidence_for_requirement(
        self,
        connection: sqlite3.Connection,
        requirement_id: str,
        current_version: int,
    ) -> list[VerificationEvidence]:
        rows = connection.execute(
            """
            select r.display_id, ve.*
            from verification_evidence ve
            join requirements r on r.requirement_id = ve.requirement_id
            where ve.requirement_id = ?
            order by recorded_at, evidence_id
            """,
            (requirement_id,),
        ).fetchall()
        return [self._verification_evidence_from_row(row, current_version) for row in rows]

    def _verification_status_for_row(
        self,
        connection: sqlite3.Connection,
        requirement: sqlite3.Row,
    ) -> RequirementVerificationStatus:
        current_version = int(requirement["current_version"])
        requirement_id = str(requirement["requirement_id"])
        evidence = self._verification_evidence_for_requirement(connection, requirement_id, current_version)
        current_evidence = [item for item in evidence if item.requirement_version == current_version]
        stale_evidence = [item for item in evidence if item.requirement_version != current_version]
        method_count = int(
            connection.execute(
                "select count(*) from verification_methods where requirement_id = ?",
                (requirement_id,),
            ).fetchone()[0]
        )
        status, reasons = self._compute_verification_status(
            str(requirement["status"]),
            method_count,
            current_evidence,
            stale_evidence,
        )
        return RequirementVerificationStatus(
            requirement_id,
            str(requirement["display_id"]),
            str(requirement["stable_id"]),
            current_version,
            status,
            reasons,
            current_evidence,
            stale_evidence,
        )

    def _compute_verification_status(
        self,
        requirement_status: str,
        method_count: int,
        current_evidence: list[VerificationEvidence],
        stale_evidence: list[VerificationEvidence],
    ) -> tuple[str, list[VerificationReason]]:
        if requirement_status not in {"approved", "deprecated"}:
            return "unknown", [VerificationReason("requirement_not_approved", "Requirement is not approved.")]
        if any(item.status == "failing" for item in current_evidence):
            evidence = next(item for item in current_evidence if item.status == "failing")
            return "unsatisfied", [
                VerificationReason(
                    "failing_evidence",
                    "Current failing evidence makes the requirement unsatisfied.",
                    evidence.id,
                )
            ]
        if any(item.status == "waived" and item.authority == "waiver" for item in current_evidence):
            evidence = next(item for item in current_evidence if item.status == "waived" and item.authority == "waiver")
            return "waived", [
                VerificationReason(
                    "human_waiver",
                    "Current human waiver evidence waives verification.",
                    evidence.id,
                )
            ]
        if any(item.status == "passing" for item in current_evidence):
            evidence = next(item for item in current_evidence if item.status == "passing")
            return "satisfied", [
                VerificationReason(
                    "passing_evidence",
                    "Current passing evidence satisfies the requirement version.",
                    evidence.id,
                )
            ]
        if any(item.status == "inconclusive" for item in current_evidence):
            evidence = next(item for item in current_evidence if item.status == "inconclusive")
            return "unknown", [
                VerificationReason("inconclusive_evidence", "Current evidence is inconclusive.", evidence.id)
            ]
        if stale_evidence:
            evidence = stale_evidence[-1]
            return "stale", [
                VerificationReason(
                    "stale_evidence",
                    "Only stale evidence is available for the current requirement version.",
                    evidence.id,
                )
            ]
        if method_count:
            return "unverified", [VerificationReason("no_current_evidence", "No current evidence has been recorded.")]
        return "unverified", [VerificationReason("no_verification_method", "No verification method has been defined.")]

    def _list_requirement_statuses(self, statuses: set[str]) -> list[RequirementVerificationStatus]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                select * from requirements
                where current_version > 0 and status in ('approved', 'deprecated')
                order by display_id
                """
            ).fetchall()
            items = [self._verification_status_for_row(connection, row) for row in rows]
        return [item for item in items if item.status in statuses]

    def _criterion_from_row(self, row: sqlite3.Row) -> AcceptanceCriterion:
        return AcceptanceCriterion(
            str(row["criterion_id"]),
            str(row["requirement_id"]),
            row["draft_id"] if isinstance(row["draft_id"], str) else None,
            self._optional_int(row["version"]),
            int(row["position"]),
            str(row["text"]),
            str(row["status"]),
            str(row["created_by"]),
            str(row["created_at"]),
        )

    def _transition_trace(
        self,
        link_id: str,
        *,
        actor: str,
        state: str,
        authority: str | None = None,
        freshness: str | None = None,
        reason: str | None = None,
    ) -> TraceLink:
        self._require_actor(actor)
        now = self._now()
        with connect(self.db_path) as connection:
            row = self._trace_row(connection, link_id)
            self._validate_trace_transition(str(row["state"]), state)
            if state == "accepted":
                self._require_accepted_trace_targets(connection, TraceRef(str(row["to_kind"]), str(row["to_id"])))
                normalized_from_ref, target_snapshot = self._normalize_trace_refs(
                    TraceRef(str(row["from_kind"]), str(row["from_id"]))
                )
            else:
                normalized_from_ref = TraceRef(str(row["from_kind"]), str(row["from_id"]))
                target_snapshot = self._snapshot_from_row(row)
            next_authority = authority or str(row["authority"])
            next_freshness = freshness or str(row["freshness"])
            accepted_by = actor if state == "accepted" else row["accepted_by"]
            connection.execute(
                """
                update trace_links
                set state = ?, from_id = ?, authority = ?, freshness = ?, accepted_by = ?, updated_at = ?,
                    target_snapshot_json = ?
                where link_id = ?
                """,
                (
                    state,
                    normalized_from_ref.id,
                    next_authority,
                    next_freshness,
                    accepted_by,
                    now,
                    json.dumps(target_snapshot, sort_keys=True),
                    link_id,
                ),
            )
            self._record_event(
                connection,
                f"trace_link_{state}",
                "trace_link",
                link_id,
                actor,
                None,
                {"link_id": link_id, "state": state, "reason": reason},
                now,
            )
            connection.commit()
            return self._trace_from_row(self._trace_row(connection, link_id))

    def _trace_row(self, connection: sqlite3.Connection, link_id: str) -> sqlite3.Row:
        row = connection.execute("select * from trace_links where link_id = ?", (link_id,)).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"trace link not found: {link_id}")
        return cast(sqlite3.Row, row)

    def _trace_from_row(self, row: sqlite3.Row) -> TraceLink:
        snapshot = self._snapshot_from_row(row)
        link = TraceLink(
            str(row["link_id"]),
            str(row["state"]),
            TraceRef(str(row["from_kind"]), str(row["from_id"])),
            str(row["relation"]),
            TraceRef(str(row["to_kind"]), str(row["to_id"])),
            str(row["authority"]),
            str(row["freshness"]),
            float(row["confidence"]) if row["confidence"] is not None else None,
            str(row["created_by"]),
            row["accepted_by"] if isinstance(row["accepted_by"], str) else None,
            snapshot,
        )
        if link.from_ref.kind == "loomweave_entity" and link.state not in {"rejected", "stale", "orphaned"}:
            return self._enrich_loomweave_trace(link)
        return link

    def _snapshot_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        snapshot = json.loads(str(row["target_snapshot_json"]))
        return snapshot if isinstance(snapshot, dict) else {}

    def _normalize_trace_refs(self, from_ref: TraceRef) -> tuple[TraceRef, dict[str, Any]]:
        if from_ref.kind != "loomweave_entity":
            return from_ref, {}
        try:
            snapshot = self._loomweave_adapter().resolve_identity(from_ref.id)
        except LoomweaveIdentityError as exc:
            raise self._loomweave_error(exc) from exc
        if snapshot.sei is None:
            raise self._error(ErrorCode.UNSUPPORTED, "Loomweave entity has no stable identity")
        return TraceRef("loomweave_entity", snapshot.sei), snapshot.to_dict()

    def _enrich_loomweave_trace(self, link: TraceLink) -> TraceLink:
        lookup = self._snapshot_lookup(link)
        if lookup is None:
            return link
        try:
            current = self._loomweave_adapter().resolve_identity(lookup)
        except LoomweaveIdentityError as exc:
            return self._trace_with_degraded_snapshot(link, exc)
        snapshot = current.to_dict()
        attached_hash = self._attached_hash(link.target_snapshot)
        if attached_hash is not None:
            snapshot["content_hash_at_attach"] = attached_hash
        freshness = "current"
        if attached_hash is not None and current.content_hash is not None and attached_hash != current.content_hash:
            freshness = "stale"
            degraded = self._snapshot_degraded(snapshot)
            degraded.append(
                {
                    "code": "content_hash_drift",
                    "message": "Current Loomweave content hash differs from the attach-time hash.",
                }
            )
            snapshot["degraded"] = degraded
        snapshot["freshness"] = freshness
        return TraceLink(
            link.id,
            link.state,
            link.from_ref,
            link.relation,
            link.to_ref,
            link.authority,
            freshness,
            link.confidence,
            link.created_by,
            link.accepted_by,
            snapshot,
        )

    def _trace_with_degraded_snapshot(self, link: TraceLink, exc: LoomweaveIdentityError) -> TraceLink:
        snapshot = dict(link.target_snapshot)
        degraded = self._snapshot_degraded(snapshot)
        degraded.append(self._loomweave_adapter().snapshot_error(exc))
        snapshot["degraded"] = degraded
        freshness = "orphaned" if exc.reason in {"orphaned", "not_found"} else "unknown"
        snapshot["freshness"] = freshness
        if freshness == "orphaned":
            snapshot["lineage_status"] = "orphaned"
        return TraceLink(
            link.id,
            link.state,
            link.from_ref,
            link.relation,
            link.to_ref,
            link.authority,
            freshness,
            link.confidence,
            link.created_by,
            link.accepted_by,
            snapshot,
        )

    def _snapshot_lookup(self, link: TraceLink) -> str | None:
        sei = link.target_snapshot.get("sei")
        if isinstance(sei, str) and sei:
            return sei
        if link.from_ref.id:
            return link.from_ref.id
        return None

    def _attached_hash(self, snapshot: dict[str, Any]) -> str | None:
        attached = snapshot.get("content_hash_at_attach")
        if isinstance(attached, str):
            return attached
        content_hash = snapshot.get("content_hash")
        return content_hash if isinstance(content_hash, str) else None

    def _snapshot_degraded(self, snapshot: dict[str, Any]) -> list[dict[str, object]]:
        degraded = snapshot.get("degraded")
        if not isinstance(degraded, list):
            return []
        return [dict(item) for item in degraded if isinstance(item, dict)]

    def _dossier_peer_facts(self, traces: DossierTraceSection) -> DossierPeerFacts:
        loomweave_traces = [
            item
            for item in traces.items
            if item.from_ref.kind == "loomweave_entity" or isinstance(item.target_snapshot.get("sei"), str)
        ]
        if not loomweave_traces:
            return DossierPeerFacts(
                False,
                [],
                ["Dossier is computed from the local Plainweave store only."],
            )
        capability = self._loomweave_adapter().adapter_capability()
        degraded = capability["degraded"] if isinstance(capability["degraded"], list) else []
        notes = ["Dossier includes Loomweave identity snapshots from local trace links."]
        for item in degraded:
            if isinstance(item, dict) and isinstance(item.get("message"), str):
                notes.append(str(item["message"]))
        status = capability["adapter_status"] if isinstance(capability["adapter_status"], dict) else {}
        if status.get("identity_http") == "configured":
            # A configured HTTP endpoint is a *capability*, not evidence a live call
            # was made: the dossier is computed from local state only, so
            # live_peer_calls stays False and the capability is recorded as a note.
            notes.append("A Loomweave HTTP identity endpoint is configured but was not called for this dossier.")
        return DossierPeerFacts(
            False,
            ["loomweave"],
            notes,
        )

    def _loomweave_adapter(self) -> LoomweaveAdapter:
        return LoomweaveAdapter(self.root)

    def _loomweave_error(self, exc: LoomweaveIdentityError) -> PlainweaveError:
        code = {
            "not_found": ErrorCode.NOT_FOUND,
            "orphaned": ErrorCode.CONFLICT,
            "unreachable": ErrorCode.PEER_ABSENT,
            "unsupported": ErrorCode.UNSUPPORTED,
        }.get(exc.reason, ErrorCode.INTERNAL)
        return PlainweaveError(
            code,
            exc.message,
            recoverable=True,
            hint="Resolve the Loomweave entity through Loomweave and retry with an alive SEI or locator.",
            details={"reason": exc.reason, "degraded": exc.degraded},
        )

    def _goal_row(self, connection: sqlite3.Connection, goal_id: str) -> sqlite3.Row:
        row = connection.execute(
            "select * from intent_goals where goal_id = ? or display_id = ? or stable_id = ?",
            (goal_id, goal_id, goal_id),
        ).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"goal not found: {goal_id}")
        return cast(sqlite3.Row, row)

    def _intent_edge_row(self, connection: sqlite3.Connection, edge_id: str) -> sqlite3.Row:
        row = connection.execute("select * from intent_edges where edge_id = ?", (edge_id,)).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"intent edge not found: {edge_id}")
        return cast(sqlite3.Row, row)

    def _association_row(self, connection: sqlite3.Connection, association_id: str) -> sqlite3.Row:
        row = connection.execute(
            "select * from entity_associations where association_id = ?",
            (association_id,),
        ).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"entity association not found: {association_id}")
        return cast(sqlite3.Row, row)

    def _code_entity_row(self, connection: sqlite3.Connection, entity_id: str) -> sqlite3.Row:
        row = connection.execute("select * from code_entities where entity_id = ?", (entity_id,)).fetchone()
        if row is None:
            raise self._error(ErrorCode.NOT_FOUND, f"code entity not found: {entity_id}")
        return cast(sqlite3.Row, row)

    def _goal_from_row(self, row: sqlite3.Row) -> IntentGoal:
        return IntentGoal(
            str(row["goal_id"]),
            str(row["display_id"]),
            str(row["stable_id"]),
            str(row["title"]),
            str(row["statement"]),
            str(row["status"]),
            str(row["created_by"]),
            str(row["created_at"]),
        )

    def _intent_edge_from_row(self, row: sqlite3.Row) -> IntentEdge:
        return IntentEdge(
            str(row["edge_id"]),
            str(row["goal_id"]),
            str(row["requirement_id"]),
            str(row["relation"]),
            str(row["authority"]),
            str(row["freshness"]),
            str(row["created_by"]),
            str(row["created_at"]),
        )

    def _code_entity_from_row(self, row: sqlite3.Row) -> CodeEntity:
        return CodeEntity(
            str(row["entity_id"]),
            str(row["entity_kind"]),
            row["display_name"] if isinstance(row["display_name"], str) else None,
            row["content_hash"] if isinstance(row["content_hash"], str) else None,
            bool(row["public"]),
            str(row["source"]),
            str(row["freshness"]),
            str(row["recorded_by"]),
            str(row["recorded_at"]),
        )

    def _binding_from_row(self, row: sqlite3.Row) -> SeiBinding:
        provenance = json.loads(str(row["provenance_json"]))
        return SeiBinding(
            str(row["entity_id"]),
            str(row["entity_kind"]),
            str(row["requirement_id"]),
            row["content_hash_at_attach"] if isinstance(row["content_hash_at_attach"], str) else None,
            str(row["drift_status"]),
            str(row["freshness"]),
            str(row["bound_by"]),
            str(row["bound_at"]),
            provenance if isinstance(provenance, dict) else {},
        )

    def _goal_ids_for_requirement(self, connection: sqlite3.Connection, requirement_id: str) -> list[str]:
        rows = connection.execute(
            """
            select goal_id from intent_edges
            where requirement_id = ? and relation = ? and freshness = ?
            order by goal_id
            """,
            (requirement_id, "justifies", "current"),
        ).fetchall()
        return [str(row["goal_id"]) for row in rows]

    def _requirement_ids_for_goal(self, connection: sqlite3.Connection, goal_id: str) -> list[str]:
        rows = connection.execute(
            """
            select requirement_id from intent_edges
            where goal_id = ? and relation = ? and freshness = ?
            order by requirement_id
            """,
            (goal_id, "justifies", "current"),
        ).fetchall()
        return [str(row["requirement_id"]) for row in rows]

    def _requirement_ids_for_entity(self, connection: sqlite3.Connection, entity_id: str) -> list[str]:
        rows = connection.execute(
            """
            select requirement_id from entity_associations
            where entity_id = ? and relation = ?
            order by requirement_id
            """,
            (entity_id, "satisfies"),
        ).fetchall()
        return [str(row["requirement_id"]) for row in rows]

    def _live_requirement_ids_for_entity(self, connection: sqlite3.Connection, entity_id: str) -> list[str]:
        """Requirement ids bound to ``entity_id`` that are still live (``draft``/``approved``).
        Deprecated requirements are excluded so :meth:`intent_coverage` never counts a dead
        obligation as live justification."""
        rows = connection.execute(
            """
            select a.requirement_id
            from entity_associations a
            join requirements r on r.requirement_id = a.requirement_id
            where a.entity_id = ? and a.relation = ? and r.status in ('draft', 'approved')
            order by a.requirement_id
            """,
            (entity_id, "satisfies"),
        ).fetchall()
        return [str(row["requirement_id"]) for row in rows]

    def _entity_ids_for_requirement(self, connection: sqlite3.Connection, requirement_id: str) -> list[str]:
        rows = connection.execute(
            """
            select entity_id from entity_associations
            where requirement_id = ? and relation = ?
            order by entity_id
            """,
            (requirement_id, "satisfies"),
        ).fetchall()
        return [str(row["entity_id"]) for row in rows]

    def _dedupe_nodes(self, nodes: list[IntentNode]) -> list[IntentNode]:
        seen: set[IntentNode] = set()
        deduped: list[IntentNode] = []
        for node in nodes:
            if node in seen:
                continue
            seen.add(node)
            deduped.append(node)
        return deduped

    def _validate_trace_relation(self, from_ref: TraceRef, relation: str, to_ref: TraceRef) -> None:
        allowed = {
            ("loomweave_entity", "satisfies", "requirement_version"),
            ("file_ref", "fragile_satisfies", "requirement_version"),
            ("verification_method", "verifies", "requirement_version"),
            ("verification_record", "evidences", "verification_method"),
            ("test_selector", "provides_evidence_for", "verification_method"),
            ("filigree_issue", "implements_work_for", "requirement_version"),
            ("filigree_issue", "resolves_gap", "gap"),
            ("wardline_finding", "violates", "acceptance_criterion"),
            ("legis_attestation", "attests", "requirement_version"),
        }
        if (from_ref.kind, relation, to_ref.kind) not in allowed:
            raise self._error(ErrorCode.VALIDATION, "trace relation is not canonical")

    def _validate_trace_transition(self, current: str, target: str) -> None:
        allowed = {
            "proposed": {"accepted", "rejected", "stale"},
            "accepted": {"stale", "orphaned"},
            "stale": {"proposed", "accepted", "rejected"},
            "orphaned": {"proposed", "rejected"},
        }
        if target not in allowed.get(current, set()):
            raise self._error(ErrorCode.CONFLICT, "trace state transition is not allowed")

    def _record_event(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        actor: str,
        idempotency_key: str | None,
        payload: dict[str, object],
        created_at: str,
    ) -> None:
        connection.execute(
            """
            insert into events(
              event_id, event_type, aggregate_type, aggregate_id,
              actor, idempotency_key, payload_json, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"EVT-{uuid.uuid4().hex}",
                event_type,
                aggregate_type,
                aggregate_id,
                actor,
                idempotency_key,
                json.dumps(payload, sort_keys=True),
                created_at,
            ),
        )

    def _store_idempotency(
        self,
        connection: sqlite3.Connection,
        key: str | None,
        operation: str,
        target_id: str,
        response: RequirementVersion | RequirementRecord,
        *,
        request: dict[str, object],
    ) -> None:
        if key is None:
            return
        if isinstance(response, RequirementVersion):
            payload = {"kind": "version", "data": asdict(response)}
        else:
            payload = {"kind": "record", "data": self._record_dict(response)}
        request_hash = self._request_hash(request)
        connection.execute(
            """
            insert into idempotency_keys(key, operation, target_id, request_hash, response_json, created_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            (key, operation, target_id, request_hash, json.dumps(payload, sort_keys=True), self._now()),
        )

    def _idempotent_version(
        self,
        key: str | None,
        *,
        operation: str,
        request: dict[str, object],
    ) -> RequirementVersion | None:
        payload = self._idempotency_payload(key, operation=operation, request=request)
        if payload is None or payload["kind"] != "version":
            return None
        return self._version_from_dict(payload["data"])

    def _idempotent_record(
        self,
        key: str | None,
        *,
        operation: str,
        request: dict[str, object],
    ) -> RequirementRecord | None:
        payload = self._idempotency_payload(key, operation=operation, request=request)
        if payload is None or payload["kind"] != "record":
            return None
        return self._record_from_dict(payload["data"])

    def _idempotency_payload(
        self,
        key: str | None,
        *,
        operation: str,
        request: dict[str, object],
    ) -> dict[str, Any] | None:
        if key is None:
            return None
        with connect(self.db_path) as connection:
            row = connection.execute(
                "select operation, target_id, request_hash, response_json from idempotency_keys where key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        if str(row["operation"]) != operation:
            raise self._error(ErrorCode.CONFLICT, "idempotency key was used for a different operation")
        if row["request_hash"] is None:
            raise self._error(ErrorCode.CONFLICT, "idempotency key has no request fingerprint")
        if str(row["request_hash"]) != self._request_hash(request):
            raise self._error(ErrorCode.CONFLICT, "idempotency key was used for a different payload")
        payload = json.loads(str(row["response_json"]))
        if not isinstance(payload, dict):
            return None
        return payload

    def _version_from_dict(self, data: object) -> RequirementVersion:
        if not isinstance(data, dict):
            raise self._error(ErrorCode.INTERNAL, "invalid idempotency payload")
        return RequirementVersion(
            str(data["requirement_id"]),
            str(data["id"]),
            str(data["stable_id"]),
            int(data["version"]),
            str(data["title"]),
            str(data["statement"]),
            str(data["statement_hash"]),
            str(data["status"]),
            str(data["approved_by"]),
            str(data["approved_at"]),
        )

    def _record_from_dict(self, data: object) -> RequirementRecord:
        if not isinstance(data, dict):
            raise self._error(ErrorCode.INTERNAL, "invalid idempotency payload")
        version_data = data["current_version_record"]
        return RequirementRecord(
            str(data["requirement_id"]),
            str(data["id"]),
            str(data["stable_id"]),
            int(data["current_version"]),
            data["active_draft_id"] if isinstance(data["active_draft_id"], str) else None,
            str(data["status"]),
            self._version_from_dict(version_data) if version_data is not None else None,
        )

    def _record_dict(self, record: RequirementRecord) -> dict[str, object]:
        return {
            "requirement_id": record.requirement_id,
            "id": record.id,
            "stable_id": record.stable_id,
            "current_version": record.current_version,
            "active_draft_id": record.active_draft_id,
            "status": record.status,
            "current_version_record": asdict(record.current_version_record) if record.current_version_record else None,
        }

    def _statement_hash(self, statement: str) -> str:
        return "sha256:" + hashlib.sha256(statement.encode("utf-8")).hexdigest()

    def _request_hash(self, request: dict[str, object]) -> str:
        payload = json.dumps(request, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _matches_requirement(self, version: RequirementVersion, requirement_id: str) -> bool:
        return requirement_id in {version.id, version.requirement_id, version.stable_id}

    def _matches_record(self, record: RequirementRecord, requirement_id: str) -> bool:
        return requirement_id in {record.id, record.requirement_id, record.stable_id}

    def _require_accepted_trace_targets(self, connection: sqlite3.Connection, to_ref: TraceRef) -> None:
        if to_ref.kind != "requirement_version":
            return
        try:
            requirement_id, version_text = to_ref.id.rsplit("@", 1)
            version = int(version_text)
        except ValueError:
            raise self._error(
                ErrorCode.VALIDATION,
                "requirement_version trace target must use REQ-ID@version",
            ) from None
        requirement = self._requirement_row(connection, requirement_id)
        if self._version_by_number(connection, str(requirement["requirement_id"]), version) is None:
            raise self._error(ErrorCode.NOT_FOUND, f"requirement version not found: {to_ref.id}")

    def _require_actor(self, actor: str) -> None:
        if not actor:
            raise self._error(ErrorCode.VALIDATION, "actor is required")

    def _validate_verification_method(self, method: str) -> None:
        if method not in {"test", "analysis", "inspection", "manual"}:
            raise self._error(ErrorCode.VALIDATION, "verification method is not supported")

    def _validate_evidence_status(self, status: str) -> None:
        if status not in {"passing", "failing", "inconclusive", "waived"}:
            raise self._error(ErrorCode.VALIDATION, "verification evidence status is not supported")

    def _actor_kind(self, connection: sqlite3.Connection, actor: str) -> str | None:
        """Return the registered kind for ``actor`` or ``None`` if unregistered."""
        row = connection.execute("select kind from actors where actor_id = ?", (actor,)).fetchone()
        return str(row["kind"]) if row is not None and row["kind"] is not None else None

    def _attester_exists(self, connection: sqlite3.Connection) -> bool:
        """True if any human/attester actor is already registered (genesis done)."""
        placeholders = ", ".join("?" for _ in self.ATTESTER_KINDS)
        row = connection.execute(
            f"select 1 from actors where kind in ({placeholders}) limit 1",
            tuple(sorted(self.ATTESTER_KINDS)),
        ).fetchone()
        return row is not None

    def _evidence_authority(self, connection: sqlite3.Connection, method: str, status: str, actor: str) -> str:
        # Authority is resolved from the registered actor record, not from the
        # honour-system actor string. An unregistered actor (no prefix, a
        # spoofed ``human:`` prefix, or anything else) defaults to the
        # least-privileged ``agent_reported`` and is denied waiver/manual
        # attestation. Only a registered human/attester may carry external or
        # manual attestation authority.
        is_attester = self._actor_kind(connection, actor) in self.ATTESTER_KINDS
        if status == "waived":
            if not is_attester:
                raise self._error(
                    ErrorCode.POLICY_REQUIRED,
                    "waiver evidence requires a registered human attester",
                )
            return "waiver"
        if method == "manual" and not is_attester:
            raise self._error(
                ErrorCode.POLICY_REQUIRED,
                "manual attestation evidence requires a registered human attester",
            )
        if method == "test":
            return "test_derived"
        if is_attester:
            return "human_attested"
        return "agent_reported"

    def _error(self, code: ErrorCode, message: str) -> PlainweaveError:
        return PlainweaveError(code, message, recoverable=True, hint="Refresh local Plainweave state and retry.")

    def _optional_int(self, value: object) -> int | None:
        return int(str(value)) if value is not None else None

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
