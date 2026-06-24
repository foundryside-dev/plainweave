"""Single source of truth for the ``weft.plainweave.intent_coverage.v1`` shape.

The committed golden fixture and live service/CLI/MCP output are all validated
through ``validate_intent_coverage`` so the four cannot drift independently (the
same discipline as :mod:`tests.preflight_contract`). The contract is ADVISORY: a
coverage *fact*, never a release/allow/block verdict, so the validator also rejects
gate vocabulary anywhere in the payload.
"""

from __future__ import annotations

from typing import Any

INTENT_COVERAGE_SECTIONS = {
    "north_star",
    "denominator_complete",
    "surfaces_truncated",
    "coverage",
    "scoping",
    "justified",
    "unjustified",
    "adapter",
}
NORTH_STAR_KEYS = {"numerator", "denominator", "ratio"}
COVERAGE_KEYS = {"public_surface_tags", "present_tags", "absent_tags", "complete", "present_plugins"}
SCOPING_KEYS = {"excluded_namespaces", "excluded_count", "surface_classes"}
SURFACE_KEYS = {"locator", "sei", "surface_classes", "goals"}
ADAPTER_KEYS = {"adapter_status", "degraded"}
ADAPTER_STATUS_KEYS = {"status", "db_path", "http_url", "identity_http", "sei_supported"}
DEGRADED_ENTRY_KEYS = {"code", "message"}

# Verdict / enforcement vocabulary that must never appear: this is a facts-only,
# advisory contract (it must not pass/fail the 90% target).
_VERDICT_KEYS = {"allow", "allowed", "block", "blocked", "verdict", "decision", "gate", "enforcement"}
_VERDICT_VALUE_TOKENS = {
    "allow",
    "allowed",
    "block",
    "blocked",
    "deny",
    "denied",
    "approved",
    "rejected",
    "pass",
    "fail",
    "pass_fail",
    "verdict",
}


def assert_no_coverage_verdicts(value: object) -> None:
    """Reject gate/verdict semantics by key and by string value."""
    if isinstance(value, dict):
        assert _VERDICT_KEYS.isdisjoint(value), f"verdict-like key in {sorted(value)}"
        for item in value.values():
            assert_no_coverage_verdicts(item)
    elif isinstance(value, list):
        for item in value:
            assert_no_coverage_verdicts(item)
    elif isinstance(value, str):
        assert value.strip().lower() not in _VERDICT_VALUE_TOKENS, f"verdict-like value: {value}"


def _validate_surface(surface: dict[str, Any], *, justified: bool) -> None:
    assert set(surface) == SURFACE_KEYS, f"surface key drift: {sorted(surface)}"
    assert isinstance(surface["locator"], str) and surface["locator"]
    assert surface["sei"] is None or isinstance(surface["sei"], str)
    assert isinstance(surface["surface_classes"], list)
    assert isinstance(surface["goals"], list)
    if justified:
        assert surface["goals"], "a justified surface must reach at least one goal"
    else:
        assert surface["goals"] == [], "an unjustified surface must reach no goal"


def validate_intent_coverage(payload: dict[str, Any]) -> None:
    """Structurally validate an intent-coverage *data* payload (no envelope wrapper)."""
    assert set(payload) == INTENT_COVERAGE_SECTIONS, f"section drift: {sorted(payload)}"

    north_star = payload["north_star"]
    assert set(north_star) == NORTH_STAR_KEYS
    numerator = north_star["numerator"]
    denominator = north_star["denominator"]
    assert isinstance(numerator, int) and numerator >= 0
    assert isinstance(denominator, int) and denominator >= 0
    assert numerator <= denominator
    ratio = north_star["ratio"]
    if denominator == 0:
        assert ratio is None, "ratio over an empty denominator must be null, never a clean 0/blank"
    else:
        assert isinstance(ratio, float)
        assert abs(ratio - numerator / denominator) < 1e-9

    # Honest denominator: the flag mirrors the catalog's coverage.complete, and a
    # degraded denominator (any absent tag class) is never reported as complete.
    coverage = payload["coverage"]
    assert set(coverage) == COVERAGE_KEYS
    assert isinstance(coverage["complete"], bool)
    for key in ("public_surface_tags", "present_tags", "absent_tags", "present_plugins"):
        assert isinstance(coverage[key], list)
    # present_plugins exposes which language/plugins the catalog actually spans, so a
    # complete (tag-class) reading is not misread as whole-product over a language-partial catalog.
    assert all(isinstance(plugin, str) for plugin in coverage["present_plugins"])
    denominator_complete = payload["denominator_complete"]
    assert isinstance(denominator_complete, bool)
    assert denominator_complete == coverage["complete"]
    if coverage["absent_tags"]:
        assert denominator_complete is False

    surfaces_truncated = payload["surfaces_truncated"]
    assert isinstance(surfaces_truncated, bool)

    scoping = payload["scoping"]
    assert set(scoping) == SCOPING_KEYS
    assert isinstance(scoping["excluded_namespaces"], list)
    assert all(isinstance(prefix, str) for prefix in scoping["excluded_namespaces"])
    assert isinstance(scoping["excluded_count"], int) and scoping["excluded_count"] >= 0
    assert scoping["surface_classes"] is None or isinstance(scoping["surface_classes"], list)

    justified = payload["justified"]
    unjustified = payload["unjustified"]
    assert isinstance(justified, list)
    assert isinstance(unjustified, list)
    for surface in justified:
        _validate_surface(surface, justified=True)
    for surface in unjustified:
        _validate_surface(surface, justified=False)
    # Counts are always the full set; the evidence lists may be bounded by max_surfaces.
    assert len(justified) <= numerator, "justified evidence cannot exceed the numerator"
    assert len(unjustified) <= denominator - numerator, "unjustified evidence cannot exceed the gap"
    if not surfaces_truncated:
        assert numerator == len(justified), "numerator must equal the justified surface count"
        assert denominator == len(justified) + len(unjustified), "denominator must equal all in-scope surfaces"

    adapter = payload["adapter"]
    assert set(adapter) == ADAPTER_KEYS
    adapter_status = adapter["adapter_status"]
    assert isinstance(adapter_status, dict)
    # Pin the adapter_status key-set and per-degraded-entry shape so the adapter block
    # gets the same fixture-vs-live drift protection as the rest of the payload (a future
    # rename in LoomweaveAdapter._adapter_status would otherwise slip past this guard).
    assert set(adapter_status) == ADAPTER_STATUS_KEYS, f"adapter_status key drift: {sorted(adapter_status)}"
    assert isinstance(adapter["degraded"], list)
    for entry in adapter["degraded"]:
        assert isinstance(entry, dict)
        assert set(entry) == DEGRADED_ENTRY_KEYS, f"degraded entry key drift: {sorted(entry)}"

    assert_no_coverage_verdicts(payload)
