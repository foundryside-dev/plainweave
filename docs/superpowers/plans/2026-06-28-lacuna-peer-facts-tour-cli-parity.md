# Lacuna peer-facts tour + Plainweave CLI parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Plainweave's two MCP-only peer-facts producers over `plainweave … --json`, and extend the Lacuna cross-member tour with `plainweave+wardline` and `plainweave+warpline` cells that regression-protect them.

**Architecture:** Part A adds two flat argparse subcommands in Plainweave that reuse `PlainweaveMcpSurface` verbatim (local import inside each handler to dodge the `mcp_surface → cli_commands` import cycle). Part B adds two Lacuna tour steps following the `plainweave_intent()` pattern — one drives `requirements-enrichment` over the existing seed; one drives `wardline-peer-facts` over a tour-time-generated frozen two-snapshot fixture.

**Tech Stack:** Python 3.12, argparse, pytest (Plainweave: uv, mypy --strict, ruff, coverage ≥90); Lacuna tour harness (`make tour`/`make verify`/`make ci`).

## Global Constraints
- **Invariants (assert, don't assume):** advisory only; **zero verdict vocabulary**; local-first (no live peer calls); **no-silent-clean** — `unresolved`/dead-binding → `unavailable` never `absent`; absent `.wardline/` → `unavailable` never clean.
- **Deterministic, frozen anchors** — no hardcoded hex SEIs; refs are stable dotted locators; the wardline fixture is frozen constants.
- **Reuse, don't duplicate** — CLI handlers call `PlainweaveMcpSurface`; never re-assemble envelope logic.
- **Plainweave gates:** `make ci` (ruff `E,F,I,UP,B,SIM` @120; mypy `strict=true`; `pytest --cov=plainweave --cov-fail-under=90`) + `wardline scan . --fail-on ERROR` clean.
- **Lacuna gates:** `make ci` (= `test scan verify cargo-check`); `make verify` (coverage + byte-lockstep). Lacuna has no mypy gate — match the repo's looser typing.
- **Envelope facts (verbatim):** success `{schema, ok, data, warnings, meta}`; error `{schema:"weft.plainweave.error.v1", ok:false, error:{code,message,recoverable,hint,details}, …}`. Exit code: `0` ok, `4` if `error.code=="INTERNAL"` else `2`.
- **Branch:** Plainweave `feat/lacuna-peer-facts-tour-cli-parity` (already created); Lacuna its own branch. No public push without owner sign-off.

---

## Task 1: Commit folded-in adjacent changes (Plainweave)

Already implemented + green (`tests/test_doctor.py` + `tests/test_warpline_requirements_enrichment.py`, 19 passed). Provenance: sibling product contract; owner-approved to ship here.

**Files:** Modify `src/plainweave/mcp_surface.py` (rejected-trace filter), `src/plainweave/cli_commands.py` (`_doctor_wardline_check` root-aware remediation), `tests/test_doctor.py`, `tests/test_warpline_requirements_enrichment.py`.

- [ ] **Step 1: Confirm green** — `uv run pytest tests/test_doctor.py tests/test_warpline_requirements_enrichment.py -q` → all pass.
- [ ] **Step 2: Commit (only these 4 files)** —
```bash
git add src/plainweave/mcp_surface.py src/plainweave/cli_commands.py tests/test_doctor.py tests/test_warpline_requirements_enrichment.py
git commit -m "fix(peer-facts): drop rejected traces from enrichment + root-aware doctor remediation"
```
(Do NOT stage `.gitignore`/`AGENTS.md`/`CLAUDE.md` — pre-existing session mods, not ours.)

---

## Task 2: `plainweave wardline-peer-facts` subcommand (TDD)

**Files:**
- Modify `src/plainweave/cli_commands.py` (registration after `dossier` block ~line 122; add `handle_wardline_peer_facts` + shared `_emit_surface_result`)
- Test: `tests/test_cli_wardline_peer_facts.py`

**Interfaces:**
- Consumes: `PlainweaveMcpSurface.plainweave_wardline_peer_facts_list(*, limit, offset)`; `project_root()`; `_emit_error`; `error_envelope`/`ErrorCode` (already imported).
- Produces: subcommand `wardline-peer-facts [--json] [--limit N] [--offset N]`; helper `_emit_surface_result(args, envelope) -> int`.

- [ ] **Step 1: Write the failing test** — `tests/test_cli_wardline_peer_facts.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main
from tests.wardline_contract import assert_no_wardline_verdicts, validate_wardline_peer_facts


def _active_defect() -> dict[str, Any]:
    return {
        "fingerprint": "fp-active", "rule_id": "PY-WL-101", "kind": "defect",
        "severity": "ERROR", "suppression_state": "active", "suppression_reason": None,
        "location": {"path": "src/a.py", "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
        "qualname": "a.unsafe", "message": "untrusted reaches a trusted producer",
    }


def _write(wdir: Path, name: str, records: list[dict[str, Any]]) -> None:
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / name).write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_wardline_peer_facts_emits_v1_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".wardline", "20260101T000000Z-findings.jsonl", [_active_defect()])
    assert main(["wardline-peer-facts", "--json"]) == 0
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["schema"] == "weft.plainweave.wardline_peer_facts.v1"
    assert envelope["ok"] is True
    data = cast(dict[str, Any], envelope["data"])
    validate_wardline_peer_facts(data)
    assert_no_wardline_verdicts(envelope)
    assert data["freshness"] == "current"


def test_wardline_peer_facts_absent_is_unavailable_not_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)  # no .wardline/
    assert main(["wardline-peer-facts", "--json"]) == 0
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    data = cast(dict[str, Any], envelope["data"])
    assert data["freshness"] == "unavailable"
    assert any(d["code"] == "wardline_findings_absent" for d in data["degraded"])
    validate_wardline_peer_facts(data)
    assert_no_wardline_verdicts(envelope)


def test_wardline_peer_facts_invalid_limit_is_validation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".wardline", "20260101T000000Z-findings.jsonl", [_active_defect()])
    assert main(["wardline-peer-facts", "--limit", "0", "--json"]) == 2
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "VALIDATION"


def test_wardline_peer_facts_human_output_prints_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path / ".wardline", "20260101T000000Z-findings.jsonl", [_active_defect()])
    assert main(["wardline-peer-facts"]) == 0
    data = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert data["freshness"] == "current"  # human path prints data (still JSON)
```
- [ ] **Step 2: Run → fail** — `uv run pytest tests/test_cli_wardline_peer_facts.py -q` → FAIL (unknown subcommand / no handler).
- [ ] **Step 3: Implement.** Registration after `dossier_parser.set_defaults(...)` (cli_commands.py:122):
```python
    wardline_facts_parser = subparsers.add_parser(
        "wardline-peer-facts",
        help="Surface Wardline findings as advisory peer facts (weft.plainweave.wardline_peer_facts.v1).",
    )
    wardline_facts_parser.add_argument("--limit", type=int, default=50, metavar="N", help="Max facts per page (1-100; default 50).")
    wardline_facts_parser.add_argument("--offset", type=int, default=0, metavar="N", help="Facts page offset (default 0).")
    wardline_facts_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    wardline_facts_parser.set_defaults(handler=handle_wardline_peer_facts)
```
Handler (top-level, near `handle_dossier`):
```python
def handle_wardline_peer_facts(args: argparse.Namespace) -> int:
    from plainweave.mcp_surface import PlainweaveMcpSurface  # local import: cli_commands<->mcp_surface cycle

    surface = PlainweaveMcpSurface(project_root())
    try:
        envelope = surface.plainweave_wardline_peer_facts_list(limit=args.limit, offset=args.offset)
    except PlainweaveError as exc:
        return _emit_error(args, exc)
    return _emit_surface_result(args, envelope)
```
Shared helper (near `_emit_error`, ~line 1159):
```python
def _emit_surface_result(args: argparse.Namespace, envelope: dict[str, Any]) -> int:
    """Print a peer-facts surface envelope and map it to an exit code.

    The surface returns a full envelope (success or error). `--json` prints it whole;
    the human path prints `data` on success or `CODE: message` on an error envelope.
    Exit mirrors `_emit_error`: 0 ok, 4 on INTERNAL, else 2.
    """
    ok = bool(envelope.get("ok"))
    if bool(args.json):
        print(json.dumps(envelope))
    elif ok:
        print(json.dumps(envelope["data"]))
    else:
        error = envelope.get("error")
        error = error if isinstance(error, dict) else {}
        print(f"{error.get('code', ErrorCode.INTERNAL.value)}: {error.get('message', '')}")
    if ok:
        return 0
    error = envelope.get("error")
    error = error if isinstance(error, dict) else {}
    return 4 if error.get("code") == ErrorCode.INTERNAL.value else 2
```
- [ ] **Step 4: Run → pass** — `uv run pytest tests/test_cli_wardline_peer_facts.py -q`.
- [ ] **Step 5: Lint + type** — `uv run ruff check src tests && uv run ruff format src tests && uv run mypy`.
- [ ] **Step 6: Commit** — `git add … && git commit -m "feat(cli): plainweave wardline-peer-facts subcommand (MCP/CLI parity)"`

---

## Task 3: `plainweave requirements-enrichment` subcommand (TDD)

**Files:** Modify `src/plainweave/cli_commands.py` (registration + `handle_requirements_enrichment`, reusing `_emit_surface_result`); Test `tests/test_cli_requirements_enrichment.py`.

**Interfaces:** Consumes `PlainweaveMcpSurface.plainweave_requirements_enrichment_get(*, entity_refs)` + `_seed_bound` from `tests/test_warpline_requirements_enrichment.py`. Produces subcommand `requirements-enrichment <ref>... [--json]`.

- [ ] **Step 1: Write the failing test** — `tests/test_cli_requirements_enrichment.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.cli import main
from tests.test_warpline_requirements_enrichment import _seed_bound
from tests.warpline_contract import assert_no_warpline_verdicts, validate_requirements_enrichment

_MISSING = "loomweave:eid:missing00000000000000000000000000"


def test_requirements_enrichment_cli_mixed_states(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    _surface, seed = _seed_bound(tmp_path)
    monkeypatch.chdir(tmp_path)
    refs = [seed["public_sei"], seed["module_sei"], _MISSING]
    assert main(["requirements-enrichment", *refs, "--json"]) == 0
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["schema"] == "weft.plainweave.requirements_enrichment.v1"
    data = cast(dict[str, Any], envelope["data"])
    validate_requirements_enrichment(data)
    assert_no_warpline_verdicts(envelope)
    statuses = {it["entity_ref"]: it["status"] for it in data["items"]}
    assert statuses[seed["public_sei"]] == "present"
    assert statuses[seed["module_sei"]] == "absent"
    assert statuses[_MISSING] == "unavailable"  # identity gap is unavailable, NOT absent


def test_requirements_enrichment_cli_uninitialized_is_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)  # no .plainweave/
    assert main(["requirements-enrichment", "python:function:x.y", "--json"]) == 2
    envelope = cast(dict[str, Any], json.loads(capsys.readouterr().out))
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "NOT_FOUND"
```
(If `_seed_bound`'s seed dict lacks `module_sei`, read it first and use the key it does expose for the resolves-but-unbound surface — `test_envelope_mixed_states` in the same file shows the canonical keys.)
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement.** Registration (after the wardline-peer-facts block):
```python
    enrichment_parser = subparsers.add_parser(
        "requirements-enrichment",
        help="Per-entity requirements enrichment for Warpline (weft.plainweave.requirements_enrichment.v1).",
    )
    enrichment_parser.add_argument("entity_ref", nargs="+", help="One or more entity refs (SEI or dotted locator).")
    enrichment_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    enrichment_parser.set_defaults(handler=handle_requirements_enrichment)
```
Handler:
```python
def handle_requirements_enrichment(args: argparse.Namespace) -> int:
    from plainweave.mcp_surface import PlainweaveMcpSurface  # local import: cli_commands<->mcp_surface cycle

    surface = PlainweaveMcpSurface(project_root())
    try:
        envelope = surface.plainweave_requirements_enrichment_get(entity_refs=args.entity_ref)
    except PlainweaveError as exc:
        return _emit_error(args, exc)
    return _emit_surface_result(args, envelope)
```
- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Lint + type** (as Task 2 Step 5).
- [ ] **Step 6: Commit** — `git commit -m "feat(cli): plainweave requirements-enrichment subcommand (MCP/CLI parity)"`

---

## Task 4: Plainweave governance (PDR-015 + CHANGELOG)

**Files:** Create `docs/product/decisions/PDR-015-cli-peer-facts-parity.md` (PDR-014 format); Modify `CHANGELOG.md` (new `## [Unreleased]` above `## [1.1.0]`); refresh `docs/product/current-state.md`.

- [ ] **Step 1:** Write PDR-015 (context: MCP-only parity gap; the call: two CLI subcommands reusing the surface; folded-in adjacent fixes attributed to sibling contract; relation to PDR-014; reversal trigger). Note the Lacuna-side tour work is recorded in Lacuna PDR-0015.
- [ ] **Step 2:** CHANGELOG `## [Unreleased]` → `### Added`: the two CLI subcommands; `### Fixed`: rejected-trace enrichment + root-aware doctor remediation. Version bump deferred (not a release blocker).
- [ ] **Step 3:** Commit — `git commit -m "docs(product): PDR-015 + CHANGELOG for CLI peer-facts parity"`
- [ ] **Step 4: Full Plainweave gate** — `make ci` green; `wardline scan . --fail-on ERROR` exit 0.

---

## Task 5: Lacuna `pw-requirements-enrichment` demo (TDD)  — repo `/home/john/lacuna`

Switch to the Lacuna repo; create branch `feat/peer-facts-tour-demos`.

**Files:** Modify `tour/steps.py` (anchors + `plainweave_requirements_enrichment()`); `tour/lacunae.toml` (entry); `tour/__main__.py` (register in `_drive`); Test `tests/test_steps_plainweave_peerfacts.py`.

**Interfaces:** Consumes `_plainweave_json`, `_tool`, `plainweave_seed.seed`, `StepResult`. Produces step `plainweave_requirements_enrichment() -> StepResult` surfacing `("pw-requirements-enrichment", "specimen.cli._add_book")`.

- [ ] **Step 1: Write the failing unit test** — `tests/test_steps_plainweave_peerfacts.py` (mirror `tests/test_steps_plainweave.py`): monkeypatch `steps._tool`, `steps.plainweave_seed.seed`, `steps._plainweave_json` with a fake that returns an enrichment envelope whose `items` carry `present`/`absent`/`unavailable`; assert the step surfaces the pair; assert a variant where the unavailable ref returns `absent` instead drops the pair (`ok is False`, empty `surfaced`).
- [ ] **Step 2: Run → fail** (step undefined).
- [ ] **Step 3: Implement.** Anchors (in the `PLAINWEAVE_*` block, steps.py ~645):
```python
PLAINWEAVE_ENRICH_COVERED = "python:function:specimen.cli._add_book"          # -> present
PLAINWEAVE_ENRICH_ABSENT = "python:function:tour.__main__.main"               # -> absent (orphan)
PLAINWEAVE_ENRICH_UNAVAILABLE = "python:function:specimen.cli._does_not_exist"  # -> unavailable (identity gap)
```
Step (after `plainweave_intent`):
```python
def plainweave_requirements_enrichment() -> StepResult:
    """plainweave+warpline: per-entity requirements enrichment, no-silent-clean.

    Over the same covered+uncovered seed, assert the three honest states a Warpline
    consumer relies on: a covered surface -> `present` (non-empty requirements); the
    recorded-but-unbound orphan -> `absent`; a well-formed-but-absent locator ->
    `unavailable` (an identity gap is "cannot tell", NEVER `absent`). Advisory,
    local-only, never gates. Frozen anchors; deterministic. Never raises (tour contract).
    """
    name = "plainweave requirements-enrichment"
    if not _tool("plainweave"):
        return StepResult(name, ok=False, detail="plainweave not installed — uv tool install /home/john/plainweave")

    def pw(args: list[str]) -> dict:
        env = _plainweave_json(args)
        if env is None or not env.get("ok"):
            raise RuntimeError(f"plainweave call failed: {args[0] if args else '?'}")
        return env.get("data") or {}

    try:
        plainweave_seed.seed(pw)
        env = _plainweave_json(
            ["requirements-enrichment", PLAINWEAVE_ENRICH_COVERED, PLAINWEAVE_ENRICH_ABSENT, PLAINWEAVE_ENRICH_UNAVAILABLE]
        )
        if env is None or not env.get("ok"):
            raise RuntimeError("requirements-enrichment call failed")
        items = {it["entity_ref"]: it for it in (env.get("data") or {}).get("items", []) if it.get("entity_ref")}
        covered = items.get(PLAINWEAVE_ENRICH_COVERED, {})
        absent = items.get(PLAINWEAVE_ENRICH_ABSENT, {})
        unavailable = items.get(PLAINWEAVE_ENRICH_UNAVAILABLE, {})
    except Exception as exc:  # tour contract: degrade, never raise. Type name only.
        return StepResult(name, ok=False, detail=f"plainweave enrichment failed: {type(exc).__name__}")

    pairs: list[tuple[str, str]] = []
    # Load-bearing no-silent-clean conjunction: present AND absent AND unavailable
    # (NOT absent). A regression collapsing unavailable->absent drops the pair -> verify reds.
    if (
        covered.get("status") == "present"
        and covered.get("requirements")
        and absent.get("status") == "absent"
        and unavailable.get("status") == "unavailable"
    ):
        pairs.append(("pw-requirements-enrichment", PLAINWEAVE_ADD_BOOK))

    return StepResult(
        name,
        ok=len(pairs) == 1,
        detail=(
            "over the covered+uncovered seed, plainweave requirements-enrichment reports "
            "cli._add_book present (bound, non-empty requirements), tour.__main__.main absent "
            "(recorded, unbound), and an unresolvable locator unavailable (identity gap — never "
            "a silent 'absent') — the Warpline-facing no-silent-clean contract; advisory, "
            "local-only, never gates"
        ),
        surfaced=tuple(pairs),
    )
```
`lacunae.toml` entry (after the `pw-surface-scoping` block):
```toml
[[lacuna]]
id = "pw-requirements-enrichment"
file = "specimen/cli.py"
symbol = "_add_book"
category = "peer-facts"
demonstrates = ["plainweave", "plainweave+warpline"]
explanation = "NOT A FLAW — a positive plainweave capability demo. Over the covered+uncovered seed, `plainweave requirements-enrichment` is the Plainweave producer for Warpline's reserved enrichment.requirements slot: a covered surface (cli._add_book) reports `present` with non-empty requirements; the recorded-but-unbound orphan (tour.__main__.main) reports `absent`; and a well-formed-but-absent locator reports `unavailable` — an identity gap is 'cannot tell', NEVER a silent `absent`. The load-bearing no-silent-clean contract. Advisory, local-only, never gates."
expected_tool = "plainweave"
expected_rule = "pw-requirements-enrichment"
```
Register in `_drive()` (`tour/__main__.py`, after `steps.plainweave_intent(),`): `steps.plainweave_requirements_enrichment(),`.
- [ ] **Step 4: Run → pass** — `.venv/bin/python -m pytest tests/test_steps_plainweave_peerfacts.py -q`.
- [ ] **Step 5: Commit** — `git commit -m "feat(tour): pw-requirements-enrichment demo (plainweave+warpline cell)"` (docs regenerated in Task 7).

---

## Task 6: Lacuna `pw-wardline-peer-facts` demo — full resolved/unseen (TDD)

**Files:** Create `tour/wardline_peerfacts_seed.py`; Modify `tour/steps.py` (extend `_plainweave_json` with `cwd`; add `plainweave_wardline_peer_facts()` + anchor); `tour/lacunae.toml` (entry); `tour/__main__.py` (register); Test extend `tests/test_steps_plainweave_peerfacts.py`.

**Interfaces:** Consumes `wardline_peerfacts_seed.materialize()/materialize_absent()`. Produces step surfacing `("pw-wardline-peer-facts", "specimen.peerfacts.unsafe_sink")`.

- [ ] **Step 1: Write failing unit tests** (add to `tests/test_steps_plainweave_peerfacts.py`): monkeypatch `steps.wardline_peerfacts_seed.materialize`/`materialize_absent` to return sentinel paths, and `steps._plainweave_json` (now `(args, cwd=None)`) to return a canned present envelope (active defect + non-defect fact + non-empty `resolved_or_unseen` + `wardline_scope_mismatch` degraded) for the present dir and an `unavailable` + `wardline_findings_absent` envelope for the absent dir. Assert the pair surfaces; assert dropping any one condition (e.g. absent dir returns `freshness:"current"`, or `resolved_or_unseen` empty) drops the pair.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement.** `tour/wardline_peerfacts_seed.py`:
```python
"""Frozen two-snapshot Wardline fixture for the plainweave+wardline tour leg.

Materializes a deterministic .wardline/ into a fresh temp workspace so the
`plainweave wardline-peer-facts` producer has a manifest-bearing scenario to read:
a finding resolved in scope, an out-of-scope prior finding honestly flagged, and a
stable active-defect + non-defect pair. Content is frozen constants -> byte-identical
every run; the temp path never appears in rendered output, so `make verify` stays
deterministic.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

RULESET = "demo-ruleset-1"


def _finding(fingerprint, kind, path, qualname, severity, message):
    return {
        "fingerprint": fingerprint, "rule_id": "PY-WL-101", "kind": kind,
        "severity": severity, "suppression_state": "active", "suppression_reason": None,
        "location": {"path": path, "line_start": 1, "line_end": 1, "col_start": 0, "col_end": 1},
        "qualname": qualname, "message": message,
    }


def _manifest(covered):
    return {"kind": "scan_manifest", "scan_id": "scan-fixed", "ruleset_id": RULESET,
            "commit": "0" * 40, "scope": {"covered_paths": covered}}


_ACTIVE = _finding("fp-active", "defect", "specimen/peerfacts.py", "specimen.peerfacts.unsafe_sink", "ERROR", "untrusted reaches a trusted producer")
_NONDEFECT = _finding("fp-nondefect", "fact", "specimen/peerfacts.py", "specimen.peerfacts.audited_helper", "INFO", "trust boundary documented")
_RESOLVED = _finding("fp-resolved", "defect", "specimen/peerfacts.py", "specimen.peerfacts.fixed_sink", "WARN", "previously untrusted; now bounded")
_OUTOFSCOPE = _finding("fp-outofscope", "defect", "specimen/legacy_area.py", "specimen.legacy_area.untouched", "ERROR", "not re-scanned this run")

_PRIOR = [_manifest(["specimen/peerfacts.py", "specimen/legacy_area.py"]), _ACTIVE, _NONDEFECT, _RESOLVED, _OUTOFSCOPE]
_LATEST = [_manifest(["specimen/peerfacts.py"]), _ACTIVE, _NONDEFECT]


def _write(wdir: Path, name: str, records: list[dict]) -> None:
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / name).write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def materialize() -> Path:
    root = Path(tempfile.mkdtemp(prefix="pw-wardline-peerfacts-"))
    wdir = root / ".wardline"
    _write(wdir, "20260101T000000Z-findings.jsonl", _PRIOR)
    _write(wdir, "20260102T000000Z-findings.jsonl", _LATEST)
    return root


def materialize_absent() -> Path:
    return Path(tempfile.mkdtemp(prefix="pw-wardline-absent-"))
```
Extend `_plainweave_json` (steps.py:648) signature to `def _plainweave_json(args: list[str], cwd: Path = ROOT) -> dict | None:` and pass `cwd` into `_run([plainweave, *args, "--json"], cwd=cwd)`. Add `import` of the new seed at the top of steps.py (`from tour import plainweave_seed, wardline_peerfacts_seed` — match existing import line). Anchor:
```python
PLAINWEAVE_WARDLINE_ACTIVE = "specimen.peerfacts.unsafe_sink"  # active defect anchor
```
Step:
```python
def plainweave_wardline_peer_facts() -> StepResult:
    """plainweave+wardline: surface Wardline findings as advisory peer facts.

    Generates a frozen two-snapshot fixture (with scan-identity manifests) in a temp
    workspace, then runs `plainweave wardline-peer-facts --json` against it. Asserts the
    full contract: an active defect AND a non-defect finding surface as advisory context;
    a finding gone from the latest in-scope snapshot is reported resolved_or_unseen; an
    out-of-scope prior finding is honestly flagged (wardline_scope_mismatch), never
    silently resolved; and an absent .wardline/ yields freshness=unavailable (NEVER clean).
    Advisory, local-only, never gates. Frozen fixture; deterministic. Never raises.
    """
    name = "plainweave wardline peer facts"
    if not _tool("plainweave"):
        return StepResult(name, ok=False, detail="plainweave not installed — uv tool install /home/john/plainweave")
    try:
        present_dir = wardline_peerfacts_seed.materialize()
        absent_dir = wardline_peerfacts_seed.materialize_absent()
        present = _plainweave_json(["wardline-peer-facts"], cwd=present_dir)
        absent = _plainweave_json(["wardline-peer-facts"], cwd=absent_dir)
        if present is None or not present.get("ok") or absent is None or not absent.get("ok"):
            raise RuntimeError("wardline-peer-facts call failed")
        data = present.get("data") or {}
        facts = data.get("facts") or []
        active_defect = any(
            f.get("suppression_state") == "active" and f.get("non_defect") is False
            and f.get("qualname") == PLAINWEAVE_WARDLINE_ACTIVE
            for f in facts
        )
        non_defect = any(f.get("non_defect") is True for f in facts)
        resolved = bool(data.get("resolved_or_unseen"))
        scope_flagged = any(d.get("code") == "wardline_scope_mismatch" for d in (data.get("degraded") or []))
        adata = absent.get("data") or {}
        absent_unavailable = adata.get("freshness") == "unavailable" and any(
            d.get("code") == "wardline_findings_absent" for d in (adata.get("degraded") or [])
        )
    except Exception as exc:  # tour contract: degrade, never raise. Type name only.
        return StepResult(name, ok=False, detail=f"plainweave wardline peer facts failed: {type(exc).__name__}")

    pairs: list[tuple[str, str]] = []
    if active_defect and non_defect and resolved and scope_flagged and absent_unavailable:
        pairs.append(("pw-wardline-peer-facts", PLAINWEAVE_WARDLINE_ACTIVE))

    return StepResult(
        name,
        ok=len(pairs) == 1,
        detail=(
            "plainweave reads .wardline/ snapshots as advisory peer facts: an active defect "
            "and a non-defect finding surface; a finding gone from the latest in-scope snapshot "
            "is reported resolved_or_unseen while an out-of-scope prior finding is honestly "
            "flagged (scope mismatch), not silently resolved; and an absent .wardline/ is "
            "unavailable, never clean — advisory, local-only, never gates"
        ),
        surfaced=tuple(pairs),
    )
```
`lacunae.toml` entry:
```toml
[[lacuna]]
id = "pw-wardline-peer-facts"
file = "specimen/peerfacts.py"
symbol = "unsafe_sink"
category = "peer-facts"
demonstrates = ["plainweave", "plainweave+wardline"]
explanation = "NOT A FLAW — a positive plainweave capability demo. `plainweave wardline-peer-facts` reads sibling-owned .wardline/ snapshots as advisory peer facts (Plainweave never scans; Wardline owns the trust gate). Over a frozen two-snapshot fixture with scan-identity manifests: an active defect and a non-defect finding surface as advisory context; a finding gone from the latest in-scope snapshot is reported resolved_or_unseen while an out-of-scope prior finding is honestly flagged (wardline_scope_mismatch), never silently resolved; and an absent .wardline/ yields freshness=unavailable, never clean. Advisory, local-only, never gates."
expected_tool = "plainweave"
expected_rule = "pw-wardline-peer-facts"
```
Register in `_drive()`: `steps.plainweave_wardline_peer_facts(),` after the enrichment step.
- [ ] **Step 4: Run → pass** (unit tests).
- [ ] **Step 5: Commit** — `git commit -m "feat(tour): pw-wardline-peer-facts demo, full resolved/unseen (plainweave+wardline cell)"`

---

## Task 7: Lacuna docs regen + PDR-0015 + gates

**Files:** Regenerate `docs/tour.md`, `docs/matrix.md`, `docs/flaws/pw-*.md` via `make tour`; Create `docs/product/decisions/PDR-0015-*.md` (PDR-0010 format).

- [ ] **Step 1:** Real end-to-end smoke (plainweave installed): does `plainweave wardline-peer-facts`/`requirements-enrichment` exist on the live tool? If the tour runs against an installed `plainweave`, reinstall from source first: `uv tool install --force /home/john/plainweave` so the tour sees the new subcommands.
- [ ] **Step 2:** `make tour` — regenerates docs; confirm `docs/matrix.md` now lists `plainweave+wardline` and `plainweave+warpline`, and `docs/tour.md` has the two new sections.
- [ ] **Step 3:** `make verify` — green (every live lacuna surfaced; narrative in lockstep).
- [ ] **Step 4:** Write PDR-0015 (the PDR-0010 format: Context/Decision/Consequences/Reversal trigger) recording the two new cells + the Plainweave CLI-parity dependency.
- [ ] **Step 5:** Commit — `git add docs/ tour/ tests/ && git commit -m "docs(tour): regenerate matrix/tour for peer-facts cells; PDR-0015"`
- [ ] **Step 6: Full Lacuna gate** — `make ci` (`test scan verify cargo-check`) green.

---

## Task 8: Final adversarial review + cross-repo gate (ultracode)

- [ ] **Step 1:** Plainweave `make ci` + `wardline scan . --fail-on ERROR`; Lacuna `make ci`. Both green.
- [ ] **Step 2:** Workflow: adversarial review of both finished diffs (invariant audit: any verdict leakage? any silent-clean path? determinism? frozen-anchor discipline?) + reviewer for hallucinated symbols. Address findings.
- [ ] **Step 3:** Plainweave product-workspace note + memory update. Summarize to owner; do NOT push public remotes without sign-off.

---

## Self-Review
- **Spec coverage:** Part A → Tasks 2,3 (both subcommands, validator-over-CLI, exit codes). Part B → Tasks 5 (enrichment, present/absent/unavailable), 6 (wardline full resolved/unseen + scope mismatch + absent→unavailable). Docs/matrix → Task 7. Governance → Tasks 4,7. Folded-in changes → Task 1. Gates → Tasks 4,6,7,8. ✓
- **Placeholder scan:** one deliberate conditional in Task 3 Step 1 (`module_sei` key name) — resolved by reading `_seed_bound` at execution; not a code placeholder.
- **Type consistency:** `_emit_surface_result(args, envelope) -> int` defined in Task 2, reused in Task 3. `_plainweave_json(args, cwd=ROOT)` extended in Task 6, consumed by the wardline step. Anchors `PLAINWEAVE_ENRICH_*`/`PLAINWEAVE_WARDLINE_ACTIVE` defined and consumed in the same task. ✓
