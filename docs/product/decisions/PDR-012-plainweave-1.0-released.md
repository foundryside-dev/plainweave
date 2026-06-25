# PDR-012: Plainweave 1.0.0 Released to PyPI — accepted as-shipped

Date: 2026-06-25   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: EXPLICIT (owner-directed across the session; release is owner-gated, PDR-002)
Related: PDR-002 (release owner-gated), PDR-009 (north-star self-computable), PDR-010, PDR-011

## Context

PDR-002 reserved "public release and packaging (final name, PyPI, hub roster)" as
owner-gated. This session the owner directed the release explicitly and repeatedly —
"get ready to release 1.0" → "push to remote" → "configure the repo and CICD" →
"pypi is setup now" → "leave it as good, we're in good shape." The build itself was
already green (235 tests, mypy strict, 90.11% cov; PDR-009/010/011 surface complete).

## Options considered

1. Ship **1.0.0** now (the owner's directive) — stable behaviour/contracts; completeness
   a documented roadmap item.
2. Ship **1.0.0rc1** first — more conservative given the open cross-member completeness
   frontier (the real-API denominator leans on scoping; Rust surface untagged upstream).

## The call

Option 1 — **plainweave 1.0.0 is live on PyPI** (`plainweave-1.0.0-py3-none-any.whl` +
`.tar.gz`, with digital attestations via Trusted Publishing). Delivered:

- version `0.0.1 → 1.0.0`, classifier `Pre-Alpha → Production/Stable`; LICENSE (MIT) +
  CHANGELOG; README status `pre-build → 1.0`; CI + release workflows; the contract suite
  made version-bump-robust (`meta.producer.version` volatile — no fixture churn on release).
- GitHub repo `foundryside-dev/plainweave` created **public** (by the owner) and pushed;
  configured topics, the `pypi` Trusted-Publishing environment, and `main` branch protection
  (required CI check, admins bypass).
- `v1.0.0` tagged → Release workflow built + published; verified live on PyPI.

**Accepted as-shipped despite one provenance wrinkle.** A concurrent session committed a
**docs-only** webUX design brainstorm (`554d11d`: `.gitignore` + one design spec, **no src,
no pyproject**) to `main` during the release; it was swept into the `v1.0.0` tag and pushed
public when the branch synced. The published **wheel is code-identical** to the 1.0.0
release. The owner reviewed and chose to leave it.

## Rationale

The release is the explicit owner directive; the entanglement is cosmetic (code-identical
wheel), and cleaning the git tag would not change the published PyPI artifact (1.0.0 is
burned). 1.0 means **stable behaviour + contracts**, not complete cross-language coverage —
the README/CHANGELOG are deliberately honest that completeness is a roadmap item, satisfying
PDR-009's no-vanity-metric guard (no headline north-star number was published).

## Reversal trigger

A published version is immutable: if 1.0.0 is found to have a real (non-cosmetic) defect,
ship **1.0.1+** — 1.0.0 cannot be re-published. The **operator web-UI direction** (the
brainstorm doc now on `main`) is owner-gated at the vision level and is **NOT** part of 1.0;
it reopens only as a separate, owner-approved bet — not implied by this release.
