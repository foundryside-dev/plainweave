from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from plainweave.cli_commands import _intent_coverage_dict
from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.intent_graph import IntentLevel
from plainweave.service import PlainweaveService
from plainweave.store import migrate
from tests.intent_coverage_contract import validate_intent_coverage
from tests.loomweave_test_utils import create_loomweave_db, insert_loomweave_entity


def service_for(tmp_path: Path) -> PlainweaveService:
    db_path = tmp_path / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    return PlainweaveService(db_path, root=tmp_path)


def add_surface(
    db_path: Path,
    locator: str,
    *,
    tags: list[str],
    sei: str | None,
    kind: str = "function",
) -> None:
    qualname = locator.split(":", 2)[-1]
    suffix = qualname.replace(".", "_").replace("-", "_")
    insert_loomweave_entity(
        db_path,
        entity_id=locator,
        kind=kind,
        name=qualname,
        path=f"/src/{suffix}.py",
        line_start=1,
        line_end=2,
        byte_start=0,
        byte_end=10,
        content_hash=f"hash-{suffix}",
        sei=sei,
        tags=tags,
    )


def justify(service: PlainweaveService, sei: str, *, key: str) -> str:
    """Bind ``sei`` to an approved requirement laddered to a goal (SEI->req->goal)."""
    draft = service.create_requirement(f"Explain {key}", f"{key} shall have explicit intent.", "human:john")
    service.add_acceptance_criterion(draft.id, "Traceable to a goal.", actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=f"ap-{key}")
    goal = service.create_goal(f"Goal {key}", "The surface explains why it exists.", actor="human:john")
    service.link_goal_to_requirement(goal.id, draft.requirement_id, actor="human:john")
    service.bind_sei_to_requirement(sei, draft.requirement_id, actor="agent:codex", content_hash_at_attach="sha256:x")
    return goal.goal_id


def bind_without_goal(service: PlainweaveService, sei: str, *, key: str) -> None:
    """Bind ``sei`` to a requirement that is NOT laddered to any goal."""
    draft = service.create_requirement(f"Bare {key}", f"{key} shall exist.", "human:john")
    service.add_acceptance_criterion(draft.id, "Exists.", actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=f"bare-{key}")
    service.bind_sei_to_requirement(sei, draft.requirement_id, actor="agent:codex", content_hash_at_attach="sha256:x")


# --- Acceptance A: numerator / denominator / ratio ---------------------------


def test_coverage_reports_numerator_denominator_and_ratio(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.alpha", tags=["exported-api"], sei="loomweave:eid:alpha")
    add_surface(db, "python:function:pkg.beta", tags=["cli-command"], sei="loomweave:eid:beta")
    add_surface(db, "python:function:pkg.gamma", tags=["http-route"], sei="loomweave:eid:gamma")
    add_surface(db, "python:function:pkg.delta", tags=["entry-point"], sei="loomweave:eid:delta")
    justify(service, "loomweave:eid:alpha", key="alpha")
    justify(service, "loomweave:eid:beta", key="beta")

    result = service.intent_coverage()

    assert result.denominator == 4
    assert result.numerator == 2
    assert result.ratio == 0.5
    assert result.denominator_complete is True
    assert {s.locator for s in result.justified} == {"python:function:pkg.alpha", "python:function:pkg.beta"}
    assert {s.locator for s in result.unjustified} == {"python:function:pkg.gamma", "python:function:pkg.delta"}
    assert all(surface.goals for surface in result.justified)
    assert all(not surface.goals for surface in result.unjustified)
    assert all(node.level == IntentLevel.GOAL for surface in result.justified for node in surface.goals)


def test_surface_bound_without_goal_is_not_justified(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.alpha", tags=["exported-api"], sei="loomweave:eid:alpha")
    bind_without_goal(service, "loomweave:eid:alpha", key="alpha")

    result = service.intent_coverage()

    # SEI->requirement exists, but the chain does not reach a goal: honest gap.
    assert result.numerator == 0
    assert result.denominator == 1
    assert [s.locator for s in result.unjustified] == ["python:function:pkg.alpha"]


def test_surfaces_without_any_sei_are_unjustified(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.unbound", tags=["exported-api"], sei=None)

    result = service.intent_coverage()

    assert result.numerator == 0
    assert result.denominator == 1
    assert result.unjustified[0].sei is None


def test_modules_without_public_tag_are_not_counted(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:module:pkg", tags=[], sei="loomweave:eid:mod", kind="module")
    add_surface(db, "python:function:pkg.api", tags=["exported-api"], sei="loomweave:eid:api")

    result = service.intent_coverage()

    assert result.denominator == 1
    assert [s.locator for s in result.unjustified] == ["python:function:pkg.api"]


def test_surface_justified_by_deprecated_requirement_becomes_unjustified(tmp_path: Path) -> None:
    # A surface counts as justified only while its requirement is *live*. Deprecating
    # the requirement must drop it from the numerator — counting a dead obligation as
    # live justification is the exact dishonesty this primitive exists to prevent, and
    # it would diverge from intent_corpus / intent_orphans, which both treat a
    # requirement as live iff status in ('draft', 'approved').
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.alpha", tags=["exported-api"], sei="loomweave:eid:alpha")
    draft = service.create_requirement("Explain alpha", "alpha shall have explicit intent.", "human:john")
    service.add_acceptance_criterion(draft.id, "Traceable to a goal.", actor="human:john")
    service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key="ap-alpha")
    goal = service.create_goal("Goal alpha", "The surface explains why it exists.", actor="human:john")
    service.link_goal_to_requirement(goal.id, draft.requirement_id, actor="human:john")
    service.bind_sei_to_requirement(
        "loomweave:eid:alpha", draft.requirement_id, actor="agent:codex", content_hash_at_attach="sha256:x"
    )

    # While live, the surface is justified.
    assert service.intent_coverage().numerator == 1

    service.deprecate_requirement(draft.id, actor="human:john", expected_version=1, idempotency_key="dep-alpha")

    after = service.intent_coverage()
    assert after.numerator == 0
    assert after.denominator == 1
    assert [s.locator for s in after.unjustified] == ["python:function:pkg.alpha"]


# --- Acceptance B: honest denominator ----------------------------------------


def test_degraded_catalog_marks_denominator_incomplete(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.alpha", tags=["exported-api"], sei="loomweave:eid:alpha")
    add_surface(db, "python:function:pkg.delta", tags=["entry-point"], sei="loomweave:eid:delta")
    justify(service, "loomweave:eid:alpha", key="alpha")

    result = service.intent_coverage()

    assert result.denominator_complete is False
    assert result.coverage["complete"] is False
    assert set(cast(list[str], result.coverage["absent_tags"])) == {"cli-command", "http-route"}
    # The ratio is still computed, but is qualified by denominator_complete=False.
    assert result.numerator == 1
    assert result.denominator == 2


def test_unavailable_catalog_is_explicit_not_silently_clean(tmp_path: Path) -> None:
    service = service_for(tmp_path)  # no Loomweave catalog seeded at all

    result = service.intent_coverage()

    assert result.denominator == 0
    assert result.numerator == 0
    assert result.ratio is None
    assert result.denominator_complete is False
    assert any(entry["code"] == "loomweave_db_missing" for entry in result.adapter_degraded)


# --- Acceptance C: surface scoping -------------------------------------------


def test_default_namespace_exclusion_drops_test_and_script_surfaces(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.real", tags=["exported-api"], sei="loomweave:eid:real")
    add_surface(db, "python:function:tests.perf.harness", tags=["entry-point"], sei="loomweave:eid:tperf")
    add_surface(db, "python:function:scripts.check_gate", tags=["entry-point"], sei="loomweave:eid:sgate")

    result = service.intent_coverage()

    surfaces = [*result.justified, *result.unjustified]
    assert [s.locator for s in surfaces] == ["python:function:pkg.real"]
    assert result.denominator == 1
    assert result.excluded_count == 2
    assert result.excluded_namespaces == ("scripts.", "tests.")


def test_overriding_exclusion_list_changes_denominator(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.real", tags=["exported-api"], sei="loomweave:eid:real")
    add_surface(db, "python:function:tests.perf.harness", tags=["entry-point"], sei="loomweave:eid:tperf")

    result = service.intent_coverage(exclude_namespaces=["pkg."])

    assert result.excluded_namespaces == ("pkg.",)
    assert result.excluded_count == 1
    assert {s.locator for s in result.unjustified} == {"python:function:tests.perf.harness"}
    assert result.denominator == 1


def test_surface_class_restriction_limits_denominator(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.api", tags=["exported-api"], sei="loomweave:eid:api")
    add_surface(db, "python:function:pkg.cli", tags=["cli-command"], sei="loomweave:eid:cli")

    result = service.intent_coverage(surface_classes=["exported-api"])

    assert result.surface_classes == ("exported-api",)
    assert {s.locator for s in result.unjustified} == {"python:function:pkg.api"}
    assert result.denominator == 1


def test_invalid_surface_class_is_rejected(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    create_loomweave_db(tmp_path)

    with pytest.raises(PlainweaveError) as excinfo:
        service.intent_coverage(surface_classes=["not-a-real-class"])

    assert excinfo.value.code == ErrorCode.VALIDATION


# --- Acceptance E: the multi-page catalog path is aggregated, not truncated ---


def test_coverage_aggregates_surfaces_across_catalog_pages(tmp_path: Path) -> None:
    # intent_coverage pages the Loomweave catalog at 100 rows; seed enough public
    # surfaces to force a second page and prove every page is folded into the
    # denominator (a single-page read would stop at 100). The justified surface is
    # the last by id-sort order, so it lands on page 2 — proving cross-page surfaces
    # are both counted and correctly laddered to a goal.
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    total = 101
    for index in range(total):
        add_surface(
            db,
            f"python:function:pkg.s{index:03d}",
            tags=["exported-api"],
            sei=f"loomweave:eid:s{index:03d}",
        )
    justify(service, f"loomweave:eid:s{total - 1:03d}", key=f"s{total - 1:03d}")

    result = service.intent_coverage()

    assert result.denominator == total
    assert len(result.justified) + len(result.unjustified) == total
    assert result.numerator == 1
    assert [s.locator for s in result.justified] == [f"python:function:pkg.s{total - 1:03d}"]


# --- Acceptance D: service output serializes to the shared contract -----------


def test_service_output_matches_the_shared_contract(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    db = create_loomweave_db(tmp_path)
    add_surface(db, "python:function:pkg.alpha", tags=["exported-api"], sei="loomweave:eid:alpha")
    add_surface(db, "python:function:pkg.gamma", tags=["http-route"], sei="loomweave:eid:gamma")
    justify(service, "loomweave:eid:alpha", key="alpha")

    payload = _intent_coverage_dict(service.intent_coverage())

    # Same serializer CLI and MCP use, validated through the same structural validator.
    validate_intent_coverage(payload)
