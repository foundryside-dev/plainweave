"""Contract test for ``weft.plainweave.loomweave_catalog.v1`` (production blocker #3:
explicit degraded peer-state envelope for the live Loomweave adapter).

The Loomweave identity-resolution + catalog BEHAVIOR is already implemented and tested
(live HTTP resolve + capability probe + closed-vocab degraded codes + the SEI §8 oracle
+ adapter/producer degraded tests). The remaining PDR-014-parity gap was the absence of
a PRODUCER-side contract pinning the catalog envelope's DEGRADED state. This freezes it,
mirroring the wardline/preflight contract tests: the committed golden and the live
producer are validated through the SAME structural validator, so they cannot diverge.
No production code changes — the behavior already exists; this is the parity contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from tests.loomweave_contract import assert_no_loomweave_verdicts, validate_loomweave_catalog
from tests.loomweave_test_utils import seed_loomweave_catalog

from plainweave.mcp_surface import PlainweaveMcpSurface
from plainweave.store import migrate

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "contracts" / "loomweave" / "catalog-degraded.json"


def _surface(tmp_path: Path) -> PlainweaveMcpSurface:
    migrate(tmp_path / ".plainweave" / "plainweave.db", project_key="AUTH")
    return PlainweaveMcpSurface(tmp_path)


def _data(envelope: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], envelope["data"])


def _minimal_unavailable() -> dict[str, Any]:
    return {
        "items": [],
        "limit": 50,
        "offset": 0,
        "has_more": False,
        "next_offset": None,
        "adapter_status": {
            "status": "unavailable",
            "db_path": ".weft/loomweave/loomweave.db",
            "http_url": None,
            "identity_http": "not_configured",
            "sei_supported": False,
        },
        "degraded": [{"code": "loomweave_db_missing", "message": "missing"}],
        "coverage": {
            "public_surface_tags": [],
            "present_tags": [],
            "absent_tags": [],
            "complete": False,
            "present_plugins": [],
        },
    }


def test_validator_accepts_a_minimal_unavailable_payload() -> None:
    validate_loomweave_catalog(_minimal_unavailable())


def test_validator_rejects_a_silent_clean_unavailable_page() -> None:
    """The cardinal violation: an unavailable adapter returning an empty page with NO
    degraded reason — a clean-empty read that hides the degradation."""
    payload = _minimal_unavailable()
    payload["degraded"] = []
    with pytest.raises(AssertionError):
        validate_loomweave_catalog(payload)


def test_validator_rejects_a_verdict_token() -> None:
    with pytest.raises(AssertionError):
        assert_no_loomweave_verdicts({"status": "blocked"})


def test_committed_degraded_golden_matches_the_validator() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema"] == "weft.plainweave.loomweave_catalog.v1"
    # Validated through the SAME structural validator as live output, so the golden and
    # the running tool cannot diverge without one test or the other failing.
    validate_loomweave_catalog({key: value for key, value in fixture.items() if key != "schema"})


def test_live_unavailable_adapter_envelope_is_valid_and_in_band_degraded(tmp_path: Path) -> None:
    """The real producer over a root with no Loomweave db: an unavailable adapter, an
    empty page, and a degraded reason carried in-band (no silent-clean)."""
    data = _data(_surface(tmp_path).plainweave_loomweave_catalog_list(limit=50, offset=0))
    validate_loomweave_catalog(data)
    assert data["adapter_status"]["status"] == "unavailable"
    assert data["items"] == []
    assert data["degraded"], "unavailable adapter must report a degraded reason in-band"


def test_live_healthy_catalog_envelope_is_valid(tmp_path: Path) -> None:
    surface = _surface(tmp_path)
    seed_loomweave_catalog(tmp_path)
    data = _data(surface.plainweave_loomweave_catalog_list(limit=50, offset=0))
    validate_loomweave_catalog(data)
    assert data["adapter_status"]["status"] == "available"
    assert data["items"]
