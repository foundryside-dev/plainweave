from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from charter.envelopes import success_envelope
from charter.paths import charter_db_path, default_project_key, project_root

SCHEMA_VERSION = 1


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_parser = subparsers.add_parser("init", help="Initialize a local Charter store.")
    init_parser.add_argument("--project-key", help="Stable project key for requirement IDs.")
    init_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    init_parser.set_defaults(handler=handle_init)

    doctor_parser = subparsers.add_parser("doctor", help="Report local Charter project health.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    doctor_parser.set_defaults(handler=handle_doctor)


def handle_init(args: argparse.Namespace) -> int:
    root = project_root()
    project_key = str(args.project_key or default_project_key(root))
    result = initialize_project(root, project_key)
    if bool(args.json):
        print(json.dumps(success_envelope("loom.charter.init.v1", result, project=project_key)))
    else:
        status = "created" if result["created"] else "already initialized"
        print(f"Charter store {status}: {result['db_path']}")
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    root = project_root()
    result = inspect_project(root)
    project = result["project_key"] if isinstance(result["project_key"], str) else None
    if bool(args.json):
        print(json.dumps(success_envelope("loom.charter.doctor.v1", result, project=project)))
    else:
        status = "initialized" if result["initialized"] else "not initialized"
        print(f"Charter project {status}: {result['db_path']}")
    return 0


def initialize_project(root: Path, project_key: str) -> dict[str, object]:
    db_path = charter_db_path(root)
    created = not db_path.exists()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("create table if not exists schema_meta (key text primary key, value text not null)")
        metadata = _schema_meta(connection)
        if not metadata:
            connection.executemany(
                "insert into schema_meta(key, value) values (?, ?)",
                [("project_key", project_key), ("schema_version", str(SCHEMA_VERSION))],
            )
        connection.commit()
        metadata = _schema_meta(connection)
    return {
        "created": created,
        "project_key": metadata["project_key"],
        "schema_version": int(metadata["schema_version"]),
        "db_path": str(db_path),
    }


def inspect_project(root: Path) -> dict[str, object]:
    db_path = charter_db_path(root)
    if not db_path.exists():
        return {
            "initialized": False,
            "project_key": None,
            "schema_version": None,
            "db_path": str(db_path),
        }
    with closing(sqlite3.connect(db_path)) as connection:
        metadata = _schema_meta(connection)
    return {
        "initialized": True,
        "project_key": metadata.get("project_key"),
        "schema_version": int(metadata["schema_version"]) if "schema_version" in metadata else None,
        "db_path": str(db_path),
    }


def _schema_meta(connection: sqlite3.Connection) -> dict[str, str]:
    rows: list[tuple[str, str]] = connection.execute("select key, value from schema_meta").fetchall()
    return dict(rows)
