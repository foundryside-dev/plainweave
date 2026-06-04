from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "contracts"

ERROR_CODES = {
    "VALIDATION",
    "NOT_FOUND",
    "CONFLICT",
    "POLICY_REQUIRED",
    "PEER_ABSENT",
    "PEER_STALE",
    "PEER_CONTRACT",
    "LOCKED",
    "UNSUPPORTED",
    "INTERNAL",
}

TRACE_STATES = {"proposed", "accepted", "rejected", "stale", "orphaned"}
TRACE_AUTHORITIES = {
    "accepted",
    "agent_proposed",
    "human_proposed",
    "inferred",
    "imported",
    "test_derived",
    "peer_reported",
}
TRACE_FRESHNESS = {"current", "stale", "unknown", "orphaned", "not_applicable"}


def load_fixture(path: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_ROOT / path).read_text(encoding="utf-8")))


def assert_meta(envelope: dict[str, Any]) -> None:
    assert envelope["warnings"] == []
    assert envelope["meta"]["producer"]["tool"] == "charter"
    assert envelope["meta"]["producer"]["version"] == "0.1.0"
    assert envelope["meta"]["project"] == "AUTH"
    assert isinstance(envelope["meta"]["generated_at"], str)


def test_success_envelope_fixture_contract() -> None:
    fixture = load_fixture("envelopes/success.json")

    assert set(fixture) == {"schema", "ok", "data", "warnings", "meta"}
    assert fixture["schema"].startswith("loom.charter.")
    assert fixture["schema"].endswith(".v1")
    assert fixture["ok"] is True
    assert isinstance(fixture["data"], dict)
    assert_meta(fixture)


def test_validation_error_envelope_fixture_contract() -> None:
    fixture = load_fixture("envelopes/error-validation.json")

    assert set(fixture) == {"schema", "ok", "error", "warnings", "meta"}
    assert fixture["schema"] == "loom.charter.error.v1"
    assert fixture["ok"] is False
    assert fixture["error"]["code"] in ERROR_CODES
    assert fixture["error"]["code"] == "VALIDATION"
    assert fixture["error"]["recoverable"] is True
    assert fixture["error"]["hint"]
    assert isinstance(fixture["error"]["details"], dict)
    assert_meta(fixture)


def test_conflict_error_envelope_fixture_contract() -> None:
    fixture = load_fixture("envelopes/error-conflict.json")

    assert fixture["schema"] == "loom.charter.error.v1"
    assert fixture["ok"] is False
    assert fixture["error"]["code"] == "CONFLICT"
    assert fixture["error"]["code"] in ERROR_CODES
    assert fixture["error"]["recoverable"] is True
    assert fixture["error"]["hint"]
    assert_meta(fixture)


def test_list_envelope_fixture_contract() -> None:
    fixture = load_fixture("envelopes/list.json")

    assert set(fixture) == {"schema", "ok", "data", "warnings", "meta"}
    assert fixture["ok"] is True
    assert set(fixture["data"]) == {"items", "has_more", "next_offset"}
    assert isinstance(fixture["data"]["items"], list)
    assert fixture["data"]["has_more"] is False
    assert fixture["data"]["next_offset"] is None
    assert_meta(fixture)


def test_batch_envelope_fixture_contract() -> None:
    fixture = load_fixture("envelopes/batch.json")

    assert set(fixture) == {"schema", "ok", "data", "warnings", "meta"}
    assert fixture["ok"] is True
    assert set(fixture["data"]) == {"succeeded", "failed"}
    assert isinstance(fixture["data"]["succeeded"], list)
    assert isinstance(fixture["data"]["failed"], list)
    assert_meta(fixture)


def test_requirement_draft_fixture_contract() -> None:
    fixture = load_fixture("requirements/requirement-draft.json")

    assert set(fixture) == {
        "schema",
        "id",
        "stable_id",
        "draft_id",
        "base_version",
        "draft_revision",
        "title",
        "statement",
        "status",
        "created_by",
        "created_at",
    }
    assert fixture["schema"] == "loom.charter.requirement_draft.v1"
    assert fixture["id"].startswith("REQ-AUTH-")
    assert fixture["stable_id"].startswith("charter:req:AUTH:")
    assert fixture["draft_id"].startswith("DRAFT-")
    assert fixture["base_version"] is None
    assert fixture["draft_revision"] == 1
    assert fixture["status"] == "draft"


def test_requirement_version_approved_fixture_contract() -> None:
    fixture = load_fixture("requirements/requirement-version-approved.json")

    assert set(fixture) == {
        "schema",
        "id",
        "stable_id",
        "version",
        "title",
        "statement",
        "statement_hash",
        "status",
        "approved_by",
        "approved_at",
    }
    assert fixture["schema"] == "loom.charter.requirement_version.v1"
    assert fixture["id"].startswith("REQ-AUTH-")
    assert fixture["stable_id"].startswith("charter:req:AUTH:")
    assert fixture["version"] == 1
    assert fixture["statement_hash"].startswith("sha256:")
    assert fixture["status"] == "approved"
    assert fixture["approved_by"].startswith(("human:", "agent:"))


def test_trace_link_proposed_fixture_contract() -> None:
    fixture = load_fixture("traces/trace-link-proposed.json")

    assert set(fixture) == {
        "schema",
        "id",
        "state",
        "from",
        "relation",
        "to",
        "authority",
        "freshness",
        "confidence",
        "created_by",
        "accepted_by",
        "target_snapshot",
    }
    assert fixture["schema"] == "loom.charter.trace_link.v1"
    assert fixture["id"].startswith("LINK-")
    assert fixture["state"] in TRACE_STATES
    assert fixture["state"] == "proposed"
    assert set(fixture["from"]) == {"kind", "id"}
    assert set(fixture["to"]) == {"kind", "id"}
    assert fixture["relation"]
    assert fixture["authority"] in TRACE_AUTHORITIES
    assert fixture["authority"] == "agent_proposed"
    assert fixture["freshness"] in TRACE_FRESHNESS
    assert 0 <= fixture["confidence"] <= 1
    assert fixture["created_by"].startswith(("human:", "agent:"))
    assert fixture["accepted_by"] is None
    assert isinstance(fixture["target_snapshot"], dict)


def test_mcp_side_effect_metadata_fixture_contract() -> None:
    fixture = load_fixture("mcp/side-effect-metadata.json")

    assert set(fixture) == {
        "name",
        "mutates",
        "idempotent",
        "requires_actor",
        "requires_human_acceptance",
        "supports_dry_run",
        "peer_side_effects",
        "retry_contract",
    }
    assert fixture["name"] == "trace_link_propose"
    assert fixture["mutates"] is True
    assert fixture["idempotent"] is True
    assert fixture["requires_actor"] is True
    assert fixture["requires_human_acceptance"] == "later"
    assert fixture["supports_dry_run"] is True
    assert fixture["peer_side_effects"] == []
    assert fixture["retry_contract"]
