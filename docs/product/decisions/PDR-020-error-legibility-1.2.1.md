# PDR-020: Error-legibility (say-what-you-know) fixes accepted; Plainweave 1.2.1 released

Date: 2026-07-01   Status: accepted   Author: agent:claude (owner-directed; ultracode workflow + inline extension)
Owner sign-off: owner directed the fix ("use ultrathink and ultracode to resolve those") and the release ("Cut 1.2.1 now"). Records an owner-authorized publish; publication is otherwise owner-gated (`vision.md` Authority Grant).
Related: PDR-019 (1.2.0 release), PDR-009 (no-silent-clean / functional-honesty doctrine this fix serves), follow-up `plainweave-de4ced60cf` (idempotency-hint precision).

## Context

Clean-room dogfooding (2026-06-29) surfaced two violations of Plainweave's flagship honesty invariant — **an error must say what it knows; a hint that doesn't point at the real fix misdirects and burns agent probe-cycles** (an adoption cost):
- **(A)** A version `CONFLICT` reported only `"expected version does not match current version"` with empty `details`, so an agent had to probe (try 0, try 2) to learn the real version.
- **(B)** `_error()` hardcoded `"Refresh local Plainweave state and retry."` on **every** error, so e.g. a missing `--actor` VALIDATION error inherited a stale-state hint that sent the agent down a dead path.

I first **evaluated** whether these were already fixed (they reproduced live against 1.2.0), then resolved them.

## The call

**RESOLVE both as one coherent, additive change to the error layer, then RELEASE 1.2.1.**

- Built via an **ultracode workflow** (sweep → implement → 4-lens adversarial verify, all passed): `_error(code, message, *, hint=None, details=None)` resolving an omitted hint from a per-`ErrorCode` **honest default map** (VALIDATION/NOT_FOUND never claim staleness; CONFLICT legitimately suggests a refetch); the version-guard CONFLICT discloses both versions in message + `details` + a `--expected-version {current}` hint; the missing-actor + method/evidence-status/trace-relation VALIDATION sites get precise hints; the duplicate blanket hardcode in `mcp_surface.py` (INTERNAL preflight-severity) replaced.
- **Design calls I locked in:** one PR not two (both prompts share `_error`, so splitting would force an artificial dependency stack); keep a non-empty cause-appropriate hint on every error (the existing contract requires one — "no hint" was rejected).
- **Extended the fix inline** to the sibling `draft_revision` guard (`update_draft`) — the *identical* say-what-you-know defect on a version conflict, with a real `--expected-draft-revision` flag. Left half-fixing it (misdirection cured but the number still hidden) would contradict the task's whole point; by the CLAUDE.md scope test this was task scope, not creep.
- **Deferred** the idempotency-key CONFLICT sites — a *distinct* class (not findings A/B), already improved by the honest CONFLICT default (strictly better than the old blanket hint), tracked as `plainweave-de4ced60cf` (P3) rather than silently dropped.
- **Additive only:** the `weft.plainweave.error.v1` envelope and the `ErrorCode` enum are unchanged; no allow/block/verdict tokens.

## Validation evidence (firsthand)

- `make ci` green: **400 passed, 91.32% cov** (up from 91.18% at 1.2.0), ruff + mypy-strict clean; `wardline scan . --fail-on ERROR` exit 0.
- **Live `uv run plainweave` repro** (working-tree code, not the stale binary) of all three scenarios: requirement-version CONFLICT, draft-revision CONFLICT, and missing-actor VALIDATION all show the disclosed values + precise hints.
- **Anti-vacuous tests** (new `tests/test_error_hints.py` + strengthened `assert_error`) were empirically confirmed to **fail against the old code** — they pin the actual current value in message/details/hint and forbid the blanket hint on validation errors.
- Released: 1.2.1 published to PyPI (verified `info.version=1.2.1`, wheel+sdist) via the proven Trusted-Publishing pipeline; GitHub Release created; `release/1.2.1 == main == v1.2.1` tag.

## What this does NOT cover

- **Idempotency-key CONFLICT hint precision** (`plainweave-de4ced60cf`, P3): they now ride the honest CONFLICT default ("refetch… it changed or was already used") — improved, not perfect (the most precise fix is "use a fresh idempotency key").
- **No north-star movement** — this is honesty/legibility hardening (an adoption-cost reduction), not coverage completeness.

## Flags routed to owners

- **None new.** The 1.2.1 publish was owner-directed this session. Carried vision/coverage escalations (PDR-019) unchanged.

## Reversal trigger

Reopen if real agent use shows an enriched hint still **misdirects** — points at a recovery that doesn't clear the error it names — which would itself violate the honesty invariant this change asserts. Watched via dogfood / agent-adoption feedback. NOTE an input-metric gap: there is no agent-adoption / probe-cycle scoreboard yet, so this trigger currently fires on qualitative feedback, not a number — worth an input metric if adoption becomes the active bet.
