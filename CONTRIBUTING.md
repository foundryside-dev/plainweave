# Contributing to Plainweave

Plainweave is the Weft federation member that holds the team's code-grounded
intent — the local-first traceability graph binding code entities (Loomweave
SEIs) to requirements and strategic goals. As of 1.0.0 it is stable
(Production/Stable on PyPI, versioned JSON envelopes, a green CI gate). Keep
changes small, tested, and aligned with the authority boundary in the canonical
design,
[`docs/design/2026-06-18-plainweave-permission-to-exist.md`](docs/design/2026-06-18-plainweave-permission-to-exist.md).

## Development setup

Plainweave uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/foundryside-dev/plainweave
cd plainweave
uv sync --group dev
```

This installs Plainweave in a uv-managed virtual environment with `ruff`, `mypy`,
`pytest`, and coverage tooling.

## Code style

- Linter and formatter: `ruff` with line length 120.
- Type checker: `mypy` in strict mode.
- Tests: `pytest`.
- Runtime base: the only approved runtime dependency is `mcp>=1.2.0` (needed by
  `plainweave-mcp`). Do not add further runtime dependencies without an explicit
  design decision.

Before committing:

```bash
make lint
make typecheck
make test
```

Run the full local gate with:

```bash
make ci
```

## Conventions

- Use TDD for new behavior.
- Keep PRs focused: one logical change per PR.
- New behavior needs tests.
- Agent-facing commands must support structured output once domain commands are
  introduced.
- Do not move authority from Loomweave, Filigree, Wardline, Legis, or future
  Shuttle into Plainweave.

## Commit messages

Use Conventional Commits:

```text
<type>: <short description>
```

Common types: `feat`, `fix`, `docs`, `test`, `ci`, `build`, `refactor`,
`style`, and `chore`.

## License

Contributions are accepted under the project license.
