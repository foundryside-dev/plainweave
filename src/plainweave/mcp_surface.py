from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from plainweave.cli_commands import (
    _baseline_dict,
    _baseline_diff_dict,
    _corpus_entry_dict,
    _current_project_key,
    _dossier_dict,
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
from plainweave.paths import plainweave_db_path, project_root
from plainweave.service import PlainweaveService

JsonObject = dict[str, object]

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
    "plainweave_project_context_get": {
        "name": "plainweave_project_context_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Reports local Plainweave project context and read-only capability metadata.",
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
}

MCP_RESOURCE_URIS = [
    "plainweave://project/context",
    "plainweave://contracts/weft.plainweave.error.v1",
    "plainweave://contracts/weft.plainweave.requirement_dossier.v1",
    "plainweave://contracts/weft.plainweave.baseline.v1",
    "plainweave://contracts/weft.plainweave.baseline_diff.v1",
    "plainweave://contracts/weft.plainweave.requirement_verification_status.v1",
    "plainweave://contracts/weft.plainweave.sei_binding.v1",
    "plainweave://contracts/weft.plainweave.intent_orphans.v1",
    "plainweave://contracts/weft.plainweave.intent_trace.v1",
    "plainweave://contracts/weft.plainweave.intent_corpus.v1",
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
        return PlainweaveService(db_path)

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
