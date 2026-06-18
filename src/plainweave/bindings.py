"""Plainweave ↔ Loomweave SEI bindings via the ADR-029 entity-association contract.

Code leaves are keyed by **Loomweave SEI** (``loomweave:eid:...``), so a binding
survives rename/move (design §3). Bindings **reuse the ADR-029 entity-association
contract** — SEI-keyed, with ``content_hash_at_attach`` drift detection, the same
pattern Filigree uses to bind issues to code — **not** a new link store
(design §4).

The write path is **authoring-time** ("speak SEI at entry," extended to intent,
design §5): when an agent creates or commits a module / public entity, Plainweave
offers an inline bind — link this SEI to a requirement (existing or a freshly
minted shell) and optionally ladder that requirement to a goal. One call,
attributed (who bound it, when). Code that skips the bind is exactly what
surfaces as an orphan via :mod:`plainweave.intent_graph`.

IMPLEMENTATION PENDING — see the ``.filigree`` backlog ("ADR-029 binding schema
for requirement↔SEI" and "authoring-time write surface"). This module defines the
*target interface only*; the ADR-029 association calls are not wired. The
``loomweave:eid:`` SEI scheme is **FROZEN** — Plainweave consumes it, never mints
or reinterprets it. See ``docs/MODULE-MAP.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

_PENDING = (
    "Plainweave SEI bindings are not implemented yet. This is a target interface "
    "stub from the repo standup — see docs/MODULE-MAP.md and the .filigree backlog."
)


@dataclass(frozen=True)
class SeiBinding:
    """A code-leaf ↔ requirement binding, recorded via the ADR-029
    entity-association contract.

    ``sei`` is an opaque ``loomweave:eid:...`` identifier (frozen scheme;
    consumed, never minted). ``content_hash_at_attach`` is stored so the consumer
    read path can detect drift between the bound entity's content and its content
    when the binding was made (ADR-029).
    """

    sei: str
    requirement_id: str
    content_hash_at_attach: str
    bound_by: str
    bound_at: str


def bind_sei_to_requirement(
    sei: str,
    requirement_id: str,
    *,
    bound_by: str,
) -> SeiBinding:
    """Bind a code SEI to a requirement at authoring time (design §5), recording
    the association through the ADR-029 contract.

    IMPLEMENTATION PENDING.
    """
    raise NotImplementedError(_PENDING)


def is_drifted(binding: SeiBinding, current_content_hash: str) -> bool:
    """Whether the bound entity's content has changed since the binding was made
    (``content_hash_at_attach`` vs. ``current_content_hash``; ADR-029 drift).

    IMPLEMENTATION PENDING.
    """
    raise NotImplementedError(_PENDING)
