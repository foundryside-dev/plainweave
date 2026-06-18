from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from plainweave.store import connect, migrate


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "select name from sqlite_master where type = 'table' and name not like 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"pragma table_info({table})").fetchall()}


def test_migration_creates_required_tables_and_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"

    migrate(db_path, project_key="AUTH")
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        assert table_names(connection) == {
            "schema_meta",
            "actors",
            "requirements",
            "requirement_drafts",
            "requirement_versions",
            "acceptance_criteria",
            "trace_links",
            "baselines",
            "baseline_members",
            "verification_methods",
            "verification_evidence",
            "events",
            "idempotency_keys",
        }
        metadata = dict(connection.execute("select key, value from schema_meta").fetchall())
        assert metadata == {"project_key": "AUTH", "schema_version": "1"}


def test_store_connections_enable_foreign_keys(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        assert connection.execute("pragma foreign_keys").fetchone()[0] == 1


def test_store_connections_configure_busy_timeout(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        assert int(connection.execute("pragma busy_timeout").fetchone()[0]) >= 5000


def test_requirements_table_does_not_store_mutable_approved_text(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        assert "statement" not in columns(connection, "requirements")
        assert {"title", "statement", "statement_hash"} <= columns(connection, "requirement_versions")


def test_requirement_version_statement_is_immutable(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        connection.execute(
            """
            insert into requirements(
              requirement_id, display_id, stable_id, current_version, active_draft_id,
              status, type, criticality, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-1",
                "REQ-AUTH-001",
                "plainweave:req:AUTH:001",
                1,
                None,
                "approved",
                "functional",
                "medium",
                "2026-06-04T10:00:00+10:00",
                "2026-06-04T10:00:00+10:00",
            ),
        )
        connection.execute(
            """
            insert into requirement_versions(
              requirement_id, version, title, statement, statement_hash, status,
              approved_by, approved_at, superseded_by_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-1",
                1,
                "Reject expired bearer tokens",
                "The API shall reject expired bearer tokens.",
                "sha256:old",
                "approved",
                "human:john",
                "2026-06-04T10:00:00+10:00",
                None,
            ),
        )

        with pytest.raises(sqlite3.IntegrityError, match="requirement version text is immutable"):
            connection.execute(
                """
                update requirement_versions
                set statement = ?, statement_hash = ?
                where requirement_id = ? and version = ?
                """,
                ("Changed text.", "sha256:new", "req-1", 1),
            )


def test_events_are_append_only(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        connection.execute(
            """
            insert into events(
              event_id, event_type, aggregate_type, aggregate_id,
              actor, idempotency_key, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EVT-1",
                "requirement_created",
                "requirement",
                "req-1",
                "human:john",
                None,
                "{}",
                "2026-06-04T10:00:00+10:00",
            ),
        )

        with pytest.raises(sqlite3.IntegrityError, match="events are append-only"):
            connection.execute(
                "update events set payload_json = ? where event_id = ?",
                ('{"changed": true}', "EVT-1"),
            )

        with pytest.raises(sqlite3.IntegrityError, match="events are append-only"):
            connection.execute("delete from events where event_id = ?", ("EVT-1",))


def test_baseline_tables_store_locked_snapshot_members(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        assert columns(connection, "baselines") == {
            "baseline_id",
            "name",
            "description",
            "locked",
            "created_by",
            "created_at",
        }
        assert columns(connection, "baseline_members") == {
            "baseline_id",
            "requirement_id",
            "version",
            "display_id",
            "stable_id",
            "statement_hash",
            "status_at_baseline",
        }


def test_baseline_members_are_immutable(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        connection.execute(
            """
            insert into requirements(
              requirement_id, display_id, stable_id, current_version, active_draft_id,
              status, type, criticality, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-1",
                "REQ-AUTH-0001",
                "plainweave:req:AUTH:0001",
                1,
                None,
                "approved",
                "functional",
                "medium",
                "2026-06-04T10:00:00+10:00",
                "2026-06-04T10:00:00+10:00",
            ),
        )
        connection.execute(
            """
            insert into requirement_versions(
              requirement_id, version, title, statement, statement_hash, status,
              approved_by, approved_at, superseded_by_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-1",
                1,
                "Reject expired bearer tokens",
                "The API shall reject expired bearer tokens.",
                "sha256:old",
                "approved",
                "human:john",
                "2026-06-04T10:00:00+10:00",
                None,
            ),
        )
        connection.execute(
            """
            insert into baselines(
              baseline_id, name, description, locked, created_by, created_at
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (
                "BASELINE-0001",
                "Release 1.0 requirements",
                "Approved requirements for release 1.0.",
                1,
                "human:john",
                "2026-06-04T10:00:00+10:00",
            ),
        )
        connection.execute(
            """
            insert into baseline_members(
              baseline_id, requirement_id, version, display_id, stable_id,
              statement_hash, status_at_baseline
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BASELINE-0001",
                "req-1",
                1,
                "REQ-AUTH-0001",
                "plainweave:req:AUTH:0001",
                "sha256:old",
                "approved",
            ),
        )

        with pytest.raises(sqlite3.IntegrityError, match="baseline members are immutable"):
            connection.execute(
                """
                update baseline_members
                set statement_hash = ?
                where baseline_id = ? and requirement_id = ? and version = ?
                """,
                ("sha256:new", "BASELINE-0001", "req-1", 1),
            )

        with pytest.raises(sqlite3.IntegrityError, match="baseline members are immutable"):
            connection.execute(
                """
                delete from baseline_members
                where baseline_id = ? and requirement_id = ? and version = ?
                """,
                ("BASELINE-0001", "req-1", 1),
            )


def test_locked_baselines_are_immutable(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        connection.execute(
            """
            insert into baselines(
              baseline_id, name, description, locked, created_by, created_at
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (
                "BASELINE-0001",
                "Release 1.0 requirements",
                "Approved requirements for release 1.0.",
                1,
                "human:john",
                "2026-06-04T10:00:00+10:00",
            ),
        )

        with pytest.raises(sqlite3.IntegrityError, match="locked baselines are immutable"):
            connection.execute(
                "update baselines set name = ? where baseline_id = ?",
                ("Changed baseline", "BASELINE-0001"),
            )

        with pytest.raises(sqlite3.IntegrityError, match="locked baselines are immutable"):
            connection.execute("delete from baselines where baseline_id = ?", ("BASELINE-0001",))


def test_verification_tables_are_created_and_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"

    migrate(db_path, project_key="AUTH")
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        assert columns(connection, "verification_methods") == {
            "method_id",
            "requirement_id",
            "requirement_version",
            "method_type",
            "target",
            "status",
            "created_by",
            "created_at",
        }
        assert columns(connection, "verification_evidence") == {
            "evidence_id",
            "method_id",
            "requirement_id",
            "requirement_version",
            "status",
            "evidence_ref",
            "authority",
            "freshness",
            "recorded_by",
            "recorded_at",
            "payload_json",
        }


def test_verification_evidence_is_append_only(tmp_path: Path) -> None:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")

    with connect(db_path) as connection:
        connection.execute(
            """
            insert into requirements(
              requirement_id, display_id, stable_id, current_version, active_draft_id,
              status, type, criticality, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-1",
                "REQ-AUTH-0001",
                "plainweave:req:AUTH:0001",
                1,
                None,
                "approved",
                "functional",
                "medium",
                "2026-06-04T10:00:00+10:00",
                "2026-06-04T10:00:00+10:00",
            ),
        )
        connection.execute(
            """
            insert into verification_methods(
              method_id, requirement_id, requirement_version, method_type,
              target, status, created_by, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "VERM-0001",
                "req-1",
                1,
                "test",
                "tests/test_auth.py::test_expired",
                "active",
                "human:john",
                "2026-06-04T10:00:00+10:00",
            ),
        )
        connection.execute(
            """
            insert into verification_evidence(
              evidence_id, method_id, requirement_id, requirement_version,
              status, evidence_ref, authority, freshness, recorded_by,
              recorded_at, payload_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "EVID-0001",
                "VERM-0001",
                "req-1",
                1,
                "passing",
                "pytest:tests/test_auth.py::test_expired",
                "test_derived",
                "current",
                "agent:codex",
                "2026-06-04T10:00:00+10:00",
                "{}",
            ),
        )

        with pytest.raises(sqlite3.IntegrityError, match="verification evidence is append-only"):
            connection.execute(
                "update verification_evidence set status = ? where evidence_id = ?",
                ("failing", "EVID-0001"),
            )

        with pytest.raises(sqlite3.IntegrityError, match="verification evidence is append-only"):
            connection.execute("delete from verification_evidence where evidence_id = ?", ("EVID-0001",))
