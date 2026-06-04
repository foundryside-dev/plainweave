from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


@dataclass(frozen=True)
class AcceptanceCriterion:
    id: str
    requirement_id: str
    draft_id: str | None
    version: int | None
    position: int
    text: str
    status: str
    created_by: str
    created_at: str

    def with_version(self, version: int) -> AcceptanceCriterion:
        return AcceptanceCriterion(
            self.id,
            self.requirement_id,
            self.draft_id,
            version,
            self.position,
            self.text,
            self.status,
            self.created_by,
            self.created_at,
        )


@dataclass(frozen=True)
class TraceRef:
    kind: str
    id: str


@dataclass(frozen=True)
class TraceLink:
    id: str
    state: str
    from_ref: TraceRef
    relation: str
    to_ref: TraceRef
    authority: str
    freshness: str
    confidence: float | None
    created_by: str
    accepted_by: str | None
    target_snapshot: dict[str, Any]


@dataclass(frozen=True)
class BaselineMember:
    requirement_id: str
    id: str
    stable_id: str
    version: int
    statement_hash: str
    status_at_baseline: str


@dataclass(frozen=True)
class Baseline:
    id: str
    name: str
    description: str
    locked: bool
    created_by: str
    created_at: str
    members: list[BaselineMember]


@dataclass(frozen=True)
class BaselineDiffItem:
    requirement_id: str
    id: str
    stable_id: str
    baseline_version: int | None
    current_version: int | None
    status: str
    baseline_statement_hash: str | None
    current_statement_hash: str | None


@dataclass(frozen=True)
class BaselineDiff:
    baseline_id: str
    summary: dict[str, int]
    items: list[BaselineDiffItem]


@dataclass(frozen=True)
class VerificationMethod:
    id: str
    requirement_id: str
    requirement_version: int
    method: str
    target: str
    status: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class VerificationEvidence:
    id: str
    method_id: str
    requirement_id: str
    requirement_version: int
    status: str
    evidence_ref: str
    authority: str
    freshness: str
    recorded_by: str
    recorded_at: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class VerificationReason:
    code: str
    message: str
    evidence_id: str | None = None


@dataclass(frozen=True)
class RequirementVerificationStatus:
    requirement_id: str
    id: str
    stable_id: str
    current_version: int
    status: str
    reasons: list[VerificationReason]
    current_evidence: list[VerificationEvidence]
    stale_evidence: list[VerificationEvidence]


@dataclass(frozen=True)
class DossierAuthoritySummary:
    status: str
    current_approved_version: int | None
    current_statement_hash: str | None
    has_active_draft: bool
    active_draft_id: str | None
    verification_status: str
    baseline_count: int


@dataclass(frozen=True)
class DossierRequirementSection:
    record: RequirementRecord
    current_version: RequirementVersion | None
    active_draft: RequirementDraft | None


@dataclass(frozen=True)
class DossierAcceptanceCriteriaSection:
    current_version: list[AcceptanceCriterion]
    active_draft: list[AcceptanceCriterion]


@dataclass(frozen=True)
class DossierTraceSection:
    incoming: list[TraceLink]
    outgoing: list[TraceLink]
    by_state: dict[str, int]
    by_relation: dict[str, int]
    items: list[TraceLink]


@dataclass(frozen=True)
class DossierBaselineExposureItem:
    baseline_id: str
    name: str
    locked: bool
    created_by: str
    created_at: str
    baseline_version: int
    baseline_statement_hash: str
    current_version: int | None
    current_statement_hash: str | None
    state: str


@dataclass(frozen=True)
class DossierBaselineExposure:
    summary: dict[str, int]
    items: list[DossierBaselineExposureItem]


@dataclass(frozen=True)
class DossierComputedGap:
    code: str
    severity: str
    message: str
    source: str


@dataclass(frozen=True)
class DossierPeerFacts:
    live_peer_calls: bool
    sources: list[str]
    notes: list[str]


@dataclass(frozen=True)
class DossierNextAction:
    action: str
    priority: int
    reason: str
    command: str | None
    blocked_by: list[str]


@dataclass(frozen=True)
class RequirementDossier:
    identity: dict[str, object]
    authority_summary: DossierAuthoritySummary
    requirement: DossierRequirementSection
    acceptance_criteria: DossierAcceptanceCriteriaSection
    traces: DossierTraceSection
    verification: RequirementVerificationStatus
    baseline_exposure: DossierBaselineExposure
    computed_gaps: list[DossierComputedGap]
    peer_facts: DossierPeerFacts
    next_actions: list[DossierNextAction]
