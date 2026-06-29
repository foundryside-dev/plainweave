"""Single source of truth for the ``weft.plainweave.loomweave_catalog.v1`` shape.

Mirrors ``tests/wardline_contract.py`` so the committed degraded golden and the live
``plainweave_loomweave_catalog_list`` producer cannot drift in shape or degraded-state
invariants (both are run through this one structural validator). The catalog envelope
carries NO ``severity`` field, so the no-verdict scan uses the warpline-style scanner
(no severity allowlist branch).

The cardinal invariant is no-silent-clean: when the Loomweave adapter is
``unavailable`` (db/schema missing) the empty page MUST carry a non-empty
``degraded[]`` reason — an empty ``items`` list must never read as a clean
"nothing here". The Loomweave identity-resolution + catalog BEHAVIOR is already
implemented and tested (live HTTP resolve + capability probe + closed-vocab degraded
codes + the SEI §8 oracle + adapter/producer degraded tests); this validator freezes
the PRODUCER-side contract that was the remaining PDR-014-parity gap.
"""

from __future__ import annotations

from typing import Any

LOOMWEAVE_ADAPTER_STATUSES = {"available", "unavailable"}
LOOMWEAVE_CATALOG_DATA_KEYS = {
    "items",
    "limit",
    "offset",
    "has_more",
    "next_offset",
    "adapter_status",
    "degraded",
    "coverage",
}
LOOMWEAVE_ADAPTER_STATUS_KEYS = {"status", "db_path", "http_url", "identity_http", "sei_supported"}
LOOMWEAVE_COVERAGE_KEYS = {"public_surface_tags", "present_tags", "absent_tags", "complete", "present_plugins"}
LOOMWEAVE_ITEM_KEYS = {
    "sei",
    "locator",
    "kind",
    "tags",
    "source",
    "content_hash",
    "content_hash_at_attach",
    "public_signal",
    "briefing_blocked",
    "lineage_status",
    "freshness",
    "observed_at",
    "degraded",
    "signals",
}

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


def assert_no_loomweave_verdicts(value: object) -> None:
    """Reject gate semantics by key and by string value (the catalog has no severity field)."""
    if isinstance(value, dict):
        assert _VERDICT_KEYS.isdisjoint(value), f"verdict-like key in {sorted(value)}"
        for item in value.values():
            assert_no_loomweave_verdicts(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_loomweave_verdicts(item)
    elif isinstance(value, str):
        assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


def validate_loomweave_catalog(payload: dict[str, Any]) -> None:
    """Structurally validate a loomweave-catalog *data* payload (no envelope wrapper)."""
    assert set(payload) == LOOMWEAVE_CATALOG_DATA_KEYS, f"section drift: {sorted(payload)}"

    status_block = payload["adapter_status"]
    assert set(status_block) == LOOMWEAVE_ADAPTER_STATUS_KEYS, f"adapter_status drift: {sorted(status_block)}"
    assert status_block["status"] in LOOMWEAVE_ADAPTER_STATUSES

    degraded = payload["degraded"]
    assert isinstance(degraded, list)
    for entry in degraded:
        assert {"code", "message"}.issubset(entry), f"degraded entry drift: {sorted(entry)}"

    items = payload["items"]
    assert isinstance(items, list)

    coverage = payload["coverage"]
    assert set(coverage) == LOOMWEAVE_COVERAGE_KEYS, f"coverage drift: {sorted(coverage)}"
    assert isinstance(coverage["complete"], bool)

    # The cardinal no-silent-clean invariant: an unavailable adapter never returns a
    # clean-empty page — it reports its degradation in-band AND never advertises any
    # positive coverage/pagination signal that would read as "we have data" while down.
    if status_block["status"] == "unavailable":
        assert items == [], "unavailable adapter must not enumerate items"
        assert degraded, "unavailable adapter must report a degraded reason in-band (no silent-clean)"
        assert coverage["complete"] is False, "unavailable adapter must not claim complete coverage"
        assert coverage["present_tags"] == [], "unavailable adapter must not claim present tags"
        assert coverage["present_plugins"] == [], "unavailable adapter must not claim present plugins"
        assert payload["has_more"] is False, "unavailable adapter must not claim more pages"
        assert payload["next_offset"] is None, "unavailable adapter must not advertise a next page"

    for item in items:
        assert set(item) == LOOMWEAVE_ITEM_KEYS, f"item key drift: {sorted(item)}"

    assert_no_loomweave_verdicts(payload)
