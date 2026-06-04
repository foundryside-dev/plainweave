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

This repository is in scaffold state. The only supported runtime behavior is:

```bash
charter --version
python -m charter --version
```

Domain commands such as `charter init`, requirement storage, MCP tools, and
federation adapters are intentionally deferred until the v0.1 product design and
implementation plan are approved.

## Concept

The current product concept lives in [docs/concept.md](docs/concept.md).

## Development

Charter uses [uv](https://docs.astral.sh/uv/), `hatchling`, `ruff`, `mypy`, and
`pytest`.

```bash
uv sync --group dev
make ci
```

The base package has no required runtime dependencies.
