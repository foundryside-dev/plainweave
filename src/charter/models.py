from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequirementDraft:
    requirement_id: str
    id: str
    stable_id: str
    draft_id: str
    base_version: int | None
    draft_revision: int
    title: str
    statement: str
    status: str


@dataclass(frozen=True)
class RequirementVersion:
    requirement_id: str
    id: str
    stable_id: str
    version: int
    title: str
    statement: str
    statement_hash: str
    status: str
    approved_by: str
    approved_at: str


@dataclass(frozen=True)
class RequirementRecord:
    requirement_id: str
    id: str
    stable_id: str
    current_version: int
    active_draft_id: str | None
    status: str
    current_version_record: RequirementVersion | None
