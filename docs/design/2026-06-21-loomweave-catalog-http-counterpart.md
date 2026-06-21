# 2026-06-21 Counterpart Ticket: Loomweave Catalog HTTP Surface

## Owner

Loomweave hub/member owner.

## Plainweave Context

Plainweave now has a local, additive Loomweave adapter that reads
`.weft/loomweave/loomweave.db` for default-altitude catalog enumeration and uses
Loomweave identity reads when available to resolve trace links to alive SEIs.
This intentionally keeps Plainweave a consumer: it stores Loomweave-emitted SEI,
locator, content hash, source, tag, public-signal, lineage, and freshness
snapshots, but it never derives or mints identity.

## Counterpart Request

Add a Loomweave-owned HTTP catalog endpoint that returns the same default
altitude Plainweave needs:

- all module entities;
- entities explicitly tagged as public/root surfaces;
- SEI, locator, kind, tags, source span, content hash, briefing-blocked state,
  lineage status, freshness, and degraded/unknown visibility metadata;
- paginated responses with explicit adapter/source status.

## Boundary

This is not a blocker for the Plainweave-side adapter. Until Loomweave owns that
HTTP catalog surface, Plainweave will continue to use read-only SQLite catalog
joins and fail closed for unresolved `loomweave_entity` trace writes.
