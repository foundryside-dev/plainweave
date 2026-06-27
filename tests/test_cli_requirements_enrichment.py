from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main
from tests.test_warpline_requirements_enrichment import _seed_bound
from tests.warpline_contract import assert_no_warpline_verdicts, validate_requirements_enrichment

_MISSING = "loomweave:eid:missing00000000000000000000000000"


def test_requirements_enrichment_cli_mixed_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _surface, seed = _seed_bound(tmp_path)
    monkeypatch.chdir(tmp_path)
    refs = [seed["public_sei"], seed["module_sei"], _MISSING]
    assert main(["requirements-enrichment", *refs, "--json"]) == 0
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["schema"] == "weft.plainweave.requirements_enrichment.v1"
    assert envelope["ok"] is True
    data = cast(dict[str, Any], envelope["data"])
    validate_requirements_enrichment(data)
    assert_no_warpline_verdicts(envelope)
    statuses = {it["entity_ref"]: it["status"] for it in data["items"]}
    assert statuses[seed["public_sei"]] == "present"
    assert statuses[seed["module_sei"]] == "absent"
    assert statuses[_MISSING] == "unavailable"  # identity gap is unavailable, NOT absent


def test_requirements_enrichment_cli_uninitialized_is_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)  # no .plainweave/ store
    assert main(["requirements-enrichment", "python:function:x.y", "--json"]) == 2
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "NOT_FOUND"
