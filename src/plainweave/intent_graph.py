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

The precursor requirements / trace / verification core
(:mod:`plainweave.service`, :mod:`plainweave.store`) is the foundation these
reads are built over. Service methods provide the database-backed read model;
``IntentGraphReads`` is a small injectable facade for tests and adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


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


class _OrphansReader(Protocol):
    def __call__(self, level: IntentLevel) -> list[IntentNode]: ...


class _TraceReader(Protocol):
    def __call__(self, node: IntentNode) -> Trace: ...


class _CorpusReader(Protocol):
    def __call__(self) -> list[CorpusEntry]: ...


class IntentGraphReads:
    """Target read surface over the intent graph (design §6).

    Built for unanticipated agent use (prescribe-nothing): three composable
    primitives, not canned reports. Consolidation is agent-driven — these serve
    the readable substrate, not an automated dedup verdict.
    """

    def __init__(
        self,
        *,
        orphans_reader: _OrphansReader | None = None,
        trace_reader: _TraceReader | None = None,
        corpus_reader: _CorpusReader | None = None,
    ) -> None:
        self._orphans_reader = orphans_reader
        self._trace_reader = trace_reader
        self._corpus_reader = corpus_reader

    def orphans(self, level: IntentLevel) -> list[IntentNode]:
        """Nodes at ``level`` with no upward edge — the reviewable
        "why does this exist?" set at that altitude.
        """
        if self._orphans_reader is None:
            return []
        return self._orphans_reader(level)

    def trace(self, node: IntentNode) -> Trace:
        """Walk up to goals and down to code for ``node``
        ("what justifies this code"; "what satisfies this requirement").

        """
        if self._trace_reader is None:
            return Trace(node, (), ())
        return self._trace_reader(node)

    def corpus(self) -> list[CorpusEntry]:
        """The readable dump of requirements with their code- and goal-links —
        the artifact an agent or human reads to curate the intent corpus.

        """
        if self._corpus_reader is None:
            return []
        return self._corpus_reader()
