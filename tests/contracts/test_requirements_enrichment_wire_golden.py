"""Plainweave-authored ``weft.plainweave.requirements_enrichment.v1`` producer golden,
STRUCTURE-pinned only — deliberately NOT byte-pinned.

Per the design spec (§11), the item-level schema for Warpline's reserved
``enrichment.requirements`` slot is *proposed* until the interface-lock owner ratifies
it (handoff: docs/handoffs/2026-06-27-warpline-interface-lock-item-schema.md). Byte-
pinning now would force an expensive re-freeze on every pre-ratification tweak. So this
test pins STRUCTURE: it regenerates the payload from the REAL producer over a seeded
project, asserts it passes ``validate_requirements_enrichment``, and asserts the
committed golden does too and agrees on the status set and item keys. When the schema is
ratified, convert this to a two-layer byte-pin mirroring the wardline wire golden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from plainweave.mcp_surface import PlainweaveMcpSurface
from tests.warpline_contract import (
    ENRICHMENT_ITEM_KEYS,
    ENRICHMENT_STATUSES,
    validate_requirements_enrichment,
)
# reuse the B1/B3 seed helper:
from tests.test_warpline_requirements_enrichment import _seed_bound

GOLDEN_PATH = Path(__file__).parents[1] / "fixtures" / "contracts" / "warpline" / "requirements-enrichment.json"


def test_golden_is_structurally_valid() -> None:
    golden = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text("utf-8")))
    assert golden["schema"] == "weft.plainweave.requirements_enrichment.v1"
    validate_requirements_enrichment({k: v for k, v in golden.items() if k != "schema"})


def test_live_producer_matches_golden_structure(tmp_path: Path) -> None:
    surface, seed = _seed_bound(tmp_path)
    envelope = surface.plainweave_requirements_enrichment_get(
        entity_refs=[seed["public_sei"], seed["module_sei"], "loomweave:eid:missing00000000000000000000000000"]
    )
    assert envelope["ok"] is True
    data = cast(dict[str, Any], envelope["data"])
    validate_requirements_enrichment(data)

    golden = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text("utf-8")))
    golden_data = {k: v for k, v in golden.items() if k != "schema"}
    assert set(golden_data["summary"]) == ENRICHMENT_STATUSES
    assert {it["status"] for it in data["items"]} <= ENRICHMENT_STATUSES
    for item in data["items"]:
        assert set(item) == ENRICHMENT_ITEM_KEYS
    # structure agreement, NOT byte equality (schema un-ratified, see module docstring)
    assert {it["status"] for it in golden_data["items"]} == {it["status"] for it in data["items"]}
