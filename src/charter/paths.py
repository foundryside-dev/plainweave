from __future__ import annotations

from pathlib import Path

CHARTER_DIR = ".charter"
CHARTER_DB = "charter.db"


def project_root(start: Path | None = None) -> Path:
    return (start or Path.cwd()).resolve()


def charter_dir(root: Path | None = None) -> Path:
    return project_root(root) / CHARTER_DIR


def charter_db_path(root: Path | None = None) -> Path:
    return charter_dir(root) / CHARTER_DB


def default_project_key(root: Path | None = None) -> str:
    name = project_root(root).name.upper()
    sanitized = "".join(character for character in name if character.isalnum())
    return sanitized or "LOCAL"
