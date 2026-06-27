"""Single source of truth for the ``weft.plainweave.requirements_enrichment.v1`` shape.

Mirrors the no-verdict discipline of ``tests/preflight_contract.py``. This payload has
NO ``severity`` field, so (unlike the wardline validator) there is no severity allowlist.
"""

from __future__ import annotations

from typing import Any

ENRICHMENT_STATUSES = {"present", "absent", "unavailable"}
ENRICHMENT_FRESHNESS = {"current", "stale", "orphaned", "unknown", "unavailable"}
ENRICHMENT_DATA_KEYS = {"items", "summary", "authority_boundary"}
ENRICHMENT_ITEM_KEYS = {"entity_ref", "status", "requirements", "reason", "freshness"}
ENRICHMENT_REQUIREMENT_KEYS = {"requirement_id", "stable_id", "version", "type", "criticality", "binding"}
ENRICHMENT_BINDING_KEYS = {"relation", "actor_kind", "freshness"}
ENRICHMENT_AUTHORITY_KEYS = {"local_only", "live_peer_calls", "governance_verdicts", "requirements_owner"}

_VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
_VERDICT_VALUE_TOKENS = {
    "allow", "allowed", "block", "blocked", "block_candidate", "deny", "denied",
    "approved", "rejected", "pass_fail", "verdict",
}


def assert_no_warpline_verdicts(value: object) -> None:
    if isinstance(value, dict):
        assert _VERDICT_KEYS.isdisjoint(value), f"verdict-like key in {sorted(value)}"
        for item in value.values():
            assert_no_warpline_verdicts(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_warpline_verdicts(item)
    elif isinstance(value, str):
        assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


def validate_requirements_enrichment(payload: dict[str, Any]) -> None:
    """Structurally validate a requirements-enrichment *data* payload (no envelope wrapper)."""
    assert set(payload) == ENRICHMENT_DATA_KEYS, f"section drift: {sorted(payload)}"

    summary = payload["summary"]
    assert set(summary) == ENRICHMENT_STATUSES
    counts = {status: 0 for status in ENRICHMENT_STATUSES}
    items = payload["items"]
    assert isinstance(items, list)
    for item in items:
        assert set(item) == ENRICHMENT_ITEM_KEYS, f"item key drift: {sorted(item)}"
        assert item["status"] in ENRICHMENT_STATUSES
        assert item["freshness"] in ENRICHMENT_FRESHNESS
        counts[item["status"]] += 1
        requirements = item["requirements"]
        assert isinstance(requirements, list)
        if item["status"] == "present":
            assert requirements, "present status must carry a non-empty requirements array (spec 6.3)"
            assert item["reason"] is None
        else:
            assert requirements == [], "non-present status must carry an empty requirements array"
            assert isinstance(item["reason"], str) and item["reason"], "non-present status must carry a reason"
        for requirement in requirements:
            assert set(requirement) == ENRICHMENT_REQUIREMENT_KEYS, f"requirement key drift: {sorted(requirement)}"
            assert set(requirement["binding"]) == ENRICHMENT_BINDING_KEYS
            assert requirement["binding"]["actor_kind"] in {"agent", "human"}
    assert summary == counts, f"summary {summary} disagrees with item counts {counts}"

    authority = payload["authority_boundary"]
    assert set(authority) == ENRICHMENT_AUTHORITY_KEYS
    assert authority["governance_verdicts"] is False
    assert authority["live_peer_calls"] is False
    assert authority["local_only"] is True
    assert authority["requirements_owner"] == "plainweave"

    assert_no_warpline_verdicts(payload)
