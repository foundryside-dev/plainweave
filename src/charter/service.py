from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from charter.errors import CharterError, ErrorCode
from charter.models import (
    AcceptanceCriterion,
    Baseline,
    BaselineDiff,
    BaselineDiffItem,
    BaselineMember,
    RequirementDraft,
    RequirementRecord,
    RequirementVersion,
    RequirementVerificationStatus,
    TraceLink,
    TraceRef,
    VerificationEvidence,
    VerificationMethod,
    VerificationReason,
)
from charter.store import connect, read_schema_meta


class CharterService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

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
            authority = self._evidence_authority(str(method["method_type"]), status, actor)
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
            return self._verification_evidence_from_row(self._verification_evidence_row(connection, evidence_id), current_version)

    def verification_status(self, requirement_id: str) -> RequirementVerificationStatus:
        with connect(self.db_path) as connection:
            requirement = self._requirement_row(connection, requirement_id)
            return self._verification_status_for_row(connection, requirement)

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
            stable_id = f"charter:req:{project_key}:{number:04d}"
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
                    "{}",
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
                link_id, state, from_ref, relation, to_ref, authority, "current", confidence, actor, accepted_by, {}
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
                VerificationReason("failing_evidence", "Current failing evidence makes the requirement unsatisfied.", evidence.id)
            ]
        if any(item.status == "waived" and item.authority == "waiver" for item in current_evidence):
            evidence = next(item for item in current_evidence if item.status == "waived" and item.authority == "waiver")
            return "waived", [VerificationReason("human_waiver", "Current human waiver evidence waives verification.", evidence.id)]
        if any(item.status == "passing" for item in current_evidence):
            evidence = next(item for item in current_evidence if item.status == "passing")
            return "satisfied", [
                VerificationReason("passing_evidence", "Current passing evidence satisfies the requirement version.", evidence.id)
            ]
        if any(item.status == "inconclusive" for item in current_evidence):
            evidence = next(item for item in current_evidence if item.status == "inconclusive")
            return "unknown", [
                VerificationReason("inconclusive_evidence", "Current evidence is inconclusive.", evidence.id)
            ]
        if stale_evidence:
            evidence = stale_evidence[-1]
            return "stale", [
                VerificationReason("stale_evidence", "Only stale evidence is available for the current requirement version.", evidence.id)
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
            next_authority = authority or str(row["authority"])
            next_freshness = freshness or str(row["freshness"])
            accepted_by = actor if state == "accepted" else row["accepted_by"]
            connection.execute(
                """
                update trace_links
                set state = ?, authority = ?, freshness = ?, accepted_by = ?, updated_at = ?
                where link_id = ?
                """,
                (state, next_authority, next_freshness, accepted_by, now, link_id),
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
        snapshot = json.loads(str(row["target_snapshot_json"]))
        return TraceLink(
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
            snapshot if isinstance(snapshot, dict) else {},
        )

    def _validate_trace_relation(self, from_ref: TraceRef, relation: str, to_ref: TraceRef) -> None:
        allowed = {
            ("clarion_entity", "satisfies", "requirement_version"),
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

    def _evidence_authority(self, method: str, status: str, actor: str) -> str:
        actor_is_agent = actor.startswith("agent:")
        if status == "waived":
            if actor_is_agent:
                raise self._error(ErrorCode.POLICY_REQUIRED, "agents cannot record waiver evidence")
            return "waiver"
        if method == "manual" and actor_is_agent:
            raise self._error(ErrorCode.POLICY_REQUIRED, "agents cannot record manual attestation evidence")
        if method == "test":
            return "test_derived"
        if actor.startswith("human:"):
            return "human_attested"
        return "agent_reported"

    def _error(self, code: ErrorCode, message: str) -> CharterError:
        return CharterError(code, message, recoverable=True, hint="Refresh local Charter state and retry.")

    def _optional_int(self, value: object) -> int | None:
        return int(str(value)) if value is not None else None

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
