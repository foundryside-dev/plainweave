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
from charter.models import AcceptanceCriterion, RequirementDraft, RequirementRecord, RequirementVersion
from charter.store import connect, read_schema_meta


class CharterService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

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
        cached = self._idempotent_version(idempotency_key)
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
            self._store_idempotency(connection, idempotency_key, "approve_requirement", requirement_id, version)
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
        cached = self._idempotent_version(idempotency_key)
        if cached is not None:
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
            self._store_idempotency(connection, idempotency_key, "supersede_requirement", requirement_id, version)
            connection.commit()
            return version

    def deprecate_requirement(
        self,
        requirement_id: str,
        *,
        actor: str,
        expected_version: int,
        idempotency_key: str | None = None,
    ) -> RequirementRecord:
        self._require_actor(actor)
        cached = self._idempotent_record(idempotency_key)
        if cached is not None:
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
            self._store_idempotency(connection, idempotency_key, "deprecate_requirement", requirement_id, record)
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
        )

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
    ) -> None:
        if key is None:
            return
        if isinstance(response, RequirementVersion):
            payload = {"kind": "version", "data": asdict(response)}
        else:
            payload = {"kind": "record", "data": self._record_dict(response)}
        connection.execute(
            """
            insert into idempotency_keys(key, operation, target_id, response_json, created_at)
            values (?, ?, ?, ?, ?)
            """,
            (key, operation, target_id, json.dumps(payload, sort_keys=True), self._now()),
        )

    def _idempotent_version(self, key: str | None) -> RequirementVersion | None:
        payload = self._idempotency_payload(key)
        if payload is None or payload["kind"] != "version":
            return None
        return self._version_from_dict(payload["data"])

    def _idempotent_record(self, key: str | None) -> RequirementRecord | None:
        payload = self._idempotency_payload(key)
        if payload is None or payload["kind"] != "record":
            return None
        return self._record_from_dict(payload["data"])

    def _idempotency_payload(self, key: str | None) -> dict[str, Any] | None:
        if key is None:
            return None
        with connect(self.db_path) as connection:
            row = connection.execute("select response_json from idempotency_keys where key = ?", (key,)).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row[0]))
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

    def _matches_requirement(self, version: RequirementVersion, requirement_id: str) -> bool:
        return requirement_id in {version.id, version.requirement_id, version.stable_id}

    def _require_actor(self, actor: str) -> None:
        if not actor:
            raise self._error(ErrorCode.VALIDATION, "actor is required")

    def _error(self, code: ErrorCode, message: str) -> CharterError:
        return CharterError(code, message, recoverable=True, hint="Refresh local Charter state and retry.")

    def _optional_int(self, value: object) -> int | None:
        return int(str(value)) if value is not None else None

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
