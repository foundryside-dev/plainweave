# Design — Plainweave webUX (operator-facing MVP)

**Date:** 2026-06-25 · **Status:** DESIGN — brainstormed + approved section-by-section; feeds an
implementation plan. **OWNER-GATED at the vision level:** Plainweave today is agent-first (CLI + a
read-only MCP surface); a human-facing web UI is a *new direction* not yet in `vision.md` or
`roadmap.md`. This spec designs the MVP as a **side task**; adopting the human-facing surface as a
standing product bet (and any outward-facing release of it) remains the owner's call.

---

## 1. What this is

A **local-first web app** that lets a human operator **enter, modify, and review requirements** — the
human-facing seam of Weft. It is a thin presentation layer over the existing
`PlainweaveService`; it adds **no** business logic, no new store, and no new authority. Its reason to
exist is the one thing the CLI/MCP surfaces do not give a human ergonomically: a place to **read the
accreted intent corpus** and to **ratify what agents proposed** (approve drafts into versions; accept
or reject agent-proposed trace links). Per `vision.md`, agent-authored bindings are *not* accepted
human truth until a human ratifies them — this UI is where that ratification happens.

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

**Stack:** Starlette + uvicorn (ASGI), Jinja2 server-rendered templates, HTMX for partial updates
(one vendored JS file — **no build toolchain**). Chosen over stdlib-only (clunky to type/test) and a
SPA (node toolchain; overkill for a single-operator local tool). Matches the federation's local-first
pattern (Filigree's dashboard, Loomweave's HTTP read API).

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
| `static/` | vendored `htmx.min.js`, one small CSS file |

**Handlers are thin by contract:** parse request → call exactly one `service` method → render a
template/partial. No business logic. This keeps each unit independently understandable and testable,
and preserves the service as the only place rules live.

**Packaging — honors the thin member.** Web deps go in an **optional extra**: `plainweave[web] =
{starlette, uvicorn, jinja2}`. A bare `pip install plainweave` stays one-dep (`mcp`). `plainweave web`
imports the web tier lazily; if the extra is absent it prints a friendly *"run `pip install
plainweave[web]`"* and exits non-zero (no traceback) — honest degradation in the federation's
enrich-only style.

## 5. Surfaces & routes

Organized around the operator's three jobs. Persistent top nav: **Corpus · Review · Intent · Goals**,
with a pending-count badge on Review and the operator identity shown.

### ① Author

- **Corpus** — `GET /` — the readable list of requirements with their status, goal-link, and
  code-link counts. **Layout: dense table, HTMX-expandable rows** — table by default for scanning
  many and spotting orphans/status at scale; click a row to reveal the statement inline (so the
  curator can read statements and catch duplication without leaving the page). Search box + status /
  "orphans only" filters on top. Reads `intent_corpus()` (+ orphan/goal/code-link counts).
- **Requirement detail** — `GET /req/{id}` — dossier-style: statement, status, acceptance criteria,
  trace links, goals it ladders to, draft/version state. Reads `requirement_dossier(id)`.
- **New / Edit draft** — `GET/POST /req/new`, `GET/POST /req/{id}/edit` — mint a shell or edit the
  active draft. Cheap minting is intentional (shells welcome).

### ② Review — the authority seam

- **Review queue** — `GET /review` — **one unified queue**, items type-badged `DRAFT` / `LINK`,
  worked top-to-bottom to zero. (Unified over two-columns: simpler "get to zero" model and it stays
  sane when one type dominates.) Two item kinds:
  - **Draft awaiting approval** — a requirement with an active draft. Shows the proposed statement,
    criteria, and proposing actor. Action: **Approve** (→ version). Sourced from requirement records
    whose `active_draft_id` is set.
  - **Agent-proposed trace link** — sourced from `trace_for(state="proposed")`. Shows
    `from —relation→ to`, proposing agent, confidence, and a **drift flag** when a code entity's
    content hash changed since the binding was proposed (compare the link's `target_snapshot` /
    `content_hash_at_attach` against the current Loomweave catalog hash). Actions: **Accept** /
    **Reject** (reason).

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
(attributed to the operator) → re-render the affected partial → HTMX swaps it in. The verbs are the
existing, confirmed service API:

| Action | Route | Service call (confirmed signature) |
|---|---|---|
| New requirement | `POST /req/new` | `create_requirement(title, statement, actor, criticality="medium")` |
| Edit draft | `POST /req/{id}/edit` | `update_draft(id, actor=…, title=…, statement=…, expected_draft_revision=…)` |
| Approve draft | `POST /req/{id}/approve` | `approve_requirement(id, actor=…, expected_version=…)` |
| Accept link | `POST /trace/{lid}/accept` | `accept_trace_link(lid, actor=…)` |
| Reject link | `POST /trace/{lid}/reject` | `reject_trace_link(lid, actor=…, reason=…)` |
| Create goal | `POST /goals/new` | `create_goal(title, statement, actor=…)` |
| Ladder req→goal | `POST /req/{id}/ladder` | `link_goal_to_requirement(goal_id, id, actor=…)` |

**Concurrency (grounded in the service).** The edit form carries the `draft_revision` it loaded and
submits it as `expected_draft_revision`; a mismatch raises `ErrorCode.CONFLICT` ("draft revision
conflict") → the handler shows a "draft changed, reload" notice rather than silently clobbering.
Approve carries `expected_version` (the requirement's `current_version`); a mismatch is a `CONFLICT`.
Both service verbs also accept idempotency keys, which the handlers may pass to make a double-submit
safe.

## 7. Error handling & honest degradation

- **`PlainweaveError` → HTTP, mapped in one place** (a Starlette exception handler, not scattered
  try/except). Switch on `ErrorCode`, never message text: `VALIDATION → 400` (inline form errors),
  `NOT_FOUND → 404`, `CONFLICT` / `INVALID_TRANSITION` / `POLICY_REQUIRED` → `409` with a clear
  message, else `500`.
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
- **Key flows end-to-end:** create → edit → approve a requirement; accept *and* reject a proposed
  trace link (including the **drift** case); coverage **banner under a degraded peer**; `web` extra
  missing → friendly exit; CSRF rejection on a forged POST.
- **Pure helpers** (error mapping, template-context builders, CSRF) unit-tested directly.
- **Gate stays green:** the tier is thin and TestClient-covered, so the 90% coverage line holds;
  mypy-strict applies (Starlette is typed). No new test infra — reuse the existing pytest setup.

## 9. Dependencies & packaging summary

- New **optional** runtime deps (extra `web` only): `starlette`, `uvicorn`, `jinja2`. Core install
  unchanged (`mcp`).
- New CLI entry behavior: `plainweave web [--actor <id>] [--host] [--port] [--no-open]`.
- Vendored static asset: `htmx.min.js` (no JS build, no node).

## 10. Assumptions to confirm during planning

1. **Operator config default** — where the default operator `--actor` comes from when the flag is
   omitted (config file vs. a first-run prompt to register a human actor). Lean: a config value under
   `.plainweave/` with a clear first-run message.
2. **Drift signal source for the review queue** — confirm the cleanest read for "code changed since
   the binding was proposed": the link's `target_snapshot` hash vs. the live Loomweave catalog hash
   via the existing adapter (vs. the `is_binding_drifted` path used for SEI bindings).
3. **Pending-drafts query** — confirm the exact read for "requirements with an active draft" (derive
   from `search_requirements()` records' `active_draft_id`, or add a thin `list_pending_drafts()`
   service read if a dedicated query is cleaner).
4. **Goal-edge ratification** — v1 scopes the review queue to drafts + proposed *trace links*; confirm
   whether agent-proposed goal↔requirement edges also need a ratify step in v1 or are operator-created
   only (current lean: operator-created only in v1).

## 11. Out (per YAGNI)

No SPA/JS build; no SEI-binding detail panel; no similarity hint; no verification/baseline surfaces;
no multi-user/auth/remote hosting; no new persistence or authority. The web tier never bypasses the
service.
