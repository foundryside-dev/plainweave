# Design — Plainweave webUX (operator-facing MVP)

**Date:** 2026-06-25 · **Status:** DESIGN — brainstormed + approved section-by-section, then hardened
by a UX review (visual / IA / interaction / accessibility) whose blocker + high + medium findings are
resolved inline below (§4.1, §5–§8, §12). Feeds an implementation plan. **OWNER-GATED at the vision
level:** Plainweave today is agent-first (CLI + a read-only MCP surface); a human-facing web UI is a
*new direction* not yet in `vision.md` or `roadmap.md`. This spec designs the MVP as a **side task**;
adopting the human-facing surface as a standing product bet (and any outward-facing release of it)
remains the owner's call.

---

## 1. What this is

A **local-first web app** that lets a human operator **enter, modify, and review requirements** — the
human-facing seam of Weft. It is a thin presentation layer over the existing `PlainweaveService`; it
adds **no** business logic, no new store, and no new authority. Its reason to exist is the one thing
the CLI/MCP surfaces do not give a human ergonomically: a place to **read the accreted intent corpus**
and to **ratify what agents proposed** (approve drafts into versions; accept or reject agent-proposed
trace links). Per `vision.md`, agent-authored bindings are *not* accepted human truth until a human
ratifies them — this UI is where that ratification happens.

## 2. Goals / non-goals

**In scope (MVP):**
- Browse the corpus; open a requirement's detail/dossier.
- Author requirements: create a shell, edit its draft, approve the draft into a version.
- **Human-review queue** — approve pending drafts; accept/reject agent-proposed trace links.
- **Intent dashboard** — the `intent_coverage` north-star (honestly qualified) + `intent_orphans`
  at the code / requirement / goal levels.
- **Goals & laddering** — create strategic goals; ladder a requirement up to a goal.

**Out of scope (deferred, not built in v1):**
- SEI-binding *display* on the detail view (drift surfacing still appears in the review queue for
  code-binding trace links).
- The optional Loomweave semantic-similarity hint.
- Verification methods/evidence and baseline surfaces (exist in the service; not exposed in v1).
- Multi-user accounts, remote hosting, RBAC. The MVP is single-operator localhost.

## 3. Users & the operator-identity model

One human operator, running the app on their own machine. The operator's identity is the **linchpin
of authority semantics**:

- Resolved once at startup in `web/context.py` from `plainweave web --actor <id>` (or a config
  default), and registered via `service.register_actor(actor_id, kind="human", display_name=…)`.
- **Every write** the UI performs passes `actor=<operator_id>`. Because the actor `kind` is `human`,
  approvals and trace-link acceptances carry **human authority** — distinct from `agent_proposed`.
  This is precisely the `vision.md` distinction: the UI is the seam where intent becomes accepted
  human truth.

## 4. Architecture

A thin web tier over `service.py`. All logic stays in the service (the single source of truth); the
web tier only translates HTTP ↔ service calls and renders.

```
browser ──HTTP──▶ Starlette routes ──▶ PlainweaveService ──▶ store (SQLite, .plainweave/)
   ▲                  │  (thin handlers)      (all logic lives here)
   └── HTML / HTMX ◀──┘
```

**Stack:** Starlette + uvicorn (ASGI), Jinja2 server-rendered templates, **HTMX ≥ 1.9** for partial
updates (one vendored JS file — **no build toolchain**). The version floor is firm: the accessibility
patterns in §4.1 use `hx-swap-oob="innerHTML:#id"`, which requires HTMX ≥ 1.8 (we pin ≥ 1.9 for
headroom). Chosen over stdlib-only (clunky to type/test) and a SPA (node toolchain; overkill for a
single-operator local tool). Matches the federation's local-first pattern (Filigree's dashboard,
Loomweave's HTTP read API).

**New subpackage `src/plainweave/web/`** (keeps the flat top-level clean):

| File | Responsibility |
|---|---|
| `app.py` | Starlette app factory: route table, templates env, static mount, exception handler |
| `context.py` | per-request service wiring + operator-actor resolution; CSRF token helper |
| `routes/requirements.py` | corpus, detail, new/edit/approve handlers |
| `routes/review.py` | review-queue handlers (approve draft; accept/reject trace link) |
| `routes/intent.py` | coverage + orphans dashboard handlers |
| `routes/goals.py` | goals list/create; ladder req→goal |
| `server.py` | `plainweave web` wiring (uvicorn launch + open browser) |
| `templates/` | Jinja2: `base.html`, page templates, `_partials/` for HTMX swaps |
| `static/` | vendored `htmx.min.js` (≥1.9), one small CSS file |

**Handlers are thin by contract:** parse request → call exactly one `service` method → render a
template/partial. No business logic. This keeps each unit independently understandable and testable,
and preserves the service as the only place rules live.

**Packaging — honors the thin member.** Web deps go in an **optional extra**: `plainweave[web] =
{starlette, uvicorn, jinja2}`. A bare `pip install plainweave` stays one-dep (`mcp`). `plainweave web`
imports the web tier lazily; if the extra is absent it prints a friendly *"run `pip install
plainweave[web]`"* and exits non-zero (no traceback) — honest degradation in the federation's
enrich-only style.

## 4.1 HTMX interaction & accessibility patterns (cross-cutting)

These contracts apply to every surface and are the load-bearing result of the UX review. Detailed,
copy-pasteable markup/handler snippets from the two SME passes feed the implementation plan; this
section fixes the *contracts* the plan must honor.

- **Span→button protocol.** The brainstorm mockups used `<span class="mock-button">` as layout
  shorthand. In production, **every interactive control is a real `<button>`** (a `type="submit"`
  inside a `<form>`, or a `type="button"` carrying HTMX attrs). Spans are not keyboard-operable and
  carry no role. **Links (`<a>`) GET; mutations POST** — never drive Approve/Accept/Reject from an
  `<a>`.
- **HTMX needs a 2xx to swap.** HTMX does **not** swap non-2xx responses. Validation/conflict states
  that must re-render in place are therefore caught **locally** in the handler and returned as **200**
  with an inline-error partial (see §7 for the two documented exceptions to the §7 global mapper).
- **Two-step pattern for irreversible / input-requiring actions.**
  `action button → GET intermediate partial → inline form/confirm → POST → OOB result`. Used for
  Reject (needs a reason), Approve (irreversible version bump, no un-approve verb), and Accept-on-drift
  (§5②). A **Cancel** in any intermediate partial GETs the original card partial back from the server
  (authoritative restore, not a stale DOM snapshot).
- **Action-result OOB response shape.** Every approve/accept/reject handler returns **one** partial:
  the acted card's target is replaced by nothing (`hx-target="#queue-item-{id}"`,
  `hx-swap="outerHTML"` → card removed), plus `hx-swap-oob` fragments that update (1) the live-status
  region, (2) the nav Review badge, and (3) the empty-queue state when the count reaches zero. One
  response per POST keeps handlers thin and the three signals consistent.
- **Persistent live region.** `base.html` carries a permanent
  `<div id="sr-status" role="status" aria-live="polite" aria-atomic="true" class="visually-hidden">`.
  It is **never** replaced via outerHTML (AT may stop tracking a re-created live region); updates are
  `hx-swap-oob="innerHTML:#sr-status"`. After an action it announces e.g. *"Approved: {title}. 2 items
  remaining in queue."* / *"…Queue is now empty."*
- **Focus management.** A small page-scoped vanilla-JS listener on `htmx:afterSettle` (scoped to events
  from `.qi-actions`) moves focus to the next `.queue-action-primary` button, or — when the queue
  empties — to the empty-state `<h2 tabindex="-1">`. This satisfies WCAG 2.4.3 across HTMX swaps.
- **Loading indicator is decorative.** A global `#global-loader` (toggled by each form's
  `hx-indicator`) is `aria-hidden="true"`; status is conveyed by the live region, not the spinner.
- **`visually-hidden` utility** (clip-rect) is added once to the CSS file for SR-only labels and the
  live region.
- **WCAG 2.2 AA** is the conformance target (single-operator localhost desktop; 3.3.8 N/A — no login).
  An **empirical NVDA/VoiceOver pass on the running app** is a required gate before the review surface
  ships (the focus-then-announce ordering is an inherent AT race no markup fully eliminates).

## 5. Surfaces & routes

Organized around the operator's three jobs. Persistent top nav: **Corpus · Review · Intent · Goals**
(`<nav aria-label="Main navigation">`, `aria-current="page"` on the active item), with a pending-count
badge on Review (OOB-updated, kept in the DOM even at zero as a stable swap target) and the operator
identity shown.

### ① Author

- **Corpus** — `GET /` — the readable list of requirements with status, goal-link, and code-link
  counts. **Layout: dense table, HTMX-expandable rows.**
  - **Multi-row expand (F-IA-2):** each row has its **own unique target** (`hx-target="#req-detail-{id}"`)
    so opening row B never collapses row A — essential to the hero job of reading statements side by
    side to spot near-duplicates. Expand GETs `/req/{id}/inline`; an in-partial "▲ Collapse" button
    GETs an empty partial back. Rows are independent toggles; no shared target, no auto-collapse.
  - **Search + filters (F-IX-4, F-A11Y-1):** one `<search>` landmark wrapping a single `<form>` so
    search + status + orphan **serialize together**. The search `<input type="search" id="req-search">`
    has a **visible `<label>`** ("Search requirements"); the magnifier glyph is decorative
    (`aria-hidden`); the placeholder is a hint only. Trigger:
    `hx-trigger="change, input changed delay:300ms from:#req-search"` with `hx-indicator`. Status and
    orphan controls are toggle buttons with **non-color** active states (border weight + bold + a `✓`
    glyph, not color alone).
  - **Orphan granularity (F-IA-3):** the binary "orphans only" becomes a radio group
    `?orphan=` → `'' (any) | no-goal | no-code | both`, inside the shared form, composing with
    search + status.
  - Reads `intent_corpus()` (+ orphan/goal/code-link counts — see §10).
- **Requirement detail** — `GET /req/{id}` — dossier-style: statement, status, acceptance criteria,
  trace links, goals it ladders to, draft/version state. Renders **current-approved vs. draft side by
  side** (both come from `requirement_dossier(id)`; no diff library needed in v1). Approve can be
  initiated here as well as from the queue. Reads `requirement_dossier(id)`.
- **New / Edit draft** — `GET/POST /req/new`, `GET/POST /req/{id}/edit` — mint a shell or edit the
  active draft. Cheap minting is intentional (shells welcome).

### ② Review — the authority seam

- **Review queue** — `GET /review` — **one unified queue**, items type-badged `DRAFT` / `LINK`, worked
  top-to-bottom to zero. (Unified over two-columns: simpler "get to zero" model; stays sane when one
  type dominates.) Each card is an `<article aria-labelledby="qi-title-{id}">`; the type badge carries
  `aria-label="Item type: Draft|Link"`; **every action button gets a Jinja-interpolated `aria-label`
  that includes the item title/relation** so no two buttons share an accessible name (F-A11Y-2).
  - **Draft awaiting approval** — a requirement with an active draft. Shows the proposed statement,
    criteria, proposing actor, and a **"View full draft →"** link to the dossier (F-IX-2, guards
    approve-blind). **Approve is a two-step confirm** ("this approves v{n}; cannot be undone")
    (F-IX-1). Sourced from requirement records whose `active_draft_id` is set.
  - **Agent-proposed trace link** — sourced from `trace_for(state="proposed")`. Shows
    `from —relation→ to`, proposing agent, and confidence. **Reject is a two-step inline `reason`
    form** — the service *requires* a reason; an empty submit returns 200 with an inline error and
    does **not** call the service (F-IX-1). Accept (non-drifted) is a direct POST.
  - **Drift flag (F-VD-1)** — when a code entity's binding has drifted (`TraceLink.freshness` is not
    the fresh sentinel — see §10), the card gets: a `queue-item--drifted` visual treatment
    (heavier/amber border + tint + a persistent `CODE DRIFTED` chip — *not* color/emoji alone); a
    real text warning *"Code changed since this link was proposed — verify before accepting,"*
    associated to the **Accept** button via `aria-describedby`; and **Accept routed through an extra
    confirm** (`drift_acknowledged`). The drift warning is the single highest-stakes signal in the
    product; it is encoded in border + chip + text + ARIA so it survives greyscale, missing emoji
    fonts, and screen readers.
  - **Empty state:** when the last item clears, `#queue-list` is OOB-swapped to an "All caught up"
    section whose `<h2 tabindex="-1">` receives focus and is announced.

### ③ Survey

- **Intent dashboard** — `GET /intent` — the `intent_coverage` north-star number, **honestly
  qualified in-band** (namespace scoping, `denominator_complete`, `present_plugins`, bounded
  evidence), plus `intent_orphans` at code / requirement / goal levels. A degraded/partial denominator
  renders a **banner**, never a clean-looking number (see §7).
- **Goals & laddering** — `GET /goals`, `POST /goals/new`, `POST /req/{id}/ladder` — create strategic
  goals; ladder a requirement to a goal. Orphan goals surface as "what am I doing here?".

## 6. Data flow & write path

**Reads:** handler → one `service` read → Jinja template (examples in §5).

**Writes — all POST; GET never mutates.** Form/HTMX POST → exactly one `service` write verb
(attributed to the operator) → return the §4.1 action-result OOB partial / a re-rendered partial. The
verbs are the existing, confirmed service API:

| Action | Route | Service call (confirmed signature) |
|---|---|---|
| New requirement | `POST /req/new` | `create_requirement(title, statement, actor, criticality="medium")` |
| Edit draft | `POST /req/{id}/edit` | `update_draft(id, actor=…, title=…, statement=…, expected_draft_revision=…)` |
| Approve draft | `POST /req/{id}/approve` | `approve_requirement(id, actor=…, expected_version=…)` |
| Accept link | `POST /trace/{lid}/accept` | `accept_trace_link(lid, actor=…)` |
| Reject link | `POST /trace/{lid}/reject` | `reject_trace_link(lid, actor=…, reason=…)` |
| Create goal | `POST /goals/new` | `create_goal(title, statement, actor=…)` |
| Ladder req→goal | `POST /req/{id}/ladder` | `link_goal_to_requirement(goal_id, id, actor=…)` |

**New GET partial routes** (reads that return partial HTML for the two-step / expand flows of §4.1 and
§5 — not mutations):

| Route | Returns |
|---|---|
| `GET /trace/{lid}/reject-form` | inline reason form |
| `GET /trace/{lid}/card` | restore link card (Cancel) |
| `GET /trace/{lid}/accept-drifted-confirm` | drifted-accept confirm |
| `GET /req/{id}/approve-confirm` | approve confirm (reads dossier) |
| `GET /req/{id}/draft-card` | restore draft card (Cancel) |
| `GET /req/{id}/inline` | corpus inline statement expand |
| `GET /req/{id}/inline/collapsed` | empty partial (collapse) |

**Concurrency (grounded in the service).** The edit form carries the `draft_revision` it loaded as
`expected_draft_revision`; `update_draft` raises `ErrorCode.CONFLICT` ("draft revision conflict") on
mismatch. Approve carries `expected_version`; a mismatch is also `CONFLICT`. Both verbs accept
idempotency keys the handlers may pass to make a double-submit safe. The **conflict UX preserves the
operator's unsaved work** (F-IX-5): on edit conflict the handler returns a 200 partial showing the
operator's submitted text in an *editable* column beside the current draft, with a resubmit carrying
the fresh revision and a "discard & start fresh" path.

## 7. Error handling & honest degradation

- **`PlainweaveError` → HTTP, mapped in one place** (a Starlette exception handler, not scattered
  try/except). Switch on `ErrorCode`, never message text: `VALIDATION → 400` (inline form errors),
  `NOT_FOUND → 404`, `CONFLICT` / `INVALID_TRANSITION` / `POLICY_REQUIRED` → `409` with a clear
  message, else `500`.
- **Two documented local-catch exceptions** (because HTMX only swaps 2xx): `POST /req/{id}/edit`
  and `POST /req/{id}/approve` catch `CONFLICT` locally and return **200** with an inline
  conflict/confirm partial; `POST /trace/{lid}/reject` catches the empty-reason case locally and
  returns **200** with the reason form + inline error. Each is commented in-code as a deliberate
  exception to the global mapper. All other errors fall through to the global handler.
- **Peer degradation is shown, never hidden.** Coverage/orphans lean on the Loomweave catalog
  adapter; when it is absent/stale the service already returns `present_plugins`,
  `denominator_complete`, and freshness, plus `PEER_ABSENT` / `PEER_STALE` codes. The dashboard
  renders a **banner** ("denominator incomplete — Loomweave catalog stale") instead of a clean
  number. This honors the machine-enforced **no-silent-clean** guardrail.
- **Missing `[web]` extra:** friendly install hint, non-zero exit, no traceback.
- **Write safety:** mutations are POST + a minimal per-session CSRF token (cookie + hidden field).
  Cheap; keeps a stray local tab from POSTing to the server.

## 8. Testing

- **Thin handlers ⇒ mostly flow tests.** Starlette `TestClient` against the app wired to a **temp
  `.plainweave` store** seeded with fixtures; assert status, that rendered HTML contains the expected
  rows/partials, and that the right `service` verb ran **with the operator actor**.
- **Key flows end-to-end:** create → edit → approve a requirement (incl. the two-step approve confirm);
  accept *and* reject a proposed trace link, where **reject with a blank reason returns 200 + inline
  error and does NOT call `reject_trace_link`**; the **drift** case (drifted Accept routes through the
  extra confirm); **edit conflict** returns 200 with both the submitted text and the current draft;
  multi-row expand (expanding row B leaves row A's detail populated); coverage **banner under a
  degraded peer**; `web` extra missing → friendly exit; CSRF rejection on a forged POST.
- **Pure helpers** (error mapping, template-context builders, CSRF, filter composition) unit-tested
  directly.
- **Accessibility gate:** an empirical **NVDA / VoiceOver pass on the running app** for the review
  queue (live-region announcement, post-action focus move, empty-state focus) — a named gate in the
  implementation plan, not a unit test.
- **Gate stays green:** the tier is thin and TestClient-covered, so the 90% coverage line holds;
  mypy-strict applies (Starlette is typed). No new test infra — reuse the existing pytest setup.

## 9. Dependencies & packaging summary

- New **optional** runtime deps (extra `web` only): `starlette`, `uvicorn`, `jinja2`. Core install
  unchanged (`mcp`).
- Vendored static asset: **`htmx.min.js` ≥ 1.9** (no JS build, no node) — version floor is firm for
  the `innerHTML` OOB swaps in §4.1.
- New CLI entry behavior: `plainweave web [--actor <id>] [--host] [--port] [--no-open]`.

## 10. Open questions to confirm during planning

**Resolved by the UX review (recorded here so the plan inherits them):** reject *requires* a reason →
two-step inline reason form; drifted-accept → extra confirm step; action results → the §4.1 OOB shape;
HTMX pinned ≥ 1.9.

**Still to confirm:**
1. **Operator config default** — where the default `--actor` comes from when the flag is omitted
   (config value under `.plainweave/` vs. a first-run register prompt). Lean: a config value with a
   clear first-run message.
2. **`TraceLink.freshness` drift sentinel** — confirm the exact field value(s) that mean "drifted"
   (the template branches on `freshness != "current"` or equivalent). This is the drift signal source
   for the review queue (vs. the `is_binding_drifted` path used for SEI bindings).
3. **Corpus counts inline** — confirm `intent_corpus()` returns `goal_count` / `code_link_count` per
   item (the table needs them for the `→ Goal` / `← Code` columns and the orphan filter); if not, add a
   thin enrichment read.
4. **Pending-count read** — confirm an efficient "items remaining" read for the OOB badge/empty-state
   after each action (one extra list query per action is acceptable at this traffic).
5. **Draft provenance field** — what the dossier exposes for "proposed by {actor}" on a draft
   (`RequirementDraft` has no `proposed_by` in the model); use the correct dossier field.
6. **Pending-drafts query** — confirm the read for "requirements with an active draft" (derive from
   `search_requirements()` records' `active_draft_id`, or add a thin `list_pending_drafts()`).
7. **Goal-edge ratification** — v1 scopes the review queue to drafts + proposed *trace links*; confirm
   agent-proposed goal↔requirement edges are operator-created only in v1 (current lean: yes).

## 11. Out (per YAGNI)

No SPA/JS build; no SEI-binding detail panel; no similarity hint; no verification/baseline surfaces;
no multi-user/auth/remote hosting; no new persistence or authority. The web tier never bypasses the
service.

## 12. Interaction & accessibility requirements (firm checklist for the plan)

Consolidated, non-optional requirements from the UX review. The two SME passes' detailed markup
(reject/approve/drift two-step partials, the OOB result template, the focus script, the corpus filter
form, the conflict panel) are the implementation reference for these.

- **Controls:** real `<button>`s only (no `<span>` buttons); links GET, mutations POST; CSRF hidden
  field on every mutating form.
- **Names:** every repeated action button carries an item-context `aria-label`; type badges carry
  `aria-label="Item type: …"`.
- **Live region + focus:** the permanent `role="status"` region (innerHTML-OOB only) + `htmx:afterSettle`
  focus management + the keep-in-DOM nav-badge OOB target, exactly as §4.1.
- **Drift encoding:** border + chip + real text + `aria-describedby` on Accept + extra confirm — never
  color/emoji alone.
- **Search:** visible `<label>`, `<search>` landmark, decorative emoji, single shared filter form.
- **Empty/loading/error states:** "All caught up" focusable empty state; decorative `aria-hidden`
  spinner; inline `role="alert"` form errors.
- **The three low findings (folded in):** column headers use text-first words (`Goal` / `Code Links`)
  with arrow glyphs `aria-hidden`; **minimum body text 14px in tables / 16px elsewhere**; the "Goals"
  nav item stays top-level (the Author-vs-Survey grouping is a label nuance in the map, not a
  structural change).
- **AT gate:** empirical NVDA/VoiceOver pass on the running review surface before it ships.
- **Residual risk to track:** focus-then-announce ordering across AT/browser combos (use polite, not
  assertive, for status; assertive reserved for errors); pin HTMX ≥ 1.9 or the `innerHTML` OOB swaps
  silently no-op.
