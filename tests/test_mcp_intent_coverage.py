from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from plainweave.mcp_surface import PlainweaveMcpSurface
from plainweave.service import PlainweaveService
from plainweave.store import migrate
from tests.intent_coverage_contract import validate_intent_coverage
from tests.loomweave_test_utils import create_loomweave_db
from tests.test_intent_coverage import add_surface, justify


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path, root=tmp_path)


def data(envelope: dict[str, Any]) -> dict[str, Any]:
    assert envelope["ok"] is True
    assert envelope["schema"] == "weft.plainweave.intent_coverage.v1"
    assert envelope["warnings"] == []
    return cast(dict[str, Any], envelope["data"])


def test_mcp_intent_coverage_matches_contract_and_scopes_namespaces(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.real", tags=["exported-api"], sei="loomweave:eid:real")
    add_surface(db, "python:function:tests.perf.harness", tags=["entry-point"], sei="loomweave:eid:tperf")
    justify(service, "loomweave:eid:real", key="real")

    surface = PlainweaveMcpSurface(tmp_path)
    payload = data(surface.plainweave_intent_coverage())

    validate_intent_coverage(payload)
    assert payload["north_star"] == {"numerator": 1, "denominator": 1, "ratio": 1.0}
    assert payload["scoping"]["excluded_count"] == 1
    assert payload["scoping"]["excluded_namespaces"] == ["scripts.", "tests."]


def test_mcp_intent_coverage_unavailable_catalog_is_explicit(tmp_path: Path) -> None:
    service_for(tmp_path)  # no Loomweave catalog seeded

    surface = PlainweaveMcpSurface(tmp_path)
    payload = data(surface.plainweave_intent_coverage())

    validate_intent_coverage(payload)
    assert payload["north_star"]["denominator"] == 0
    assert payload["north_star"]["ratio"] is None
    assert payload["denominator_complete"] is False
    assert any(entry["code"] == "loomweave_db_missing" for entry in payload["adapter"]["degraded"])


def test_mcp_intent_coverage_surface_class_restriction(tmp_path: Path) -> None:
    service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.api", tags=["exported-api"], sei="loomweave:eid:api")
    add_surface(db, "python:function:pkg.cli", tags=["cli-command"], sei="loomweave:eid:cli")

    surface = PlainweaveMcpSurface(tmp_path)
    payload = data(surface.plainweave_intent_coverage(surface_classes=["exported-api"]))

    validate_intent_coverage(payload)
    assert payload["scoping"]["surface_classes"] == ["exported-api"]
    assert [s["locator"] for s in payload["unjustified"]] == ["python:function:pkg.api"]
