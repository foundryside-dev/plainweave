from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from plainweave import __version__
from plainweave.cli_commands import (
    _baseline_dict,
    _baseline_diff_dict,
    _corpus_entry_dict,
    _current_project_key,
    _dossier_dict,
    _intent_coverage_dict,
    _intent_goal_dict,
    _intent_node_dict,
    _intent_trace_dict,
    _record_dict,
    _requirement_verification_status_dict,
    _trace_dict,
    inspect_project,
)
from plainweave.envelopes import error_envelope, success_envelope
from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.intent_graph import IntentLevel, IntentNode
from plainweave.loomweave_adapter import PUBLIC_SURFACE_TAGS, LoomweaveAdapter, LoomweaveIdentityError
from plainweave.models import TraceLink, TraceRef
from plainweave.paths import plainweave_db_path, project_root
from plainweave.service import PlainweaveService
from plainweave.wardline_adapter import WardlineAdapter

JsonObject = dict[str, object]
ENTITY_TRACE_KINDS = {"loomweave_entity", "file_ref"}
MAX_ENTITY_CONTEXT_REFS = 100
PREFLIGHT_SCOPE_KINDS = {"pending_diff", "commit_range", "explicit_requirements", "project"}
PREFLIGHT_DIFF_SCOPE_KINDS = {"pending_diff", "commit_range"}
# Neutral fact severities only. There is deliberately NO enforcement tier (e.g.
# "block_candidate"): Plainweave emits facts, Legis owns any gate decision.
PREFLIGHT_SEVERITIES = {"info", "warn", "critical"}
PREFLIGHT_FRESHNESS_STATES = {"current", "partial", "unavailable"}

MCP_TOOL_METADATA: dict[str, JsonObject] = {
    "plainweave_intent_corpus": {
        "name": "plainweave_intent_corpus",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local readable intent corpus rows; no consolidation verdict is made.",
    },
    "plainweave_intent_orphans": {
        "name": "plainweave_intent_orphans",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local missing-justification facts; it does not decide release readiness.",
    },
    "plainweave_intent_trace": {
        "name": "plainweave_intent_trace",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local code-up/down intent graph neighbors without creating accepted truth.",
    },
    "plainweave_intent_coverage": {
        "name": "plainweave_intent_coverage",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": (
            "Returns the local north-star coverage fact (% of public surfaces that answer 'why does this "
            "exist?'), qualified by denominator completeness; it is advisory and makes no pass/fail verdict."
        ),
    },
    "plainweave_baseline_diff": {
        "name": "plainweave_baseline_diff",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local baseline drift facts; it does not make release decisions.",
    },
    "plainweave_baseline_get": {
        "name": "plainweave_baseline_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns one local immutable baseline snapshot.",
    },
    "plainweave_baseline_list": {
        "name": "plainweave_baseline_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Lists local immutable baselines without creating or changing snapshots.",
    },
    "plainweave_entity_intent_context_get": {
        "name": "plainweave_entity_intent_context_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": (
            "Returns local entity-to-intent context for peer planning; live peer identity resolution is "
            "explicit unavailable state."
        ),
    },
    "plainweave_preflight_facts_get": {
        "name": "plainweave_preflight_facts_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns scoped Plainweave facts for Legis preflight; contains no governance verdicts.",
    },
    "plainweave_project_context_get": {
        "name": "plainweave_project_context_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Reports local Plainweave project context and read-only capability metadata.",
    },
    "plainweave_loomweave_catalog_list": {
        "name": "plainweave_loomweave_catalog_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": (
            "Reads Loomweave local catalog identity snapshots without mutating Plainweave or Loomweave."
        ),
    },
    "plainweave_requirement_dossier_get": {
        "name": "plainweave_requirement_dossier_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns the local computed dossier; live peer calls are not made in P0.",
    },
    "plainweave_requirement_get": {
        "name": "plainweave_requirement_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": (
            "Returns one local requirement record; active drafts remain separate from approved truth."
        ),
    },
    "plainweave_requirement_search": {
        "name": "plainweave_requirement_search",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local requirement records without changing authority state.",
    },
    "plainweave_trace_link_list": {
        "name": "plainweave_trace_link_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local trace links with state, authority, and freshness preserved.",
    },
    "plainweave_verification_status_get": {
        "name": "plainweave_verification_status_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns derived local verification status and evidence freshness.",
    },
    "plainweave_verification_status_list": {
        "name": "plainweave_verification_status_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Lists local unverified or stale verification statuses without recording evidence.",
    },
    "plainweave_wardline_peer_facts_list": {
        "name": "plainweave_wardline_peer_facts_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": (
            "Reads Wardline's local findings snapshots as advisory peer facts; it runs no scan, makes no "
            "trust decision, and emits no verdict. Wardline owns trust policy."
        ),
    },
}

MCP_RESOURCE_URIS = [
    "plainweave://project/context",
    "plainweave://contracts/weft.plainweave.error.v1",
    "plainweave://contracts/weft.plainweave.requirement_dossier.v1",
    "plainweave://contracts/weft.plainweave.baseline.v1",
    "plainweave://contracts/weft.plainweave.baseline_diff.v1",
    "plainweave://contracts/weft.plainweave.entity_intent_context.v1",
    "plainweave://contracts/weft.plainweave.preflight_facts.v1",
    "plainweave://contracts/weft.plainweave.requirement_verification_status.v1",
    "plainweave://contracts/weft.plainweave.sei_binding.v1",
    "plainweave://contracts/weft.plainweave.intent_orphans.v1",
    "plainweave://contracts/weft.plainweave.intent_trace.v1",
    "plainweave://contracts/weft.plainweave.intent_corpus.v1",
    "plainweave://contracts/weft.plainweave.intent_coverage.v1",
    "plainweave://contracts/weft.plainweave.wardline_peer_facts.v1",
]

REQUIREMENT_STATUS_FILTERS = {"draft", "approved", "deprecated", "rejected"}
TRACE_STATE_FILTERS = {"proposed", "accepted", "rejected", "stale", "orphaned"}

CONTRACT_RESOURCES: dict[str, JsonObject] = {
    "plainweave://contracts/weft.plainweave.error.v1": {
        "contract": "weft.plainweave.error.v1",
        "required_keys": ["schema", "ok", "error", "warnings", "meta"],
        "recovery": "Switch on error.code and use error.hint; do not parse message text.",
    },
    "plainweave://contracts/weft.plainweave.requirement_dossier.v1": {
        "contract": "weft.plainweave.requirement_dossier.v1",
        "required_sections": [
            "identity",
            "authority_summary",
            "requirement",
            "acceptance_criteria",
            "traces",
            "verification",
            "baseline_exposure",
            "computed_gaps",
            "peer_facts",
            "next_actions",
        ],
        "authority_boundary": "Computed from local Plainweave state only in P0.",
    },
    "plainweave://contracts/weft.plainweave.baseline.v1": {
        "contract": "weft.plainweave.baseline.v1",
        "authority_boundary": "Immutable local snapshot of approved/deprecated requirement versions.",
    },
    "plainweave://contracts/weft.plainweave.baseline_diff.v1": {
        "contract": "weft.plainweave.baseline_diff.v1",
        "statuses": ["unchanged", "changed", "missing_current", "new_since_baseline", "superseded_since_baseline"],
        "authority_boundary": "Diff facts only; not a release-readiness verdict.",
    },
    "plainweave://contracts/weft.plainweave.entity_intent_context.v1": {
        "contract": "weft.plainweave.entity_intent_context.v1",
        "required_sections": [
            "input_ref",
            "resolution",
            "bindings",
            "requirement_trail",
            "orphan",
            "freshness",
            "drift",
        ],
        "resolution_states": ["resolved", "resolved_no_binding", "unresolved"],
        "local_catalog_states": ["resolved", "unresolved", "unavailable"],
        "peer_resolution_states": ["unavailable"],
        "orphan_states": ["bound", "stale_binding", "orphaned_trace", "pending_review", "unbound", "unavailable"],
        "freshness_states": ["current", "stale", "orphaned", "unknown", "unavailable"],
        "drift_states": ["not_detected", "stale", "orphaned", "unknown", "unavailable"],
        "authority_boundary": (
            "Input refs are canonicalized against the local Loomweave catalog (no live peer call); "
            "Loomweave remains the identity authority."
        ),
    },
    "plainweave://contracts/weft.plainweave.preflight_facts.v1": {
        "contract": "weft.plainweave.preflight_facts.v1",
        "required_sections": [
            "producer",
            "scope",
            "generated_at",
            "freshness",
            "facts",
            "summary",
            "warnings",
            "provenance",
            "authority_boundary",
        ],
        "fact_kinds": [
            "requirement_touched",
            "requirement_nearby",
            "requirement_verification_stale",
            "requirement_verification_missing",
            "baseline_drift",
            "trace_gap",
            "open_linked_work",
            "active_finding_linked",
            "waived_finding_linked",
            "orphaned_entity_link",
            "untraced_change",
        ],
        "severities": sorted(PREFLIGHT_SEVERITIES),
        "freshness_states": sorted(PREFLIGHT_FRESHNESS_STATES),
        "authority_boundary": "Plainweave emits facts only; Legis owns policy cells, audit, and enforcement.",
    },
    "plainweave://contracts/weft.plainweave.requirement_verification_status.v1": {
        "contract": "weft.plainweave.requirement_verification_status.v1",
        "statuses": ["satisfied", "unsatisfied", "unverified", "stale", "unknown", "waived"],
        "authority_boundary": "Derived local status with reason codes and evidence freshness.",
    },
    "plainweave://contracts/weft.plainweave.sei_binding.v1": {
        "contract": "weft.plainweave.sei_binding.v1",
        "required_keys": [
            "entity_id",
            "entity_kind",
            "requirement_id",
            "content_hash_at_attach",
            "drift_status",
            "freshness",
            "bound_by",
            "bound_at",
            "provenance",
        ],
        "authority_boundary": "Plainweave consumes opaque SEIs and records local bindings; it does not mint SEIs.",
    },
    "plainweave://contracts/weft.plainweave.intent_orphans.v1": {
        "contract": "weft.plainweave.intent_orphans.v1",
        "data_shape": {"items": [{"level": "code|requirement|goal", "node_id": "opaque node id"}]},
        "authority_boundary": "Orphan facts are review prompts, not release verdicts.",
    },
    "plainweave://contracts/weft.plainweave.intent_trace.v1": {
        "contract": "weft.plainweave.intent_trace.v1",
        "required_sections": ["node", "up", "down"],
        "authority_boundary": "Trace reads local intent graph context without creating accepted truth.",
    },
    "plainweave://contracts/weft.plainweave.intent_corpus.v1": {
        "contract": "weft.plainweave.intent_corpus.v1",
        "data_shape": {"items": [{"requirement": "IntentNode", "goals": "IntentNode[]", "code": "IntentNode[]"}]},
        "authority_boundary": "Corpus rows support human/agent curation; they are not deduplication verdicts.",
    },
    "plainweave://contracts/weft.plainweave.intent_coverage.v1": {
        "contract": "weft.plainweave.intent_coverage.v1",
        "required_sections": [
            "north_star",
            "denominator_complete",
            "coverage",
            "scoping",
            "justified",
            "unjustified",
            "adapter",
        ],
        "surface_classes": sorted(PUBLIC_SURFACE_TAGS),
        "authority_boundary": (
            "An advisory coverage fact over the explicitly-tagged public surface; the ratio is qualified by "
            "denominator_complete and is never a pass/fail on the north-star target."
        ),
    },
    "plainweave://contracts/weft.plainweave.wardline_peer_facts.v1": {
        "contract": "weft.plainweave.wardline_peer_facts.v1",
        "required_sections": [
            "source", "freshness", "facts", "resolved_or_unseen",
            "engine_metrics", "summary", "degraded", "authority_boundary", "notes",
        ],
        "freshness_states": ["current", "stale", "unavailable"],
        "suppression_states": ["active", "waived", "baselined", "judged"],
        "degrade_codes": [
            "wardline_findings_absent", "wardline_single_snapshot", "wardline_scope_mismatch",
            "wardline_scan_identity_absent", "wardline_ruleset_mismatch",
        ],
        "authority_boundary": "Advisory Wardline findings read from local .wardline snapshots; no verdict, no scan.",
    },
}


class PlainweaveMcpSurface:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or project_root()

    def plainweave_project_context_get(self, *, include_contracts: bool = False) -> JsonObject:
        result = inspect_project(self.root)
        project = result["project_key"] if isinstance(result["project_key"], str) else None
        context: JsonObject = {
            **result,
            "capabilities": [dict(value) for value in MCP_TOOL_METADATA.values()],
            "peer_read_capabilities": {
                "loomweave": self._loomweave_adapter().adapter_capability(),
            },
            "authority_boundary": {
                "local_only": True,
                "live_peer_calls": False,
                "mutations": False,
                "release_verdicts": False,
            },
        }
        if include_contracts:
            context["contract_resources"] = list(MCP_RESOURCE_URIS)
        return success_envelope("weft.plainweave.project_context.v1", context, project=project)

    def plainweave_loomweave_catalog_list(self, *, limit: int = 50, offset: int = 0) -> JsonObject:
        try:
            self._validate_pagination(limit, offset)
            page = self._loomweave_adapter().list_catalog(limit=limit, offset=offset)
        except PlainweaveError as exc:
            return self._error(exc)
        data: JsonObject = {
            "items": [item.to_dict() for item in page.items],
            "limit": page.limit,
            "offset": page.offset,
            "has_more": page.has_more,
            "next_offset": page.next_offset,
            "adapter_status": page.adapter_status,
            "degraded": page.degraded,
            "coverage": page.coverage,
        }
        return success_envelope("weft.plainweave.loomweave_catalog.v1", data, project=self._project_key())

    def plainweave_requirement_search(
        self,
        *,
        query: str | None = None,
        status_filter: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> JsonObject:
        if status_filter is not None:
            validation_error = self._validate_filter(status_filter, REQUIREMENT_STATUS_FILTERS, "status_filter")
            if validation_error is not None:
                return validation_error
        return self._result(
            "weft.plainweave.requirement_list.v1",
            lambda service: self._list(
                [
                    _record_dict(item)
                    for item in service.search_requirements(query)
                    if status_filter is None or item.status == status_filter
                ],
                limit=limit,
                offset=offset,
            ),
            list_result=True,
        )

    def plainweave_requirement_get(self, requirement_id: str) -> JsonObject:
        return self._result(
            "weft.plainweave.requirement.v1",
            lambda service: _record_dict(service.get_requirement(requirement_id)),
        )

    def plainweave_requirement_dossier_get(self, requirement_id: str) -> JsonObject:
        return self._result(
            "weft.plainweave.requirement_dossier.v1",
            lambda service: _dossier_dict(service.requirement_dossier(requirement_id)),
        )

    def plainweave_trace_link_list(
        self,
        *,
        requirement_id: str | None = None,
        state_filter: str | None = None,
        relation_filter: str | None = None,
        direction: str = "both",
        limit: int = 50,
        offset: int = 0,
    ) -> JsonObject:
        def action(service: PlainweaveService) -> JsonObject:
            self._validate_choice(direction, {"incoming", "outgoing", "both"}, "direction")
            if state_filter is not None:
                self._validate_choice(state_filter, TRACE_STATE_FILTERS, "state_filter")
            refs = self._requirement_refs(service, requirement_id) if requirement_id is not None else None
            links = []
            for link in service.trace_for(requirement_id=None, state=state_filter):
                if relation_filter is not None and link.relation != relation_filter:
                    continue
                if refs is not None:
                    incoming = self._trace_ref_matches(link.to_ref.id, refs)
                    outgoing = self._trace_ref_matches(link.from_ref.id, refs)
                    if direction == "incoming" and not incoming:
                        continue
                    if direction == "outgoing" and not outgoing:
                        continue
                links.append(_trace_dict(link))
            return self._list(links, limit=limit, offset=offset)

        return self._result("weft.plainweave.trace_link_list.v1", action, list_result=True)

    def plainweave_intent_orphans(
        self,
        *,
        level: str,
        limit: int = 50,
        offset: int = 0,
    ) -> JsonObject:
        def action(service: PlainweaveService) -> JsonObject:
            intent_level = self._intent_level(level)
            return self._list(
                [_intent_node_dict(item) for item in service.intent_orphans(intent_level)],
                limit=limit,
                offset=offset,
            )

        return self._result("weft.plainweave.intent_orphans.v1", action, list_result=True)

    def plainweave_intent_trace(self, *, level: str, node_id: str) -> JsonObject:
        def action(service: PlainweaveService) -> JsonObject:
            return _intent_trace_dict(service.intent_trace(IntentNode(self._intent_level(level), node_id)))

        return self._result("weft.plainweave.intent_trace.v1", action)

    def plainweave_intent_corpus(self, *, limit: int = 50, offset: int = 0) -> JsonObject:
        return self._result(
            "weft.plainweave.intent_corpus.v1",
            lambda service: self._list(
                [_corpus_entry_dict(item) for item in service.intent_corpus()],
                limit=limit,
                offset=offset,
            ),
            list_result=True,
        )

    def plainweave_intent_coverage(
        self,
        *,
        exclude_namespaces: Sequence[str] | None = None,
        surface_classes: Sequence[str] | None = None,
        max_surfaces: int | None = None,
    ) -> JsonObject:
        return self._result(
            "weft.plainweave.intent_coverage.v1",
            lambda service: _intent_coverage_dict(
                service.intent_coverage(
                    exclude_namespaces=exclude_namespaces,
                    surface_classes=surface_classes,
                    max_surfaces=max_surfaces,
                )
            ),
        )

    def plainweave_baseline_list(self, *, limit: int = 25, offset: int = 0) -> JsonObject:
        return self._result(
            "weft.plainweave.baseline_list.v1",
            lambda service: self._list(
                [_baseline_dict(item) for item in service.list_baselines()],
                limit=limit,
                offset=offset,
            ),
            list_result=True,
        )

    def plainweave_baseline_get(self, baseline_id: str) -> JsonObject:
        return self._result(
            "weft.plainweave.baseline.v1",
            lambda service: _baseline_dict(service.show_baseline(baseline_id)),
        )

    def plainweave_baseline_diff(self, baseline_id: str) -> JsonObject:
        return self._result(
            "weft.plainweave.baseline_diff.v1",
            lambda service: _baseline_diff_dict(service.diff_baseline(baseline_id)),
        )

    def plainweave_entity_intent_context_get(self, *, entity_refs: Sequence[str]) -> JsonObject:
        validation_error = self._validate_entity_refs(entity_refs)
        if validation_error is not None:
            return validation_error

        def action(service: PlainweaveService) -> JsonObject:
            traces = service.trace_for()
            items = [self._entity_intent_context_item(service, entity_ref, traces) for entity_ref in entity_refs]
            return {
                "items": items,
                "summary": self._entity_intent_summary(items),
                "authority_boundary": {
                    "local_only": True,
                    "live_peer_calls": False,
                    "identity_authority": "loomweave",
                    "drift_source": "local_trace_freshness",
                },
            }

        return self._result("weft.plainweave.entity_intent_context.v1", action)

    def plainweave_preflight_facts_get(
        self,
        *,
        scope_kind: str = "pending_diff",
        base: str | None = None,
        head: str | None = None,
        requirement_ids: Sequence[str] | None = None,
        entity_refs: Sequence[str] | None = None,
        baseline_id: str | None = None,
    ) -> JsonObject:
        validation_error = self._validate_preflight_inputs(scope_kind, requirement_ids, entity_refs)
        if validation_error is not None:
            return validation_error

        def action(service: PlainweaveService) -> JsonObject:
            scoped_requirement_ids = self._preflight_requirement_ids(service, requirement_ids)
            scoped_entity_refs = self._dedupe(entity_refs)
            requirement_basis = self._preflight_requirement_basis(scope_kind, requirement_ids)
            facts: list[JsonObject] = []
            warnings = self._preflight_warnings(scope_kind, scoped_requirement_ids)
            scope = self._preflight_scope(
                scope_kind,
                base,
                head,
                scoped_requirement_ids,
                scoped_entity_refs,
                baseline_id,
            )
            for requirement_id in scoped_requirement_ids:
                try:
                    self._append_requirement_preflight_facts(service, facts, requirement_id, basis=requirement_basis)
                except PlainweaveError as exc:
                    # A single unresolvable scoped requirement soft-degrades to a warning
                    # rather than hard-failing the whole report (consistent with how
                    # unresolvable entity refs are handled).
                    if exc.code != ErrorCode.NOT_FOUND:
                        raise
                    warnings.append(
                        self._preflight_warning(
                            "requirement_unresolved",
                            f"Scoped requirement could not be resolved and was skipped: {requirement_id}",
                        )
                    )
            if baseline_id is not None:
                try:
                    self._append_baseline_preflight_facts(service, facts, baseline_id, scoped_requirement_ids)
                except PlainweaveError as exc:
                    if exc.code != ErrorCode.NOT_FOUND:
                        raise
                    warnings.append(
                        self._preflight_warning(
                            "baseline_unresolved",
                            f"Scoped baseline could not be resolved and was skipped: {baseline_id}",
                        )
                    )
            self._append_entity_preflight_facts(service, facts, scoped_entity_refs)
            subjects_requested = bool(scoped_requirement_ids or scoped_entity_refs or baseline_id)
            return {
                "producer": {"tool": "plainweave", "version": __version__, "project": self._project_key()},
                "scope": scope,
                "generated_at": datetime.now(UTC).isoformat(),
                "freshness": self._preflight_freshness(facts, scope_kind, subjects_requested=subjects_requested),
                "facts": facts,
                "summary": self._preflight_summary(facts),
                "warnings": warnings,
                "provenance": {
                    "producer": "plainweave",
                    "inputs": self._preflight_provenance_inputs(facts),
                },
                "authority_boundary": {
                    "local_only": True,
                    "live_peer_calls": False,
                    "governance_verdicts": False,
                    "legis_policy_cells": "external",
                },
            }

        return self._result("weft.plainweave.preflight_facts.v1", action)

    def plainweave_verification_status_get(self, requirement_id: str) -> JsonObject:
        return self._result(
            "weft.plainweave.requirement_verification_status.v1",
            lambda service: _requirement_verification_status_dict(service.verification_status(requirement_id)),
        )

    def plainweave_verification_status_list(
        self,
        *,
        status_filter: str,
        limit: int = 25,
        offset: int = 0,
    ) -> JsonObject:
        def action(service: PlainweaveService) -> JsonObject:
            self._validate_choice(status_filter, {"unverified", "stale"}, "status_filter")
            statuses = (
                service.list_unverified_requirements()
                if status_filter == "unverified"
                else service.list_stale_requirements()
            )
            return self._list(
                [_requirement_verification_status_dict(item) for item in statuses],
                limit=limit,
                offset=offset,
            )

        return self._result("weft.plainweave.requirement_verification_status_list.v1", action, list_result=True)

    def read_resource(self, uri: str) -> JsonObject:
        if uri == "plainweave://project/context":
            return self.plainweave_project_context_get(include_contracts=True)
        if uri not in CONTRACT_RESOURCES:
            return self._error(
                PlainweaveError(
                    ErrorCode.NOT_FOUND,
                    "MCP resource was not found",
                    recoverable=True,
                    hint="Use one of the advertised Plainweave MCP resource URIs.",
                    details={"uri": uri, "resources": list(MCP_RESOURCE_URIS)},
                )
            )
        return success_envelope(
            "weft.plainweave.mcp_contract_resource.v1",
            {"uri": uri, **CONTRACT_RESOURCES[uri]},
            project=self._project_key(),
        )

    def _result(self, schema: str, action: Any, *, list_result: bool = False) -> JsonObject:
        try:
            data = action(self._service())
            if list_result:
                return success_envelope(schema, data, project=self._project_key())
            return success_envelope(schema, data, project=self._project_key())
        except PlainweaveError as exc:
            return self._error(exc)

    def _service(self) -> PlainweaveService:
        db_path = plainweave_db_path(self.root)
        if not db_path.exists():
            raise PlainweaveError(
                ErrorCode.NOT_FOUND,
                "Plainweave project is not initialized",
                recoverable=True,
                hint="Run `plainweave init` in this project and retry.",
                details={"db_path": str(db_path)},
            )
        return PlainweaveService(db_path, root=self.root)

    def _loomweave_adapter(self) -> LoomweaveAdapter:
        return LoomweaveAdapter(self.root)

    def _wardline_adapter(self) -> WardlineAdapter:
        return WardlineAdapter(self.root)

    def plainweave_wardline_peer_facts_list(self, *, limit: int = 50, offset: int = 0) -> JsonObject:
        try:
            self._validate_pagination(limit, offset)
            data = self._wardline_adapter().list_peer_facts(limit=limit, offset=offset)
        except PlainweaveError as exc:
            return self._error(exc)
        return success_envelope("weft.plainweave.wardline_peer_facts.v1", data, project=self._project_key())

    def _requirements_enrichment_status(self, item: JsonObject) -> tuple[str, str | None]:
        resolution = cast(JsonObject, item["resolution"])
        local = cast(JsonObject, resolution["local_catalog"])
        requirement_trail = cast(list[object], item["requirement_trail"])
        matched = cast(list[object], resolution["matched_refs"])
        if requirement_trail:
            return "present", None
        if local["state"] == "unavailable":
            return "unavailable", "Local Loomweave catalog could not be consulted; cannot determine requirements."
        if not matched:
            if local["state"] == "resolved":
                return "absent", "Entity resolves locally but no requirement is bound to it."
            return "unavailable", "Entity identity is not resolvable locally; cannot determine requirements."
        # A trace matched but no alive requirement loaded behind it: this is "cannot
        # tell", never "definitively none" (no-silent-clean, spec §4).
        return "unavailable", "A binding exists but its requirement could not be resolved; cannot determine."

    def _project_key(self) -> str | None:
        if self.root == project_root():
            return _current_project_key()
        metadata = inspect_project(self.root)
        return metadata["project_key"] if isinstance(metadata["project_key"], str) else None

    def _error(self, exc: PlainweaveError) -> JsonObject:
        return error_envelope(
            exc.code,
            exc.message,
            recoverable=exc.recoverable,
            hint=exc.hint,
            details=exc.details,
            project=self._project_key(),
        )

    def _list(self, items: Sequence[object], *, limit: int, offset: int) -> JsonObject:
        self._validate_pagination(limit, offset)
        page = list(items[offset : offset + limit])
        next_offset = offset + limit if offset + limit < len(items) else None
        return {"items": page, "has_more": next_offset is not None, "next_offset": next_offset}

    def _validate_pagination(self, limit: int, offset: int) -> None:
        if limit < 1 or limit > 100:
            raise PlainweaveError(
                ErrorCode.VALIDATION,
                "limit must be between 1 and 100",
                recoverable=True,
                hint="Pass a limit from 1 through 100.",
                details={"limit": limit},
            )
        if offset < 0:
            raise PlainweaveError(
                ErrorCode.VALIDATION,
                "offset must be non-negative",
                recoverable=True,
                hint="Pass offset 0 or a next_offset returned by a list tool.",
                details={"offset": offset},
            )

    def _validate_choice(self, value: str, allowed: set[str], field: str) -> None:
        if value not in allowed:
            raise PlainweaveError(
                ErrorCode.VALIDATION,
                f"{field} is not supported",
                recoverable=True,
                hint=f"Use one of: {', '.join(sorted(allowed))}.",
                details={field: value, "allowed": sorted(allowed)},
            )

    def _validate_entity_refs(self, entity_refs: Sequence[str]) -> JsonObject | None:
        if len(entity_refs) == 0:
            return self._error(
                PlainweaveError(
                    ErrorCode.VALIDATION,
                    "entity_refs must contain at least one entity reference",
                    recoverable=True,
                    hint="Pass one or more Loomweave SEI or locator strings.",
                    details={"entity_refs": []},
                )
            )
        if len(entity_refs) > MAX_ENTITY_CONTEXT_REFS:
            return self._error(
                PlainweaveError(
                    ErrorCode.VALIDATION,
                    "entity_refs exceeds the maximum batch size",
                    recoverable=True,
                    hint=f"Pass at most {MAX_ENTITY_CONTEXT_REFS} entity refs per call.",
                    details={"count": len(entity_refs), "max": MAX_ENTITY_CONTEXT_REFS},
                )
            )
        for index, entity_ref in enumerate(entity_refs):
            if not isinstance(entity_ref, str) or entity_ref == "":
                return self._error(
                    PlainweaveError(
                        ErrorCode.VALIDATION,
                        "entity_refs must be non-empty strings",
                        recoverable=True,
                        hint="Remove empty refs and retry with explicit Loomweave SEI or locator strings.",
                        details={"index": index},
                    )
                )
        return None

    def _validate_preflight_inputs(
        self,
        scope_kind: str,
        requirement_ids: Sequence[str] | None,
        entity_refs: Sequence[str] | None,
    ) -> JsonObject | None:
        if scope_kind not in PREFLIGHT_SCOPE_KINDS:
            return self._error(
                PlainweaveError(
                    ErrorCode.VALIDATION,
                    "scope_kind is not supported",
                    recoverable=True,
                    hint=f"Use one of: {', '.join(sorted(PREFLIGHT_SCOPE_KINDS))}.",
                    details={"scope_kind": scope_kind, "allowed": sorted(PREFLIGHT_SCOPE_KINDS)},
                )
            )
        for field, values in (("requirement_ids", requirement_ids), ("entity_refs", entity_refs)):
            if values is None:
                continue
            if len(values) > 100:
                return self._error(
                    PlainweaveError(
                        ErrorCode.VALIDATION,
                        f"{field} exceeds the maximum batch size",
                        recoverable=True,
                        hint=f"Pass at most 100 {field} per call.",
                        details={field: len(values), "max": 100},
                    )
                )
            for index, value in enumerate(values):
                if not isinstance(value, str) or value == "":
                    return self._error(
                        PlainweaveError(
                            ErrorCode.VALIDATION,
                            f"{field} must contain non-empty strings",
                            recoverable=True,
                            hint=f"Remove empty {field} entries and retry.",
                            details={"field": field, "index": index},
                        )
                    )
        return None

    def _intent_level(self, value: str) -> IntentLevel:
        try:
            return IntentLevel(value)
        except ValueError:
            allowed = [level.value for level in IntentLevel]
            raise PlainweaveError(
                ErrorCode.VALIDATION,
                "intent level is not supported",
                recoverable=True,
                hint=f"Use one of: {', '.join(allowed)}.",
                details={"level": value, "allowed": allowed},
            ) from None

    def _validate_filter(self, value: str, allowed: set[str], field: str) -> JsonObject | None:
        try:
            self._validate_choice(value, allowed, field)
        except PlainweaveError as exc:
            return self._error(exc)
        return None

    def _requirement_refs(self, service: PlainweaveService, requirement_id: str | None) -> set[str]:
        if requirement_id is None:
            return set()
        record = service.get_requirement(requirement_id)
        return {record.requirement_id, record.id, record.stable_id}

    def _trace_ref_matches(self, value: str, refs: set[str]) -> bool:
        if value in refs:
            return True
        prefix, separator, _version = value.rpartition("@")
        return separator == "@" and prefix in refs

    def _preflight_requirement_ids(
        self,
        service: PlainweaveService,
        requirement_ids: Sequence[str] | None,
    ) -> list[str]:
        if requirement_ids is not None:
            return self._dedupe(requirement_ids)
        return [record.id for record in service.search_requirements()]

    def _dedupe(self, values: Sequence[str] | None) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values or []:
            if value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped

    def _preflight_requirement_basis(self, scope_kind: str, requirement_ids: Sequence[str] | None) -> str:
        if requirement_ids is not None:
            return "touched"
        if scope_kind == "project":
            return "touched"
        # Diff scope with no explicit ids: the live diff is not resolved locally, so
        # the corpus-fallback requirements are "nearby", not proven "touched".
        return "nearby"

    def _preflight_provenance_inputs(self, facts: Sequence[JsonObject]) -> list[str]:
        inputs: set[str] = set()
        for fact in facts:
            provenance = cast(JsonObject, fact["provenance"])
            for value in cast(Sequence[str], provenance["inputs"]):
                inputs.add(value)
        return sorted(inputs)

    def _preflight_scope(
        self,
        scope_kind: str,
        base: str | None,
        head: str | None,
        requirement_ids: Sequence[str],
        entity_refs: Sequence[str],
        baseline_id: str | None,
    ) -> JsonObject:
        scope: JsonObject = {
            "kind": scope_kind,
            "base": base,
            "head": head,
            "requirement_ids": list(requirement_ids),
            "entity_refs": list(entity_refs),
            "baseline_id": baseline_id,
        }
        return scope

    def _preflight_warnings(self, scope_kind: str, requirement_ids: Sequence[str]) -> list[JsonObject]:
        warnings: list[JsonObject] = []
        if scope_kind in {"pending_diff", "commit_range"}:
            warnings.append(
                self._preflight_warning(
                    "live_diff_resolution_unavailable",
                    "Plainweave did not call Legis or Loomweave to resolve the live diff.",
                )
            )
        if requirement_ids:
            warnings.append(
                self._preflight_warning(
                    "goal_trail_unavailable",
                    "Strategic goal nodes are not implemented in the local store.",
                )
            )
        warnings.append(
            self._preflight_warning(
                "linked_work_facts_unavailable",
                "Filigree linked-work facts are not joined by this local-only producer.",
            )
        )
        warnings.append(
            self._preflight_warning(
                "finding_facts_unavailable",
                "Wardline finding facts are not joined by this local-only producer.",
            )
        )
        return warnings

    def _preflight_warning(self, code: str, message: str) -> JsonObject:
        return {
            "code": code,
            "severity": "info",
            "message": message,
            "freshness": "unavailable",
            "provenance": {"producer": "plainweave", "inputs": []},
        }

    def _append_requirement_preflight_facts(
        self,
        service: PlainweaveService,
        facts: list[JsonObject],
        requirement_id: str,
        *,
        basis: str = "touched",
    ) -> None:
        requirement = service.requirement_preflight_profile(requirement_id)
        status = service.verification_status(requirement_id)
        dossier = service.requirement_dossier(requirement_id)
        if basis == "nearby":
            scope_kind, scope_message = (
                "requirement_nearby",
                "Scoped requirement is in the preflight corpus fallback; the live diff was not resolved.",
            )
        else:
            scope_kind, scope_message = (
                "requirement_touched",
                "Scoped requirement is included in the preflight context.",
            )
        self._append_preflight_fact(
            facts,
            kind=scope_kind,
            severity="info",
            requirement=requirement,
            message=scope_message,
            evidence_refs=[str(requirement["id"])],
            source={"kind": "scope", "id": str(requirement["id"])},
            freshness="current",
            inputs=["requirements"],
        )
        if status.status == "stale":
            evidence_refs = [evidence.id for evidence in status.stale_evidence]
            self._append_preflight_fact(
                facts,
                kind="requirement_verification_stale",
                severity="warn",
                requirement=requirement,
                message="Scoped requirement has stale verification evidence.",
                evidence_refs=evidence_refs,
                source={"kind": "verification_status", "id": str(requirement["id"])},
                freshness="current",
                inputs=["verification_evidence"],
            )
        elif status.status == "unverified":
            self._append_preflight_fact(
                facts,
                kind="requirement_verification_missing",
                severity="warn",
                requirement=requirement,
                message="Scoped requirement has no current satisfying verification evidence.",
                evidence_refs=[],
                source={"kind": "verification_status", "id": str(requirement["id"])},
                freshness="current",
                inputs=["verification_methods", "verification_evidence"],
            )
        accepted_current = [
            trace
            for trace in dossier.traces.items
            if trace.state == "accepted"
            and trace.freshness == "current"
            and trace.from_ref.kind in ENTITY_TRACE_KINDS
            and trace.to_ref.kind == "requirement_version"
            and trace.to_ref.id == f"{requirement['id']}@{requirement['version']}"
        ]
        if not accepted_current:
            self._append_preflight_fact(
                facts,
                kind="trace_gap",
                severity="warn",
                requirement=requirement,
                message="Scoped requirement has no accepted current code-entity trace.",
                evidence_refs=[trace.id for trace in dossier.traces.items],
                source={"kind": "trace_links", "id": str(requirement["id"])},
                freshness="current",
                inputs=["trace_links"],
            )
        stale_or_orphaned = [
            trace
            for trace in dossier.traces.items
            if trace.from_ref.kind in ENTITY_TRACE_KINDS and trace.state in {"stale", "orphaned"}
        ]
        if stale_or_orphaned:
            self._append_preflight_fact(
                facts,
                kind="orphaned_entity_link",
                severity="warn",
                requirement=requirement,
                message="Scoped requirement has stale or orphaned entity trace links.",
                evidence_refs=[trace.id for trace in stale_or_orphaned],
                source={"kind": "trace_links", "id": str(requirement["id"])},
                freshness="current",
                inputs=["trace_links"],
            )

    def _append_baseline_preflight_facts(
        self,
        service: PlainweaveService,
        facts: list[JsonObject],
        baseline_id: str,
        requirement_ids: Sequence[str],
    ) -> None:
        scoped = set(requirement_ids)
        diff = service.diff_baseline(baseline_id)
        for item in diff.items:
            if item.id not in scoped and item.requirement_id not in scoped and item.stable_id not in scoped:
                continue
            if item.status == "unchanged":
                continue
            try:
                requirement = service.requirement_preflight_profile(item.requirement_id)
            except PlainweaveError as exc:
                # A baseline can outlive a requirement that was since deleted; keep the
                # drift fact with an unavailable profile rather than aborting the report.
                if exc.code != ErrorCode.NOT_FOUND:
                    raise
                requirement = self._unavailable_requirement_profile()
            self._append_preflight_fact(
                facts,
                kind="baseline_drift",
                severity="warn",
                requirement=requirement,
                message=f"Scoped requirement baseline state is {item.status}.",
                evidence_refs=[baseline_id],
                source={"kind": "baseline_diff", "id": baseline_id},
                freshness="current",
                inputs=["baselines", "baseline_members"],
            )

    def _append_entity_preflight_facts(
        self,
        service: PlainweaveService,
        facts: list[JsonObject],
        entity_refs: Sequence[str],
    ) -> None:
        traces = service.trace_for()
        for entity_ref in entity_refs:
            local = self._local_catalog_resolution(entity_ref)
            match_refs = {entity_ref}
            if isinstance(local["sei"], str):
                match_refs.add(local["sei"])
            if isinstance(local["locator"], str):
                match_refs.add(local["locator"])
            matching = [trace for trace in traces if self._trace_matches_entity_refs(trace, match_refs)]
            accepted_current = [
                trace for trace in matching if trace.state == "accepted" and trace.freshness == "current"
            ]
            if not accepted_current:
                self._append_preflight_fact(
                    facts,
                    kind="untraced_change",
                    severity="critical",
                    requirement=self._unavailable_requirement_profile(),
                    message="Scoped entity has no accepted current requirement trace.",
                    evidence_refs=[entity_ref],
                    source={"kind": "entity_ref", "id": entity_ref},
                    freshness="partial",
                    inputs=["trace_links"],
                )

    def _append_preflight_fact(
        self,
        facts: list[JsonObject],
        *,
        kind: str,
        severity: str,
        requirement: JsonObject,
        message: str,
        evidence_refs: Sequence[str],
        source: JsonObject,
        freshness: str,
        inputs: Sequence[str],
    ) -> None:
        if severity not in PREFLIGHT_SEVERITIES:
            raise PlainweaveError(
                ErrorCode.INTERNAL,
                "preflight severity is not supported",
                recoverable=True,
                hint="Refresh local Plainweave state and retry.",
            )
        facts.append(
            {
                "id": f"FACT-{len(facts) + 1:04d}",
                "kind": kind,
                "severity": severity,
                "requirement": requirement,
                "message": message,
                "evidence_refs": list(evidence_refs),
                "source": source,
                "freshness": freshness,
                "provenance": {"producer": "plainweave", "inputs": list(inputs)},
            }
        )

    def _unavailable_requirement_profile(self) -> JsonObject:
        return {
            "id": None,
            "requirement_id": None,
            "stable_id": None,
            "version": None,
            "criticality": "unknown",
            "type": "unknown",
        }

    def _preflight_freshness(self, facts: Sequence[JsonObject], scope_kind: str, *, subjects_requested: bool) -> str:
        # Derived from the facts and the scope, NOT from the always-present
        # capability-gap warnings (linked-work / finding joins), which described a
        # permanent out-of-scope join and pinned this field to a constant "partial".
        if scope_kind in PREFLIGHT_DIFF_SCOPE_KINDS:
            # The live diff that defines a diff scope is never resolved locally.
            return "partial"
        fact_freshness = {str(fact["freshness"]) for fact in facts}
        if fact_freshness & {"partial", "unavailable"}:
            return "partial"
        if not facts:
            # Subjects were requested but none resolved -> partial knowledge; nothing
            # requested at all (e.g. empty project scope) -> genuinely unavailable.
            return "partial" if subjects_requested else "unavailable"
        return "current"

    def _preflight_summary(self, facts: Sequence[JsonObject]) -> JsonObject:
        severity_counts = {"info": 0, "warn": 0, "critical": 0}
        by_kind: dict[str, int] = {}
        by_freshness: dict[str, int] = {}
        for fact in facts:
            severity = str(fact["severity"])
            severity_counts[severity] += 1
            kind = str(fact["kind"])
            freshness = str(fact["freshness"])
            by_kind[kind] = by_kind.get(kind, 0) + 1
            by_freshness[freshness] = by_freshness.get(freshness, 0) + 1
        summary: JsonObject = dict(severity_counts)
        summary["facts"] = len(facts)
        summary["by_kind"] = dict(sorted(by_kind.items()))
        summary["by_freshness"] = dict(sorted(by_freshness.items()))
        return summary

    def _entity_intent_context_item(
        self,
        service: PlainweaveService,
        entity_ref: str,
        traces: Sequence[TraceLink],
    ) -> JsonObject:
        # Canonicalize the input ref against the local Loomweave catalog first.
        # loomweave_entity traces are stored under the canonical SEI (writes map
        # locator -> SEI), so a peer passing the legacy locator form would otherwise
        # never match a genuinely bound entity. This is a local-only lookup.
        local = self._local_catalog_resolution(entity_ref)
        match_refs = {entity_ref}
        if isinstance(local["sei"], str):
            match_refs.add(local["sei"])
        if isinstance(local["locator"], str):
            match_refs.add(local["locator"])
        matching_traces = [trace for trace in traces if self._trace_matches_entity_refs(trace, match_refs)]
        binding_pairs = [self._entity_binding_context(service, trace) for trace in matching_traces]
        requirement_ids = self._resolved_requirement_ids(binding_pairs)
        if matching_traces:
            resolution_state = "resolved"
        elif local["state"] == "resolved":
            resolution_state = "resolved_no_binding"
        else:
            resolution_state = "unresolved"
        return {
            "input_ref": entity_ref,
            "resolution": {
                "state": resolution_state,
                "matched_refs": self._matched_entity_refs(entity_ref, match_refs, matching_traces),
                "local_catalog": local,
                "peer_resolution": self._peer_resolution_unavailable(),
            },
            "bindings": [binding for binding, _requirement_id in binding_pairs],
            "requirement_trail": [
                self._requirement_trail_entry(service, requirement_id, binding_pairs)
                for requirement_id in requirement_ids
            ],
            "orphan": self._entity_orphan_context(matching_traces, local_state=str(local["state"])),
            "freshness": self._entity_freshness_context(matching_traces),
            "drift": self._entity_drift_context(matching_traces),
        }

    def _local_catalog_resolution(self, entity_ref: str) -> JsonObject:
        try:
            snapshot = self._loomweave_adapter().resolve_identity_local(entity_ref)
        except LoomweaveIdentityError as exc:
            # not_found / orphaned -> the catalog answered "no such alive identity";
            # unreachable / unsupported -> the catalog itself could not be consulted.
            state = "unavailable" if exc.reason in {"unreachable", "unsupported"} else "unresolved"
            return {"state": state, "sei": None, "locator": None, "reason": exc.message}
        return {"state": "resolved", "sei": snapshot.sei, "locator": snapshot.locator, "reason": None}

    def _entity_binding_context(
        self,
        service: PlainweaveService,
        trace: TraceLink,
    ) -> tuple[JsonObject, str | None]:
        requirement_ref = self._requirement_ref_for_trace(trace)
        base: JsonObject = {
            "trace": _trace_dict(trace),
            "requirement_ref": self._trace_ref_dict(requirement_ref) if requirement_ref is not None else None,
        }
        if requirement_ref is None:
            base.update(
                {
                    "requirement_resolution": {
                        "state": "unavailable",
                        "reason": "Trace link is not connected to a requirement ref.",
                    },
                    "requirement": None,
                    "verification": {
                        "state": "unavailable",
                        "reason": "Verification requires a resolved requirement.",
                    },
                }
            )
            return base, None

        requirement_id = self._requirement_id_from_ref(requirement_ref)
        try:
            requirement = service.get_requirement(requirement_id)
            verification = service.verification_status(requirement_id)
        except PlainweaveError as exc:
            if exc.code != ErrorCode.NOT_FOUND:
                raise
            base.update(
                {
                    "requirement_resolution": {
                        "state": "unresolved",
                        "reason": "Local trace target does not resolve to a requirement.",
                    },
                    "requirement": None,
                    "verification": {
                        "state": "unavailable",
                        "reason": "Verification requires a resolved requirement.",
                    },
                }
            )
            return base, None

        base.update(
            {
                "requirement_resolution": {"state": "resolved"},
                "requirement": _record_dict(requirement),
                "verification": _requirement_verification_status_dict(verification),
            }
        )
        return base, requirement.requirement_id

    def _requirement_trail_entry(
        self,
        service: PlainweaveService,
        requirement_id: str,
        binding_pairs: Sequence[tuple[JsonObject, str | None]],
    ) -> JsonObject:
        # Reuse the requirement/verification dicts already computed by
        # _entity_binding_context rather than re-fetching them from the store.
        matching = [
            binding for binding, binding_requirement_id in binding_pairs if binding_requirement_id == requirement_id
        ]
        return {
            "requirement": cast(JsonObject, matching[0]["requirement"]),
            "via_bindings": [cast(JsonObject, binding["trace"]) for binding in matching],
            "verification": cast(JsonObject, matching[0]["verification"]),
            "goal_trail": self._goal_trail(service, requirement_id),
        }

    def _goal_trail(self, service: PlainweaveService, requirement_id: str) -> JsonObject:
        try:
            goals = service.goals_for_requirement(requirement_id)
        except PlainweaveError as exc:
            # Defensive: callers only reach here with an already-resolved requirement,
            # so NOT_FOUND is not expected in normal flow — but keep the explicit state
            # rather than letting an unexpected resolution failure abort the report.
            if exc.code != ErrorCode.NOT_FOUND:
                raise
            return {
                "state": "unavailable",
                "goals": [],
                "reason": "Requirement could not be resolved for goal laddering.",
            }
        if not goals:
            return {
                "state": "no_goal",
                "goals": [],
                "reason": "Requirement ladders to no strategic goal (laddering gap).",
            }
        return {
            "state": "resolved",
            "goals": [{**_intent_goal_dict(goal), "edge_freshness": edge_freshness} for goal, edge_freshness in goals],
        }

    def _entity_intent_summary(self, items: Sequence[JsonObject]) -> JsonObject:
        resolved = 0
        resolved_no_binding = 0
        unresolved = 0
        orphaned = 0
        for item in items:
            resolution = cast(JsonObject, item["resolution"])
            orphan = cast(JsonObject, item["orphan"])
            state = resolution["state"]
            if state == "resolved":
                resolved += 1
            elif state == "resolved_no_binding":
                resolved_no_binding += 1
            else:
                unresolved += 1
            if orphan["is_orphan"] is True:
                orphaned += 1
        return {
            "requested": len(items),
            "resolved": resolved,
            "resolved_no_binding": resolved_no_binding,
            "unresolved": unresolved,
            "peer_resolution_unavailable": len(items),
            "orphaned": orphaned,
        }

    def _trace_matches_entity_refs(self, trace: TraceLink, refs: set[str]) -> bool:
        return self._trace_ref_matches_entity_input(trace.from_ref, refs) or self._trace_ref_matches_entity_input(
            trace.to_ref,
            refs,
        )

    def _trace_ref_matches_entity_input(self, trace_ref: TraceRef, refs: set[str]) -> bool:
        return trace_ref.kind in ENTITY_TRACE_KINDS and trace_ref.id in refs

    def _matched_entity_refs(
        self,
        entity_ref: str,
        match_refs: set[str],
        traces: Sequence[TraceLink],
    ) -> list[JsonObject]:
        matches: list[JsonObject] = []
        seen: set[tuple[str, str]] = set()
        for trace in traces:
            for trace_ref in (trace.from_ref, trace.to_ref):
                key = (trace_ref.kind, trace_ref.id)
                if self._trace_ref_matches_entity_input(trace_ref, match_refs) and key not in seen:
                    seen.add(key)
                    match_kind = "exact_local_trace" if trace_ref.id == entity_ref else "canonical_identity"
                    matches.append({"kind": trace_ref.kind, "id": trace_ref.id, "match": match_kind})
        return matches

    def _peer_resolution_unavailable(self) -> JsonObject:
        return {
            "state": "unavailable",
            "peer": "loomweave",
            "reason": "Plainweave does not make live peer identity calls from this local-only read surface.",
        }

    def _resolved_requirement_ids(self, binding_pairs: Sequence[tuple[JsonObject, str | None]]) -> list[str]:
        requirement_ids: list[str] = []
        seen: set[str] = set()
        for _binding, requirement_id in binding_pairs:
            if requirement_id is not None and requirement_id not in seen:
                seen.add(requirement_id)
                requirement_ids.append(requirement_id)
        return requirement_ids

    def _requirement_ref_for_trace(self, trace: TraceLink) -> TraceRef | None:
        for trace_ref in (trace.to_ref, trace.from_ref):
            if trace_ref.kind in {"requirement", "requirement_version"}:
                return trace_ref
        return None

    def _requirement_id_from_ref(self, trace_ref: TraceRef) -> str:
        if trace_ref.kind == "requirement_version":
            requirement_id, separator, _version = trace_ref.id.rpartition("@")
            if separator == "@":
                return requirement_id
        return trace_ref.id

    def _trace_ref_dict(self, trace_ref: TraceRef) -> JsonObject:
        return {"kind": trace_ref.kind, "id": trace_ref.id}

    def _actor_kind_from_authority(self, authority: str) -> str:
        return "human" if authority in {"accepted", "human_proposed", "human_attested"} else "agent"

    def _requirements_enrichment_items(
        self, service: PlainweaveService, item: JsonObject
    ) -> list[JsonObject]:
        items: list[JsonObject] = []
        for entry in cast(list[JsonObject], item["requirement_trail"]):
            record = cast(JsonObject, entry["requirement"])
            profile = service.requirement_preflight_profile(str(record["requirement_id"]))
            via = cast(list[JsonObject], entry["via_bindings"])
            binding_trace = via[0] if via and isinstance(via[0], dict) else {}
            authority = str(binding_trace.get("authority", ""))
            items.append(
                {
                    "requirement_id": profile["requirement_id"],
                    "stable_id": profile["stable_id"],
                    "version": profile["version"],
                    "type": profile["type"],
                    "criticality": profile["criticality"],
                    "binding": {
                        "relation": binding_trace.get("relation"),
                        "actor_kind": self._actor_kind_from_authority(authority),
                        "freshness": binding_trace.get("freshness"),
                    },
                }
            )
        return items

    def _entity_orphan_context(self, traces: Sequence[TraceLink], *, local_state: str) -> JsonObject:
        if not traces:
            # An entity known to the local catalog but bound to no trace is a genuine
            # unbound orphan. A ref we could not resolve (unresolved/unavailable) is not
            # something we can assert orphan-hood for, so it stays out of the count.
            if local_state == "resolved":
                return {"state": "unbound", "is_orphan": True, "accepted_bindings": 0, "nonaccepted_bindings": 0}
            return {"state": "unavailable", "is_orphan": False, "accepted_bindings": 0, "nonaccepted_bindings": 0}
        accepted_bindings = sum(1 for trace in traces if trace.state == "accepted" and trace.freshness == "current")
        nonaccepted_bindings = len(traces) - accepted_bindings
        if accepted_bindings:
            state = "bound"
            is_orphan = False
        elif any(trace.state == "orphaned" for trace in traces):
            state = "orphaned_trace"
            is_orphan = True
        elif any(trace.state == "stale" or trace.freshness == "stale" for trace in traces):
            state = "stale_binding"
            is_orphan = True
        elif any(trace.state == "proposed" for trace in traces):
            state = "pending_review"
            is_orphan = True
        else:
            state = "unbound"
            is_orphan = True
        return {
            "state": state,
            "is_orphan": is_orphan,
            "accepted_bindings": accepted_bindings,
            "nonaccepted_bindings": nonaccepted_bindings,
        }

    def _entity_freshness_context(self, traces: Sequence[TraceLink]) -> JsonObject:
        if not traces:
            return {
                "state": "unavailable",
                "source": "local_trace_freshness",
                "trace_freshness": [],
            }
        values = [trace.freshness for trace in traces]
        return {
            "state": self._worst_freshness(values),
            "source": "local_trace_freshness",
            "trace_freshness": values,
        }

    def _entity_drift_context(self, traces: Sequence[TraceLink]) -> JsonObject:
        if not traces:
            return {
                "state": "unavailable",
                "source": "local_trace_freshness",
                "reason": "No local binding and no live Loomweave drift check was made.",
            }
        freshness = self._worst_freshness([trace.freshness for trace in traces])
        if freshness == "current":
            return {
                "state": "not_detected",
                "source": "local_trace_freshness",
                "reason": "All local trace freshness values are current.",
            }
        return {
            "state": freshness,
            "source": "local_trace_freshness",
            "reason": "At least one local trace link reports non-current freshness.",
        }

    def _worst_freshness(self, values: Sequence[str]) -> str:
        if "orphaned" in values:
            return "orphaned"
        if "stale" in values:
            return "stale"
        if "current" in values:
            return "current"
        if "unknown" in values:
            return "unknown"
        return "unknown"
