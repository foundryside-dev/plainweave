You are working in /home/john/charter on Charter, the fifth Loom federation tool.

Goal:
Implement the approved Charter v0.1 local-core plan end to end, using repeated implement/review/verify cycles until the plan is fully delivered, you stop making meaningful progress, or you require operator intervention.

Source baseline:
- Latest initiation milestone commit/tag should be present:
  - commit: abfb79e docs: establish Charter initiation milestone
  - tag: initiation-milestone
- Treat current worktree and Filigree state as authoritative; inspect before acting.

Required skills/plugins before work:
- superpowers:using-superpowers
- superpowers:using-git-worktrees
- superpowers:executing-plans or superpowers:subagent-driven-development if available
- superpowers:test-driven-development
- superpowers:systematic-debugging for failures
- superpowers:requesting-code-review after each implementation step or small batch
- superpowers:verification-before-completion before any completion claim
- axiom-python-engineering:using-python-engineering
- axiom-sdlc-engineering:quality-assurance
- using-mcp-engineering for JSON/MCP contract discipline
- filigree-workflow for tracker coordination

Primary plans:
- docs/superpowers/plans/2026-06-04-charter-v0.1-local-core.md
- docs/superpowers/plans/2026-06-04-charter-v0.1-work-package-execution-guide.md
- docs/superpowers/specs/2026-06-04-charter-contract-fixture-plan.md
- docs/superpowers/specs/2026-06-04-charter-v0.1-quality-gates.md
- docs/superpowers/specs/2026-06-04-charter-v0.1-traceability-matrix.md
- docs/architecture/decisions/ADR-001-charter-authority-boundary.md through ADR-006-legis-preflight-fact-envelope.md

Before product code:
1. Run `git status --short --branch`, `git log --oneline --decorate -5`, and `filigree session-context`.
2. Verify whether ADR-001 through ADR-004 and Filigree issue `charter-76a416ec15` are approved/accepted.
3. If approval is not explicit in current state, stop and ask the operator whether this prompt constitutes approval to begin v0.1 product implementation. Do not write product code until that is clear.

Implementation scope:
Implement only v0.1 local core:
- `charter init`
- `charter doctor`
- local `.charter/charter.db`
- requirements, drafts, immutable versions
- acceptance criteria
- manual/proposed trace links
- append-only v0.1 events
- JSON CLI envelopes
- CLI commands from the execution guide
- unit, contract, state-machine, and CLI tests

Do not implement:
- verification records
- baselines
- impact engine
- MCP server or MCP mutation tools
- live Clarion, Filigree, Wardline, or Legis integrations
- import/export
- context.md generation
- LLM assistance

Execution rules:
- Use a dedicated worktree unless the operator explicitly says to work directly on main.
- Follow the plan task by task.
- Use TDD strictly: write failing tests first, verify RED, implement minimal GREEN, refactor only after GREEN.
- Commit after each completed implementation step if tests pass.
- After each step or small batch, run a review cycle. Fix Critical/Important findings before continuing.
- Update Filigree issues as work starts/completes, using comments for handoff context.
- Continue autonomously through the plan while making progress.

Stop conditions:
Stop and request operator intervention if:
- approval is missing or ambiguous;
- plan instructions conflict with ADRs;
- a required dependency/tool is unavailable;
- the same blocker repeats after real debugging effort;
- tests fail repeatedly and systematic debugging cannot isolate a credible fix;
- implementing the next step would require out-of-scope v0.2+ behavior.

Required final gates:
- `make lint`
- `make typecheck`
- `make test`
- `uv run pytest tests/contracts -q`
- `uv run pytest tests/state -q`
- `make ci`
- scope audit:
  `rg -n "verification|baseline|impact|clarion|filigree|wardline|legis|mcp" src tests`
  Results must be only inert contracts, help/deferred markers, or explicitly approved references.

Completion response:
When finished, report:
- commits created;
- Filigree issues completed or still open;
- verification commands and results;
- any review findings addressed;
- any remaining risks or deferred items.

Do not mark the implementation complete unless every v0.1 work-package item is delivered and verified against the plans above.