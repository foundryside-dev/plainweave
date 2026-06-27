from __future__ import annotations

import pytest

from tests.warpline_contract import assert_no_warpline_verdicts, validate_requirements_enrichment


def test_validator_accepts_minimal_payload() -> None:
    validate_requirements_enrichment(
        {
            "items": [
                {"entity_ref": "loomweave:eid:x", "status": "unavailable",
                 "requirements": [], "reason": "cannot determine", "freshness": "unavailable"}
            ],
            "summary": {"present": 0, "absent": 0, "unavailable": 1},
            "authority_boundary": {"local_only": True, "live_peer_calls": False,
                                   "governance_verdicts": False, "requirements_owner": "plainweave"},
        }
    )


def test_present_requires_non_empty_requirements() -> None:
    with pytest.raises(AssertionError):
        validate_requirements_enrichment(
            {
                "items": [{"entity_ref": "e", "status": "present", "requirements": [],
                           "reason": None, "freshness": "current"}],
                "summary": {"present": 1, "absent": 0, "unavailable": 0},
                "authority_boundary": {"local_only": True, "live_peer_calls": False,
                                       "governance_verdicts": False, "requirements_owner": "plainweave"},
            }
        )


def test_rejects_verdict_token() -> None:
    with pytest.raises(AssertionError):
        assert_no_warpline_verdicts({"status": "blocked"})
