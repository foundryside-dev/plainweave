# PDR-019: Plainweave 1.2.0 released to PyPI — the full 1.2 line shipped live (web a11y, peer-facts CLI parity, requirements producer gated-live, seam hardening, plainweave-workflow skill)

Date: 2026-06-30   Status: accepted   Author: agent:claude (release session, owner-directed)
Owner sign-off: owner directed the release end-to-end this session ("merge the PR and tag/publish"), clearing the publication escalation held since PDR-016/PDR-017. This records an owner-authorized publish; publication is otherwise owner-gated (`vision.md` Authority Grant; PDR-002/PDR-012).
Related: PDR-012 (1.0.0 release precedent), PDR-015 (peer-facts CLI parity), PDR-016 (web a11y overhaul), PDR-017 (requirements producer gated-live + wheel-build fix), PDR-018 (seam hardening), PDR-011 (operability parity — the `plainweave-workflow` skill pack was the Option-2-deferred bet there), observation `plainweave-obs-6a7255ffbe` (wheel-build bug, now resolved), PDR-020 (the 1.2.1 honesty follow-on).

## Context

The entire 1.2 line had accumulated on `main` (PDR-015 CLI peer-facts parity + PDR-016 web/a11y overhaul + PDR-017 requirements producer + PDR-018 seam hardening) but **publication was held, owner-gated** — the single most-cited open escalation in the last three checkpoints. Two things unblocked it this session: (1) the owner directed the release live; (2) the load-bearing packaging fix (PDR-017) was in place. That fix mattered for the release itself, not just local installs: the **v1.1.0 release build had FAILED** at `uv build` on the redundant `force-include` collision, so PyPI was stuck at 1.0.0 — the fix is what let the 1.2.0 build pass and publish.

## The call

**RELEASE 1.2.0 to PyPI.** Consolidated the work that was stranded off every release branch (PDR-018 seam commit + the wheel-fix/PDR-017 docs) onto `main` via PR #7; bumped `_version.py` 1.1.0 → 1.2.0; finalized the CHANGELOG `[1.2.0]` section; **created the `plainweave-workflow` skill pack** (federation-standard: authored in-package at `src/plainweave/skills/`, shipped as package data via `packages=["src/plainweave"]`, dogfooded into the repo's `.claude/`+`.agents/` trees — this delivers part of the Option-2 operability-parity bet PDR-011 deferred); tagged **annotated** `v1.2.0` on `main`; `release.yml` built + published via PyPI Trusted Publishing. PyPI now serves **1.2.0** (wheel+sdist); **1.1.0 is absent** — its release build had failed on the wheel bug and was not backfilled (PyPI: `[1.0.0, 1.2.0]`).

## Validation evidence (firsthand, this session)

- **Publish verified live, not just green-checkmark:** PyPI JSON API shows `plainweave-1.2.0` wheel+sdist, `info.version=1.2.0`. Precondition checks confirmed v1.0.0 published green through this exact `release.yml` + `pypi` environment with **zero workflow drift**, so Trusted Publishing's pins held.
- **Gate:** pre-tag `make ci` green (390 passed, 91.18% cov, ruff+mypy-strict clean) and full `uv build` (sdist+wheel) — the exact steps `release.yml` runs; the skill ships in both artifacts.
- **Wheel-build blocker resolved** (`plainweave-obs-6a7255ffbe`): the wheel builds `web/static/.gitkeep` exactly once (was the collision).
- **Topology:** PR #7 gate green, merged to `main`; `v1.2.0` annotated (matches v1.0.0/v1.1.0); `release/1.2.0` reconciled to `main` (was a stale ceremony cut); GitHub Release `v1.2.0` created so the CHANGELOG links resolve.
- Guardrails intact: advisory-only, no verdict tokens; the release artifacts publish **no headline north-star number** (README states completeness is a roadmap item) → the PDR-009 vanity-metric trigger did NOT fire.

## What this does NOT cover

- **The error-legibility fixes** — those are 1.2.1 (PDR-020), a same-day honesty follow-on.
- **The rest of the operability-parity bet** (PDR-011 Option 2): SessionStart hook, `.mcp.json` self-registration, and a `plainweave install` distribution command remain **future/uncommitted** — only the skill pack shipped.
- **Coverage-completeness** (north-star mover) — unchanged, owner-gated (Rust public surface untagged upstream on Loomweave).
- **Carried `vision.md` edits** — authority-grant metadata, "Serves" naming human operators (PDR-013), publishing a headline north-star number — still owner-gated; not touched.

## Flags routed to owners

- **Operational (in-grant, done):** the global uv-tool `plainweave` was reverted off the editable dev install to the published `plainweave[web]==1.2.1` from PyPI, so siblings (Warpline) consume the released package, not the dev tree — the "revert at publish" step. Reversible.

## Reversal trigger

Reopen if a clean `pip install plainweave==1.2.0` (or `uv tool install`) fails to install or the CLI verb surface regresses for a consumer — the producer would be correct but not *installable/present* where consumed (mirrors PDR-017's darkened-member trigger). Watched via a clean-install smoke + the federation-member-coverage reading. (This trigger fired *benignly* into 1.2.1 — a fast honesty patch — but on new dogfood findings, not a 1.2.0 install defect.)
