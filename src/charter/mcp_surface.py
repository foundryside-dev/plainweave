from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from charter.cli_commands import (
    _baseline_dict,
    _baseline_diff_dict,
    _current_project_key,
    _dossier_dict,
    _record_dict,
    _requirement_verification_status_dict,
    _trace_dict,
    inspect_project,
)
from charter.envelopes import error_envelope, success_envelope
from charter.errors import CharterError, ErrorCode
from charter.paths import charter_db_path, project_root
from charter.service import CharterService

JsonObject = dict[str, object]

MCP_TOOL_METADATA: dict[str, JsonObject] = {
    "charter_baseline_diff": {
        "name": "charter_baseline_diff",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local baseline drift facts; it does not make release decisions.",
    },
    "charter_baseline_get": {
        "name": "charter_baseline_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns one local immutable baseline snapshot.",
    },
    "charter_baseline_list": {
        "name": "charter_baseline_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Lists local immutable baselines without creating or changing snapshots.",
    },
    "charter_project_context_get": {
        "name": "charter_project_context_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Reports local Charter project context and read-only capability metadata.",
    },
    "charter_requirement_dossier_get": {
        "name": "charter_requirement_dossier_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns the local computed dossier; live peer calls are not made in P0.",
    },
    "charter_requirement_get": {
        "name": "charter_requirement_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": (
            "Returns one local requirement record; active drafts remain separate from approved truth."
        ),
    },
    "charter_requirement_search": {
        "name": "charter_requirement_search",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local requirement records without changing authority state.",
    },
    "charter_trace_link_list": {
        "name": "charter_trace_link_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns local trace links with state, authority, and freshness preserved.",
    },
    "charter_verification_status_get": {
        "name": "charter_verification_status_get",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Returns derived local verification status and evidence freshness.",
    },
    "charter_verification_status_list": {
        "name": "charter_verification_status_list",
        "mutates": False,
        "local_only": True,
        "peer_side_effects": [],
        "authority_boundary": "Lists local unverified or stale verification statuses without recording evidence.",
    },
}

MCP_RESOURCE_URIS = [
    "charter://project/context",
    "charter://contracts/weft.charter.error.v1",
    "charter://contracts/weft.charter.requirement_dossier.v1",
    "charter://contracts/weft.charter.baseline.v1",
    "charter://contracts/weft.charter.baseline_diff.v1",
    "charter://contracts/weft.charter.requirement_verification_status.v1",
]

REQUIREMENT_STATUS_FILTERS = {"draft", "approved", "deprecated", "rejected"}
TRACE_STATE_FILTERS = {"proposed", "accepted", "rejected", "stale", "orphaned"}

CONTRACT_RESOURCES: dict[str, JsonObject] = {
    "charter://contracts/weft.charter.error.v1": {
        "contract": "weft.charter.error.v1",
        "required_keys": ["schema", "ok", "error", "warnings", "meta"],
        "recovery": "Switch on error.code and use error.hint; do not parse message text.",
    },
    "charter://contracts/weft.charter.requirement_dossier.v1": {
        "contract": "weft.charter.requirement_dossier.v1",
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
        "authority_boundary": "Computed from local Charter state only in P0.",
    },
    "charter://contracts/weft.charter.baseline.v1": {
        "contract": "weft.charter.baseline.v1",
        "authority_boundary": "Immutable local snapshot of approved/deprecated requirement versions.",
    },
    "charter://contracts/weft.charter.baseline_diff.v1": {
        "contract": "weft.charter.baseline_diff.v1",
        "statuses": ["unchanged", "changed", "missing_current", "new_since_baseline", "superseded_since_baseline"],
        "authority_boundary": "Diff facts only; not a release-readiness verdict.",
    },
    "charter://contracts/weft.charter.requirement_verification_status.v1": {
        "contract": "weft.charter.requirement_verification_status.v1",
        "statuses": ["satisfied", "unsatisfied", "unverified", "stale", "unknown", "waived"],
        "authority_boundary": "Derived local status with reason codes and evidence freshness.",
    },
}


class CharterMcpSurface:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or project_root()

    def charter_project_context_get(self, *, include_contracts: bool = False) -> JsonObject:
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
        return success_envelope("weft.charter.project_context.v1", context, project=project)

    def charter_requirement_search(
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
            "weft.charter.requirement_list.v1",
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

    def charter_requirement_get(self, requirement_id: str) -> JsonObject:
        return self._result(
            "weft.charter.requirement.v1",
            lambda service: _record_dict(service.get_requirement(requirement_id)),
        )

    def charter_requirement_dossier_get(self, requirement_id: str) -> JsonObject:
        return self._result(
            "weft.charter.requirement_dossier.v1",
            lambda service: _dossier_dict(service.requirement_dossier(requirement_id)),
        )

    def charter_trace_link_list(
        self,
        *,
        requirement_id: str | None = None,
        state_filter: str | None = None,
        relation_filter: str | None = None,
        direction: str = "both",
        limit: int = 50,
        offset: int = 0,
    ) -> JsonObject:
        def action(service: CharterService) -> JsonObject:
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

        return self._result("weft.charter.trace_link_list.v1", action, list_result=True)

    def charter_baseline_list(self, *, limit: int = 25, offset: int = 0) -> JsonObject:
        return self._result(
            "weft.charter.baseline_list.v1",
            lambda service: self._list(
                [_baseline_dict(item) for item in service.list_baselines()],
                limit=limit,
                offset=offset,
            ),
            list_result=True,
        )

    def charter_baseline_get(self, baseline_id: str) -> JsonObject:
        return self._result(
            "weft.charter.baseline.v1",
            lambda service: _baseline_dict(service.show_baseline(baseline_id)),
        )

    def charter_baseline_diff(self, baseline_id: str) -> JsonObject:
        return self._result(
            "weft.charter.baseline_diff.v1",
            lambda service: _baseline_diff_dict(service.diff_baseline(baseline_id)),
        )

    def charter_verification_status_get(self, requirement_id: str) -> JsonObject:
        return self._result(
            "weft.charter.requirement_verification_status.v1",
            lambda service: _requirement_verification_status_dict(service.verification_status(requirement_id)),
        )

    def charter_verification_status_list(
        self,
        *,
        status_filter: str,
        limit: int = 25,
        offset: int = 0,
    ) -> JsonObject:
        def action(service: CharterService) -> JsonObject:
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

        return self._result("weft.charter.requirement_verification_status_list.v1", action, list_result=True)

    def read_resource(self, uri: str) -> JsonObject:
        if uri == "charter://project/context":
            return self.charter_project_context_get(include_contracts=True)
        if uri not in CONTRACT_RESOURCES:
            return self._error(
                CharterError(
                    ErrorCode.NOT_FOUND,
                    "MCP resource was not found",
                    recoverable=True,
                    hint="Use one of the advertised Charter MCP resource URIs.",
                    details={"uri": uri, "resources": list(MCP_RESOURCE_URIS)},
                )
            )
        return success_envelope(
            "weft.charter.mcp_contract_resource.v1",
            {"uri": uri, **CONTRACT_RESOURCES[uri]},
            project=self._project_key(),
        )

    def _result(self, schema: str, action: Any, *, list_result: bool = False) -> JsonObject:
        try:
            data = action(self._service())
            if list_result:
                return success_envelope(schema, data, project=self._project_key())
            return success_envelope(schema, data, project=self._project_key())
        except CharterError as exc:
            return self._error(exc)

    def _service(self) -> CharterService:
        db_path = charter_db_path(self.root)
        if not db_path.exists():
            raise CharterError(
                ErrorCode.NOT_FOUND,
                "Charter project is not initialized",
                recoverable=True,
                hint="Run `charter init` in this project and retry.",
                details={"db_path": str(db_path)},
            )
        return CharterService(db_path)

    def _project_key(self) -> str | None:
        if self.root == project_root():
            return _current_project_key()
        metadata = inspect_project(self.root)
        return metadata["project_key"] if isinstance(metadata["project_key"], str) else None

    def _error(self, exc: CharterError) -> JsonObject:
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
            raise CharterError(
                ErrorCode.VALIDATION,
                "limit must be between 1 and 100",
                recoverable=True,
                hint="Pass a limit from 1 through 100.",
                details={"limit": limit},
            )
        if offset < 0:
            raise CharterError(
                ErrorCode.VALIDATION,
                "offset must be non-negative",
                recoverable=True,
                hint="Pass offset 0 or a next_offset returned by a list tool.",
                details={"offset": offset},
            )

    def _validate_choice(self, value: str, allowed: set[str], field: str) -> None:
        if value not in allowed:
            raise CharterError(
                ErrorCode.VALIDATION,
                f"{field} is not supported",
                recoverable=True,
                hint=f"Use one of: {', '.join(sorted(allowed))}.",
                details={field: value, "allowed": sorted(allowed)},
            )

    def _validate_filter(self, value: str, allowed: set[str], field: str) -> JsonObject | None:
        try:
            self._validate_choice(value, allowed, field)
        except CharterError as exc:
            return self._error(exc)
        return None

    def _requirement_refs(self, service: CharterService, requirement_id: str | None) -> set[str]:
        if requirement_id is None:
            return set()
        record = service.get_requirement(requirement_id)
        return {record.requirement_id, record.id, record.stable_id}

    def _trace_ref_matches(self, value: str, refs: set[str]) -> bool:
        if value in refs:
            return True
        prefix, separator, _version = value.rpartition("@")
        return separator == "@" and prefix in refs
