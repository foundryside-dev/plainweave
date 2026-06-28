# 03 — Architecture Diagrams (C4-style)

**Subject:** Plainweave · **Live tree:** HEAD `8258f76` · **Date:** 2026-06-28
Diagrams encode the Loomweave-verified dependency map
(`temp/dependency-reconciliation.md`). Mermaid `flowchart`/`sequenceDiagram`
syntax (portable rendering); the C4 level is noted per diagram.

---

## 1. System Context (C4 L1) — who uses Plainweave and what it touches

```mermaid
flowchart TB
    agent["AI coding agent<br/>(authoring / reasoning)"]
    operator["Human operator<br/>(single, local)"]

    subgraph PW["Plainweave — code-grounded intent corpus"]
        direction TB
        core["Intent graph + reads<br/>(advisory, enrich-only)"]
    end

    db[("SQLite store<br/>.plainweave/plainweave.db")]
    lw["Loomweave<br/>(catalog / SEI / rename / semantic)"]
    wl["Wardline<br/>(trust-boundary findings)"]
    legis["Legis<br/>(git/CI boundary + teeth + audit)"]
    warp["Warpline<br/>(temporal change-impact)"]

    agent -->|"read-only MCP tools"| PW
    operator -->|"CLI + web console (writes)"| PW
    PW -->|"owns / persists"| db
    PW -->|"reads catalog (ro SQLite) + opt. HTTP identity"| lw
    PW -->|"reads .wardline/*-findings.jsonl"| wl
    PW -. "coverage facts ride out at git/CI<br/>(advisory; teeth dialed via Legis cells)" .-> legis
    PW -. "PRODUCES requirements_enrichment.v1<br/>for Warpline's reserved slot" .-> warp

    classDef ext fill:#eef,stroke:#88a;
    class lw,wl,legis,warp ext;
```

**Reading:** Plainweave is a *thin* member. It owns the intent graph + reads and
its own SQLite store; it **reads** Loomweave and Wardline local artifacts
(enrich-only), and **produces** facts that Legis (at the git/CI boundary) and
Warpline (its enrichment slot) consume. Dotted edges are enrich/produce seams
that never gate.

---

## 2. Container (C4 L2) — the deployable pieces

```mermaid
flowchart TB
    agent["AI agent"]
    operator["Human operator"]

    subgraph deploy["plainweave package (one wheel)"]
        direction TB
        cli["CLI<br/>plainweave (console script)<br/>cli.py + cli_commands.py"]
        mcp["MCP server (READ-ONLY)<br/>plainweave-mcp<br/>mcp_server.py + mcp_surface.py"]
        web["Web console (WRITE surface, [web] extra)<br/>Starlette + HTMX<br/>web/"]
        svc["PlainweaveService<br/>(domain + data-access + intent engine)<br/>service.py 3027 LOC"]
        ig["Intent Graph types<br/>intent_graph.py"]
        store["Persistence<br/>store.py (connect-per-call)"]
        adapters["Sibling adapters<br/>loomweave_adapter / wardline_adapter"]
        contract["Response contract<br/>envelopes.py / errors.py"]
    end

    db[("SQLite<br/>.plainweave/")]
    lwdb[("Loomweave DB<br/>.weft/loomweave/ (ro)")]
    wljson[/".wardline/*-findings.jsonl"/]

    agent --> mcp
    operator --> cli
    operator --> web
    cli --> svc
    mcp --> svc
    web --> svc
    cli -. "init/inspect only (layering exception)" .-> store
    mcp -. "serializers + inspect_project (surface↔surface)" .-> cli

    svc --> store
    svc --> ig
    svc --> adapters
    svc --> contract
    cli --> contract
    mcp --> contract
    web --> contract
    store --> db
    adapters --> lwdb
    adapters --> wljson

    classDef write fill:#fee,stroke:#c66;
    classDef read fill:#efe,stroke:#6a6;
    class web write;
    class mcp read;
```

**Reading:** Three surfaces, one service, one store. The MCP server is read-only;
the **web console is the only write surface**. Two dotted edges are the
architectural exceptions: the CLI hits the store directly for `init`/`inspect`,
and the MCP surface reaches back into `cli_commands` for serializers +
`inspect_project` (a function-local coupling — **no module-load cycle**).

---

## 3. Component (C4 L3) — the 8 subsystems and their edges

```mermaid
flowchart LR
    subgraph surfaces["Delivery surfaces"]
        CLI["CLI Surface<br/>16 cmds / 38 handlers"]
        MCP["MCP Surface<br/>19 tools / 15 resources"]
        WEB["Web UI<br/>22 routes (15 GET / 7 POST)"]
    end

    subgraph coredom["Core domain"]
        SVC["Domain Service Core<br/>PlainweaveService (god object)"]
        IG["Intent Graph<br/>(types/contract; logic in service)"]
    end

    subgraph infra["Infrastructure / cross-cutting"]
        PERS["Persistence<br/>store.connect (fan-in 44)"]
        ADP["Sibling-Tool Adapters<br/>Loomweave + Wardline"]
        RC["Response Contract<br/>envelopes + ErrorCode(10)"]
    end

    CLI --> SVC
    MCP --> SVC
    WEB --> SVC
    MCP -. "DTO/serializers + inspect_project" .-> CLI
    CLI -. "init/inspect" .-> PERS

    SVC --> PERS
    SVC --> IG
    SVC --> ADP
    SVC --> RC
    CLI --> RC
    MCP --> RC
    WEB --> RC
    SVC -. "produces requirements_enrichment.v1" .-> MCP

    classDef god fill:#fdd,stroke:#c44,stroke-width:2px;
    class SVC god;
```

**Reading:** Every surface depends on the Domain Service Core and the Response
Contract; the core fans out to Persistence, Intent Graph, and the Adapters. The
red node is the 3027-LOC god object that is simultaneously use-case tier,
data-access tier, and intent-graph engine — the dominant refactor target.

---

## 4. The intent graph data model (the product's reason to exist)

```mermaid
flowchart BT
    code["Code SEI (leaf)<br/>loomweave:eid:… (rename-stable)"]
    req["Requirement (obligation)<br/>draft → approved → superseded/deprecated"]
    goal["Strategic Goal (root intent)"]

    code -->|"bind_sei_to_requirement<br/>(ADR-029, content_hash_at_attach)"| req
    req -->|"link_goal_to_requirement"| goal

    note1["orphans(level): nodes with NO upward edge at any altitude"]
    note2["coverage(): fraction of public surfaces with a LIVE upward edge<br/>(north-star; advisory, honestly qualified)"]
    note3["trace(node): up to goals, down to code"]
```

**Reading:** Edges mean *"justified by / satisfies."* A node with no upward edge
is a reviewable question. `coverage()` counts **live** justification only
(excludes deprecated); `trace()` still *explains* deprecated links — "trace
explains, coverage counts" (`service.py:1537-1539`).

---

## 5. Sequence — MCP `intent_coverage` read (illustrates connect-per-call / N+1)

```mermaid
sequenceDiagram
    actor A as AI agent
    participant M as MCP Surface (_result)
    participant S as PlainweaveService.intent_coverage
    participant LA as LoomweaveAdapter
    participant DB as SQLite (per-call connect)

    A->>M: plainweave_intent_coverage(...)
    M->>S: action(service)
    S->>LA: list_catalog()  (opens 2 ro connections to Loomweave DB)
    LA-->>S: public surfaces + coverage block (present_plugins verbatim)
    loop per catalog surface (N+1)
        S->>DB: with connect(): _goal_nodes_for_surface(sei)
        DB-->>S: live requirement ids
    end
    S-->>M: IntentCoverage (full counts, evidence bounded by max_surfaces)
    M->>M: success_envelope(schema, data)  [generated_at = now(UTC)]
    M-->>A: weft.plainweave.intent_coverage.v1 envelope
```

**Reading:** Each catalog surface opens its **own** SQLite connection inside the
loop (`service.py:1529-1550`) — the confirmed N+1 / connect-per-call pattern.
Combined with no WAL (`DELETE` journal mode), concurrent surfaces serialize on
the writer lock. Correct and honest at single-operator scale; the scaling risk
the two open P3 tracker tasks name.

---

## 6. Sequence — Web write (ratify a draft) showing the sole mutation path

```mermaid
sequenceDiagram
    actor O as Human operator
    participant W as Web /review (POST approve)
    participant CSRF as CSRF middleware
    participant CTX as RequestContext (process-singleton operator)
    participant S as PlainweaveService.approve_requirement
    participant DB as SQLite

    O->>W: POST /req/{id}/approve (_csrf, expected_version)
    W->>CSRF: double-submit-cookie check (constant-time)
    CSRF-->>W: ok (else 403)
    W->>CTX: ctx.operator.actor_id (bound at create_app, human:operator)
    W->>S: approve_requirement(id, actor, expected_version)
    S->>DB: with connect(): optimistic check + immutable version row + event
    alt version conflict
        DB-->>S: stale expected_version
        S-->>W: PlainweaveError(CONFLICT)
        W-->>O: 200 + conflict partial (preserves operator text)
    else ok
        DB-->>S: committed (+ EVT-uuid event)
        S-->>W: RequirementRecord
        W-->>O: updated card + SR live-region announcement
    end
```

**Reading:** Writes flow only through the web console → service. Identity is a
launch-time process singleton (no per-request auth); CSRF is the sole
request-level control. Optimistic concurrency surfaces `CONFLICT` as a 200 HTMX
partial that preserves the operator's text — a deliberate UX choice.
