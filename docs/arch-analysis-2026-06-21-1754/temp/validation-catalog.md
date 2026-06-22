# Validation Report — 02-subsystem-catalog.md

**Validator:** analysis-validator (independent, fresh-eyes verification)
**Document:** `docs/arch-analysis-2026-06-21-1754/02-subsystem-catalog.md`
**Context:** `docs/arch-analysis-2026-06-21-1754/01-discovery-findings.md`
**Codebase HEAD:** `72e8df2`
**Date:** 2026-06-21

---

## Overall Verdict: **PASS-WITH-NOTES**

The catalog is structurally sound and substantively accurate on every load-bearing
architectural claim the coordinator asked to verify: the cross-presentation coupling
(`mcp_surface` → `cli_commands` privates), the leaky persistence boundary
(`cli_commands` calling `store.connect`/`migrate` directly), the `service.py` god-class,
and the two unimplemented reframe stubs are all **confirmed against source**. Subsystem
membership and LOC figures are correct.

Two classes of defect keep this from a clean PASS, neither blocking:

1. **One factual error** — entry 1 attributes "29 frozen dataclasses" to `models.py`;
   `models.py` actually contains **25**. The "29" is the project-wide dataclass
   inventory (25 in models + 3 in `intent_graph` + 1 in `bindings`).
2. **Overstated/inconsistently-sourced coupling figures** — the fan-in numbers for the
   service methods (`create_requirement` 31, `record_verification_evidence` 24,
   `approve_requirement` 21) are **test-inclusive caller counts**, not production
   coupling. App-only production fan-in for `create_requirement` is **6**. The numbers
   trace to a real Loomweave measure but the framing ("highest-coupled methods in the
   repo") overstates production centrality.

No critical (blocking) issues. Corrections below should be applied before the catalog is
treated as canonical, but downstream phases may proceed.

---

## Contract compliance

All 6 entries carry every required field: **Location, Responsibility, Key Components,
Dependencies (Inbound/Outbound), Patterns Observed, Concerns, Confidence (with
reasoning).** Format is consistent across entries. Catalog claims 6 subsystems and
delivers 6. **PASS** on contract structure.

---

## Per-claim findings table

| # | Claim | Verified? | Evidence |
|---|-------|-----------|----------|
| 1 | 6 subsystems, each with full contract fields | ✅ Yes | All 6 entries present with all 7 required fields |
| 2 | Every cited file exists and is in its assigned subsystem | ✅ Yes | All 15 `src/plainweave/*.py` files exist; assignments match module responsibility |
| 3 | `mcp_surface.py` imports private `_*_dict` helpers + `inspect_project` from `cli_commands` | ✅ Yes | `mcp_surface.py:9-18` imports `_baseline_dict, _baseline_diff_dict, _current_project_key, _dossier_dict, _record_dict, _requirement_verification_status_dict, _trace_dict, inspect_project` |
| 3a | Catalog's enumerated import list is complete | ⚠️ Minor | Catalog Concerns lists 5 `_*_dict` names + `_current_project_key` + `inspect_project`; **omits `_baseline_diff_dict`** (actual = 7 underscore names). Understates, does not misstate |
| 4 | `cli_commands.py` calls `store.connect`/`migrate` directly | ✅ Yes | `cli_commands.py:39` imports `connect, migrate, read_schema_meta`; calls at `:627` (`migrate`), `:628`, `:647` (`connect`) |
| 5 | `service.py` is ~2136 LOC single class | ✅ Yes | `wc -l` = 2136; exactly one `class PlainweaveService` (line 43); 29 public + 64 private methods |
| 5a | "~29 public + ~40 private methods" | ⚠️ Minor | Public = 29 ✅. Private = **64**, not ~40. Understates private method count substantially (god-object claim is if anything strengthened) |
| 6 | `intent_graph.py` + `bindings.py` are NotImplementedError stubs | ✅ Yes | `intent_graph.py` raises at `:97,105,113`; `bindings.py` raises at `:62,71` |
| 7 | Stubs have no intra-package imports (standalone) | ✅ Yes | Both import only stdlib (`__future__`, `dataclasses`, `enum`). Zero `from plainweave`/`from .` imports |
| 8 | LOC figures for all modules | ✅ Yes | All match exactly: service 2136, mcp_surface 1141, cli_commands 1066, models 273, store 254, mcp_server 132, envelopes 115, intent_graph 113, bindings 71, cli 35, errors 34, paths 24 |
| 9 | `store.migrate` is "227-line" migration | ✅ Yes | `migrate` spans lines 22–249 (≈227 lines incl. signature). Accurate |
| 10 | `store.py` outbound deps = stdlib `sqlite3` only | ✅ Yes | Imports only `sqlite3`, `collections.abc`, `contextlib`, `pathlib`. No intra-package imports |
| 11 | `models.py`/`errors.py`/`paths.py` are pure leaf (no intra-package imports) | ✅ Yes | `models.py` has zero `from plainweave` imports; errors/paths likewise |
| 12 | Service Core outbound = Store + Domain Model & Errors | ⚠️ Minor | `service.py:12` imports errors, `:13` models, `:40` `store.connect, read_schema_meta`. Correct, but service imports **only `connect`/`read_schema_meta`, not `migrate`** — direction is right, granularity unstated (not an error) |
| 13 | `models.py` — "29 frozen dataclasses" | ❌ **No** | `models.py` has **25** `@dataclass` (all 25 `frozen=True`). The "29" is project-wide (25 + 3 stub + 1 binding). **Factual error in entry 1** |
| 14 | `store.connect` fan-in 48, highest-coupled in repo | ⚠️ Partial | "Highest-coupled" ✅ (tops coupling hotspot list). "48": resolved callers incl. tests ≈ 50; **app-only production coupling = 32**. Figure is test-inclusive; approximately right but mis-framed |
| 15 | `create_requirement` fan-in 31 | ⚠️ Overstated | Resolved callers ≈ 33 but **all are test functions**; **app-only production fan_in = 6**. "31" is test-inflated |
| 16 | `approve_requirement` fan-in 21 | ⚠️ Overstated | App-only fan_in = **6** (coupling 18 = 6 in + 12 out). "21" is test-inclusive |
| 17 | `record_verification_evidence` fan-in 24 | ⚠️ Overstated | Not in top-15 production hotspots; caller list dominated by tests. App-only fan-in far below 24 |
| 18 | `_handle_service_result` fan-in 18 | ✅ Yes | Loomweave: fan_in 18 exactly |
| 19 | `mcp_server.create_mcp_server` fan-out 14 | ✅ Yes | Loomweave: fan_out 14 exactly |
| 20 | `plainweave_preflight_facts_get` fan-out 11 | ✅ Yes | Loomweave: fan_out 11 exactly |
| 21 | `cli.main` fan-in 21 | ⚠️ Likely test-inclusive | Consistent with the other CLI/service figures being test-inclusive; not independently re-counted here |
| 22 | Dependency direction (leaf→root) diagram | ✅ Yes | Import graph confirms: models/errors/paths are leaves; store depends on nothing intra-package; service → store+models+errors; CLI+MCP → service; MCP → cli_commands |
| 23 | Reframe stubs "not wired to anything" | ✅ Yes | Zero intra-package imports in/out of `intent_graph.py`/`bindings.py`; no other module imports them |

---

## Corrections needed (apply before treating catalog as canonical)

1. **Entry 1, Key Components (BLOCKING for accuracy, not for progression):**
   Change "`models.py` — 29 frozen dataclasses" → "`models.py` — **25** frozen
   dataclasses". If the intent was the project-wide count, state it as "25 in
   `models.py`; 29 domain dataclasses project-wide including the 4 reframe-stub shapes."
   (The discovery doc §5 already handles this correctly — the catalog regressed it.)

2. **Entries 2 & 3, coupling figures (framing fix):** Qualify the fan-in numbers.
   Either (a) report the **app-only/production** figures (`store.connect` 32,
   `create_requirement` 6, `approve_requirement` 6) when arguing architectural
   centrality, or (b) explicitly label the current numbers as "total callers incl.
   tests." As written, "highest-coupled methods in the repo" reads as production
   coupling but is dominated by test callers. The god-object verdict does **not** depend
   on these numbers (LOC + method count carry it), so this is presentation hygiene, not a
   load-bearing correction.

3. **Entry 3, Concerns (completeness):** The imported-privates list omits
   `_baseline_diff_dict`. Add it for an accurate enumeration (7 underscore-private names,
   not 6).

4. **Entry 3, Service Core:** "~40 private methods" → **64** private methods (the
   god-object concern is strengthened, not weakened, by the correction).

---

## Cross-document consistency

- Discovery (01) and catalog (02) agree on subsystem set, module assignment, and LOC.
- **Divergence:** Discovery §5 correctly separates models' 25 dataclasses from the 4
  reframe-stub shapes; catalog entry 1 collapses them into "29 in `models.py`". Catalog
  should inherit discovery's more careful framing.
- Both docs carry the same test-inclusive fan-in figures; the inconsistency is
  systemic to the analysis, not a catalog-only regression.

---

## Scope boundary note

This validation covers **structural** correctness: contract compliance, file/module
existence and assignment, dependency-edge reality, LOC accuracy, and figure
verification against source + Loomweave. It does **not** adjudicate technical-accuracy
judgments (e.g., whether "extract per-aggregate services" is the right refactor, or
whether the idempotency/event-log design is sound) — those require a Python/architecture
SME (`axiom-python-engineering:python-code-reviewer` /
`axiom-system-architect:architecture-critic`).

---

## Confidence Assessment

**High.** Every claim in the findings table was checked against primary source
(`grep`/`wc`/`Read`) and/or the Loomweave index, not against the document's assertions.
The two defects (the 25-vs-29 error and the test-inclusive fan-in framing) were
independently reproduced from `models.py` source and Loomweave `entity_callers_list` /
`entity_coupling_hotspot_list` respectively.

## Risk Assessment

**Low.** No blocking errors. The factual error (29 dataclasses) is contained to one
sentence and self-correcting against the discovery doc. The coupling-figure framing
could mislead a downstream quality/architecture pass into overstating production
coupling of service methods, but the structural verdicts (god-class, leaky persistence,
homeless serializers, unimplemented reframe) stand on independent, verified evidence.

## Information Gaps

- `cli.main` fan-in 21 was not independently re-counted; flagged as "likely
  test-inclusive" by consistency with the other figures, not verified.
- I did not enumerate the full ~29 public method inventory of `PlainweaveService`
  against the catalog's bulleted list one-by-one; public count (29) matches and the named
  methods all exist, but exhaustive name-by-name parity was not performed.
- Loomweave's "resolved callers" excludes attribute-receiver dynamic call sites
  (e.g. `service.create_requirement`), which it lists as unresolved; the true production
  fan-in of service methods is therefore *higher than the app-only resolved count but
  still test-dominated* — the qualitative finding (test-inflated) holds regardless.

## Caveats

- Coupling figures depend on Loomweave index freshness (HEAD `72e8df2`,
  reported fresh); if re-indexed, re-verify.
- "Approximately correct" LOC tolerance was treated generously; all figures in fact
  matched **exactly**, so no tolerance was needed.
