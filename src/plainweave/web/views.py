from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from plainweave.intent_graph import CorpusEntry, IntentLevel, IntentNode
from plainweave.models import RequirementRecord

if TYPE_CHECKING:
    from plainweave.service import PlainweaveService


@dataclass(frozen=True)
class CorpusRow:
    req_id: str
    display_id: str
    title: str
    status: str
    goal_count: int
    code_count: int


def build_corpus_rows(
    corpus: list[CorpusEntry],
    records: list[RequirementRecord],
    titles: dict[str, str],
) -> list[CorpusRow]:
    """Build corpus rows from pre-fetched corpus entries, records, and resolved titles.

    ``titles`` maps requirement_id -> resolved title (caller resolves draft vs version title
    before calling here, keeping this function pure and unit-testable).
    """
    by_id = {r.requirement_id: r for r in records}
    rows: list[CorpusRow] = []
    for entry in corpus:
        rid = entry.requirement.node_id
        rec = by_id.get(rid)
        if rec is None:
            continue
        title = titles.get(rid, rec.id)
        rows.append(
            CorpusRow(
                req_id=rid,
                display_id=rec.id,
                title=title,
                status=rec.status,
                goal_count=len(entry.goals),
                code_count=len(entry.code),
            )
        )
    return rows


@dataclass(frozen=True)
class OrphanItem:
    """One orphan rendered as a human-readable, linkable row (M7)."""

    label: str
    href: str | None


@dataclass(frozen=True)
class OrphanSection:
    """A non-empty group of orphans at one intent altitude."""

    level: str
    items: list[OrphanItem]


def build_orphan_sections(
    orphans: dict[str, list[IntentNode]],
    req_titles: dict[str, str],
    goal_titles: dict[str, str],
) -> list[OrphanSection]:
    """Resolve raw orphan nodes into titled, linked rows, dropping empty altitudes (M7).

    Requirement orphans link to their detail page and show their resolved title; goal
    orphans link to the goals page and show their title; code orphans keep their SEI
    ``node_id`` as the label (there is no human title to resolve, and the design scopes
    titling to requirements and goals). Zero-count altitudes are omitted entirely so the
    page never shows an empty "Orphans — X (0)" section.
    """
    sections: list[OrphanSection] = []
    for level in (IntentLevel.CODE, IntentLevel.REQUIREMENT, IntentLevel.GOAL):
        nodes = orphans.get(level.value, [])
        if not nodes:
            continue
        items: list[OrphanItem] = []
        for node in nodes:
            if level is IntentLevel.REQUIREMENT:
                items.append(OrphanItem(req_titles.get(node.node_id, node.node_id), f"/req/{node.node_id}"))
            elif level is IntentLevel.GOAL:
                items.append(OrphanItem(goal_titles.get(node.node_id, node.node_id), "/goals"))
            else:
                items.append(OrphanItem(node.node_id, None))
        sections.append(OrphanSection(level=level.value, items=items))
    return sections


def coverage_banner(cov: object) -> str | None:
    if getattr(cov, "denominator_complete", True) and not getattr(cov, "adapter_degraded", ()):
        return None
    return "Coverage denominator is incomplete — the Loomweave catalog is absent or stale. This number is partial."


@dataclass(frozen=True)
class DraftItem:
    kind: str  # "draft"
    req_id: str
    display_id: str
    title: str
    statement: str
    current_version: int


@dataclass(frozen=True)
class LinkItem:
    kind: str  # "link"
    link_id: str
    from_label: str
    relation: str
    to_label: str
    proposing_actor: str
    confidence: float | None
    drifted: bool


def pending_items(service: PlainweaveService) -> list[DraftItem | LinkItem]:
    """Return unified review queue: pending drafts + proposed trace links."""
    items: list[DraftItem | LinkItem] = []
    for rec in service.search_requirements():
        if rec.active_draft_id is None:
            continue
        d = service.requirement_dossier(rec.requirement_id).requirement.active_draft
        if d is None:
            continue
        items.append(
            DraftItem(
                kind="draft",
                req_id=rec.requirement_id,
                display_id=rec.id,
                title=d.title,
                statement=d.statement,
                current_version=rec.current_version,
            )
        )
    for link in service.trace_for(state="proposed"):
        items.append(
            LinkItem(
                kind="link",
                link_id=link.id,
                from_label=link.from_ref.id,
                relation=link.relation,
                to_label=link.to_ref.id,
                proposing_actor=link.created_by,
                confidence=link.confidence,
                drifted=link.freshness != "current",
            )
        )
    return items


def filter_rows(rows: list[CorpusRow], *, q: str, status: str, orphan: str) -> list[CorpusRow]:
    out = rows
    if q:
        needle = q.lower()
        out = [r for r in out if needle in r.title.lower() or needle in r.display_id.lower()]
    if status:
        out = [r for r in out if r.status == status]
    if orphan == "no-goal":
        out = [r for r in out if r.goal_count == 0]
    elif orphan == "no-code":
        out = [r for r in out if r.code_count == 0]
    elif orphan == "both":
        out = [r for r in out if r.goal_count == 0 and r.code_count == 0]
    return out
