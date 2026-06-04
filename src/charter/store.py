from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma foreign_keys = on")
    try:
        yield connection
    finally:
        connection.close()


def migrate(db_path: Path, *, project_key: str) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as connection:
        connection.executescript(
            """
            create table if not exists schema_meta (
              key text primary key,
              value text not null
            );

            create table if not exists actors (
              actor_id text primary key,
              kind text,
              display_name text
            );

            create table if not exists requirements (
              requirement_id text primary key,
              display_id text not null unique,
              stable_id text not null unique,
              current_version integer,
              active_draft_id text,
              status text not null,
              type text,
              criticality text,
              created_at text not null,
              updated_at text not null
            );

            create table if not exists requirement_drafts (
              draft_id text primary key,
              requirement_id text not null references requirements(requirement_id),
              base_version integer,
              title text not null,
              statement text not null,
              draft_revision integer not null,
              created_by text not null,
              created_at text not null,
              updated_at text not null
            );

            create table if not exists requirement_versions (
              requirement_id text not null references requirements(requirement_id),
              version integer not null,
              title text not null,
              statement text not null,
              statement_hash text not null,
              status text not null,
              approved_by text not null,
              approved_at text not null,
              superseded_by_version integer,
              primary key(requirement_id, version)
            );

            create trigger if not exists requirement_versions_text_immutable
            before update of title, statement, statement_hash on requirement_versions
            for each row
            when old.title <> new.title
              or old.statement <> new.statement
              or old.statement_hash <> new.statement_hash
            begin
              select raise(abort, 'requirement version text is immutable');
            end;

            create table if not exists acceptance_criteria (
              criterion_id text primary key,
              requirement_id text not null references requirements(requirement_id),
              draft_id text references requirement_drafts(draft_id),
              version integer,
              position integer not null,
              text text not null,
              status text not null,
              created_by text not null,
              created_at text not null
            );

            create table if not exists trace_links (
              link_id text primary key,
              state text not null,
              from_kind text not null,
              from_id text not null,
              relation text not null,
              to_kind text not null,
              to_id text not null,
              authority text not null,
              freshness text not null,
              confidence real,
              created_by text not null,
              accepted_by text,
              created_at text not null,
              updated_at text not null,
              target_snapshot_json text not null
            );

            create table if not exists events (
              event_id text primary key,
              event_type text not null,
              aggregate_type text not null,
              aggregate_id text not null,
              actor text not null,
              idempotency_key text,
              payload_json text not null,
              created_at text not null
            );

            create table if not exists idempotency_keys (
              key text primary key,
              operation text not null,
              target_id text not null,
              response_json text not null,
              created_at text not null
            );
            """
        )
        connection.executemany(
            "insert or ignore into schema_meta(key, value) values (?, ?)",
            [("project_key", project_key), ("schema_version", str(SCHEMA_VERSION))],
        )
        connection.commit()


def read_schema_meta(connection: sqlite3.Connection) -> dict[str, str]:
    rows: list[tuple[str, str]] = connection.execute("select key, value from schema_meta").fetchall()
    return dict(rows)
