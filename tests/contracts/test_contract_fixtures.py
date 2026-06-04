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
VERIFICATION_METHODS = {"test", "analysis", "inspection", "manual"}
VERIFICATION_EVIDENCE_STATUSES = {"passing", "failing", "inconclusive", "waived"}
VERIFICATION_AUTHORITIES = {"test_derived", "human_attested", "agent_reported", "waiver"}
VERIFICATION_FRESHNESS = {"current", "stale"}
REQUIREMENT_VERIFICATION_STATUSES = {
    "satisfied",
    "unsatisfied",
    "unverified",
    "stale",
    "unknown",
    "waived",
}

REQUIRED_FIXTURES = {
    "baselines/baseline.json",
    "baselines/baseline-diff.json",
    "verification/verification-method.json",
    "verification/verification-evidence.json",
    "verification/requirement-verification-status.json",
    "dossiers/requirement-dossier.json",
    "envelopes/success.json",
    "envelopes/error-validation.json",
    "envelopes/error-conflict.json",
    "envelopes/list.json",
    "envelopes/batch.json",
    "requirements/requirement-draft.json",
    "requirements/requirement-version-approved.json",
    "requirements/requirement-version-superseded.json",
    "traces/trace-link-proposed.json",
    "traces/trace-link-accepted.json",
    "traces/trace-link-stale.json",
    "traces/trace-link-orphaned.json",
    "mcp/side-effect-metadata.json",
    "cli/req-add-json.json",
    "cli/req-show-json.json",
    "cli/req-approve-json.json",
    "cli/criterion-add-json.json",
    "cli/dossier-json.json",
    "cli/trace-propose-json.json",
    "cli/trace-accept-json.json",
    "cli/trace-reject-json.json",
    "cli/trace-list-json.json",
    "cli/error-validation-json.json",
    "cli/error-conflict-json.json",
    "cli/baseline-create-json.json",
    "cli/baseline-show-json.json",
    "cli/baseline-list-json.json",
    "cli/baseline-diff-json.json",
    "cli/verify-method-add-json.json",
    "cli/verify-evidence-record-json.json",
    "cli/verify-status-json.json",
    "cli/status-requirement-json.json",
    "cli/status-unverified-json.json",
    "cli/status-stale-json.json",
}


def load_fixture(path: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_ROOT / path).read_text(encoding="utf-8")))


def assert_computed_gap_shape(gap: dict[str, Any]) -> None:
    assert set(gap) == {"code", "severity", "message", "source"}


def assert_next_action_shape(action: dict[str, Any]) -> None:
    assert set(action) == {"action", "priority", "reason", "command", "blocked_by"}


def test_required_fixture_plan_files_exist() -> None:
    missing = sorted(path for path in REQUIRED_FIXTURES if not (FIXTURE_ROOT / path).is_file())

    assert missing == []


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


def assert_trace_link_fixture(fixture: dict[str, Any], *, expected_state: str) -> None:
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
    assert fixture["state"] == expected_state
    assert set(fixture["from"]) == {"kind", "id"}
    assert set(fixture["to"]) == {"kind", "id"}
    assert fixture["relation"]
    assert fixture["authority"] in TRACE_AUTHORITIES
    assert fixture["freshness"] in TRACE_FRESHNESS
    if fixture["confidence"] is not None:
        assert 0 <= fixture["confidence"] <= 1
    assert fixture["created_by"].startswith(("human:", "agent:"))
    assert isinstance(fixture["target_snapshot"], dict)


def test_requirement_version_superseded_fixture_contract() -> None:
    fixture = load_fixture("requirements/requirement-version-superseded.json")

    assert fixture["schema"] == "loom.charter.requirement_version.v1"
    assert fixture["version"] == 1
    assert fixture["status"] == "superseded"
    assert fixture["superseded_by_version"] == 2


def test_trace_link_proposed_fixture_contract() -> None:
    fixture = load_fixture("traces/trace-link-proposed.json")

    assert_trace_link_fixture(fixture, expected_state="proposed")
    assert fixture["authority"] == "agent_proposed"
    assert fixture["accepted_by"] is None


def test_trace_link_accepted_fixture_contract() -> None:
    fixture = load_fixture("traces/trace-link-accepted.json")

    assert_trace_link_fixture(fixture, expected_state="accepted")
    assert fixture["authority"] == "accepted"
    assert fixture["accepted_by"].startswith(("human:", "agent:"))


def test_trace_link_stale_fixture_contract() -> None:
    fixture = load_fixture("traces/trace-link-stale.json")

    assert_trace_link_fixture(fixture, expected_state="stale")
    assert fixture["freshness"] == "stale"


def test_trace_link_orphaned_fixture_contract() -> None:
    fixture = load_fixture("traces/trace-link-orphaned.json")

    assert_trace_link_fixture(fixture, expected_state="orphaned")
    assert fixture["freshness"] == "orphaned"


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


def test_baseline_fixture_contract() -> None:
    fixture = load_fixture("baselines/baseline.json")

    assert set(fixture) == {
        "schema",
        "id",
        "name",
        "description",
        "locked",
        "created_by",
        "created_at",
        "members",
    }
    assert fixture["schema"] == "loom.charter.baseline.v1"
    assert fixture["id"].startswith("BASELINE-")
    assert fixture["name"]
    assert isinstance(fixture["description"], str)
    assert fixture["locked"] is True
    assert fixture["created_by"].startswith(("human:", "agent:"))
    assert isinstance(fixture["members"], list)
    assert fixture["members"]
    for member in fixture["members"]:
        assert set(member) == {
            "requirement_id",
            "id",
            "stable_id",
            "version",
            "statement_hash",
            "status_at_baseline",
        }
        assert member["id"].startswith("REQ-AUTH-")
        assert member["stable_id"].startswith("charter:req:AUTH:")
        assert isinstance(member["version"], int)
        assert member["statement_hash"].startswith("sha256:")
        assert member["status_at_baseline"] in {"approved", "deprecated"}


def test_baseline_diff_fixture_contract() -> None:
    fixture = load_fixture("baselines/baseline-diff.json")

    assert set(fixture) == {"schema", "baseline_id", "summary", "items"}
    assert fixture["schema"] == "loom.charter.baseline_diff.v1"
    assert fixture["baseline_id"].startswith("BASELINE-")
    assert set(fixture["summary"]) == {
        "unchanged",
        "changed",
        "missing_current",
        "new_since_baseline",
        "superseded_since_baseline",
    }
    for count in fixture["summary"].values():
        assert isinstance(count, int)
        assert count >= 0
    assert isinstance(fixture["items"], list)
    assert fixture["items"]
    for item in fixture["items"]:
        assert set(item) == {
            "requirement_id",
            "id",
            "stable_id",
            "baseline_version",
            "current_version",
            "status",
            "baseline_statement_hash",
            "current_statement_hash",
        }
        assert item["status"] in {
            "unchanged",
            "changed",
            "missing_current",
            "new_since_baseline",
            "superseded_since_baseline",
        }


def test_verification_method_fixture_contract() -> None:
    fixture = load_fixture("verification/verification-method.json")

    assert set(fixture) == {
        "schema",
        "id",
        "requirement_id",
        "requirement_version",
        "method",
        "target",
        "status",
        "created_by",
        "created_at",
    }
    assert fixture["schema"] == "loom.charter.verification_method.v1"
    assert fixture["id"].startswith("VERM-")
    assert fixture["requirement_id"].startswith("REQ-AUTH-")
    assert isinstance(fixture["requirement_version"], int)
    assert fixture["method"] in VERIFICATION_METHODS
    assert fixture["target"]
    assert fixture["status"] == "active"
    assert fixture["created_by"].startswith(("human:", "agent:"))
    assert isinstance(fixture["created_at"], str)


def test_verification_evidence_fixture_contract() -> None:
    fixture = load_fixture("verification/verification-evidence.json")

    assert set(fixture) == {
        "schema",
        "id",
        "method_id",
        "requirement_id",
        "requirement_version",
        "status",
        "evidence_ref",
        "authority",
        "freshness",
        "recorded_by",
        "recorded_at",
        "payload",
    }
    assert fixture["schema"] == "loom.charter.verification_evidence.v1"
    assert fixture["id"].startswith("EVID-")
    assert fixture["method_id"].startswith("VERM-")
    assert fixture["requirement_id"].startswith("REQ-AUTH-")
    assert isinstance(fixture["requirement_version"], int)
    assert fixture["status"] in VERIFICATION_EVIDENCE_STATUSES
    assert fixture["evidence_ref"]
    assert fixture["authority"] in VERIFICATION_AUTHORITIES
    assert fixture["freshness"] in VERIFICATION_FRESHNESS
    assert fixture["recorded_by"].startswith(("human:", "agent:"))
    assert isinstance(fixture["recorded_at"], str)
    assert isinstance(fixture["payload"], dict)


def test_requirement_verification_status_fixture_contract() -> None:
    fixture = load_fixture("verification/requirement-verification-status.json")

    assert set(fixture) == {
        "schema",
        "requirement_id",
        "id",
        "stable_id",
        "current_version",
        "status",
        "reasons",
        "current_evidence",
        "stale_evidence",
    }
    assert fixture["schema"] == "loom.charter.requirement_verification_status.v1"
    assert fixture["requirement_id"].startswith("req-")
    assert fixture["id"].startswith("REQ-AUTH-")
    assert fixture["stable_id"].startswith("charter:req:AUTH:")
    assert isinstance(fixture["current_version"], int)
    assert fixture["status"] in REQUIREMENT_VERIFICATION_STATUSES
    assert isinstance(fixture["reasons"], list)
    assert fixture["reasons"]
    for reason in fixture["reasons"]:
        assert set(reason) == {"code", "message", "evidence_id"}
        assert reason["code"]
        assert reason["message"]
    assert isinstance(fixture["current_evidence"], list)
    assert isinstance(fixture["stale_evidence"], list)


def test_requirement_dossier_fixture_contract() -> None:
    fixture = load_fixture("dossiers/requirement-dossier.json")

    assert set(fixture) == {
        "schema",
        "identity",
        "authority_summary",
        "requirement",
        "acceptance_criteria",
        "traces",
        "verification",
        "baseline_exposure",
        "computed_gaps",
        "peer_facts",
        "next_actions",
    }
    assert fixture["schema"] == "loom.charter.requirement_dossier.v1"
    assert set(fixture["identity"]) == {"requirement_id", "id", "stable_id", "current_version"}
    assert set(fixture["authority_summary"]) == {
        "status",
        "current_approved_version",
        "current_statement_hash",
        "has_active_draft",
        "active_draft_id",
        "verification_status",
        "baseline_count",
    }
    assert set(fixture["requirement"]) == {"record", "current_version", "active_draft"}
    assert set(fixture["acceptance_criteria"]) == {"current_version", "active_draft"}
    assert set(fixture["traces"]) == {"incoming", "outgoing", "by_state", "by_relation", "items"}
    assert set(fixture["verification"]) == {"status", "reasons", "current_evidence", "stale_evidence"}
    assert set(fixture["baseline_exposure"]) == {"summary", "items"}
    assert set(fixture["peer_facts"]) == {"live_peer_calls", "sources", "notes"}
    assert fixture["peer_facts"]["live_peer_calls"] is False
    assert isinstance(fixture["computed_gaps"], list)
    assert isinstance(fixture["next_actions"], list)
    computed_gap_fixture = {
        "code": "no_verification_method",
        "severity": "high",
        "message": "Requirement has no verification method.",
        "source": "verification",
    }

    identity = fixture["identity"]
    requirement_record = fixture["requirement"]["record"]
    current_version = fixture["requirement"]["current_version"]
    current_version_record = requirement_record["current_version_record"]
    acceptance_criteria = fixture["acceptance_criteria"]["current_version"]
    statement_hash = fixture["authority_summary"]["current_statement_hash"]

    assert identity["requirement_id"] == "req-1"
    assert requirement_record["requirement_id"] == identity["requirement_id"]
    assert current_version["requirement_id"] == identity["requirement_id"]
    assert current_version_record["requirement_id"] == identity["requirement_id"]
    for criterion in acceptance_criteria:
        assert criterion["requirement_id"] == identity["requirement_id"]
    assert requirement_record["id"] == identity["id"]
    assert current_version["id"] == identity["id"]
    assert current_version_record["id"] == identity["id"]
    assert requirement_record["stable_id"] == identity["stable_id"]
    assert current_version["stable_id"] == identity["stable_id"]
    assert current_version_record["stable_id"] == identity["stable_id"]
    assert current_version["statement_hash"] == statement_hash
    assert current_version_record["statement_hash"] == statement_hash
    for exposure in fixture["baseline_exposure"]["items"]:
        assert exposure["baseline_statement_hash"] == statement_hash
        assert exposure["current_statement_hash"] == statement_hash
    for trace_group in ("incoming", "items"):
        for trace in fixture["traces"][trace_group]:
            if trace["relation"] == "provides_evidence_for":
                assert trace["to"] == {"kind": "verification_method", "id": "VERM-0001"}

    assert_computed_gap_shape(computed_gap_fixture)
    for gap in fixture["computed_gaps"]:
        assert_computed_gap_shape(gap)
    for action in fixture["next_actions"]:
        assert_next_action_shape(action)
