"""Weft SEI §8 conformance oracle — Plainweave as consumer.

Plainweave consumes Loomweave's Stable Entity Identity (SEI) via
:class:`plainweave.loomweave_adapter.LoomweaveAdapter`. This module proves
Plainweave is a §8 SEI CONFORMER: each of the six shared scenarios is driven
through the REAL adapter HTTP resolve path (``resolve_identity`` →
``_resolve_identity_http``) with a fake ``_http_json`` injected at the same seam
the existing ``test_identity_resolution_over_http_*`` tests use. The assertions
check the consumer's own verdict — alive / orphaned / unsupported / opacity —
NOT a re-implementation of the oracle (NON-CIRCULAR).

The scenario list is loaded from the vendored ``sei-conformance-oracle.json``
fixture, copied BYTE-VERBATIM from Loomweave's authoritative fixture. Loomweave
is the PRODUCER/authority for the six-scenario §8 oracle; Plainweave is the
CONSUMER. Two layers protect the vendored bytes:

  * Layer 1 (default suite): ``UPSTREAM_BLOB_SHA`` git-blob byte-pin — any edit
    to the vendored copy reds the default PR suite.
  * Layer 2 (opt-in, ``-m sei_drift``): byte-compare against the sibling
    Loomweave checkout — the release-gate drift alarm; skips clean when the
    sibling is absent.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from tests.loomweave_test_utils import seed_loomweave_catalog

from plainweave.loomweave_adapter import LoomweaveAdapter, LoomweaveIdentityError

ORACLE_PATH = Path(__file__).parent / "fixtures" / "sei-conformance-oracle.json"

# The git blob hash of the vendored SEI conformance oracle as authored upstream by
# Loomweave (docs/federation/fixtures/sei-conformance-oracle.json). Loomweave is the
# PRODUCER/authority for the six-scenario §8 oracle; Plainweave is the CONSUMER and
# VENDORS the fixture byte-verbatim. This Layer-1 byte-pin runs in the DEFAULT suite,
# so ANY byte change to the vendored copy fails loudly — re-vendors are deliberate and
# update this constant in the SAME commit as the new bytes.
#
# RE-VENDOR PROCEDURE (run ``pytest -m sei_drift -v`` before every release; on drift, or
# on a deliberate upstream oracle bump):
#   1. Copy ``$LOOMWEAVE_REPO/docs/federation/fixtures/sei-conformance-oracle.json``
#      byte-verbatim over the vendored copy (``cmp`` to confirm). NEVER hand-edit the
#      vendored fixture; Loomweave's oracle (cargo gate ``sei_conformance_oracle``) is the
#      only author.
#   2. Update ``UPSTREAM_BLOB_SHA`` to ``git hash-object`` of the vendored file
#      (equivalently ``hashlib.sha1(b"blob %d\0" % len(data) + data)``) — same commit.
#   3. Re-run conformance and CONFORM the consumer (``plainweave.loomweave_adapter``)
#      until green; never weaken the assertions.
UPSTREAM_BLOB_SHA = "0ea577025d94c028a0f682b7d29765079455718c"

CAPABILITIES_PATH = "/api/v1/_capabilities"
SEI_SUPPORTED_CAPS: dict[str, Any] = {"sei": {"supported": True, "version": 1}}


def _load_oracle() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(ORACLE_PATH.read_text(encoding="utf-8")))


def _scenario(scenario_id: str) -> dict[str, Any]:
    for item in _load_oracle()["scenarios"]:
        if item["id"] == scenario_id:
            return cast("dict[str, Any]", item)
    raise AssertionError(f"missing SEI oracle scenario {scenario_id!r}")


def _loomweave_oracle_source() -> Path | None:
    # Env takes EXCLUSIVE precedence: if ``LOOMWEAVE_REPO`` is set, resolve the sibling
    # ONLY from it and skip clean if the oracle is absent under it. Otherwise fall back
    # to the documented local-dev convenience checkout at ``/home/john/loomweave``. A
    # CI runner (env unset, no convenience sibling) skips clean — the documented basis
    # for the clean skip is the sibling's ABSENCE, not a guarantee independent of layout.
    subpath = ("docs", "federation", "fixtures", "sei-conformance-oracle.json")
    env = os.environ.get("LOOMWEAVE_REPO")
    if env:
        path = Path(env).joinpath(*subpath)
        return path if path.exists() else None
    path = Path("/home/john/loomweave").joinpath(*subpath)
    return path if path.exists() else None


COVERED_SCENARIOS = {
    "identity_round_trip_and_opacity",
    "rename",
    "move",
    "ambiguous",
    "delete",
    "capability_absent",
}


def _fake_http_json(
    *,
    caps: dict[str, Any] | None,
    identity: dict[str, Any] | None,
    calls: list[str],
) -> Callable[..., dict[str, object]]:
    """Build a fake ``_http_json`` that records every wire path and routes the
    ``_capabilities`` probe to ``caps`` and any identity resolve to ``identity``."""

    def fake(method: str, path: str, payload: object | None = None) -> dict[str, object]:
        calls.append(path)
        if path == CAPABILITIES_PATH:
            if caps is None:
                # Model a remote that 2xx-returns a body with no SEI capability.
                return {}
            return cast("dict[str, object]", caps)
        assert identity is not None, f"unexpected identity wire call: {path}"
        return cast("dict[str, object]", identity)

    return fake


# --------------------------------------------------------------------------- #
# Fixture integrity (Layer 1 + Layer 2)                                        #
# --------------------------------------------------------------------------- #


def test_vendored_oracle_matches_upstream_blob_pin() -> None:
    """Layer 1 (default suite): the vendored SEI oracle byte-pins to the upstream
    git blob hash. ANY edit to the vendored fixture without a matching re-pin reds
    the default suite — the fail-closed protection that lets the Layer-2 drift
    recheck skip clean when the sibling checkout is absent."""
    assert len(UPSTREAM_BLOB_SHA) == 40 and set(UPSTREAM_BLOB_SHA) <= set("0123456789abcdef"), (
        f"UPSTREAM_BLOB_SHA must be 40 lowercase hex chars (a git blob SHA-1): {UPSTREAM_BLOB_SHA!r}"
    )
    data = ORACLE_PATH.read_bytes()
    actual = hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()
    assert actual == UPSTREAM_BLOB_SHA, (
        f"the vendored SEI oracle changed (git blob {actual}, pinned {UPSTREAM_BLOB_SHA}) — "
        "if this was a deliberate re-vendor, update UPSTREAM_BLOB_SHA in the same commit and "
        "re-run conformance; if not, someone edited the vendored copy (forbidden — Loomweave's "
        "oracle is the only author; see the RE-VENDOR PROCEDURE at the top of this module)"
    )


@pytest.mark.sei_drift
def test_vendored_oracle_matches_loomweave_source() -> None:
    """Layer 2 (opt-in, ``-m sei_drift``): the sibling Loomweave checkout's
    authoritative oracle must be BYTE-IDENTICAL to the vendored copy — the
    release-gate drift alarm. Absent checkout (CI/default suite) skips clean;
    divergence FAILS.

    FAIL-CLOSED ARMING: a release gate sets ``PLAINWEAVE_SEI_DRIFT_REQUIRED`` to
    turn the skip into a HARD FAILURE when the sibling oracle is missing — so an
    armed drift gate cannot silently no-op (e.g. a runner that forgot to provide
    ``LOOMWEAVE_REPO``). Unset (the default) keeps the skip-clean behaviour.

    Byte-exact (not JSON-semantic) by design: the RE-VENDOR PROCEDURE mandates a
    byte-verbatim copy and the Layer-1 ``UPSTREAM_BLOB_SHA`` pins the git blob, so
    a copy that is reordered/reformatted (JSON-equal but byte-different) would leave
    the blob-pin silently stale yet pass a parsed-dict compare. Comparing raw bytes
    enforces the same byte-verbatim invariant Layer-1 assumes."""
    source = _loomweave_oracle_source()
    if source is None:
        if os.environ.get("PLAINWEAVE_SEI_DRIFT_REQUIRED"):
            pytest.fail(
                "SEI drift check ARMED (PLAINWEAVE_SEI_DRIFT_REQUIRED) but no Loomweave sibling "
                "oracle was found — point LOOMWEAVE_REPO at a checkout that carries "
                "docs/federation/fixtures/sei-conformance-oracle.json so drift can be proven"
            )
        pytest.skip("Loomweave repo not found; set LOOMWEAVE_REPO to enable the drift check")
    if ORACLE_PATH.read_bytes() != source.read_bytes():
        pytest.fail(
            f"upstream {source} has drifted from the vendored "
            "tests/conformance/fixtures/sei-conformance-oracle.json — re-vendor + conform: follow "
            "the RE-VENDOR PROCEDURE at the top of this module (byte-verbatim copy, bump "
            "UPSTREAM_BLOB_SHA in the same commit, re-run conformance)"
        )


def test_every_oracle_scenario_is_covered() -> None:
    fixture_ids = {item["id"] for item in _load_oracle()["scenarios"]}
    assert fixture_ids == COVERED_SCENARIOS


# --------------------------------------------------------------------------- #
# The six §8 scenarios, driven through the REAL adapter HTTP resolve path       #
# --------------------------------------------------------------------------- #


def test_identity_round_trip_and_opacity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """round_trip: resolve(locator) → sei; resolve(sei) → locator; the SEI is opaque
    (carries the reserved prefix, is never equal to the locator, never parsed)."""
    scenario = _scenario("identity_round_trip_and_opacity")
    seed = seed_loomweave_catalog(tmp_path)
    locator = seed["public_locator"]
    sei = seed["public_sei"]
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")
    adapter = LoomweaveAdapter(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        adapter,
        "_http_json",
        _fake_http_json(
            caps=SEI_SUPPORTED_CAPS,
            identity={"alive": True, "current_locator": locator, "sei": sei, "content_hash": "hash-public-v1"},
            calls=calls,
        ),
    )

    by_locator = adapter.resolve_identity(locator)
    by_sei = adapter.resolve_identity(sei)

    assert scenario["expect"]["resolve_locator"]["alive"] is True
    # resolve(locator) → sei
    assert by_locator.locator == locator
    assert by_locator.sei == sei
    assert by_locator.lineage_status == "alive"
    # resolve(sei) → locator
    assert by_sei.locator == locator
    assert by_sei.sei == sei
    # opacity: reserved prefix, not equal to the locator (the consumer never parses it).
    assert by_locator.sei is not None and by_locator.sei.startswith("loomweave:eid:")
    assert by_locator.sei != locator
    assert CAPABILITIES_PATH in calls


@pytest.mark.parametrize("scenario_id", ["rename", "move"])
def test_carried_sei_remains_alive_for_rename_and_move(
    scenario_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """rename / move: identity is CARRIED — the same SEI resolves alive (at the new
    locator), so the consumer's verdict stays ALIVE across the re-index."""
    scenario = _scenario(scenario_id)
    seed = seed_loomweave_catalog(tmp_path)
    new_locator = seed["public_locator"]
    carried_sei = seed["public_sei"]
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")
    adapter = LoomweaveAdapter(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        adapter,
        "_http_json",
        _fake_http_json(
            caps=SEI_SUPPORTED_CAPS,
            identity={
                "alive": True,
                "current_locator": new_locator,
                "sei": carried_sei,
                "content_hash": "hash-public-v1",
            },
            calls=calls,
        ),
    )

    resolved = adapter.resolve_identity(carried_sei)

    assert scenario["expect"]["carry"] is True
    assert resolved.sei == carried_sei  # carried verbatim — unchanged token
    assert resolved.locator == new_locator
    assert resolved.lineage_status == "alive"


@pytest.mark.parametrize("scenario_id", ["ambiguous", "delete"])
def test_orphaned_sei_surfaces_as_orphaned_for_ambiguous_and_delete(
    scenario_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ambiguous / delete: the old binding is ORPHANED — resolve_sei returns
    ``alive:false`` with an ``orphaned`` lineage event, so the consumer raises the
    ``orphaned`` verdict (fail-closed: never silently re-pointed)."""
    scenario = _scenario(scenario_id)
    seed = seed_loomweave_catalog(tmp_path)
    orphaned_sei = seed["public_sei"]
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")
    adapter = LoomweaveAdapter(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        adapter,
        "_http_json",
        _fake_http_json(
            caps=SEI_SUPPORTED_CAPS,
            identity={"alive": False, "lineage": [{"event": "orphaned"}]},
            calls=calls,
        ),
    )

    assert "orphaned" in json.dumps(scenario["expect"])
    with pytest.raises(LoomweaveIdentityError) as exc_info:
        adapter.resolve_identity(orphaned_sei)

    assert exc_info.value.reason == "orphaned"


@pytest.mark.parametrize(
    "caps",
    [
        pytest.param({"sei": {"supported": False}}, id="supported_false"),
        pytest.param({}, id="sei_key_absent"),
        pytest.param({"sei": {"version": 1}}, id="supported_key_absent"),
    ],
)
def test_capability_absent_degrades_honestly(
    caps: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """capability_absent: a REACHABLE remote whose ``_capabilities.sei.supported`` is
    false OR ABSENT (the §8 scenario names both) → the consumer detects the absent
    capability and degrades HONESTLY to ``unsupported`` (identity unavailable) — NOT
    ``unreachable`` (down), and NEVER a fabricated alive identity. The identity resolve
    route is never even called."""
    scenario = _scenario("capability_absent")
    seed = seed_loomweave_catalog(tmp_path)
    locator = seed["public_locator"]
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")
    adapter = LoomweaveAdapter(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        adapter,
        "_http_json",
        # Reachable remote (the probe 2xx-returns), but SEI is not supported / not advertised.
        _fake_http_json(caps=caps, identity=None, calls=calls),
    )

    assert "DEGRADES gracefully" in json.dumps(scenario["expect"])
    with pytest.raises(LoomweaveIdentityError) as exc_info:
        adapter.resolve_identity(locator)

    # Honest degrade: capability-absent, NOT a down/unreachable verdict.
    assert exc_info.value.reason == "unsupported"
    assert exc_info.value.reason != "unreachable"
    # The consumer probed _capabilities and STOPPED — it never resolved against a
    # remote it knows serves no SEI (no fabricated identity).
    assert calls == [CAPABILITIES_PATH]


def test_capability_absent_distinguished_from_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The split that makes capability_absent honest: a DOWN remote (the probe itself
    raises) still surfaces ``unreachable``, while a REACHABLE pre-SEI remote surfaces
    ``unsupported``. Conflating the two is exactly the §8 capability_absent failure."""
    seed = seed_loomweave_catalog(tmp_path)
    locator = seed["public_locator"]
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")

    # (a) Remote DOWN: the probe raises before any capability is read → unreachable.
    down = LoomweaveAdapter(tmp_path)

    def probe_raises(method: str, path: str, payload: object | None = None) -> dict[str, object]:
        raise LoomweaveIdentityError(
            "unreachable",
            "down",
            [{"code": "identity_unreachable", "message": "down"}],
        )

    monkeypatch.setattr(down, "_http_json", probe_raises)
    with pytest.raises(LoomweaveIdentityError) as down_exc:
        down.resolve_identity(locator)
    assert down_exc.value.reason == "unreachable"

    # (b) Remote REACHABLE but pre-SEI → unsupported (the honest capability_absent).
    absent = LoomweaveAdapter(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(
        absent,
        "_http_json",
        _fake_http_json(caps={"sei": {"supported": False}}, identity=None, calls=calls),
    )
    with pytest.raises(LoomweaveIdentityError) as absent_exc:
        absent.resolve_identity(locator)
    assert absent_exc.value.reason == "unsupported"
