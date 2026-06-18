from __future__ import annotations

from pathlib import Path

PLAINWEAVE_DIR = ".plainweave"
PLAINWEAVE_DB = "plainweave.db"


def project_root(start: Path | None = None) -> Path:
    return (start or Path.cwd()).resolve()


def plainweave_dir(root: Path | None = None) -> Path:
    return project_root(root) / PLAINWEAVE_DIR


def plainweave_db_path(root: Path | None = None) -> Path:
    return plainweave_dir(root) / PLAINWEAVE_DB


def default_project_key(root: Path | None = None) -> str:
    name = project_root(root).name.upper()
    sanitized = "".join(character for character in name if character.isalnum())
    return sanitized or "LOCAL"
