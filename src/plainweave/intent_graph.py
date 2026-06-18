"""Plainweave intent graph — the code-up traceability reads.

The reframe (``docs/design/2026-06-18-plainweave-permission-to-exist.md``, §3, §6)
models intent as a directed graph::

    strategic goal ──▲── requirement ──▲── code SEI (leaf)
       (root intent)        (obligation)        (the thing that exists)

An edge means *"justified by / satisfies."* A node with **no upward edge** is the
reviewable question at its altitude: a code leaf with no requirement is
*"why does this code exist?"*; a requirement with no goal is *"what am I doing
here?"*. The three primitives below are general graph queries — the orphan-code
report and the duplicate-requirements report are just two of them.

IMPLEMENTATION PENDING — see the ``.filigree`` backlog ("intent graph: goal node
type + goal↔requirement edge" and "three read primitives"). This module defines
the *target interface only*. The precursor requirements / trace / verification
core (:mod:`plainweave.service`, :mod:`plainweave.store`) is the foundation these
reads will be built over; nothing here is wired yet. See
``docs/MODULE-MAP.md`` for the carry-forward audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_PENDING = (
    "Plainweave intent-graph reads are not implemented yet. This is a target "
    "interface stub from the repo standup — see docs/MODULE-MAP.md and the "
    ".filigree backlog."
)


class IntentLevel(StrEnum):
    """An altitude in the intent graph. Altitudes are just node types; the graph
    does not fix the number of levels (design §3)."""

    CODE = "code"
    """A code entity — a Loomweave SEI (module or public surface). A graph leaf."""

    REQUIREMENT = "requirement"
    """An obligation. Trivially mintable (shells welcome); value is the corpus
    being visible and queryable, then consolidated."""

    GOAL = "goal"
    """A strategic goal — root intent the requirements ladder up to."""


@dataclass(frozen=True)
class IntentNode:
    """A node in the intent graph, identified within its altitude.

    For ``CODE`` nodes, ``node_id`` is a Loomweave SEI (``loomweave:eid:...``), so
    the node survives rename/move (design §3)."""

    level: IntentLevel
    node_id: str


@dataclass(frozen=True)
class Trace:
    """The justification neighbourhood of a node: upward toward goals and
    downward toward code (design §6, ``trace(node)``)."""

    node: IntentNode
    up: tuple[IntentNode, ...]
    """Nodes this node is justified by, walking toward goals."""
    down: tuple[IntentNode, ...]
    """Nodes justified by this node, walking toward code."""


@dataclass(frozen=True)
class CorpusEntry:
    """One requirement with its code- and goal-links — a row of the readable
    corpus a curator reads to spot *"these three are the same"* (design §6)."""

    requirement: IntentNode
    goals: tuple[IntentNode, ...]
    code: tuple[IntentNode, ...]


class IntentGraphReads:
    """Target read surface over the intent graph (design §6).

    Built for unanticipated agent use (prescribe-nothing): three composable
    primitives, not canned reports. Consolidation is agent-driven — these serve
    the readable substrate, not an automated dedup verdict.
    """

    def orphans(self, level: IntentLevel) -> list[IntentNode]:
        """Nodes at ``level`` with no upward edge — the reviewable
        "why does this exist?" set at that altitude.

        IMPLEMENTATION PENDING.
        """
        raise NotImplementedError(_PENDING)

    def trace(self, node: IntentNode) -> Trace:
        """Walk up to goals and down to code for ``node``
        ("what justifies this code"; "what satisfies this requirement").

        IMPLEMENTATION PENDING.
        """
        raise NotImplementedError(_PENDING)

    def corpus(self) -> list[CorpusEntry]:
        """The readable dump of requirements with their code- and goal-links —
        the artifact an agent or human reads to curate the intent corpus.

        IMPLEMENTATION PENDING.
        """
        raise NotImplementedError(_PENDING)
