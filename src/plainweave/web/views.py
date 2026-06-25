from __future__ import annotations

from dataclasses import dataclass

from plainweave.intent_graph import CorpusEntry
from plainweave.models import RequirementRecord


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
