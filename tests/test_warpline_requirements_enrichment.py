from __future__ import annotations

from pathlib import Path

from plainweave.mcp_surface import PlainweaveMcpSurface
from plainweave.models import TraceRef
from plainweave.service import PlainweaveService
from plainweave.store import migrate
from tests.loomweave_test_utils import seed_loomweave_catalog
from tests.warpline_contract import validate_requirements_enrichment


def _seed_bound(tmp_path: Path) -> tuple[PlainweaveMcpSurface, dict[str, str]]:
    # Verified pattern from tests/contracts/test_preflight_facts_wire_golden.py::_seed_preflight_project.
    # `service_for` is a PER-FILE local helper elsewhere (not importable); seed directly.
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    service = PlainweaveService(db_path, root=tmp_path)
    seed = seed_loomweave_catalog(tmp_path)
    draft = service.create_requirement(
        "Reject expired tokens", "The API shall reject expired bearer tokens.", "human:john"
    )
    service.add_acceptance_criterion(draft.id, "Expired tokens return 401.", actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="approve-1")
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", f"{draft.id}@1"),
        actor="human:john",
        authority="accepted",
    )
    return PlainweaveMcpSurface(tmp_path), seed


def _item(surface: PlainweaveMcpSurface, root: Path, ref: str) -> dict[str, object]:
    service = surface._service()
    return surface._entity_intent_context_item(service, ref, service.trace_for())


def test_status_present_when_alive_requirement_bound(tmp_path: Path) -> None:
    surface, seed = _seed_bound(tmp_path)
    status, reason = surface._requirements_enrichment_status(_item(surface, tmp_path, seed["public_sei"]))
    assert status == "present"
    assert reason is None


def test_status_absent_when_resolved_but_unbound(tmp_path: Path) -> None:
    surface, seed = _seed_bound(tmp_path)
    status, reason = surface._requirements_enrichment_status(_item(surface, tmp_path, seed["module_sei"]))
    assert status == "absent"
    assert reason


def test_status_unavailable_when_unresolved(tmp_path: Path) -> None:
    surface, _seed = _seed_bound(tmp_path)
    status, reason = surface._requirements_enrichment_status(
        _item(surface, tmp_path, "loomweave:eid:doesnotexist00000000000000000000")
    )
    assert status == "unavailable"
    assert reason


def test_present_item_shape(tmp_path: Path) -> None:
    surface, seed = _seed_bound(tmp_path)
    service = surface._service()
    items = surface._requirements_enrichment_items(service, _item(surface, tmp_path, seed["public_sei"]))
    assert len(items) == 1
    it = items[0]
    assert set(it) == {"requirement_id", "stable_id", "version", "type", "criticality", "binding"}
    assert it["stable_id"].startswith("plainweave:req:")
    # anti-trap: type/criticality must come from requirement_preflight_profile, NOT be silent nulls
    assert it["version"] == 1
    assert it["criticality"] is not None
    assert it["type"] is not None
    assert set(it["binding"]) == {"relation", "actor_kind", "freshness"}
    assert it["binding"]["actor_kind"] == "human"  # trace authority == "accepted"
    assert it["binding"]["relation"] == "satisfies"


def test_envelope_mixed_states(tmp_path: Path) -> None:
    surface, seed = _seed_bound(tmp_path)
    envelope = surface.plainweave_requirements_enrichment_get(
        entity_refs=[seed["public_sei"], seed["module_sei"], "loomweave:eid:missing00000000000000000000000000"]
    )
    assert envelope["schema"] == "weft.plainweave.requirements_enrichment.v1"
    assert envelope["ok"] is True
    data = envelope["data"]
    validate_requirements_enrichment(data)
    statuses = {it["entity_ref"]: it["status"] for it in data["items"]}
    assert statuses[seed["public_sei"]] == "present"
    assert statuses[seed["module_sei"]] == "absent"
    assert statuses["loomweave:eid:missing00000000000000000000000000"] == "unavailable"
    assert data["summary"] == {"present": 1, "absent": 1, "unavailable": 1}
    assert data["authority_boundary"]["requirements_owner"] == "plainweave"
    present = next(it for it in data["items"] if it["status"] == "present")
    assert present["requirements"]  # non-empty per §6.3
    for it in data["items"]:
        if it["status"] != "present":
            assert it["requirements"] == [] and it["reason"]
