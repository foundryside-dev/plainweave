# PDR-017: Requirements-enrichment producer gated live end-to-end against its first sibling consumer (Warpline); known wheel-build blocker fixed

Date: 2026-06-29   Status: accepted   Author: agent:claude (Wardline-session cross-repo gate, owner-directed)
Owner sign-off: owner directed the end-to-end re-gate of the sibling-consumer enrichment push ("ultracode") and the recording of this PDR ("lock down that PDR"). This records VALIDATION of the already-delivered producer (PDR-014/PDR-015) against its now-built consumer (Warpline PDR-0008), plus one in-grant, repo-local build-config fix. The fix is **uncommitted**; the commit, the `1.2.0` CHANGELOG/version cut, and the held PyPI publish remain **owner-gated** (authority grant: publication + sibling obligations escalate — see `current-state.md`, PDR-002/PDR-012).
Related: PDR-014 (producer delivered — `weft.plainweave.requirements_enrichment.v1`, `bc37a24`), PDR-015 (peer-facts CLI/MCP parity), PDR-009 (no-silent-clean / no-vanity-metric), Warpline **PDR-0008** (the consumer acceptance this pairs with), observation **`plainweave-obs-6a7255ffbe`** (the wheel-build blocker, now fixed), the producer handoff `docs/handoffs/2026-06-28-warpline-requirements-enrichment-consumer-impl.md`.

## Context

PDR-014 delivered the `requirements_enrichment.v1` producer Plainweave-side and PDR-015 added the `plainweave requirements-enrichment <refs> --json` CLI for transport parity — but **sibling follow-on #1** (the Warpline consumer) stayed handed-off/owner-gated, so the producer surface had never been exercised by a real consumer. Two things changed: (1) the Warpline session built and accepted the consumer (Warpline PDR-0008 — the 4th federation member, structure/status-pinned against the vendored golden); (2) an owner-directed re-gate proved the loop actually closes on PATH.

The gate exposed that the producer's *correctness in source* (`uv run`) had masked a packaging regression: committed `main` (HEAD `c1e125e`, the PDR-016 web-UX commit) **cannot build a wheel** — the already-tracked **`plainweave-obs-6a7255ffbe`** (P2). `[tool.hatch.build.targets.wheel.force-include]` re-maps `web/templates` + `web/static`, which `packages = ["src/plainweave"]` (src-layout) already vendors, colliding on `web/static/.gitkeep`. Because `uv tool install` builds a wheel and the *installed* `plainweave` was a stale **1.0.0**, Warpline's `--help` capability probe never saw the verb → the requirements member read `disabled` in practice **even though both sides' code was correct**. The contract was dark for an install/packaging reason, not a contract reason.

## The call

**ACCEPT the requirements-enrichment producer as proven live-consumable, and bank the fix for the wheel-build blocker.** Removed the redundant `force-include` block — `packages = ["src/plainweave"]` already includes `web/templates` + `web/static`; the wheel now builds and ships every web asset exactly once. Reinstalled the `plainweave` uv tool **1.0.0 → 1.1.0** (both entry points, `plainweave` + `plainweave-mcp`), lighting the verb up on PATH. This is a repo-local, reversible build-config change (in-grant) — **not** a commit, a version cut, or a publish.

## Validation evidence (end-to-end re-gate, firsthand)

- **Wheel build fixed + asset-verified:** post-fix `uv build --wheel` succeeds; the wheel carries `app.css`, `htmx.min.js`, all 20+ templates, and `web/static/.gitkeep` **exactly once** (was the collision). Resolves `plainweave-obs-6a7255ffbe`.
- **Verb live on PATH:** `plainweave --help` advertises `requirements-enrichment`; the verb returns the `weft.plainweave.requirements_enrichment.v1` envelope (`ok:true`; `authority_boundary{local_only:true, live_peer_calls:false, governance_verdicts:false, requirements_owner:"plainweave"}`; producer 1.1.0).
- **Consumer flips disabled→enabled:** Warpline's real `PlainweaveRequirementsClient.available()` went `False → True` across the reinstall; a live CLI round-trip parsed cleanly into `{entity_ref: item}` with the 5-key item shape and honesty (`unavailable` ≠ `absent`) intact.
- **Graceful degradation traced:** against a non-Plainweave repo the producer returns its `ok:false` NOT_FOUND envelope; Warpline catches it (`federation.py:502`) → `reason("unreachable")`, never crashes.
- **Suite green:** Warpline's 41 requirements-scoped tests pass; no live/un-mocked test pins the disabled posture, so the reinstall flipped nothing.
- **Live scope, stated honestly:** `unavailable` is proven **live** end-to-end; `present`/`absent` remain pinned by Warpline's structure/status contract test (fixture-based), not live-demonstrated this session.

## What this does NOT cover (owner-gated)

- **Commit / version / publish.** The build-config fix is **uncommitted** on Plainweave `main` (also 1 ahead of `origin`). Committing it, the `1.2.0` CHANGELOG/version cut, and the held PyPI publish are owner escalations. **Until the fix commits, the *installed* tool diverges from committed source and the next clean `uv tool install` breaks again** — i.e. the fix is load-bearing for the contract staying live.
- **Patching Warpline.** None done — the consumer is Warpline's own work (PDR-0008), uncommitted on `release/1.2.0` and co-mingled with a concurrent stream; committing/untangling it is the Warpline owner's call. Warpline's uncommitted files were left untouched.
- **Item-schema ratification (interface-lock prompt #3).** Unchanged — the contract test stays structure/status-pinned until the requirement *item* shape is ratified, then byte-pin.

## Flags routed to owners

- **Plainweave (investigated — NOT a defect, no fix):** the originally-flagged exit-0-vs-2 "inconsistency" was a **measurement artifact**, not cwd-dependence. `_emit_surface_result` (`cli_commands.py:1204`; introduced `a6044a1`, used by `requirements-enrichment` from `9334838`) maps `ok:true → 0`, `INTERNAL → 4`, else `→ 2`, so `ok:false` NOT_FOUND is **deterministically exit 2** — reproduced across `/tmp`, `/home/john/warpline`, and `/home/john/wardline`, and pinned by `tests/test_cli_requirements_enrichment.py`. The phantom "exit 0" came from a piped exit capture (`… | head; echo $?` reports `head`'s status, not plainweave's). Exit 2 + `ok:false` is the *honest* answer (an uninitialised store is a genuine producer failure → Warpline maps it to `unavailable`); a faked `ok:true` with per-entity `unavailable` items would violate no-silent-clean. The real residual is **operational, not exit codes**: Warpline execs bare `plainweave` from PATH = the uv-tool snapshot, which silently lags the dev tree until `uv tool install --force` / `uv tool upgrade plainweave` (this gate's stale-1.0.0-binary was exactly that drift). Worth an editable install (`uv tool install -e .`) or a re-snapshot hook to kill the drift class — owner's call.
- **Warpline (in-flight session):** against a non-Plainweave repo the member now reads `enabled` (verb advertised) yet every consult is `unreachable` — whether that vs. `absent`/`disabled` is the right posture is a Warpline design call.

## Reversal trigger

Reopen if, over real federated use, the requirements dimension perpetually reads `disabled`/`unavailable` because the installed Plainweave never advertises `requirements-enrichment` in member repos — the producer is correct but never *present* where consumed, so the axis adds no signal (mirrors Warpline PDR-0008 trigger (a); watched via the `metrics.md` federation-member-coverage reading). The packaging fix going uncommitted is the near-term instance of exactly this failure mode: if `main` ships without it, every clean install re-darkens the member.
