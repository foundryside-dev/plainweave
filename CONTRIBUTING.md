# Contributing to Charter

Charter is a local-first requirements and verification authority for the Loom
suite. It is early-stage; keep changes small, tested, and aligned with the
authority boundary in `docs/concept.md`.

## Development setup

Charter uses [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/foundryside-dev/charter
cd charter
uv sync --group dev
```

This installs Charter in a uv-managed virtual environment with `ruff`, `mypy`,
`pytest`, and coverage tooling.

## Code style

- Linter and formatter: `ruff` with line length 120.
- Type checker: `mypy` in strict mode.
- Tests: `pytest`.
- Runtime base: keep required dependencies empty unless the approved design says
  otherwise.

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
- Do not move authority from Clarion, Filigree, Wardline, Legis, or future
  Shuttle into Charter.

## Commit messages

Use Conventional Commits:

```text
<type>: <short description>
```

Common types: `feat`, `fix`, `docs`, `test`, `ci`, `build`, `refactor`,
`style`, and `chore`.

## License

Contributions are accepted under the project license.
