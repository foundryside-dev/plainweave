"""Contract test for Plainweave's FILIGREE seam (production blocker #5).

Unlike the warpline/wardline/legis seams, Plainweave emits NO dedicated Filigree
``.v1`` payload: there is no filigree adapter, no ``filigree_*`` MCP tool, no
``weft.plainweave.filigree*.v1`` envelope. Plainweave's Filigree seam is two
plainweave-OWNED representations embedded in existing envelopes, plus a
deliberately-absent live join:

  (A) ``preflight_facts.v1``: ``open_linked_work`` is a RESERVED fact kind that the
      local-only producer NEVER emits; Filigree linked-work absence is reported
      in-band by the ``linked_work_facts_unavailable`` warning (no-silent-clean).
  (B) ``requirement_dossier`` / ``trace_link``: ``filigree_issue`` is a canonical
      TraceRef kind with two canonical relations; Plainweave stores an OPAQUE pointer
      to a Filigree issue id and never reads/resolves/mutates live Filigree.

This pins the honest representation, mirroring the warpline/wardline contract tests,
WITHOUT taking on Filigree's work lifecycle and WITHOUT a live Filigree call. The
live linked-work join (turning the warning into real ``open_linked_work`` facts) and
the ``gap_create_work`` write path are sibling-gated; see
``docs/handoffs/2026-06-29-filigree-linked-work-facts.md``.

The scope-INDEPENDENT presence of ``linked_work_facts_unavailable`` (invariant 1) is
pinned by an extension to
``tests/test_mcp_read_surface.py::test_mcp_preflight_freshness_is_unavailable_for_empty_project_scope`` —
the two files together are the Filigree contract test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from tests.test_mcp_read_surface import approve_requirement, service_for

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.mcp_surface import PlainweaveMcpSurface
from plainweave.models import TraceRef

# Governance gate/decision tokens the advisory dossier must never introduce — checked both
# as KEYS and as VALUES. NOTE: unlike the peer-facts producers, the dossier legitimately
# carries requirement-lifecycle VALUES ("approved"/"rejected") and trace authority/state
# ("accepted") as DOMAIN state — those are not governance verdicts — so the off-the-shelf
# peer-facts value-token scanner (assert_no_preflight_verdicts) would false-positive here.
# Instead we whitelist exactly those lifecycle/authority values and still reject every OTHER
# governance token appearing as a value, so a verdict expressed as a value (e.g. "block")
# under a non-verdict key cannot slip through.
_VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
_DOSSIER_LIFECYCLE_VALUES = {"approved", "rejected", "accepted"}
_VERDICT_VALUE_TOKENS = {
    "allow",
    "allowed",
    "block",
    "blocked",
    "block_candidate",
    "deny",
    "denied",
    "approved",
    "rejected",
    "pass_fail",
    "verdict",
} - _DOSSIER_LIFECYCLE_VALUES


def data(envelope: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], envelope["data"])


def _assert_dossier_is_verdict_free(value: object) -> None:
    """Reject governance verdicts by KEY anywhere and by VALUE (except the whitelisted
    requirement-lifecycle / trace-authority values that are legitimate dossier state)."""
    if isinstance(value, dict):
        offenders = sorted(set(value) & _VERDICT_KEYS)
        assert not offenders, f"verdict-like key in dossier: {offenders}"
        for item in value.values():
            _assert_dossier_is_verdict_free(item)
    elif isinstance(value, list):
        for item in value:
            _assert_dossier_is_verdict_free(item)
    elif isinstance(value, str):
        assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value in dossier: {value}"


def test_filigree_linked_work_absence_is_warned_not_silently_clean(tmp_path: Path) -> None:
    """No-silent-clean. The LOAD-BEARING pin is that ``linked_work_facts_unavailable`` is
    present on every scope (it is the in-band signal of Filigree linked-work absence). The
    second assertion (no ``open_linked_work`` fact) is a FORWARD-GUARD: ``open_linked_work``
    is reserved vocab the local-only producer never constructs today, so it must never appear
    as an empty-but-ok fact list when a future live Filigree join lands (sibling-gated)."""
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    surface = PlainweaveMcpSurface(tmp_path)

    for envelope in (
        surface.plainweave_preflight_facts_get(scope_kind="project"),
        surface.plainweave_preflight_facts_get(scope_kind="explicit_requirements", requirement_ids=[requirement_id]),
        surface.plainweave_preflight_facts_get(scope_kind="pending_diff"),
    ):
        preflight = data(envelope)
        facts = cast(list[dict[str, Any]], preflight["facts"])
        assert all(fact["kind"] != "open_linked_work" for fact in facts)
        warning_codes = {warning["code"] for warning in preflight["warnings"]}
        assert "linked_work_facts_unavailable" in warning_codes


def test_filigree_issue_implements_work_for_trace_is_canonical_and_opaque(tmp_path: Path) -> None:
    """The ``implements_work_for`` relation (previously untested; only ``resolves_gap``
    was exercised) is accepted and the Filigree issue id is stored as an OPAQUE
    pointer surfaced verbatim in the dossier — no live Filigree resolution."""
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)

    service.propose_trace_link(
        TraceRef("filigree_issue", "PW-123"),
        "implements_work_for",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="agent:codex",
    )

    dossier = service.requirement_dossier(requirement_id)
    filigree_traces = [item for item in dossier.traces.items if item.from_ref.kind == "filigree_issue"]
    assert len(filigree_traces) == 1
    assert filigree_traces[0].from_ref.id == "PW-123"  # opaque, never resolved/rewritten
    assert filigree_traces[0].relation == "implements_work_for"


def test_noncanonical_filigree_relation_is_rejected(tmp_path: Path) -> None:
    """Only the two canonical ``filigree_issue`` relations are accepted; a
    non-canonical relation is a VALIDATION error, never silently stored."""
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)

    with pytest.raises(PlainweaveError) as exc_info:
        service.propose_trace_link(
            TraceRef("filigree_issue", "PW-123"),
            "satisfies",  # canonical for loomweave_entity, NOT for filigree_issue
            TraceRef("requirement_version", f"{requirement_id}@1"),
            actor="agent:codex",
        )
    assert exc_info.value.code == ErrorCode.VALIDATION


def test_dossier_carrying_a_filigree_trace_is_verdict_free(tmp_path: Path) -> None:
    """The advisory boundary: a dossier surfacing a Filigree trace introduces NO governance
    verdict — by key OR by value — beyond the whitelisted requirement-lifecycle/authority
    values that are legitimate domain state (see the _VERDICT_VALUE_TOKENS note above)."""
    service = service_for(tmp_path)
    requirement_id = approve_requirement(service)
    service.propose_trace_link(
        TraceRef("filigree_issue", "PW-123"),
        "implements_work_for",
        TraceRef("requirement_version", f"{requirement_id}@1"),
        actor="agent:codex",
    )

    envelope = PlainweaveMcpSurface(tmp_path).plainweave_requirement_dossier_get(requirement_id)

    assert envelope["ok"] is True
    _assert_dossier_is_verdict_free(envelope)
