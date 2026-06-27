"""Plainweave-authored ``weft.plainweave.wardline_peer_facts.v1`` envelope, frozen
to a vendored byte golden with a non-circular producer-source recheck.

Two layers, mirroring ``test_preflight_facts_wire_golden.py``:
* Layer-1 (``test_golden_matches_blob_pin``): git-blob byte-pin; any silent wire
  edit reds the default suite. On its own this is CIRCULAR.
* Producer recheck (``test_golden_matches_live_producer``): re-invokes the REAL
  producer (``plainweave_wardline_peer_facts_list``) over scenario_a seeded into
  ``tmp/.wardline`` and asserts the regenerated ``schema + data`` EQUALS the golden.

Scenario A is same-scope WITH a manifest, so the envelope carries no float jaccard,
no scan-identity-absent note, and a basename-only source.snapshot — the properties
that keep the byte-pin stable. ``generated_at`` / ``producer.version`` are the only
non-deterministic fields; they are asserted LIVE then normalized to the golden's
frozen values, exactly as the preflight golden does.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, cast

from plainweave.mcp_surface import PlainweaveMcpSurface

GOLDEN_PATH = Path(__file__).parents[1] / "fixtures" / "contracts" / "wardline" / "peer-facts.json"
SCENARIO_A = Path(__file__).parents[1] / "fixtures" / "wardline" / "scenario_a"

# Recompute with: git hash-object tests/fixtures/contracts/wardline/peer-facts.json
UPSTREAM_BLOB_SHA = "d9d56edc9ce508ccc8f2ee55f7eefac3fbc7afe0"
_FROZEN_GENERATED_AT = "2026-06-04T10:00:00+00:00"
_FROZEN_VERSION = "1.0.0"


def _produce_schema_plus_data(root: Path) -> dict[str, Any]:
    shutil.copytree(SCENARIO_A, root / ".wardline")
    envelope = PlainweaveMcpSurface(root).plainweave_wardline_peer_facts_list()
    assert envelope["ok"] is True
    return {"schema": envelope["schema"], **cast(dict[str, Any], envelope["data"])}


def test_golden_matches_blob_pin() -> None:
    assert len(UPSTREAM_BLOB_SHA) == 40 and set(UPSTREAM_BLOB_SHA) <= set("0123456789abcdef"), (
        f"UPSTREAM_BLOB_SHA must be 40 lowercase hex chars: {UPSTREAM_BLOB_SHA!r}"
    )
    data = GOLDEN_PATH.read_bytes()
    actual = hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()
    assert actual == UPSTREAM_BLOB_SHA, (
        f"vendored wardline golden changed (git blob {actual}, pinned {UPSTREAM_BLOB_SHA}); "
        "if deliberate, regenerate from the producer, refreeze generated_at/version, re-pin in the same commit."
    )


def test_golden_matches_live_producer(tmp_path: Path) -> None:
    """Non-circular recheck: the volatile fields (generated_at, producer.version) live
    in the envelope ``meta``, which the golden does NOT vendor (it vendors only
    ``schema + data``). The data payload is therefore fully deterministic, so no
    normalization is needed — assert deep equality directly. If a future field adds a
    non-deterministic value INTO data, port the preflight normalize-then-compare block."""
    golden = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text("utf-8")))
    regenerated = _produce_schema_plus_data(tmp_path)
    assert golden["schema"] == "weft.plainweave.wardline_peer_facts.v1"
    assert "generated_at" not in regenerated, "data must stay deterministic; generated_at belongs in meta"
    assert regenerated == golden, (
        "the live wardline_peer_facts producer drifted from the vendored golden — "
        "regenerate and re-pin per the RE-VENDOR PROCEDURE."
    )
