"""Single source of truth for the ``weft.plainweave.wardline_peer_facts.v1`` shape.

Mirrors ``tests/preflight_contract.py`` so the committed golden and the live
producer cannot drift. Wardline severity is CRITICAL|ERROR|WARN|INFO|NONE, so the
no-verdict scan uses a Wardline-specific severity allowlist (NOT the preflight one).
"""

from __future__ import annotations

from typing import Any

WARDLINE_SEVERITIES = {"CRITICAL", "ERROR", "WARN", "INFO", "NONE"}
WARDLINE_SUPPRESSION_STATES = {"active", "waived", "baselined", "judged"}
WARDLINE_KINDS = {"defect", "metric", "fact", "classification", "suggestion"}
WARDLINE_FRESHNESS = {"current", "stale", "unavailable"}
WARDLINE_DATA_KEYS = {
    "source", "freshness", "facts", "resolved_or_unseen",
    "engine_metrics", "summary", "degraded", "authority_boundary", "notes",
}
WARDLINE_FACT_KEYS = {
    "fingerprint", "rule_id", "kind", "non_defect", "severity",
    "suppression_state", "suppression_reason", "location", "qualname", "message",
}
WARDLINE_SUMMARY_KEYS = {
    "by_suppression_state", "by_kind", "defect", "non_defect", "resolved_or_unseen", "indeterminate",
}
WARDLINE_AUTHORITY_KEYS = {"local_only", "live_peer_calls", "governance_verdicts", "trust_policy_owner"}

_VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
_VERDICT_VALUE_TOKENS = {
    "allow", "allowed", "block", "blocked", "block_candidate", "deny", "denied",
    "approved", "rejected", "pass_fail", "verdict",
}


def assert_no_wardline_verdicts(value: object) -> None:
    """Reject gate semantics by key, by severity value, and by string value."""
    if isinstance(value, dict):
        assert _VERDICT_KEYS.isdisjoint(value), f"verdict-like key in {sorted(value)}"
        severity = value.get("severity")
        if isinstance(severity, str):
            assert severity in WARDLINE_SEVERITIES, f"non-wardline severity value: {severity}"
        for item in value.values():
            assert_no_wardline_verdicts(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_wardline_verdicts(item)
    elif isinstance(value, str):
        assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


def validate_wardline_peer_facts(payload: dict[str, Any]) -> None:
    """Structurally validate a wardline-peer-facts *data* payload (no envelope wrapper)."""
    assert set(payload) == WARDLINE_DATA_KEYS, f"section drift: {sorted(payload)}"
    assert payload["freshness"] in WARDLINE_FRESHNESS
    assert set(payload["source"]) == {"snapshot", "snapshot_count", "prior"}
    snapshot = payload["source"]["snapshot"]
    assert snapshot is None or "/" not in snapshot, "source.snapshot must be a basename, not a path"

    facts = payload["facts"]
    assert isinstance(facts, list)
    for fact in facts:
        assert set(fact) == WARDLINE_FACT_KEYS, f"fact key drift: {sorted(fact)}"
        assert fact["kind"] in WARDLINE_KINDS
        assert fact["severity"] in WARDLINE_SEVERITIES
        assert fact["suppression_state"] in WARDLINE_SUPPRESSION_STATES
        assert fact["non_defect"] == (fact["kind"] != "defect")
        assert "path" in fact["location"]

    for item in payload["resolved_or_unseen"]:
        assert set(item) == {"fingerprint", "rule_id", "location"}

    summary = payload["summary"]
    assert set(summary) == WARDLINE_SUMMARY_KEYS
    assert set(summary["by_suppression_state"]) == WARDLINE_SUPPRESSION_STATES
    assert summary["defect"] + summary["non_defect"] >= 0

    for entry in payload["degraded"]:
        assert {"code", "message"}.issubset(entry)

    authority = payload["authority_boundary"]
    assert set(authority) == WARDLINE_AUTHORITY_KEYS
    assert authority["governance_verdicts"] is False
    assert authority["live_peer_calls"] is False
    assert authority["local_only"] is True
    assert authority["trust_policy_owner"] == "wardline"

    assert isinstance(payload["notes"], list)
    assert isinstance(payload["engine_metrics"], list)

    assert_no_wardline_verdicts(payload)
