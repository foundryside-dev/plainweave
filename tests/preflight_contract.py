"""Single source of truth for the ``weft.plainweave.preflight_facts.v1`` shape.

Both the committed golden fixture and live tool output are validated through
``validate_preflight_facts`` so the two cannot drift independently (previously
they were checked by two separate hand-maintained bodies and had diverged).
"""

from __future__ import annotations

from typing import Any

PREFLIGHT_SECTIONS = {
    "producer",
    "scope",
    "generated_at",
    "freshness",
    "facts",
    "summary",
    "warnings",
    "provenance",
    "authority_boundary",
}
PREFLIGHT_FACT_KINDS = {
    "requirement_touched",
    "requirement_nearby",
    "requirement_verification_stale",
    "requirement_verification_missing",
    "baseline_drift",
    "trace_gap",
    "open_linked_work",
    "active_finding_linked",
    "waived_finding_linked",
    "orphaned_entity_link",
    "untraced_change",
}
PREFLIGHT_SEVERITIES = {"info", "warn", "critical"}
PREFLIGHT_FRESHNESS = {"current", "partial", "unavailable"}
PREFLIGHT_FACT_KEYS = {
    "id",
    "kind",
    "severity",
    "requirement",
    "message",
    "evidence_refs",
    "source",
    "freshness",
    "provenance",
}
PREFLIGHT_REQUIREMENT_KEYS = {"id", "requirement_id", "stable_id", "version", "criticality", "type"}
PREFLIGHT_SUMMARY_KEYS = {"info", "warn", "critical", "facts", "by_kind", "by_freshness"}
PREFLIGHT_WARNING_KEYS = {"code", "severity", "message", "freshness", "provenance"}
PREFLIGHT_AUTHORITY_KEYS = {"local_only", "live_peer_calls", "governance_verdicts", "legis_policy_cells"}
PREFLIGHT_PROVENANCE_KEYS = {"producer", "inputs"}

# Verdict / enforcement vocabulary that must never appear: facts-only contract.
_VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
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
}


def assert_no_preflight_verdicts(value: object) -> None:
    """Reject gate semantics by key, by severity value, and by string value."""
    if isinstance(value, dict):
        assert _VERDICT_KEYS.isdisjoint(value), f"verdict-like key in {sorted(value)}"
        severity = value.get("severity")
        if isinstance(severity, str):
            assert severity in PREFLIGHT_SEVERITIES, f"non-neutral severity value: {severity}"
        for item in value.values():
            assert_no_preflight_verdicts(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_preflight_verdicts(item)
    elif isinstance(value, str):
        assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


def validate_preflight_facts(payload: dict[str, Any]) -> None:
    """Structurally validate a preflight-facts *data* payload (no envelope wrapper)."""
    assert set(payload) == PREFLIGHT_SECTIONS, f"section drift: {sorted(payload)}"
    assert set(payload["producer"]) == {"tool", "version", "project"}
    assert payload["producer"]["tool"] == "plainweave"
    assert "kind" in payload["scope"]
    assert payload["freshness"] in PREFLIGHT_FRESHNESS

    facts = payload["facts"]
    assert isinstance(facts, list)
    for fact in facts:
        assert set(fact) == PREFLIGHT_FACT_KEYS
        assert str(fact["id"]).startswith("FACT-")
        assert fact["kind"] in PREFLIGHT_FACT_KINDS
        assert fact["severity"] in PREFLIGHT_SEVERITIES
        assert set(fact["requirement"]) == PREFLIGHT_REQUIREMENT_KEYS
        assert isinstance(fact["evidence_refs"], list)
        assert set(fact["source"]) == {"kind", "id"}
        assert fact["freshness"] in PREFLIGHT_FRESHNESS
        assert set(fact["provenance"]) == PREFLIGHT_PROVENANCE_KEYS
        assert fact["provenance"]["producer"] == "plainweave"

    summary = payload["summary"]
    assert set(summary) == PREFLIGHT_SUMMARY_KEYS
    assert summary["facts"] == len(facts)
    for severity in ("info", "warn", "critical"):
        assert summary[severity] == sum(1 for fact in facts if fact["severity"] == severity)
    expected_by_kind: dict[str, int] = {}
    expected_by_freshness: dict[str, int] = {}
    for fact in facts:
        expected_by_kind[fact["kind"]] = expected_by_kind.get(fact["kind"], 0) + 1
        expected_by_freshness[fact["freshness"]] = expected_by_freshness.get(fact["freshness"], 0) + 1
    assert summary["by_kind"] == expected_by_kind
    assert summary["by_freshness"] == expected_by_freshness

    warnings = payload["warnings"]
    assert isinstance(warnings, list)
    for warning in warnings:
        assert set(warning) == PREFLIGHT_WARNING_KEYS
        assert warning["severity"] in PREFLIGHT_SEVERITIES
        assert warning["freshness"] in PREFLIGHT_FRESHNESS
        assert set(warning["provenance"]) == PREFLIGHT_PROVENANCE_KEYS

    assert set(payload["provenance"]) == PREFLIGHT_PROVENANCE_KEYS

    authority = payload["authority_boundary"]
    assert set(authority) == PREFLIGHT_AUTHORITY_KEYS
    assert authority["governance_verdicts"] is False
    assert authority["live_peer_calls"] is False

    assert_no_preflight_verdicts(payload)
