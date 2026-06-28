# Validation Report — 02-subsystem-catalog.md

**Validator:** analysis-validator (independent gate) · **Date:** 2026-06-28
**Artifact under test:** `docs/arch-analysis-2026-06-28-0751/02-subsystem-catalog.md`
**Live tree validated against:** HEAD `8258f76` (confirmed via `git rev-parse`)
**Basis docs read:** `01-discovery-findings.md`, `temp/dependency-reconciliation.md`,
`temp/catalog-E{1..5}.md`

---

## (a) VERDICT: **PASS-WITH-FIXES**

The catalog is contract-conformant (8/8 entries complete) and substantively
accurate. **Every one of the 8 high-stakes claims I was asked to spot-verify is
VERIFIED against live source** (line-precise in most cases). No claim was
refuted as architecturally wrong; no over-claim found. The fixes below are
**citation/count corrections** — none change a single architectural conclusion,
none block the downstream quality pass.

> **Environmental caveat (material to scope):** Loomweave has **no index** for
> this project right now (`.weft/loomweave/loomweave.db` is absent — every
> `mcp__loomweave__*` tool returns "NO INDEX"). I therefore could **not**
> re-verify the Loomweave-derived integer metrics (`store.connect` fan-in **44**,
> `_error` fan-in **36**, `_handle_service_result` fan-in **24**, `_result`
> fan-in **16**, `success_envelope` fan-in **11**, `cycles:[]`). I verified the
> *qualitative facts those integers stand for* directly from source and at
> runtime instead (see §c). The fan-in integers themselves are **UNCONFIRMED**
> (not refuted) — the catalog's own basis-fidelity note honestly discloses the
> index↔live delta, which mitigates.

---

## (b) Contract-conformance table (8 entries × required fields)

Required per entry: Location · Responsibility · Key Components · Dependencies
(Inbound + Outbound) · Patterns Observed · Concerns · Confidence (w/ reasoning).

| # | Entry | Loc | Resp | KeyComp | Dep-In | Dep-Out | Patterns | Concerns | Conf+reason | Verdict |
|---|-------|-----|------|---------|--------|---------|----------|----------|-------------|---------|
| 1 | Domain Service Core | ✅ | ✅¹ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 2 | Intent Graph | ✅ | ✅ | ✅ | ✅ | ✅² | ✅ | ✅ | ✅ | PASS |
| 3 | CLI Surface | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 4 | MCP Surface | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 5 | Web UI | ✅ | ✅¹ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 6 | Persistence | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 7 | Sibling-Tool Adapters | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| 8 | Response Contract / X-cut | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |

¹ Single sentence per the contract, but very long/semicolon-dense (Domain
Service Core, Web UI). Conformant; readability-only.
² Intent Graph Outbound = "none — stdlib only." Explicitly stated, not empty.

All 8 Confidence fields carry evidence-based reasoning (files read in full,
cross-checks named). **Contract conformance: PASS for all 8.**

---

## (c) Spot-verified claims (the 8 high-stakes checks)

| # | Claim | Verdict | Evidence (live tree `8258f76`) |
|---|-------|---------|--------------------------------|
| 1 | **N+1 connections** `service.py:1467→1479→1529-1550` opens own `connect()` per surface | **VERIFIED** | `:1467` `for entity in items:`; `:1479` `goals = self._goal_nodes_for_surface(entity.sei)`; `:1529` def; **`:1542` `with connect(self.db_path) as connection:`** inside, one fresh connection per catalog entity. Exactly as described. |
| 2 | **`store.connect` connect-per-call, no pool, no WAL, only `foreign_keys=on`** (store.py:11-19) | **VERIFIED** | `store.py:11-19` verbatim: fresh `sqlite3.connect`, `row_factory=Row`, `execute("pragma foreign_keys = on")`, close in `finally`. **No `journal_mode`/`wal`/`busy_timeout` anywhere in `src/plainweave/`.** Fan-in 44 itself UNCONFIRMED (no Loomweave index) — connect-per-call pattern confirmed from the code shape. |
| 3 | **DB exceptions escape `ErrorCode`** — `connection.execute` unguarded; only `_error`→`PlainweaveError` wrapped | **VERIFIED (end-to-end)** | Service side: `_error:3020` is the sole `PlainweaveError` factory; **86 `connection.execute(...)` calls; exactly 3 `except` total — `LoomweaveIdentityError`×2 (`:2477,:2489`) + `ValueError`×1 (`:2959`). None guard a DB exec.** Surface side (closes the "escapes past callers" half): **both adapters catch `except PlainweaveError` ONLY** — `_result` (`mcp_surface.py:730`), `_handle_output` (`cli_commands.py:1179`); no generic `except Exception` on the result path (the two `except Exception` in cli_commands `:536,:593` are scoped to *doctor sibling probes*, not the service path). So a raw `sqlite3.IntegrityError`/`OperationalError` is **not** normalized to INTERNAL — it propagates past the `ErrorCode` contract. Concern is accurate, not over-claimed. |
| 4 | **MCP preflight fan-out** — bare call → whole corpus via `search_requirements` (`:990`) → 3 calls/req (`:1084-1086`), no limit/offset | **VERIFIED** | `_preflight_requirement_ids:983`: when `requirement_ids is None` → `return [record.id for record in service.search_requirements()]` (**`:990`**, whole corpus, no pagination). `:1084-1086` = `requirement_preflight_profile` + `verification_status` + `requirement_dossier` (**3 service calls/req**). Line-exact. |
| 5 | **No module-load cycle; function-local import dodges it** (correction of E3's "module-level cycle") | **VERIFIED — correction is RIGHT** | `mcp_surface.py:9` imports from `cli_commands` at **module level**; `cli_commands.py` imports `PlainweaveMcpSurface` **only function-locally** (`:1103`, `:1114`, comment `# local import: cli_commands<->mcp_surface cycle`). `grep` confirms **NO module-level `mcp_surface` import in `cli_commands`**; runtime `import plainweave.cli_commands; import plainweave.mcp_surface` succeeds with **no ImportError**. Genuinely no import cycle. (Couldn't run `module_circular_import_list` — index absent — but source+runtime are dispositive.) ⚠ **Catalog cites the import at `cli_commands.py:1095`; actual sites are `:1103` and `:1114` (two sites).** |
| 6 | **Warpline = producer, not consumer** — no warpline in src; `requirements_enrichment_get` at mcp_surface.py:189,759 | **VERIFIED** | `grep -rn warpline src/plainweave/` → **empty**. `mcp_surface.py:189` = `authority_boundary` string "...for Warpline's reserved enrichment slot..."; `plainweave_requirements_enrichment_get` def at **`:761`** (catalog cites 759 — section header; def is 761, ±2). No warpline adapter exists. |
| 7 | **Version `1.1.0`** (catalog) vs README's 1.0 | **VERIFIED** | `_version.py` → `__version__ = "1.1.0"`. Code says 1.1.0. (README/classifier "1.0 / Development Status 5" is a separate doc-vs-code drift already noted in `01`.) |
| 8a | **19 MCP tools** | **VERIFIED** | `mcp_server.py`: **19** `@mcp.tool()`; `mcp_surface.py`: **19** `MCP_TOOL_METADATA` entries (counted by `"mutates"`). Match. |
| 8b | **15 contract resources** | **VERIFIED (count) / phrasing loose** | `len(MCP_RESOURCE_URIS) == 15` (registered via loop `mcp_server.py:173-174`). Count right. Catalog/E2 phrasing "registers 15 `@mcp.resource()` readers" is loose — there is **1** `@mcp.resource()` decorator applied in a loop, not 15 literal decorators. Cosmetic. |
| 8c | **16 commands / 38 CLI handlers** | **VERIFIED (38 direct) / 16 by enumeration** | `set_defaults(handler=` → **38** leaf handlers (exact). 16 top-level commands matches the entry's own enumerated list (init/doctor/req/criterion/trace/catalog/goal/bind/intent/baseline/actor/verify/status/dossier/wardline-peer-facts/web). |
| 8d | **22 web routes (15 GET + 7 POST)** | **VERIFIED (app-wide) — attribution nit only** | The numbers are **correct app-wide**: `web/routes/` registers **21** (requirements 8, review 9, goals 3, intent 1 = **14 GET + 7 POST**); **`app.py:85` `/healthz`** adds the 15th GET → **15 GET + 7 POST = 22**. The only defect is the catalog attributing all 22 to "`routes/`" when one GET lives in `app.py`. **POST=7 is exact** and matches the 7 named write endpoints. (Downgraded from an initial "REFUTED" — the count is right; only the locus label is imprecise.) |

---

## (d) Inconsistencies / over-claims (with severity)

**No CRITICAL or HIGH findings.** No architectural claim is wrong; no concern is
stated as fact beyond what source supports. Findings are citation/count drift:

| ID | Severity | Finding | Evidence | Fix |
|----|----------|---------|----------|-----|
| F1 | **Low** | Web route tally **mis-attributed** (not miscounted). Catalog: "routes/ — 22 routes (15 GET + 7 POST)". App-wide count is correct (22/15/7); but `routes/` alone = **21 (14 GET + 7 POST)** — the 15th GET is `app.py:85` `/healthz`. | route greps; `app.py:85` | Re-attribute: "21 routes in `routes/` (14 GET + 7 POST) + `/healthz` & `/static` mount in `app.py`" (or label the 22 as app-wide). Keep "7 writes" — exact. |
| F2 | **Low** | Local-import citation drift. Catalog (×2: cross-cutting + CLI concern) cites the `PlainweaveMcpSurface` function-local import at **`cli_commands.py:1095`**; actual = **`:1103` and `:1114`** (two sites). | grep | Change `:1095` → `:1103,:1114`. |
| F3 | **Low** | Count error: "register_commands + **nine** `_register_*` helpers". Actual = **11** (`_register_{requirement,criterion,trace,catalog,goal,bind,intent,baseline,actor,verify,status}_commands`). | 11 `def _register_*` | "nine" → "eleven". |
| F4 | **Low/Info** | Loomweave integer metrics not re-derivable via MCP (index absent): fan-in 44/36/24/16/11. **Grep call-site bounds are all consistent** (not contradicted): `self._result(`=**16** (exact), `_handle_service_result(`=25 raw vs 24, `self._error(`=48 raw calls ≥ 36 entity-fan-in, `connect(`=36 in service.py alone ≤ 44 codebase-wide, `success_envelope(` external callers ≈10 ≈ 11. | NO-INDEX state + grep | Leave figures (consistent); carry the basis-fidelity caveat wherever reused; `loomweave analyze` before treating integers as current-HEAD. |
| F5 | **Low/Info** | Coverage: `__init__.py` and `__main__.py` (`python -m plainweave`→`cli.main`) are not explicitly placed in any of the 8 entries. Trivial wiring, zero architectural weight; `experimental/` correctly excluded as dead. | `find` + `cat __main__.py` | Optional one-line note that trivial package wiring (`__init__`/`__main__`) is intentionally not cataloged. |
| F6 | **Info** | Minor ±1–9 line drift on a few non-headline citations (`requirements_enrichment_get` def 761 vs cited 759; `inspect_project` use 396/828 vs cited 395-413/825-829). Consistent with the disclosed +77 LOC `cli_commands.py` delta. Reconciliation-map temp doc cites `initialize_project`/`inspect_project` at 1115/1129 vs actual **1124/1138** (temp doc, not the artifact). | reads | No action required for the catalog; substantively correct. |

**Internal-consistency cross-checks that PASS:**
- Bidirectional edges reconcile: Service Inbound{CLI,MCP,Web} ↔ each surface's
  Outbound{Service}; MCP Outbound{CLI} ↔ CLI Inbound{MCP reaches back};
  Adapters Inbound{Service,MCP,CLI-doctor} ↔ Service/MCP Outbound{Adapters};
  Persistence Inbound{Service,CLI} ↔ Service/CLI Outbound{Persistence}.
- "No module-load cycle" is stated consistently across cross-cutting themes +
  CLI + MCP entries (E3's contradicting "module-level cycle" was correctly
  overridden at merge — and the override is factually right, §c #5).
- The catalog matches the reconciliation map on direction (surfaces→service;
  service composes adapters; CLI init/inspect bypasses service to store).
- Minor asymmetry (Info): Web Outbound lists "Persistence path resolution"
  (`paths.py`) but the Persistence entry's Inbound omits Web. Not an error —
  `paths.py` is explicitly double-homed (shared by Persistence + Response
  Contract); Web touches `paths`, not `store.connect`.

---

## (e) Punch-list (to reach a clean PASS — all non-blocking)

1. **F1** — Correct the web-route count: `routes/` = 21 (14 GET + 7 POST); state
   `/healthz` + `/static` live in `app.py`. (Keep "7 write endpoints".)
2. **F2** — Fix the local-import citation `:1095` → `:1103,:1114` (two sites).
3. **F3** — "nine `_register_*` helpers" → "eleven".
4. **F4** — Tag the Loomweave fan-in integers as index-basis (`e95b6ad`) and
   carry the basis-fidelity caveat wherever they're reused; re-run
   `loomweave analyze` before downstream phases treat them as current.
5. **F5** (optional) — One line acknowledging `__init__.py`/`__main__.py` as
   intentionally-uncataloged trivial wiring.

---

## SME Agent Protocol sections

**Confidence Assessment — High (structural) / Medium (a few integer metrics).**
- High on all 8 contract-conformance verdicts and on 7 of 8 spot-checks (read
  the relevant source spans directly; line-precise).
- High on the route-count refutation and the no-module-cycle correction (source
  + runtime import test are dispositive).
- Medium-only where I depended on the catalog's Loomweave integers, which I
  could not independently re-derive (index absent).

**Risk Assessment.**
- *Low residual risk to downstream phases.* The catalog's architectural
  conclusions (god-object/no-layering, connect-per-call + no WAL, DB-exceptions
  escape `ErrorCode`, preflight O(corpus) fan-out, surface↔surface coupling,
  enrich-only honesty, Warpline-as-producer) are all source-verified and safe to
  build the quality/architect passes on.
- *Risk if F1–F3 propagate verbatim:* a downstream consumer quoting "22 routes",
  "nine helpers", or ":1095" inherits a small inaccuracy. Cosmetic, not
  decision-altering. Fix before publication.
- *Risk from F4:* if anyone treats the fan-in integers as live HEAD truth they
  may be a few commits stale (confined to `cli_commands.py`/`mcp_surface.py`).

**Information Gaps.**
- Loomweave index absent → exact fan-in 44/36/24/16/11 not re-derivable via
  MCP; **bounded consistent** by grep call-site counts (one exact: `_result`=16)
  and `cycles:[]` confirmed by source + runtime import test. No contradiction
  found; precise integers remain index-basis (`e95b6ad`).
- I did not re-execute the `busy_timeout` test (E5 reports it passes); I
  confirmed only the precondition — `connect` sets no `busy_timeout` pragma.
- Technical-accuracy judgements (is connect-per-call the *right* design, is the
  god-object the *top* refactor target) are out of a structural validator's
  remit — left to the quality/architecture pass.

**Caveats.**
- This is a **structural** validation: contract conformance, cross-document
  consistency, evidence presence, and source-fidelity of the high-stakes claims.
  It is **not** a code-quality or architectural-soundness judgement.
- "PASS-WITH-FIXES" means the artifact is fit to proceed; the punch-list is
  polish, and zero items block the next phase.
- Per the adversarial mandate: the findings above are deliberately exhaustive
  down to Info severity — a zero-finding pass would have been an audit defect,
  not a clean bill of health.
