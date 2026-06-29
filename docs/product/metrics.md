# Plainweave Beta Metrics

## North Star

At least 90 percent of sampled public surfaces in the beta proving repo can
answer "why does this exist?" through `SEI -> requirement -> goal`.

> CAVEAT (PDR-009, supersedes PDR-006): the north-star is now self-computed by the
> `intent_coverage` primitive. Every reading is qualified IN-BAND by three signals that
> must travel with any number: (a) namespace scoping (default `tests.`/`scripts.` excluded
> — "public surface" means the real exported API); (b) `denominator_complete` (tag-class
> completeness only — NOT language coverage); (c) `present_plugins` (the catalog's language
> span). A `denominator_complete=true` reading can still be language-partial. Publishing a
> headline number remains owner-gated (PDR-002).

## Input Metrics

- Count of public code entities recorded from the catalog.
- Count of code entities bound to requirements.
- Count of requirements linked to goals.
- Count of orphan code entities and orphan requirements.
- Count of corpus rows with both goal and code context.

## Guardrails

- Zero Plainweave allow/block release decisions.
- Zero Plainweave-minted SEIs.
- Zero agent-created bindings represented as accepted human truth.
- Zero silent-clean results when peer context is absent or stale.

## Validation Method

Run the golden vector on Plainweave first, then on Loomweave as the default
representative sibling. Sample public surfaces, compute trace coverage, and
inspect orphan output for honest gaps.

## Readings

### 2026-06-24 — Plainweave self-dogfood (PDR-005)

| Metric | Reading |
|--------|---------|
| Public code entities recorded | 2 (`cli.main`, `mcp_server.main`) |
| Code entities bound to requirements | 2 |
| Requirements linked to goals | 2 |
| Orphan code entities / orphan requirements | 0 / 0 |
| Corpus rows with both goal and code context | 2 |
| **North-star** | 100% of the explicitly-tagged public surface (2/2); **full-surface % indeterminate** — denominator degraded (PDR-006, plainweave-44be10cc2c) |

Guardrails — all intact: 0 SEIs minted (consumed opaquely); 0 release/allow/block
verdicts; bindings carry an `agent:` actor (not human-accepted truth); 0 silent-clean
results — the catalog honestly reported degraded coverage. No reversal trigger fired.

### 2026-06-24 — Live peer dogfood (PDR-008)

Read each peer's own Loomweave catalog (read-only); corpus built in a scratch store
(peer repos untouched). Demonstrates the cross-member seam (PDR-004) on real peers.

| Peer | Catalog coverage | Public surfaces | Recorded / bound | Honest orphans | North-star | Denominator |
|------|------------------|-----------------|------------------|----------------|------------|-------------|
| Lacuna | incomplete (2/4) | 4 | 4 / 3 | 1 | 75% | qualified |
| Loomweave | **complete (4/4)** | 45 | 45 / 10 | 35 | 22% | **trustworthy** |

Takeaway: the coverage gap (PDR-006 / plainweave-44be10cc2c) is per-repo — on a
complete-coverage peer the north-star is honestly computable. Secondary finding: the
public-surface set includes test/perf/CI-script entry-points (plainweave-7be2817d58).
Guardrails intact on both peers; no reversal trigger fired.

### 2026-06-24 — intent_coverage primitive shipped; north-star now self-computable (PDR-009)

**PDR-006's reversal trigger FIRED:** plainweave-44be10cc2c and plainweave-7be2817d58 closed,
so the north-star is no longer coverage-blocked — the product computes it directly via
`plainweave intent coverage`. Re-read against the Loomweave peer (catalog complete, 4/4):

| Scope | Denominator | Excluded | denominator_complete | present_plugins |
|-------|-------------|----------|----------------------|-----------------|
| default (excl. `tests.`/`scripts.`) | **1** | 44 | true | core, python, rust |
| no exclusion | 45 | 0 | true | core, python, rust |

Reading: the real exported-API denominator on Loomweave is **1** (`plugins.python…server.main`);
the other 44 public-tagged surfaces are vendored `elspeth_mini` / `check-*` harness — the 22%
(10/45) figure from PDR-008 was the *unscoped* number. `present_plugins` exposes that the catalog
spans core/python/rust while every tagged public surface is `python:` — the Rust public surface is
untagged upstream (the cross-member coverage gap; owner-gated). Numerator over the committed
Plainweave intent DB is 0 (no bindings ladder Loomweave's surfaces; the dogfood's 10 were
throwaway) — an honest 0, not a defect.

Guardrails — all intact: advisory only, verdict vocabulary machine-rejected by the contract
validator; SEIs consumed opaquely; no silent-clean (degraded tag-classes AND language-partial spans
both flagged in-band). The release review fixed a real honesty defect (surfaces bound to *deprecated*
requirements were inflating the numerator). No NEW reversal trigger fired.

### 2026-06-25 — Lacuna intent regression-harness oracle (PDR-010)

A **controlled fixture** reading, NOT a real-surface north-star reading. The harness seeds a
deterministic 2-covered:2-uncovered corpus over the Lacuna specimen; `intent coverage` reads
**2/4 default, 2/3 scoped** (excl. `tour.`), with `denominator_complete=false` and
`absent_tags=[exported-api, http-route]` carried in-band; `intent orphans`/`trace`/`corpus`
all populated. Deterministic across repeated `make verify` runs (the value is regression
protection of the liveness/deprecation numerator semantics, not the headline number).

PDR-009 reversal-trigger check: the reading was only ever presented WITH its scoping +
`denominator_complete` qualifiers, so the vanity-metric/silent-clean trigger did NOT fire.
Guardrails intact (advisory; consumed SEIs opaquely; no specimen/sibling-repo mutation).

### 2026-06-25 — Operability guardrail added (PDR-011)

New, separate from the north-star: `plainweave doctor` self-verifies configuration
(store/schema + Loomweave catalog binding + MCP surface) and exits non-zero on any ERROR —
config health is now CI-gateable. Against the Plainweave repo it reads **3 ok / 0 warn /
0 error**. The Loomweave catalog gap stays an advisory WARN with a `loomweave analyze`
next-action (never auto-fixed — consumer boundary).

### 2026-06-25 — Plainweave 1.0.0 released to PyPI (PDR-012)

Delivery milestone, NOT a north-star reading. `plainweave 1.0.0` is live on PyPI (wheel +
sdist + Trusted-Publishing attestations); `pip install plainweave` resolves it. The north-star
(coverage **completeness**) is unchanged — 1.0 ships stable behaviour/contracts, not complete
cross-language coverage.

PDR-009 reversal-trigger check: the release artifacts (README / CHANGELOG) did NOT publish a
headline north-star number — they state completeness is a roadmap item — so the
vanity-metric / silent-clean trigger did NOT fire. Guardrails intact (advisory, no verdict).

### 2026-06-26 — Plainweave 1.1.0 cut: operator web UI + SEI conformance (PDR-013)

Delivery milestone, NOT a north-star reading. The operator web UI (`plainweave[web]`) and
the SEI 4th-conformer landed on `main`; `release/1.1.0` (PR #2) is open; the public site is
live. North-star (coverage completeness) unchanged. Guardrails intact (web writes are
human-attributed; advisory; no release verdict). Owner ratified the direction (PDR-013).

### 2026-06-27 — Peer facts: production-blocker reduction + contract-test coverage (PDR-014)

Hardening reading, NOT a north-star reading. Two local-first advisory producers shipped
with frozen `.v1` contracts; `make ci` green (355 tests, **90.94% coverage**, up from
90.11% at 1.0; mypy --strict, ruff clean); `wardline scan` clean (0 active). Retires 3 of
the 5 named production blockers (live-data peer adapters, explicit degraded-state,
Warpline/Wardline contract tests).

Guardrails — all intact and now contract-test-pinned: advisory only (no-verdict validator
on both new envelopes); SEIs consumed opaquely; no-silent-clean (resolved/unseen
scope-bounded; `unresolved`/dead-binding → `unavailable`, not `absent` — both
mutation-verified). No reversal trigger fired; PDR-014's trigger (Warpline schema
rejection) is pending the owner-gated interface-lock ratification.

### 2026-06-28 — Peer-facts CLI/MCP parity + Lacuna tour regression (PDR-015)

Hardening / surface-completeness reading, NOT a north-star reading. The two 1.1 peer-facts
producers (MCP-only since PDR-014) gained CLI surfaces — `plainweave wardline-peer-facts`
and `plainweave requirements-enrichment` — reusing `PlainweaveMcpSurface` verbatim. `make ci`
green: **378 tests, 91.14% coverage** (up from 90.94% at 1.1); mypy --strict + ruff clean;
`wardline scan` clean (0 active). Merged to `main`; the work rode the concurrent
`release/1.2.0` cut (CHANGELOG `[Unreleased]`). Lacuna's cross-member tour gained
`plainweave+wardline` / `plainweave+warpline` cells (sibling repo, Lacuna PDR-0015).

Guardrails — all intact: advisory only (the CLI passes the producers' envelopes through
unchanged; the no-verdict structural validators run over CLI output in tests); no-silent-clean
preserved and now ALSO regression-asserted cross-member (the Lacuna demos pin
covered→present, orphan→absent, identity-gap→`unavailable`-never-`absent`,
absent-`.wardline/`→`unavailable`-never-clean, out-of-scope→`indeterminate`-never-resolved).
No reversal trigger fired. (Out-of-scope item filed: a pre-existing wheel-build packaging bug
blocks `uv tool install` — observation `plainweave-obs-6a7255ffbe`.)

### 2026-06-28 — Operator web UI a11y hardening + 1.2 line delivered to main (PDR-016)

Hardening reading, NOT a north-star reading. Two operator-UI a11y review findings
(owner-supplied) were **adversarially verified, then fixed**: (1) visited primary anchors
regained `--text-on-accent` — the "New requirement" link was ~1.7:1 (a WCAG AA failure) once
visited, because the global `a:visited` rule (0,1,1) outspecified `.btn--primary` (0,1,0);
(2) the success toast now auto-dismisses on **every** page — the dismiss timer was gated
behind `review.html`'s `.qi-actions` handler, so the confirm-step queue flows and the
requirement dossier left it stuck. `make ci` green: **378 tests, 91.14% coverage** (unchanged
from PDR-015 — the changes are CSS / template / JS, no Python coverage delta); CI gate passed
(37s). The full `feat/lacuna-peer-facts-tour-cli-parity` line (web overhaul `9f00ae0` +
design-review docs + peer-facts CLI parity + these fixes) merged to **`origin/main`** via PR #5
— owner-directed (resolves the standing "push `main`" escalation).

Guardrails — all intact: web writes remain human-attributed; advisory, no release verdict; the
a11y fix *restores* a contrast guardrail rather than tripping one. No reversal trigger fired.
Publication held by owner ("we haven't published it yet") — the PyPI publish + the CHANGELOG
version/date finalization remain owner-gated.
