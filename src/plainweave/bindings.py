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

The ``loomweave:eid:`` SEI scheme is **FROZEN** — Plainweave consumes it, never
mints or reinterprets it. Persistence lives in :mod:`plainweave.service`; this
module holds the public value object and small drift helpers used by CLI/MCP
serializers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SeiBinding:
    """A code-leaf ↔ requirement binding, recorded via the ADR-029
    entity-association contract.

    ``sei`` is an opaque ``loomweave:eid:...`` identifier (frozen scheme;
    consumed, never minted). ``content_hash_at_attach`` is stored so the consumer
    read path can detect drift between the bound entity's content and its content
    when the binding was made (ADR-029).
    """

    entity_id: str
    entity_kind: str
    requirement_id: str
    content_hash_at_attach: str | None
    drift_status: str
    freshness: str
    bound_by: str
    bound_at: str
    provenance: dict[str, Any]

    @property
    def sei(self) -> str:
        """Backward-compatible alias for the opaque Loomweave entity ID."""
        return self.entity_id


def bind_sei_to_requirement(
    sei: str,
    requirement_id: str,
    *,
    bound_by: str,
    content_hash_at_attach: str | None = None,
    entity_kind: str = "loomweave_entity",
    bound_at: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> SeiBinding:
    """Construct a SEI binding value object for the ADR-029 contract.

    The service method with the same semantic name persists this object. This
    module-level helper stays storage-free so callers can validate envelope
    shapes without opening a project database.
    """
    if not sei:
        raise ValueError("sei is required")
    if not requirement_id:
        raise ValueError("requirement_id is required")
    if not bound_by:
        raise ValueError("bound_by is required")
    return SeiBinding(
        entity_id=sei,
        entity_kind=entity_kind,
        requirement_id=requirement_id,
        content_hash_at_attach=content_hash_at_attach,
        drift_status="unknown" if content_hash_at_attach is None else "attached",
        freshness="unknown" if content_hash_at_attach is None else "current",
        bound_by=bound_by,
        bound_at=bound_at or datetime.now(UTC).isoformat(),
        provenance=dict(provenance or {}),
    )


def is_drifted(binding: SeiBinding, current_content_hash: str) -> bool:
    """Whether the bound entity's content has changed since the binding was made
    (``content_hash_at_attach`` vs. ``current_content_hash``; ADR-029 drift).
    """

    if binding.content_hash_at_attach is None:
        return False
    return binding.content_hash_at_attach != current_content_hash
