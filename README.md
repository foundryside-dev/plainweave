# Charter

Charter is the fifth Loom member: a local-first requirements and verification
authority for agentic development.

Charter records what must be true, links those obligations to code and work,
tracks how they are verified, and tells agents what requirements a change
touches. It is designed to sit beside the other Loom tools without taking over
their authority:

- Clarion owns code identity and structure.
- Filigree owns work state and issue lifecycle.
- Wardline owns trust-boundary analysis.
- Legis owns git, CI, governance, and attestations.
- Charter owns requirements, traceability, baselines, and verification evidence.

The authoritative federation roster, axiom, and per-member authority split live
in the Loom hub at `~/loom/doctrine.md`; the summary above mirrors it for
convenience. The hub's ruling is that the roster is **five realized members**
(Clarion, Filigree, Wardline, Legis, Charter).

Shuttle is **not** a committed sixth member. It is a roadmap thought-bubble — a
named but undesigned change-execution gap with no repo, displaceable by any
better idea (Charter was exactly such an idea). See `~/loom/members/shuttle.md`.

## Status

The local core is implemented. Supported runtime behavior includes:

```bash
charter --version
charter init
charter doctor
charter req add|edit|show|search|approve|supersede|deprecate|reject
charter criterion add|list
charter trace propose|accept|reject|list
charter baseline create|show|list|diff
charter verify method add
charter verify evidence record
charter verify status
charter status requirement|unverified|stale
charter dossier REQ_ID
charter-mcp
```

`charter-mcp` exposes the P0 read-only agentic surface for local project
context, requirement search/show, dossiers, trace listing, baselines, baseline
diffs, and verification status. Mutation, live federation calls, impact
analysis, durable gaps, import/export, and release-readiness verdicts remain
deferred.

## Concept

The current product concept lives in [docs/concept.md](docs/concept.md).

## Development

Charter uses [uv](https://docs.astral.sh/uv/), `hatchling`, `ruff`, `mypy`, and
`pytest`.

```bash
uv sync --group dev
make ci
```

The runtime package depends on the official Python MCP SDK for `charter-mcp`.
