# Validation Report — Synthesis Layer (03 / 04 / 05 / 06)

**Validator:** analysis-validator (second independent gate — synthesis layer) · **Date:** 2026-06-28
**Artifacts under test:** `03-diagrams.md`, `04-final-report.md`, `05-quality-assessment.md`, `06-architect-handover.md`
**Ground truth checked against:** `02-subsystem-catalog.md` (V1-validated, fixes applied), `temp/dependency-reconciliation.md`, `temp/validation-catalog.md` (V1 report), and **live source at HEAD `8258f76`**.
**Mandate:** adversarial — catch synthesis-time judgment claims that drift from evidence. V1 never saw 03–06 (they post-date that gate).

---

## (a) VERDICT: **PASS-WITH-FIXES**

The synthesis layer is contract-conformant, internally near-consistent, and substantively well-supported. Every high-stakes claim I was asked to re-derive against source is **VERIFIED** — including the just-added Q23 `ResourceWarning` correction, whose three sub-claims hold end-to-end. The four initiatives' remediations are technically sound for the stated scope.

**One required fix (Medium) and a short Low/Info punch-list.** The required fix is a genuine over-claim: the Q23 correction was propagated to docs **05** and **06** but **not** to doc **04**, which still carries the retracted pre-Q23 framing — a direct 04↔05 contradiction in the most-read document. It does **not** block the analysis from proceeding to `/axiom-system-architect`; it must be corrected before publication.

---

## (b) Per-document findings

### Doc 04 — Final Report

**S1 · ResourceWarning over-claim contradicts the corrected evidence (Q23) · MEDIUM · required fix · HEADLINE**
`04:150-152` (Maturity & fitness, caveat *(b)*) states:
> "the **persistence layer** carries a documented, suppressed `ResourceWarning: unclosed database` ('track the underlying leak separately') that **corroborates the connect-per-call concern** in the team's own words."

This is the **pre-Q23 framing that Q23 explicitly retracts.** I verified Q23 against live source (see §c) and it is correct, so 04's clause is the wrong one:
- **"persistence layer carries"** → false attribution. Production connection sites close deterministically in `finally` — `store.connect` (`store.py:16-19`) and `LoomweaveAdapter._connect` (`loomweave_adapter.py:602-605`, comment: "closed deterministically rather than left to GC"). The warning originates in **test fixtures** (`tests/loomweave_test_utils.py:10,90`, `with sqlite3.connect(...) as conn` — commits but does not close). It is **not** a production/store-layer leak.
- **"corroborates the connect-per-call concern"** → directly contradicted by Q23's own correction note: *"the connect-per-call concern stands on connection **count** and journal mode, **not** on this warning."*

Doc 05's metrics snapshot (`05:234-237`) and Q23 (`05:205-222`), and doc 06's Initiative A note (`06:47-49`) + Initiative G (`06:130-135`), are all already Q23-consistent. **Only 04 is stale.**
→ **Fix:** delete caveat *(b)* or rewrite Q23-consistently, e.g.: *"(b) a suppressed `ResourceWarning: unclosed database` traces to **test fixtures** (`with sqlite3.connect()` that never close), not a production leak — production closes deterministically; the suppression comment's 'store-layer' attribution is itself inaccurate (see Q23). It is **not** evidence for the connect-per-call concern, which stands on connection count + journal mode."* Keep caveat *(a)* (a11y) — it is accurate.

**S4 · Ranked-risk list mixes severity tiers without saying so · INFO (transparency, not an error)**
`04:103-129` ranks 5 risks: #1 god object (Q9-High), #2 connect-per-call/N+1+no-WAL (Q3-High, **with Q4-High folded into its prose**), #3 DB exceptions escape (Q1-High), #4 surface↔surface coupling (Q10-**Medium**), #5 web exposure (Q13-**Medium**). All four register-High items (Q1/Q3/Q4/Q9) **are** represented (Q4 inside #2), so this is *not* a miscount — but a reader mapping "top-5 ranked" onto "4 High" sees Q4 missing as a line item and two Mediums promoted. The exec summary's "concentrated in two places + one correctness gap" framing is fully consistent. No fix required; optionally add one clause noting the ranking reflects *risk concentration*, not severity order.

**S7 · "clean / textbook layered service" headline — qualification check · INFO**
`04:25-26` ("textbook layered service whose discipline is real, not aspirational") sits next to a 3027-LOC god object rated risk #1. It is **defensible** if "clean" is read as *module-graph topology* — `cycles:[]`, which I independently reconfirmed (§c). The exec summary immediately names the god object as concentrated risk, so it is adequately qualified. Flagging only so a downstream architect does not read "sound/clean" as "no structural problem." Soundness adjudication is `architecture-critic`'s remit, not mine — no change recommended.

### Doc 05 — Quality Assessment

**Clean on the synthesis-integrity axis.** Severity tally **4 High / 8 Medium / 11 Low = 23** matches the 23 Q-items exactly (High: Q1,Q3,Q4,Q9; Medium: Q2,Q5,Q6,Q10,Q11,Q13,Q14,Q17; Low: the remaining 11). No item's severity contradicts its own impact description (§d). Q23 is correctly framed and self-aware. Every Q traces to a `02` concern or to source (§e).

**S2 · Tracker linkage `3edcd19943` → Q5 is imprecise · LOW**
`05:87` (and `06:191`) cite tracker `plainweave-3edcd19943` against **Q5 (N+1 in `intent_coverage`)**. The task's actual title/body is *"Preflight: N+1 SQLite connections per scoped requirement"* (`mcp_surface.py:698-700`) — a **different code site** from Q5's `intent_coverage` loop (`service.py:1467→1479→1529-1550`). Same per-call-connect *pattern*, but closing `3edcd19943` would not by itself fix Q5's site. Its `→ Q3` linkage is sound (the task self-describes as "the repo-wide per-call connect pattern"); its natural Q-home is **Q3/Q4** (preflight).
→ **Fix:** remap `3edcd19943 → Q3/Q4`; note that **Q5 (intent_coverage N+1) has no dedicated tracker task** (file one, or fold explicitly under Initiative A). Low — both are remediated together by A's unit-of-work, so planning impact is nil.

**S5 · "361 test functions" is approximate · INFO**
`04:59`, `05:228` cite 361. A raw `def test_` sweep of `tests/` yields ≈369. Within counting-method noise (parametrize expansion, helper defs, collected-vs-defined); not decision-altering. Optionally label as "~360".

### Doc 06 — Architect Handover

**Clean on traceability and sequencing.** All 23 Q-items map to exactly one initiative (A:Q1,2,3,5,7 · B:Q9,12[,19] · C:Q10,16,17,18,22 · D:Q4,6,8 · E:Q13,14,15 · F:Q11 · G:Q19,20,21,23) — no orphan Q, no phantom Q. Q19's double-listing (B step 2 + G) is explicitly reconciled ("folds into B"). Dependency graph (A⇒B, A⇒D, C⇒B-goldens) is coherent. The "what to leave alone" anti-gold-plating section correctly preserves the doctrine.

**S3 · Initiative A remediation menu — minor technical caveats · LOW/INFO (route to embedded-database)**
The remediation set (WAL + explicit `busy_timeout` + `sqlite3.Error→PlainweaveError` + `BEGIN IMMEDIATE`/sequence) is **technically sound and will work** for single-operator/local-first. Two precision caveats for the implementer:
- `IntegrityError → CONFLICT` (`06:38-40`, `05:46-48`) is slightly **too broad**: NOT-NULL/CHECK violations are also `IntegrityError` but are not "conflicts." Map only UNIQUE/PK collisions to `CONFLICT`; route other `IntegrityError` to `INTERNAL`/`VALIDATION`.
- `BEGIN IMMEDIATE` **serializes** the `count(*)+1` read-then-insert, which *prevents* the id collision rather than needing "retry-to-`CONFLICT`" (`05:56-57`). The two listed fixes are alternatives, not a sequence; the "retry-to-CONFLICT" phrasing conflates them. Mechanisms are all valid.
These are implementation-detail refinements, not contract breakers. Doc 06 already routes Initiatives A & F to `/axiom-embedded-database (audit-sqlite-discipline)` — the authoritative SQLite-discipline pass. No verdict impact.

### Doc 03 — Diagrams

**Faithful to the reconciled edge map and the V1-corrected catalog.** Spot-checks all PASS:
- 3 surfaces → 1 service (D2/D3 CLI/MCP/WEB→SVC); MCP read-only + Web sole-write (D2 `classDef web write` / `mcp read`, reading text). ✅ Matches `02`.
- Two layering exceptions present as dotted edges: CLI⤏store (init/inspect), MCP⤏CLI (serializers + inspect_project). ✅ Matches reconciliation map; D2 reading correctly notes "no module-load cycle."
- Warpline = **producer**, dotted, off the MCP/CLI surface (not an adapter): D1 `PW -. PRODUCES requirements_enrichment.v1 .-> warp`; D3 `SVC -. produces requirements_enrichment.v1 .-> MCP`. ✅ Matches the reconciliation correction.
- Web route counts: D3 labels Web "22 routes (15 GET / 7 POST)" — the **app-wide** figure, consistent with V1's F1 fix (21 in `routes/` [14 GET+7 POST] + `/healthz` in `app.py` = 22 app-wide). ✅ Numbers right.
- N+1 sequence (D5) matches `service.py:1467` (`for entity in items`) → `:1479` (`_goal_nodes_for_surface`) → `:1542` (`with connect(...)`) inside `:1529-1550`. ✅ Verified line-exact (§c). D5's "list_catalog opens 2 ro connections" matches Q7.
- Web-write sequence (D6) matches the catalog's optimistic-concurrency + CSRF double-submit + process-singleton-operator + CONFLICT→200-partial patterns. ✅

**S6 · D3 web label drops the routes/-vs-app.py locus · INFO**
D3's "22 routes" is the correct app-wide count but does not carry the "21 in `routes/` + `/healthz` in `app.py`" attribution V1's F1 added to the catalog. Numbers are right; only the locus nuance is absent. Optional annotation; no fix required.

---

## (c) Source re-derivations (the high-stakes checks)

| # | Claim | Verdict | Evidence (live `8258f76`) |
|---|-------|---------|---------------------------|
| 1 | **Q23a** — `store.connect` closes in `finally` | **VERIFIED** | `store.py:16-19`: `try: yield connection / finally: connection.close()`. Production closes deterministically. |
| 2 | **Q23b** — `LoomweaveAdapter._connect` closes in `finally` | **VERIFIED** | `loomweave_adapter.py:602-605`: `try: yield / finally: connection.close()`; comment `:598-599` "closed deterministically rather than left to GC". |
| 3 | **Q23c** — test fixtures `with sqlite3.connect()` do NOT close | **VERIFIED** | `tests/loomweave_test_utils.py:10` and `:90`: `with sqlite3.connect(db_path) as connection:` — stdlib `sqlite3` `__exit__` commits the txn but does **not** close; connection left to GC. This is the true origin of the suppressed warning. **Q23 reasoning is SOUND.** |
| 4 | **Q23 quote** — pyproject suppression attributes to "store-layer" | **VERIFIED** | `pyproject.toml:89-93`: comment "pre-existing **store-layer** connections surfaced only under --cov… Track the underlying leak separately." Q23's quote and its "inaccurate attribution" verdict both hold. |
| 5 | **N+1** `1467→1479→1529-1550` per-entity connect | **VERIFIED** | `service.py:1467` `for entity in items:`; `:1479` `goals = self._goal_nodes_for_surface(entity.sei)`; `:1542` `with connect(self.db_path) as connection:` inside def `:1529`. One fresh connection per catalog surface. |
| 6 | **`count(*)+1`** racy id sites (Q2) | **VERIFIED** | `service.py:2110` `_next_requirement_number`, `:2137` `_next_link_number`, `:2149` `_next_evidence_number` (plus 7 sibling `_next_*` at 2114-2147) all `select count(*) … + 1`. |
| 7 | **`fail_under = 90`** branch gate | **VERIFIED** | `pyproject.toml:101` `branch = true`; `:106` `fail_under = 90`. The repeated "≥90% branch gate" claim holds. |
| 8 | **One runtime dependency** ("thin / one runtime dep, mcp") | **VERIFIED** | `pyproject.toml:24-26` `dependencies = ["mcp>=1.2.0"]`. starlette/uvicorn/jinja2 are `[web]` extras (`:48-53`); coverage/mypy/pytest/ruff are dev-group. Exactly one runtime dep. |
| 9 | **No import cycles** (`cycles:[]`) | **VERIFIED (now index-confirmed)** | Loomweave index — **absent during V1, now rebuilt** — `module_circular_import_list` → `cycles:[]`, confidence `resolved`. Independently reconfirms what V1 could only show via source+runtime. |
| 10 | **Tracker tasks exist, open P3, subjects match** | **VERIFIED (w/ S2 nuance)** | `plainweave-706d80dc8e` "Preflight: project scope fans out … no cap or facts pagination" (open, P3) = Q4 exactly. `plainweave-3edcd19943` "Preflight: N+1 SQLite connections per scoped requirement" (open, P3) = Q3 pattern (not Q5's site — see S2). `plainweave-02376962ab` = semantic-similarity feature, correctly tagged out-of-scope in `06:192-193`. Note: docs cite bare hashes; full IDs carry the `plainweave-` prefix. |

---

## (d) Severity-consistency audit (check 4)

Counts internally consistent (4/8/11 = 23 = Q1–Q23). No item's severity contradicts its own impact:
- **Q1 High** — contract breach is concurrency-independent (any `OperationalError`: disk-full/locked/corrupt escapes the closed vocab), so High "before relying on a stated contract" holds, not merely a scaling artefact.
- **Q3 High** — single-operator still runs MCP-agent reads concurrent with web-operator writes → the writer-lock ceiling is reachable in-scope. Defensible.
- **Q4 High vs Q6 Medium** — both O(corpus) read amplification, but Q4 is **agent-facing, unpaginated, 3×-amplified, defaults to whole corpus**; Q6 is **operator-facing** (one human, naturally bounded). The High/Medium split tracks the threat surface, not a contradiction.
- **Q9 High** — 3027 LOC / ~13 aggregates; dominant maintainability liability. Defensible.
- **Q13 Medium** (web no-authN + `--host`) — the item most likely to be contested upward by a security review, but against the stated local-first/default-loopback scope and the "unguarded flag, latent on misconfig" framing, Medium is internally consistent. (`06` already routes the `--host` threat model to `/ordis-security-architect`.)

## (e) Traceability sweep (checks 1 & 6) — no unbacked synthesis claims

All 23 Q-items trace to a `02` concern or to live source; all map to exactly one initiative; no phantom/orphan items. The **only** synthesis-time claim found that the corrected evidence refutes is **S1** (doc 04's ResourceWarning clause) — the very class of error the mandate primed for ("like the ResourceWarning one already caught"). Q23 itself is a synthesis-time *new* item but is source-backed and corrective, not an over-claim. Report "Limitations" (`04:161-173`) is honestly hedged (static-only, index/live split, tests-read-not-rerun) — no hedge needs firming.

---

## (f) Punch-list (required + optional)

1. **S1 (required, Medium)** — Rewrite or delete doc `04:150-152` caveat *(b)* so it is Q23-consistent (test-fixture origin, not a production/persistence leak; **not** corroboration of the connect-per-call concern). Eliminates the 04↔05 contradiction.
2. **S2 (Low)** — Remap tracker `3edcd19943` from Q5 → **Q3/Q4** (it is the *preflight* N+1); note Q5 (intent_coverage N+1) has no dedicated tracker task. Update `05:87` and `06:191`.
3. **S3 (Low/Info)** — Tighten Initiative A's mapping note: UNIQUE/PK→`CONFLICT` only (not all `IntegrityError`); present `BEGIN IMMEDIATE` and "retry-to-CONFLICT" as alternatives. (Defer to `/axiom-embedded-database`.)
4. **S4 / S6 / S5 / S7 (Info, optional)** — one-clause note that 04's risk ranking is concentration-not-severity-order; annotate D3's web-route locus; soften "361" to "~360"; ensure "clean" reads as module-graph topology.

None of items 2–4 block progression. Item 1 blocks **publication** of 04, not the downstream architect pass.

---

## SME Agent Protocol

**Confidence Assessment — High (structural + the re-derived source claims) / Medium (deep remediation soundness).**
- High on all four documents' contract conformance, cross-document consistency, traceability completeness, and the 10 source re-derivations in §c (read the spans directly, line-precise; `cycles:[]` now index-confirmed).
- High on S1: it is a direct, verbatim contradiction between `04:150-152` and the Q23 correction I independently verified.
- Medium on remediation **technical** soundness (S3): I reasoned about WAL/busy_timeout/BEGIN IMMEDIATE/error-mapping from first principles and found them sound, but a definitive SQLite-discipline adjudication is `/axiom-embedded-database`'s remit (already routed in 06).

**Risk Assessment.**
- *Low residual risk to the downstream `/axiom-system-architect` pass.* The synthesis conclusions (god object #1, persistence/read-path #2, DB-contract gap, surface coupling, web exposure) are all source-grounded and safe to build on.
- *Publication risk if S1 ships:* doc 04 would assert, in its most-read section, a production "leak corroborates connect-per-call" claim that the same analysis (05/06) retracts — an internal contradiction a careful reader will catch and an over-claim the evidence refutes. Fix before publishing 04.
- *Minor planning risk from S2:* a reader could think closing `3edcd19943` resolves the intent_coverage N+1 (it does not); harmless because Initiative A remediates both.

**Information Gaps.**
- I did **not** re-execute the test suite or benchmark the N+1 — consistent with the report's stated static-only limitation; performance claims rest on call-shape, which I confirmed structurally.
- Loomweave fan-in integers (44/36/24/16/11) were not re-derived to exact values; the index is now rebuilt and queryable (cycles reconfirmed), so 04's "re-run `loomweave analyze` before treating integers as current-HEAD" caveat could now be **discharged** by a quick re-pull — out of synthesis-layer scope, noted for the orchestrator.
- README "1.0/Production-Stable" vs code 1.1.0 / classifier "Development Status :: 5" is a pre-existing doc-vs-code drift owned by `01`, not re-adjudicated here.

**Caveats.**
- This is a **structural + evidence-fidelity** gate over the synthesis layer: contract conformance, cross-document consistency, traceability, and source-truth of the high-stakes and newly-introduced claims. It is **not** an architectural-soundness judgement — whether the god object is *the* right #1 target, or connect-per-call *the* right design, is `architecture-critic`'s call.
- Per the adversarial mandate, findings are deliberately exhaustive to Info severity; a zero-finding pass over a freshly-synthesised layer would be an audit defect, not a clean bill of health. The verdict is **PASS-WITH-FIXES** — one required fix (S1), the remainder polish.
