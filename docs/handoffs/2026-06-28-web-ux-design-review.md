# Design Review: Plainweave Operator Web UI

> **Resolution (2026-06-28, same day):** all 9 Major findings + the folded Minors were
> implemented in the working tree (26 web files + new `error.html`) and verified — `make ci`
> green (ruff/mypy/pytest, 91.14% coverage) and `wardline` clean. Adopted site-kit's linen/ink/
> brass tokens; drift badge now 5.11:1; all action buttons 44px; 320px reflow eliminated; global
> pending badge; linked orphan titles; New-requirement button; visible auto-dismissing toast;
> confidence chips. An adversarial review caught a regression (the global context processor could
> double-fault and naked-500 the error page on a launch-time ctx failure) — fixed and covered by a
> regression test. Before/after screenshots in the session scratchpad `shots/` (`desk_*` vs `after_*`).

**Reviewer:** lyra-ux-designer / design-review · **Date:** 2026-06-28
**Method:** Live Playwright drive (Chromium 1226) against a freshly-seeded instance
(`src/plainweave/web`, Starlette + HTMX + Jinja2), plus static read of all
templates/CSS/routes and a computed-style + contrast + target-size + reflow audit.
Seed: 5 requirements (approved / draft / orphan mix), 2 goals (1 orphan), 2 proposed
trace links (1 clean conf 0.82, 1 **drifted** conf 0.55), coverage 1/2 = 50%.
Screenshots + raw audit JSON: session scratchpad `shots/`.

## Summary

**Overall Assessment:** Needs Work (visual layer), Strong (markup/interaction/a11y semantics)

**Critical Issues:** 0 · **Major Issues:** 9 · **Minor Issues:** 6

The single defining finding: **the markup is accessibility-literate and the interaction
design is genuinely good, but `app.css` (19 lines) styles only ~20 classes while the
templates reference ~25 more.** The result is a UI that is ~60% unstyled — and among the
queue items the one component that *is* fully styled is the *drift warning*, producing an
inverted hierarchy where the alarming state looks more finished than the normal one. None
of this trips a WCAG **A** gate, there is no data-loss or security hole (CSRF is enforced),
keyboard works, and focus is visible — so the severity is concentrated in **AA** +
visual-hierarchy, not showstoppers.

**Important context for the fix:** the operator UI hand-rolls its own minimal `app.css` and
class vocabulary (`.banner--warn`, `.type-badge`, `.big-number`, its own amber `#c47b1a`) and
references **nothing** from the Weft design system. Yet `site/vendor/site-kit` already ships a
**framework-free** token + component CSS layer — `tokens/*.css` (`--brass-*` amber family,
`--ink-*` text scale, `--linen-*` surfaces) and `components/components.css` (`.wf-banner--warn`,
`.wf-badge--warn`, `.wf-fresh`, `.wf-enr`, plain CSS, no React) — whose vocabulary maps almost
one-to-one onto the operator UI's unstyled classes. The operator tool's hand-picked palette
(`#c47b1a` amber, pure white/black) also **drifts from the suite's linen theme** ("natural dyes
on unbleached cloth"; `--brass-500 #AC8222`, `--linen-100` page). So the right remedy is largely
"adopt the existing tokens," not "invent new CSS" — see Recommendation #1.

---

## Visual Design

### Strengths
- Body copy is `#1c1c1c` on white = **17:1** contrast — excellent legibility, 16px base.
- The **drift state is exemplary**: amber left-border, warn-background card, "CODE DRIFTED"
  badge, an explicit note, and the action morphs from "Accept" to "Accept…". It is the one
  place where visual treatment, copy, and affordance all align.
- Restraint is appropriate for an operator tool — no decorative noise.

### Issues
| Issue | Severity | Evidence | Recommendation |
|-------|----------|----------|----------------|
| ~25 referenced classes have **no CSS rule** — most UI renders unstyled | Major | Computed: `.banner--warn` color `rgb(28,28,28)` / bg transparent / border none / padding 0; `.queue-item` border 0 / padding 0; `.type-badge` no bg; `.queue-action-primary` = native UA button; `.muted` opacity 1; `.big-number` 16px/400 | Write component CSS for banners, cards, badges, primary buttons, muted/warn text |
| `role="alert"` / `role="status"` banners have **zero visual emphasis** | Major | `.banner--warn` renders as plain black text on Intent page, error banners, edit-conflict | Give alerts a colored bg + left border + padding (site-kit `.wf-banner--warn`). NB: not a 1.4.1 fail — the meaning is in the text; the gap is visual *emphasis/hierarchy* |
| **Inverted hierarchy on the KPI** — the Intent "50% 1/2" north-star number renders at body size while "Orphans" section `<h2>`s dominate | Major | `.big-number` computed 16px/weight 400; see `desk_intent.png` | Make `.big-number` large/bold (e.g. 2.5rem 700); demote orphan-section headers |
| **Review queue is a wall of text** — clean DRAFT/LINK cards have no separation; only the drifted card is bordered | Major | `desk_review.png`: `.queue-item` border/padding/margin all 0 | Card-style every queue item (border, padding, gap); reserve amber strictly for drift |
| **Primary action has no visual primacy** — Approve/Accept look identical to Reject/Cancel | Major | `.queue-action-primary` bg `rgb(239,239,239)`, native `2px outset` border — same as every other button | Style primary as filled/high-contrast; secondary as outline/ghost |
| **"CODE DRIFTED" badge fails contrast** | Major | White on amber `#c47b1a` = **3.39:1** for 11.2px bold (needs 4.5, SC 1.4.3) | Darken amber to ≥ `#a8650f` *or* use dark text on amber |
| Secondary text not de-emphasised — IDs/version labels (`.muted`) render at full black | Minor→Major | `.muted` color `rgb(28,28,28)`, opacity 1; titles and their IDs are indistinguishable (`Audit log is append-only REQ-SEEDROOT-0001`) | Define `.muted { color:#6b6b6b }` |
| Orphan/gap markers (`.warn` "none") not colored — the gap signal is invisible | Minor→Major | Corpus "none" cells + Goals "— no requirements ladder here" render as plain text | Color `.warn` (e.g. amber/red ink) — text alone is the only current cue |
| Control boundaries faint | Minor | Toggle/table borders `#d9d9d9` = **1.41:1** (needs 3.0, SC 1.4.11) | Darken to ≥ `#767676` |

---

## Information Architecture

### Strengths
- Flat, legible top nav (Corpus / Review / Intent / Goals) with `aria-current="page"`.
- Corpus filtering is well-modelled: search + Status + Orphans facets as `fieldset`/`legend`
  groups; orphan facet (No goal / No code / Both) maps directly to the product's gap concept.

### Issues
| Issue | Severity | Evidence | Recommendation |
|-------|----------|----------|----------------|
| **"New requirement" is undiscoverable** — no affordance anywhere; reachable only by typing `/req/new` | Major | Corpus page has no create button; Goals page *does* have an inline create form (inconsistent) | Add a "New requirement" button to Corpus |
| **Intent orphans are raw node IDs, not titles, and not links** | Major | `desk_intent.png`: lists `req-3 req-4 req-5`, `goal-2` — an operator can't tell which requirement, nor click to fix | Render titles + link each orphan to its detail page |
| **Nav "pending review" badge is blank on every page except `/review`** | Major | Code-confirmed: `corpus`, `intent_dashboard`, `goals_page` omit `pending_count` from context; `base.html` `{% if pending_count %}` → falsy elsewhere | Compute `pending_count` in a shared context layer so the badge is global |
| Intent shows empty section headers (`Orphans — code (0)`) | Minor | `desk_intent.png` | Hide zero-count sections |

---

## Interaction Design

### Strengths
- **Review-queue flow is genuinely good:** optimistic card removal, the pending-count badge
  updates out-of-band, the SR live region announces e.g. *"Approved: Exports respect per-field
  redaction rules. 3 items remaining in queue."*, and focus advances to the next primary action
  (or the "All caught up" heading). Verified live.
- **Reversibility is handled with care:** approve confirm ("*This cannot be undone — there is
  no un-approve*"); drifted-link accept is a deliberate two-step ("*ratifies the link in its
  current drifted state*"); reject **requires a typed reason** (inline error if blank).
- **Edit-conflict recovery is excellent:** optimistic-concurrency clash shows your unsaved text
  beside the current draft — no silent data loss.
- CSRF tokens on every mutating form; HTMX bound to real `<button>`/`<form>` elements.

### Issues
| Issue | Severity | Evidence | Recommendation |
|-------|----------|----------|----------------|
| **No explicit visible success message** — the only sighted cues are the card vanishing and the badge decrementing; the positive confirmation ("Approved: …") goes only to the SR live region | Major | `#sr-status` is `visually-hidden`; after approve only the SR region carries the wording (`desk_review_after_approve.png`, badge 4→3) | Add a brief visible toast/inline confirmation mirroring the SR text |
| **Action buttons are 21px tall (< 24px)** | Major | Audit: every Approve/Accept/Reject/Confirm/Cancel measured h=21 (SC 2.5.8) | Set min-height 24px (44px recommended for touch) + padding |
| Consequential confirm button not visually distinguished from Cancel, and sits in the leading position | Minor | `desk_review_drift_confirm.png`: "Accept drifted link" == "Cancel" styling | Style the consequential action distinctly; consider trailing position |
| Focus ring relies on the UA default | Minor | Audit: outline `auto 1px rgb(16,16,16)` (present — passes 2.4.7) | Define an explicit `:focus-visible` ring for cross-browser / forced-colors robustness |

---

## Accessibility

### WCAG 2.2 AA Compliance
- 1.4.3 Contrast (text): **Fail** — "CODE DRIFTED" badge 3.39:1 (white on amber). Body/nav pass.
- 1.4.1 Use of Color: **Pass** — warnings/gap-markers carry meaning in *text* ("none", "Coverage denominator is incomplete…"), not color. (The unstyled `.banner--warn`/`.warn` is a visual **hierarchy/emphasis** weakness — Major — not a 1.4.1 violation.)
- 1.4.10 Reflow (320px): **Fail** — Review page overflows on long unbreakable identifiers in `<code>`/`<em>` (no `overflow-wrap`); scrollW 375 > 320. (Corpus's overflow is the data table, which 1.4.10 exempts as 2-D content — wrap it in a horizontal-scroll container rather than treating the table as the violation.)
- 1.4.11 Non-text Contrast: **Fail** — control/table borders `#d9d9d9` = 1.41:1.
- 2.1.1 Keyboard: **Pass** — all actions are native controls.
- 2.4.7 Focus Visible: **Pass** (UA default outline present).
- 2.4.11 Focus Not Obscured: **Pass** — no sticky overlays.
- 2.5.7 Dragging Movements: **Pass (N/A)** — no drag interactions.
- 2.5.8 Target Size (24px): **Fail** — action buttons 21px tall.
- 3.2.6 Consistent Help: **Pass (N/A)** — no help mechanism.
- 3.3.7 Redundant Entry: **Pass** — edit-conflict preserves prior entry.
- 3.3.8 Accessible Authentication: **Pass (N/A)** — no auth challenge.
- 4.1.2 Name/Role/Value: **Pass** — strong: per-item unique `aria-label`s, `aria-describedby`
  linking the drift note to its accept button, `role=status`/`role=alert`/`role=note`, labelled
  `fieldset`/`legend`, visible `<label for>` on search.

### AI Trust Stack (the review queue is a human-in-the-loop AI-proposal surface)
- **Legibility: Partial** — `agent:lacuna` provenance is shown per link, so the operator knows
  it's an agent proposal; but there's no prominent framing that the queue *is* AI proposals, and
  the DRAFT/LINK provenance badges are unstyled text.
- **Grounding: Strong for drift, weak otherwise** — the drift note ("Code changed since this link
  was proposed — verify before accepting") is exactly right. But a *non-drifted* link offers no
  drill-down to the code span / diff / rationale — you accept on a file path + a bare confidence
  number.
- **Steering: Adequate** — accept / reject-with-reason / edit-draft cover the needed moves.
- **Refusal & Recovery: Strong** — reject-requires-reason and edit-conflict recovery.
- **Reversibility: Strong** — preview-then-confirm on both irreversible paths (approve, accept-drifted).
- **Calibration: Weak (richest gap)** — confidence is shown as raw `conf 0.82` / `conf 0.55`
  with no scale, no threshold, no model attribution, and no visual link to risk. An operator can't
  tell whether 0.55 is "risky." Encode confidence visually (bar / band / low-med-high) and state
  what the number means.

---

## Platform-Specific Notes
- **Mobile (390px):** content reflows acceptably; nav wraps the operator label. Buttons remain 21px
  (below the 44px touch target guidance).
- **Reflow (320px):** Review overflow is driven by long unbreakable identifiers in `<code>`/`<em>`
  (`src/plainweave/audit.py —fragile_satisfies→ REQ-SEEDROOT-0001@v1`) — add `overflow-wrap:anywhere`.
  Corpus overflow is the data table's min-content width.
- **Full-page error is naked:** `error.html` does **not** `{% extends "base.html" %}` — it returns a
  bare `<main>` fragment. A `GET /req/<bad-id>` (or any `PlainweaveError` on a full page) renders with
  the browser's default serif font, **no stylesheet, no nav, no skip-link, no `<html lang>`** — the
  operator is stranded with a single "Back to corpus" link. **Major.** Render it inside the
  `base.html` chrome on non-HTMX requests — via the `HX-Request` branch, not a blind `extends`
  (the same handler serves HTMX error swaps; see Recommendation #2).

---

## Priority Recommendations

### Critical (Fix Before Launch)
- None.

### Major (Fix Soon)
1. **Adopt the existing Weft design system instead of inventing CSS.** `site/vendor/site-kit`
   ships a framework-free token layer (`tokens/*.css`) and component CSS (`components/components.css`:
   `.wf-banner--warn`, `.wf-badge--warn/--danger/--info`, `.wf-fresh`, `.wf-enr`) that map onto the
   operator UI's unstyled classes (banner, type-badge, drift/freshness, primary button) and onto its
   concepts (`SeiTag`, `FreshnessMeter`, `EnrichmentChip`). Pull in the token CSS + the relevant
   `.wf-*` rules (no React needed) and align the operator classes to that vocabulary. This resolves
   ~half the findings *and* closes the **brand drift** (the tool's `#c47b1a` amber / pure-white theme
   vs the suite's `--brass`/`--linen` linen theme); site-kit's `--warn`/`--brass-700` pairings are
   already designed to pass contrast, fixing the drift-badge fail for free. Confirm whether the MVP
   deliberately scoped a standalone stylesheet (`docs/superpowers/plans/2026-06-25-plainweave-webux-mvp.md`
   inlines `app.css`) before committing to the adoption.
2. **Fix the naked full-page error** — `error.html` must render with the `base.html` chrome on
   non-HTMX requests. Do **not** simply add `{% extends "base.html" %}`: `on_error` returns this
   partial for HTMX errors too, so blindly extending it would inject a full document into an HTMX
   swap. Use the same `HX-Request` branch the corpus route already uses (full page when not
   `HX-Request`, fragment otherwise).
3. **Fix the KPI hierarchy** — the Intent coverage number is the product's headline; make it the
   most prominent element.
4. **Card-style the review queue** and give the **primary action** visual primacy; reserve amber for drift.
5. **Target size** — action buttons to ≥ 24px (44px for touch).
6. **Reflow** — `overflow-wrap:anywhere` on code/identifier labels; let the corpus table scroll in a wrapper.
7. **Drift-badge contrast** — darken the amber or flip to dark text.
8. **Global pending badge** — populate `pending_count` on every page.
9. **AI calibration** — encode link confidence visually and explain the scale; add a visible success toast.

### Minor (Improvement Opportunities)
1. De-emphasise secondary text (`.muted`); color `.warn`.
2. Darken faint `#d9d9d9` borders to ≥ 3:1.
3. Render Intent orphans as linked titles, not raw IDs; hide zero-count sections.
4. Add a "New requirement" affordance to Corpus.
5. Goals "Statement" → textarea (match requirement form).
6. Define an explicit `:focus-visible` ring.

## Testing Recommendations
- [x] Keyboard-only navigation (tab order, focus advance) — verified
- [x] Programmatic focus-ring / target-size / reflow / contrast audit — verified
- [ ] Screen reader pass (NVDA/VoiceOver) — confirm live-region announcements land as designed
- [ ] Forced-colors / high-contrast mode (Windows) — the all-default-button styling is a risk
- [ ] Real touch device — 21px targets will be hard to hit
