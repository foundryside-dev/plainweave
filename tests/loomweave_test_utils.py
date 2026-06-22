from __future__ import annotations

import sqlite3
from pathlib import Path


def create_loomweave_db(root: Path, *, with_sei: bool = True) -> Path:
    db_path = root / ".weft" / "loomweave" / "loomweave.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            create table entities (
              id text primary key,
              plugin_id text not null,
              kind text not null,
              name text not null,
              short_name text not null,
              parent_id text,
              source_file_id text,
              source_file_path text,
              source_byte_start integer,
              source_byte_end integer,
              source_line_start integer,
              source_line_end integer,
              properties text not null,
              content_hash text,
              summary text,
              wardline text,
              first_seen_commit text,
              last_seen_commit text,
              created_at text not null,
              updated_at text not null,
              signature text
            );

            create table entity_tags (
              entity_id text not null,
              plugin_id text not null,
              tag text not null,
              primary key (entity_id, plugin_id, tag)
            );
            """
        )
        if with_sei:
            connection.executescript(
                """
                create table sei_bindings (
                  sei text primary key,
                  current_locator text,
                  body_hash text,
                  signature text,
                  status text not null,
                  born_run_id text not null,
                  updated_run_id text not null,
                  updated_at text not null
                );

                create table sei_lineage (
                  id integer primary key autoincrement,
                  sei text not null,
                  event text not null,
                  old_locator text,
                  new_locator text,
                  run_id text not null,
                  recorded_at text not null
                );
                """
            )
    return db_path


def insert_loomweave_entity(
    db_path: Path,
    *,
    entity_id: str,
    kind: str,
    name: str,
    path: str,
    line_start: int,
    line_end: int,
    byte_start: int,
    byte_end: int,
    content_hash: str,
    sei: str | None,
    tags: list[str] | None = None,
    properties: str = "{}",
    status: str = "alive",
) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            insert into entities(
              id, plugin_id, kind, name, short_name, source_file_path,
              source_byte_start, source_byte_end, source_line_start,
              source_line_end, properties, content_hash, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                entity_id.split(":", 1)[0],
                kind,
                name,
                name.rsplit(".", 1)[-1],
                path,
                byte_start,
                byte_end,
                line_start,
                line_end,
                properties,
                content_hash,
                "2026-06-21T00:00:00Z",
                "2026-06-21T00:00:00Z",
            ),
        )
        for tag in tags or []:
            connection.execute(
                "insert into entity_tags(entity_id, plugin_id, tag) values (?, ?, ?)",
                (entity_id, entity_id.split(":", 1)[0], tag),
            )
        if sei is not None:
            connection.execute(
                """
                insert into sei_bindings(
                  sei, current_locator, body_hash, signature, status,
                  born_run_id, updated_run_id, updated_at
                ) values (?, ?, ?, null, ?, 'run-1', 'run-1', '2026-06-21T00:00:00Z')
                """,
                (sei, entity_id if status == "alive" else None, content_hash, status),
            )
            connection.execute(
                """
                insert into sei_lineage(sei, event, old_locator, new_locator, run_id, recorded_at)
                values (?, 'born', null, ?, 'run-1', '2026-06-21T00:00:00Z')
                """,
                (sei, entity_id),
            )


def seed_loomweave_catalog(root: Path) -> dict[str, str]:
    db_path = create_loomweave_db(root)
    insert_loomweave_entity(
        db_path,
        entity_id="python:module:pkg",
        kind="module",
        name="pkg",
        path=str(root / "pkg" / "__init__.py"),
        line_start=1,
        line_end=2,
        byte_start=0,
        byte_end=18,
        content_hash="hash-module",
        sei="loomweave:eid:module00000000000000000000000000",
    )
    insert_loomweave_entity(
        db_path,
        entity_id="python:function:pkg.public_api",
        kind="function",
        name="pkg.public_api",
        path=str(root / "pkg" / "api.py"),
        line_start=10,
        line_end=12,
        byte_start=100,
        byte_end=180,
        content_hash="hash-public-v1",
        sei="loomweave:eid:public00000000000000000000000000",
        tags=["exported-api"],
    )
    insert_loomweave_entity(
        db_path,
        entity_id="python:function:pkg.main",
        kind="function",
        name="pkg.main",
        path=str(root / "pkg" / "cli.py"),
        line_start=20,
        line_end=24,
        byte_start=200,
        byte_end=280,
        content_hash="hash-entry",
        sei="loomweave:eid:entry000000000000000000000000000",
        tags=["entry-point"],
    )
    insert_loomweave_entity(
        db_path,
        entity_id="python:function:pkg._internal",
        kind="function",
        name="pkg._internal",
        path=str(root / "pkg" / "internal.py"),
        line_start=30,
        line_end=31,
        byte_start=300,
        byte_end=340,
        content_hash="hash-internal",
        sei="loomweave:eid:internal000000000000000000000000",
    )
    return {
        "db_path": str(db_path),
        "module_sei": "loomweave:eid:module00000000000000000000000000",
        "public_sei": "loomweave:eid:public00000000000000000000000000",
        "entry_sei": "loomweave:eid:entry000000000000000000000000000",
        "public_locator": "python:function:pkg.public_api",
    }
