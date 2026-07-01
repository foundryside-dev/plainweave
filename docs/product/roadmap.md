# Plainweave Roadmap            Updated: 2026-07-01 (PDR-019, PDR-020)

> Sequencing, WSJF / cost-of-delay, and dated forecasts are produced by
> /axiom-program-management. This file records bets as INTENT, not a delivery
> schedule. Do not compute WSJF here; hand the committed bet over for sequencing.

## Now (committed, in-flight)

- **Dogfood against live sibling peers** — Lacuna + Loomweave done (PDR-008): the
  code-up graph and the cross-member seam (PDR-004) reproduce on real sibling corpora.
  Remaining: more peers as desired; keep proving the seam holds. · metric: north-star.
- **Operator web UI** (ratified PDR-013) — the human-facing seam (`plainweave[web]`,
  Starlette+HTMX over PlainweaveService) is now an **accepted standing bet**, shipped in
  1.1.0; keep hardening/extending it under the soft-launch posture. · metric: operator
  use (once real users exist).
- **Live peer adapters + contract hardening** (PDR-014) — Wardline peer facts +
  Warpline requirements enrichment shipped to `main` with frozen `.v1` contracts;
  continue retiring production blockers (Loomweave-owned identity resolution, Legis fact
  emission, Filigree contract tests remain). · metric: production-readiness.

## Next (shaped, decreasing certainty)

- **Explicit degraded peer-state envelopes** for live Loomweave and Legis adapters.
- **Contract fixtures** for the intent-graph and binding envelopes (shared
  structural validator already landed for preflight, F5).
- **Bound preflight project-scope fan-out** + revisit the N+1 connection pattern
  once a real corpus makes them bite. · tracker: plainweave-706d80dc8e,
  plainweave-3edcd19943 (currently acceptable at pre-alpha scale).

## Later (directional bets, no order, no dates)

- **Cross-member coverage completeness** — a peer's north-star can only cover languages
  whose public surface its Loomweave plugin tags. The Rust plugin's public-surface tagging
  is weak: on the Loomweave peer `present_plugins` shows core/python/rust, yet all tagged
  public surfaces are `python:`. Plainweave already surfaces the gap (`present_plugins`);
  **closing it upstream is owner-gated** (sibling obligation — do not file a Loomweave
  ticket unilaterally). Owner-raised this session as the most pressing remaining gap.
- **Federation operability parity** — `doctor` + `--fix` shipped (PDR-011: store/schema +
  Loomweave catalog binding + MCP surface, `--root`, non-zero-exit gate). The
  **`plainweave-workflow` skill pack is now DELIVERED** in 1.2.0 (PDR-019: federation-standard,
  in-package + dogfooded). The remaining agent-orientation surfaces the sibling doctors manage —
  a SessionStart hook, `.mcp.json` self-registration, and a `plainweave install` distribution
  command — remain a future onboarding bet (the rest of PDR-011's Option 2), not yet committed.
- Optional Loomweave semantic-similarity hint over requirement text — DEFERRED by
  PDR-003; advisory only, never a dedup verdict. · tracker: plainweave-02376962ab.
- Corpus-curation workflows for duplicate or overlapping requirements.
- Formal suite membership / hub-roster admission — **owner-gated** (PDR-002). The 1.0.0
  packaging + PyPI release shipped (PDR-012); formal suite admission is a separate owner step.
  _(The operator web UI moved Later → Now: ratified as a standing bet, PDR-013.)_

## Done since last checkpoint (2026-06-29 → 07-01)

- **Plainweave 1.2.0 RELEASED to PyPI** (PDR-019, owner-directed) — the full 1.2 line
  (peer-facts CLI parity PDR-015 + web/a11y overhaul PDR-016 + requirements producer
  gated-live PDR-017 + seam hardening PDR-018) shipped live via Trusted Publishing. PyPI
  jumps 1.0.0 → 1.2.0 (1.1.0's release build had failed on the wheel bug, now fixed). Clears
  the publication escalation held across the last three checkpoints.
- **`plainweave-workflow` skill pack delivered** (PDR-019) — moved **Later → Done**: the
  federation-standard agent skill (SKILL.md + reference sheets) ships in-package as package
  data and is dogfooded into the repo skill trees. Delivers part of PDR-011's Option-2
  operability-parity bet; the hook / `.mcp.json` / `install` surfaces remain future.
- **Plainweave 1.2.1 RELEASED to PyPI** (PDR-020, owner-directed) — error-legibility
  (say-what-you-know) fixes: version-conflict errors now disclose the actual version in
  message + details + hint; cause-specific hints replace the misleading blanket "refresh
  state" hint. Additive (frozen error envelope + `ErrorCode` unchanged); `make ci` 400 passed
  / 91.32%. Idempotency-hint precision deferred (`plainweave-de4ced60cf`, P3).

## Done (2026-06-26 → 06-27)

- **Plainweave 1.1.0 cut: operator web UI + SEI conformance** (PDR-013 ratifies the web-UI
  direction). The human-facing seam (`plainweave[web]`) merged to `main`; the public site
  `plainweave.foundryside.dev` is live; `release/1.1.0` (PR #2) is the open release-ceremony
  vehicle. **The PyPI publish is held, owner-gated.**
- **Peer facts shipped** (PDR-014): `weft.plainweave.wardline_peer_facts.v1` +
  `weft.plainweave.requirements_enrichment.v1`, merged to `main` (`bc37a24`) via 17-task
  subagent-driven TDD. `make ci` green (355 tests, 90.94% cov); `wardline scan` clean.
  Retires 3 of 5 production blockers. Sibling wiring handed off as 3 owner-gated peer
  prompts (`docs/handoffs/`).

## Done earlier (2026-06-24 → 06-25)

- **Plainweave 1.0.0 RELEASED to PyPI** (PDR-012, owner-directed): public repo
  `foundryside-dev/plainweave` + CI/CD (Trusted Publishing, `main` branch protection);
  `pip install plainweave` → 1.0.0 (wheel + sdist + attestations). Stable behaviour/contracts;
  completeness a documented roadmap item. Accepted as-shipped despite a docs-only concurrent
  commit swept into the tag (wheel is code-identical).
- **Lacuna intent regression-harness** (PDR-010): Plainweave added as Lacuna's 6th tour
  member — a self-seeding leg + 4 catalogued `pw-*` capability demos over a deterministic
  2-covered:2-uncovered mix (oracle 2/4 default, 2/3 scoped). Banked as a demonstrator +
  regression-harness for the liveness/deprecation numerator semantics, **not** north-star
  movement (the seam was already proven read-only, PDR-008). Merged to Lacuna's local `main`
  (unpushed); recorded Lacuna-side in Lacuna PDR-0005; 2 plan rounds + a code review (2 HIGH fixed).
- **Doctor → federation parity** (PDR-011): `plainweave doctor` + `--fix`/`--root`/non-zero-exit,
  checking store/schema, the Loomweave catalog binding (report-only, consumer boundary), and the
  MCP surface; envelope v1→v2. `make ci` green (mypy strict, 235 tests, 90.11% cov); wardline clean.
- **`intent_coverage` read primitive shipped to `main`** (PDR-009): the product
  self-computes the north-star honestly — scoped denominator (excl. `tests.`/`scripts.`),
  `denominator_complete`, `present_plugins`, bounded evidence (`max_surfaces`) — advisory,
  no verdict (machine-enforced). Closes plainweave-44be10cc2c + plainweave-7be2817d58;
  reviewed (15-agent adversarial pass, 0 blockers); fixed a deprecated-requirement
  numerator-inflation defect; kept the intent_trace explain/count split (52b743d5b9).
- Beta vertical slice shipped: intent-graph model, ADR-029 SEI binding, read
  primitives (orphans/trace/corpus), authoring-time write surface.
- Cross-member seams: Loomweave catalog adapter, Legis preflight advisory cell,
  peer-ready entity-intent-context API.
- Independent review cycle: 3 findings fixed (F1/F2/F5); 2 perf findings deferred.
- **Beta-candidate golden-vector gate: PASS on Plainweave self-dogfood** (PDR-005).
- **Cross-member seam validated on live peers** Lacuna + Loomweave (PDR-008).
