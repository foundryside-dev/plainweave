# 03 — Architecture Diagrams (C4)

*Mermaid C4-style diagrams. Solid arrows = direct import/call dependency
(import-confirmed). Dashed = planned/unbuilt (reframe). Diagrams reflect the
**as-built** structure at HEAD `72e8df2`; reframe targets are marked.*

## C1 — System Context

Plainweave in the Weft federation. Plainweave is advisory/enrich-only; siblings
are optional (absent → honest degradation).

```mermaid
graph TB
    agent["AI Agent / Developer"]
    subgraph weft["Weft federation"]
        pw["<b>Plainweave</b><br/>intent graph + reasoning reads<br/>(permission for code to exist)"]
        loom["Loomweave<br/>entity catalog, SEI identity,<br/>rename feed, semantic search"]
        legis["Legis<br/>git/CI boundary, graded<br/>enforcement, audit trail"]
    end
    db[("SQLite<br/>.plainweave/ (repo-local)")]

    agent -->|"CLI / MCP stdio"| pw
    pw --> db
    pw -.->|"consumes SEIs, rename feed,<br/>semantic hint (PLANNED)"| loom
    pw -.->|"surfaces coverage facts at<br/>git/CI boundary (PLANNED)"| legis

    classDef planned stroke-dasharray:5 5,fill:#f5f5f5;
    class loom,legis planned;
```

> Today Plainweave is self-contained (one runtime dep: the MCP SDK; local
> SQLite). The Loomweave/Legis seams are *additive, hub-blessed, prove-the-need*
> and not yet wired.

## C2 — Container / Module view

The six subsystems and their import-confirmed dependencies.

```mermaid
graph TD
    cli["<b>CLI</b><br/>cli.py, cli_commands.py, __main__.py<br/>+ homeless _*_dict serializers"]
    mcp["<b>MCP Read Surface</b><br/>mcp_surface.py, mcp_server.py"]
    env["Envelopes<br/>envelopes.py<br/>(output contract)"]
    svc["<b>Service Core</b><br/>service.py — PlainweaveService<br/>(2136 LOC god-object)"]
    store["Persistence / Store<br/>store.py (SQLite, migrate, event log)"]
    model["Domain Model & Errors<br/>models.py, errors.py, paths.py"]
    db[("SQLite")]

    subgraph reframe["Reframe target — STUBBED (NotImplementedError)"]
        ig["Intent Graph<br/>intent_graph.py<br/>orphans/trace/corpus"]
        bind["Bindings<br/>bindings.py<br/>ADR-029 SEI binding"]
    end

    cli --> svc
    cli --> store
    cli --> env
    cli --> model
    mcp --> svc
    mcp --> env
    mcp --> model
    mcp -->|"imports PRIVATE _*_dict<br/>(smell)"| cli
    svc --> store
    svc --> model
    env --> model
    store --> db

    ig -.->|"PLANNED: walk over<br/>trace_links + goal nodes"| svc
    bind -.->|"PLANNED: ADR-029 assoc<br/>+ Loomweave SEI"| svc

    classDef smell stroke:#c00,stroke-width:2px;
    classDef god stroke:#e69500,stroke-width:3px;
    classDef planned stroke-dasharray:5 5,fill:#f5f5f5;
    class svc god;
    class ig,bind planned;
```

**Read this diagram for two things:**
1. **`mcp ──► cli`** (red): the MCP surface depends on *private* serializers in
   the CLI module — a layering inversion. Both front doors should depend on a
   neutral `serializers`/`views` module instead.
2. **`svc` (god-object, orange):** every front door funnels through one
   2136-LOC class, and both reframe stubs point back at it — the intent graph is
   on a trajectory to be absorbed into the god-object unless it is decomposed
   first.

## C3 — Component view: the as-built request path

How a single operation flows (e.g. `create_requirement` / a requirement read).

```mermaid
graph LR
    subgraph front["Front doors"]
        a1["plainweave CLI<br/>cli.main → register_commands"]
        a2["plainweave-mcp<br/>mcp_server.main → create_mcp_server"]
    end
    h["cli_commands.handle_*<br/>/ PlainweaveMcpSurface.plainweave_*"]
    ser["_*_dict serializers<br/>(in cli_commands)"]
    s["PlainweaveService.<method>"]
    ev["_record_event +<br/>_idempotent_* (event log)"]
    c["store.connect / migrate"]
    db[("SQLite tables:<br/>requirements, versions, trace_links,<br/>baselines, verification_*, events")]
    out["JSON envelope<br/>schema/ok/data/warnings/meta"]

    a1 --> h
    a2 --> h
    h --> s
    s --> ev
    s --> c
    c --> db
    s --> ser
    ser --> out
    h --> out
```

## C4 — Domain model (intent ladder: built vs. target)

```mermaid
graph BT
    code["code SEI (leaf)<br/>loomweave:eid:..."]
    reqv["RequirementVersion / Record<br/>(+ Draft, AcceptanceCriterion)"]
    goal["Strategic Goal node<br/>(IntentLevel.GOAL)"]

    code -->|"satisfies<br/>(BUILT: trace_links<br/>loomweave_entity→requirement_version)"| reqv
    reqv -.->|"justified by<br/>(TARGET: no goal kind /<br/>no req→goal triple yet)"| goal

    subgraph built["Built today — requirements/trace/verification core"]
        reqv
        v["Verification: Method, Evidence, Status"]
        b["Baseline (+Member, +Diff)"]
        d["RequirementDossier (+ Dossier* sections)"]
        reqv --- v
        reqv --- b
        reqv --- d
    end

    classDef target stroke-dasharray:5 5,fill:#f5f5f5;
    class goal target;
```

**Key:** the *lower* half of the intent ladder (`code → requirement`) is modeled
today in the generic `trace_links` edge table. The *upper* half
(`requirement → goal`) — the reframe's defining edge — has **no node kind and no
relation triple** in the as-built validation set (`_validate_trace_relation`,
`service.py:1877`). The storage substrate is reusable; the graph behavior is
net-new.

## Legend

| Marker | Meaning |
| --- | --- |
| solid arrow | import/call dependency, confirmed in source |
| dashed arrow / grey box | planned (reframe), not implemented |
| red edge | architectural smell (layering inversion) |
| orange node | god-object / dominant risk |
