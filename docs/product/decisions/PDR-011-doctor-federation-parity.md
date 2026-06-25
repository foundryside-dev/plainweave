# PDR-011: Doctor Brought to Federation Parity (doctor --fix)

Date: 2026-06-25   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: within grant (local CLI/operability); local-only (unpushed)
Related: PDR-002 (consumer boundary, owner-gated publication), PDR-004 (cross-member seam)

## Context

Every federation sibling (wardline / loomweave / legis / warpline / filigree) ships
`doctor` + `--fix`/`--repair` (idempotent), `--json`, `--root`, a non-zero exit on
unresolved problems, and checks of store/sibling-binding + agent-orientation install
surfaces. Owner flagged that `doctor`/`doctor --fix` are the federation standard and asked
whether Plainweave conforms. It did not: Plainweave's `doctor` was a stub — reported only
`initialized`/`schema_version`/`db_path`, had no `--fix` and no `--root`, and always exited 0
(it never checked the Loomweave catalog binding the whole intent graph depends on).

## Options considered

1. **Config-doctor** — a real doctor + `--fix`/`--root`/`--json`/exit-codes covering what
   Plainweave owns today: store + schema health, the Loomweave catalog-adapter binding, and
   the MCP surface. No new install surfaces.
2. **Full parity** — also build the agent-orientation install surfaces the sibling doctors
   manage (a `plainweave-workflow` skill pack, a SessionStart hook, `.mcp.json`
   self-registration, an `install` command). Materially an onboarding feature, not a doctor.

## The call

Option 1, delivered to `main` (local). `plainweave doctor` now runs three checks, each with
`status / fixable / next_action`: **store** (initialized + schema == `SCHEMA_VERSION`; `--fix`
inits/migrates in place), **loomweave_catalog** (the sibling-owned catalog the intent graph
consumes — reported with a next-action, **not** auto-fixed), and **mcp_surface** (the
`plainweave-mcp` entry point resolves). Adds `--fix` (idempotent), `--root DIR` (first `--root`
on the CLI), and a **non-zero exit when any check is ERROR** (warnings advisory) — usable as a
CI/pre-commit gate. Envelope bumped `weft.plainweave.doctor.v1 → v2` (`checks[]` + `summary`),
retaining the v1 continuity fields; `LoomweaveAdapter.health()` exposes adapter status without
a scan. `make ci` green (ruff, **mypy strict 0 issues**, **235 passed, 90.11% cov**); wardline
trust-boundary scan clean (`--root` path handling). Option 2 deferred as a future onboarding bet.

## Rationale

Operability + launch-readiness: a tool that cannot self-verify its configuration is not
release-ready, and federation conformance is table stakes. The load-bearing call is the
**consumer boundary**: `--fix` repairs only what Plainweave owns (the store) and reports the
Loomweave catalog gap with a `loomweave analyze` next-action rather than building a sibling's
artifact (PDR-002/PDR-004). Warnings (e.g. catalog-absent) are advisory and do not fail the
exit, so a fresh project pre-Loomweave-analyze is "configured properly" once its own store is.

## Reversal trigger

Reopen if (a) the consumer-boundary call proves wrong in operation — operators want `--fix`
to also run `loomweave analyze` (then it becomes an orchestration decision, still bounded by
PDR-004), or (b) the federation doctor standard adds an agent-orientation surface Plainweave
should self-manage, at which point build the deferred Option-2 install surfaces.
