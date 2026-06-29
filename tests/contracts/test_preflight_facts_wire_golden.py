"""Plainweave-authored ``weft.plainweave.preflight_facts.v1`` envelope frozen to a
vendored byte golden (ADR-006), with a non-circular producer-source recheck.

``tests/fixtures/contracts/legis/preflight-facts.json`` is the preflight-facts
``schema + data`` payload plainweave emits from
``PlainweaveMcpSurface.plainweave_preflight_facts_get`` — the producer named in
ADR-006 (Status: Accepted). Legis is the CONSUMER of this envelope. As of
2026-06-29 a legis-side consumer + constructed oracle of this contract exists, but
per the federation enrich-only discipline that read ships solo and creates NO
plainweave obligation — plainweave OWNS the contract and legis conforms to it. This
row therefore stays PRODUCER-SIDE ONLY by design: it freezes plainweave's own
produced bytes and ties them to the live producer; plainweave runs no cross-repo
drift gate against the legis copy (legis re-pins on its side).

PLAINWEAVE IS THE AUTHORITY for this seam — it OWNS the preflight-facts shape via
``PlainweaveMcpSurface.plainweave_preflight_facts_get``. The protection is a
two-layer affair (mirroring wardline's vocabulary-descriptor wire golden):

* Layer-1 (``test_golden_matches_blob_pin``): a git-blob byte-pin on the vendored
  golden, so any silent edit to the envelope wire reds the default suite. On its
  OWN this is CIRCULAR — plainweave pins plainweave's own bytes.
* Producer-source recheck (``test_golden_matches_live_producer``): the
  non-circular break. It re-invokes the REAL producer
  (``PlainweaveMcpSurface.plainweave_preflight_facts_get``) over a fixed,
  deterministically seeded tmp project and asserts the regenerated ``schema +
  data`` payload EQUALS the frozen golden. The frozen bytes are tied to the live
  producer, so if the envelope shape drifts from the golden — a fact kind
  added/removed, a message/severity/provenance changed, a section added — it reds
  even though the byte-pin still passes.

NON-DETERMINISTIC / RELEASE-COUPLED FIELDS (honest caveat). The producer embeds
exactly two fields that are not byte-stable across runs/releases:

* ``data.generated_at`` — ``datetime.now(UTC).isoformat()``; changes every call.
* ``data.producer.version`` — ``plainweave.__version__``; bumps every release with
  no contract change.

The golden freezes these to realistic, representative values
(``generated_at`` = ``2026-06-04T10:00:00+00:00``, ``producer.version`` =
``1.0.0``) so it reads as a real envelope and the byte-pin is stable across the
clock and releases. The recheck keeps them bound to the LIVE producer
NON-CIRCULARLY: BEFORE normalizing it asserts the regenerated ``generated_at``
parses as an aware ISO-8601 UTC instant and that the regenerated
``producer.version`` EQUALS the live ``plainweave.__version__`` — these
pre-normalization asserts ARE the non-circularity for the two normalized fields.
ONLY THEN does it copy the golden's frozen values over those two fields and
assert deep dict-equality. A producer that dropped ``generated_at`` or emitted a
garbage version would red on the asserts, not be hidden by the normalization.

RE-VENDOR PROCEDURE: if you deliberately change the preflight-facts shape (a new
fact kind, a changed message, an added section), regenerate the golden from the
real producer over the seeding below, freeze ``generated_at`` /
``producer.version`` back to the representative values, recompute the blob SHA
(``git hash-object tests/fixtures/contracts/legis/preflight-facts.json``) and
update ``UPSTREAM_BLOB_SHA`` in the SAME commit — the recheck will otherwise red.
The independent structural check in
``tests/contracts/test_contract_fixtures.py::test_preflight_facts_fixture_contract``
validates the same golden through ``validate_preflight_facts`` as a free
cross-check.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from tests.loomweave_test_utils import seed_loomweave_catalog

from plainweave import __version__
from plainweave.mcp_surface import PlainweaveMcpSurface
from plainweave.models import TraceRef
from plainweave.service import PlainweaveService
from plainweave.store import migrate

GOLDEN_PATH = Path(__file__).parents[1] / "fixtures" / "contracts" / "legis" / "preflight-facts.json"

# Layer-1 byte-pin: the git-blob SHA-1 of legis/preflight-facts.json. Recomputed
# below as hashlib.sha1(b"blob %d\0" % len(data) + data) (== `git hash-object`).
# Any edit to the vendored golden without a matching re-pin reds the default suite.
UPSTREAM_BLOB_SHA = "10506f0359317da614237df3694f038bc141009e"

# The two fields the producer cannot emit deterministically; the golden freezes
# them to representative values and the recheck re-binds them to the live producer.
_FROZEN_GENERATED_AT = "2026-06-04T10:00:00+00:00"
_FROZEN_VERSION = "1.0.0"


def _seed_preflight_project(root: Path) -> dict[str, Any]:
    """Deterministically seed a tmp project that exercises every preflight fact kind.

    Mirrors the seeding in
    ``tests/test_mcp_read_surface.py::test_mcp_preflight_facts_returns_scoped_advisory_facts_without_verdicts``
    so the regenerated envelope reproduces the frozen golden byte-for-byte (modulo
    the two normalized fields). All inputs (IDs, SEIs, content hashes, dates) are
    fixed, so the producer's output is stable across runs.
    """
    db_path = root / ".plainweave" / "plainweave.db"
    migrate(db_path, project_key="AUTH")
    service = PlainweaveService(db_path, root=root)
    seed = seed_loomweave_catalog(root)

    def approve(*, title: str, statement: str, criterion: str, key: str) -> str:
        draft = service.create_requirement(title, statement, "human:john")
        service.add_acceptance_criterion(draft.id, criterion, actor="human:john")
        service.approve_requirement(draft.id, actor="human:john", expected_version=0, idempotency_key=key)
        return draft.id

    stale = approve(
        title="Rotate signing keys",
        statement="The API shall rotate signing keys.",
        criterion="Rotated keys are accepted.",
        key="approve-stale",
    )
    method = service.add_verification_method(
        stale, method="test", target="tests/test_keys.py::test_rotation", actor="human:john"
    )
    service.record_verification_evidence(
        method.id,
        status="passing",
        evidence_ref="pytest:tests/test_keys.py::test_rotation",
        actor="agent:codex",
    )
    service.create_trace_link(
        TraceRef("loomweave_entity", seed["public_locator"]),
        "satisfies",
        TraceRef("requirement_version", f"{stale}@1"),
        actor="human:john",
        authority="accepted",
    )
    baseline = service.create_baseline("Release 1.0", actor="human:john")
    service.supersede_requirement(
        stale,
        title="Rotate signing keys promptly",
        statement="The API shall rotate signing keys within the configured window.",
        actor="human:john",
        expected_version=1,
        idempotency_key="supersede-stale",
    )
    missing = approve(
        title="Audit password resets",
        statement="The API shall audit password resets.",
        criterion="Password resets are audited.",
        key="approve-missing",
    )
    return {
        "root": root,
        "stale": stale,
        "missing": missing,
        "baseline_id": baseline.id,
        "public_sei": seed["public_sei"],
    }


def _produce_schema_plus_data(root: Path) -> dict[str, Any]:
    """Re-invoke the REAL producer and return the ``schema + data`` payload shape
    the golden vendors (``{"schema": ..., **data}``, NOT the full envelope)."""
    seeded = _seed_preflight_project(root)
    surface = PlainweaveMcpSurface(root)
    envelope = surface.plainweave_preflight_facts_get(
        scope_kind="pending_diff",
        base="main",
        head="WORKTREE",
        requirement_ids=[seeded["stale"], seeded["missing"]],
        entity_refs=[seeded["public_sei"], "loomweave:eid:untraced"],
        baseline_id=seeded["baseline_id"],
    )
    assert envelope["ok"] is True
    return {"schema": envelope["schema"], **cast(dict[str, Any], envelope["data"])}


def test_golden_matches_blob_pin() -> None:
    """Layer-1 (default suite): the plainweave-authored preflight-facts golden
    byte-pins to its git blob hash. ANY edit without a matching re-pin reds the
    default suite. On its OWN this pin is plainweave-pins-plainweave (circular);
    the non-circular protection is ``test_golden_matches_live_producer`` below,
    which regenerates the payload from the LIVE producer."""
    assert len(UPSTREAM_BLOB_SHA) == 40 and set(UPSTREAM_BLOB_SHA) <= set("0123456789abcdef"), (
        f"UPSTREAM_BLOB_SHA must be 40 lowercase hex chars (a git blob SHA-1): {UPSTREAM_BLOB_SHA!r}"
    )
    data = GOLDEN_PATH.read_bytes()
    actual = hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()
    assert actual == UPSTREAM_BLOB_SHA, (
        f"the vendored preflight-facts golden changed (git blob {actual}, pinned {UPSTREAM_BLOB_SHA}) — "
        "if this was a deliberate re-vendor, regenerate it from the real producer, freeze generated_at / "
        "producer.version back to the representative values, update UPSTREAM_BLOB_SHA in the same commit "
        "(see the RE-VENDOR PROCEDURE at the top of this module); if not, revert the edit."
    )


def test_golden_matches_live_producer(tmp_path: Path) -> None:
    """PRODUCER-SOURCE recheck (non-circular): regenerate the preflight-facts
    payload from the REAL ``plainweave_preflight_facts_get`` producer over a fixed
    seeded project and assert it EQUALS the frozen golden. This ties the
    byte-pinned golden to the live producer, so an envelope-shape drift — a fact
    kind added/removed, a message/severity/provenance changed, a section added —
    without a re-vendor reds even though the byte-pin still passes.

    The two non-deterministic / release-coupled fields (``generated_at``,
    ``producer.version``) are asserted LIVE *before* being normalized to the
    golden's frozen values; those pre-normalization asserts are what keep drift
    coverage on the exact fields the normalization clobbers."""
    golden = cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text("utf-8")))
    regenerated = _produce_schema_plus_data(tmp_path)

    # --- non-circular core: assert the LIVE values BEFORE clobbering them ---
    generated_at = regenerated["generated_at"]
    parsed = datetime.fromisoformat(generated_at)  # valid ISO-8601…
    assert parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0, (  # type: ignore[union-attr]
        f"generated_at must be an aware UTC instant, got {generated_at!r}"
    )
    assert regenerated["producer"]["version"] == __version__, (
        f"producer.version must equal the live plainweave.__version__ ({__version__!r}), "
        f"got {regenerated['producer']['version']!r}"
    )

    # --- normalize the two fields to the golden's frozen values, then deep-compare ---
    assert golden["generated_at"] == _FROZEN_GENERATED_AT
    assert golden["producer"]["version"] == _FROZEN_VERSION
    normalized = copy.deepcopy(regenerated)
    normalized["generated_at"] = golden["generated_at"]
    normalized["producer"]["version"] = golden["producer"]["version"]

    assert normalized == golden, (
        "the live preflight-facts producer drifted from the vendored golden — see the "
        "RE-VENDOR PROCEDURE at the top of this module."
    )
