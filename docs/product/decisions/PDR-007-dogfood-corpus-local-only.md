# PDR-007: Keep the Self-Dogfood Corpus Local-Only

Date: 2026-06-24   Status: accepted   Author: agent:claude-product-owner   Owner sign-off: n/a (within grant)
Related: PDR-005, vision.md (guardrail: agent bindings are not accepted human truth)

## Context

The self-dogfood (PDR-005) wrote a real seed corpus — 1 goal, 2 requirements, 2 SEI
bindings — to `.plainweave/plainweave.db`, a binary SQLite store that was not
gitignored (unlike `.weft/`, the established local-store precedent).

## Options considered

1. Commit the store — the corpus travels with the repo, but it commits a churning
   binary blob and the corpus is agent-authored, not human-ratified.
2. Gitignore the store; keep the corpus reproducible via the documented dogfood
   procedure — matches the `.weft/` precedent and the local-first doctrine; the corpus
   must be regenerated.

## The call

Option 2. Added `.plainweave/` to `.gitignore`.

## Rationale

The store is local, regenerable proving state, and the seed corpus is agent-authored.
Committing a binary as if it were ratified truth conflicts with the guardrail that
agent-created bindings are not accepted human truth. Local-only matches `.weft/`.

## Reversal trigger

Revisit if the dogfood corpus needs to be a shared, reviewable artifact — at which
point export a *text* fixture (e.g. a JSON corpus dump for contract tests), not the
binary DB.
