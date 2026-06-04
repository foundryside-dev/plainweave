from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from charter.envelopes import error_envelope, list_envelope, success_envelope
from charter.errors import CharterError, ErrorCode
from charter.models import (
    AcceptanceCriterion,
    Baseline,
    BaselineDiff,
    BaselineDiffItem,
    BaselineMember,
    RequirementDraft,
    RequirementRecord,
    RequirementVersion,
    TraceLink,
    TraceRef,
)
from charter.paths import charter_db_path, default_project_key, project_root
from charter.service import CharterService
from charter.store import connect, migrate, read_schema_meta


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_parser = subparsers.add_parser("init", help="Initialize a local Charter store.")
    init_parser.add_argument("--project-key", help="Stable project key for requirement IDs.")
    init_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    init_parser.set_defaults(handler=handle_init)

    doctor_parser = subparsers.add_parser("doctor", help="Report local Charter project health.")
    doctor_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    doctor_parser.set_defaults(handler=handle_doctor)

    req_parser = subparsers.add_parser("req", help="Manage local requirements.")
    req_subparsers = req_parser.add_subparsers(dest="req_command", required=True)
    _register_requirement_commands(req_subparsers)

    criterion_parser = subparsers.add_parser("criterion", help="Manage acceptance criteria.")
    criterion_subparsers = criterion_parser.add_subparsers(dest="criterion_command", required=True)
    _register_criterion_commands(criterion_subparsers)

    trace_parser = subparsers.add_parser("trace", help="Manage trace links.")
    trace_subparsers = trace_parser.add_subparsers(dest="trace_command", required=True)
    _register_trace_commands(trace_subparsers)

    baseline_parser = subparsers.add_parser("baseline", help="Manage requirement baselines.")
    baseline_subparsers = baseline_parser.add_subparsers(dest="baseline_command", required=True)
    _register_baseline_commands(baseline_subparsers)


def _register_requirement_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    add_parser = subparsers.add_parser("add", help="Create a draft requirement.")
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--statement", required=True)
    add_parser.add_argument("--actor", default="")
    add_parser.add_argument("--json", action="store_true")
    add_parser.set_defaults(handler=handle_req_add)

    edit_parser = subparsers.add_parser("edit", help="Update the active requirement draft.")
    edit_parser.add_argument("requirement_id")
    edit_parser.add_argument("--title")
    edit_parser.add_argument("--statement")
    edit_parser.add_argument("--actor", default="")
    edit_parser.add_argument("--expected-draft-revision", type=int)
    edit_parser.add_argument("--json", action="store_true")
    edit_parser.set_defaults(handler=handle_req_edit)

    show_parser = subparsers.add_parser("show", help="Show a requirement.")
    show_parser.add_argument("requirement_id")
    show_parser.add_argument("--json", action="store_true")
    show_parser.set_defaults(handler=handle_req_show)

    search_parser = subparsers.add_parser("search", help="Search requirements.")
    search_parser.add_argument("query", nargs="?")
    search_parser.add_argument("--json", action="store_true")
    search_parser.set_defaults(handler=handle_req_search)

    approve_parser = subparsers.add_parser("approve", help="Approve the active requirement draft.")
    approve_parser.add_argument("requirement_id")
    approve_parser.add_argument("--actor", default="")
    approve_parser.add_argument("--expected-version", required=True, type=int)
    approve_parser.add_argument("--idempotency-key")
    approve_parser.add_argument("--json", action="store_true")
    approve_parser.set_defaults(handler=handle_req_approve)

    supersede_parser = subparsers.add_parser("supersede", help="Supersede an approved requirement version.")
    supersede_parser.add_argument("requirement_id")
    supersede_parser.add_argument("--title", required=True)
    supersede_parser.add_argument("--statement", required=True)
    supersede_parser.add_argument("--actor", default="")
    supersede_parser.add_argument("--expected-version", required=True, type=int)
    supersede_parser.add_argument("--idempotency-key")
    supersede_parser.add_argument("--json", action="store_true")
    supersede_parser.set_defaults(handler=handle_req_supersede)

    deprecate_parser = subparsers.add_parser("deprecate", help="Deprecate a requirement.")
    deprecate_parser.add_argument("requirement_id")
    deprecate_parser.add_argument("--actor", default="")
    deprecate_parser.add_argument("--expected-version", required=True, type=int)
    deprecate_parser.add_argument("--idempotency-key")
    deprecate_parser.add_argument("--json", action="store_true")
    deprecate_parser.set_defaults(handler=handle_req_deprecate)

    reject_parser = subparsers.add_parser("reject", help="Reject the active requirement draft.")
    reject_parser.add_argument("requirement_id")
    reject_parser.add_argument("--actor", default="")
    reject_parser.add_argument("--expected-version", required=True, type=int)
    reject_parser.add_argument("--reason", required=True)
    reject_parser.add_argument("--json", action="store_true")
    reject_parser.set_defaults(handler=handle_req_reject)


def _register_criterion_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    add_parser = subparsers.add_parser("add", help="Add an acceptance criterion to the active draft.")
    add_parser.add_argument("requirement_id")
    add_parser.add_argument("--text", required=True)
    add_parser.add_argument("--actor", default="")
    add_parser.add_argument("--position", type=int)
    add_parser.add_argument("--json", action="store_true")
    add_parser.set_defaults(handler=handle_criterion_add)

    list_parser = subparsers.add_parser("list", help="List acceptance criteria for a requirement.")
    list_parser.add_argument("requirement_id")
    list_parser.add_argument("--version", type=int)
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=handle_criterion_list)


def _register_trace_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    propose_parser = subparsers.add_parser("propose", help="Propose a trace link.")
    propose_parser.add_argument("--from-kind", required=True)
    propose_parser.add_argument("--from-id", required=True)
    propose_parser.add_argument("--relation", required=True)
    propose_parser.add_argument("--to-kind", required=True)
    propose_parser.add_argument("--to-id", required=True)
    propose_parser.add_argument("--actor", default="")
    propose_parser.add_argument("--confidence", type=float)
    propose_parser.add_argument("--json", action="store_true")
    propose_parser.set_defaults(handler=handle_trace_propose)

    accept_parser = subparsers.add_parser("accept", help="Accept a proposed trace link.")
    accept_parser.add_argument("link_id")
    accept_parser.add_argument("--actor", default="")
    accept_parser.add_argument("--json", action="store_true")
    accept_parser.set_defaults(handler=handle_trace_accept)

    reject_parser = subparsers.add_parser("reject", help="Reject a proposed trace link.")
    reject_parser.add_argument("link_id")
    reject_parser.add_argument("--actor", default="")
    reject_parser.add_argument("--reason", required=True)
    reject_parser.add_argument("--json", action="store_true")
    reject_parser.set_defaults(handler=handle_trace_reject)

    list_parser = subparsers.add_parser("list", help="List trace links.")
    list_parser.add_argument("--requirement")
    list_parser.add_argument("--state")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=handle_trace_list)


def _register_baseline_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    create_parser = subparsers.add_parser("create", help="Create a locked baseline of approved requirements.")
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--description")
    create_parser.add_argument("--actor", default="")
    create_parser.add_argument("--json", action="store_true")
    create_parser.set_defaults(handler=handle_baseline_create)

    show_parser = subparsers.add_parser("show", help="Show a baseline.")
    show_parser.add_argument("baseline_id")
    show_parser.add_argument("--json", action="store_true")
    show_parser.set_defaults(handler=handle_baseline_show)

    list_parser = subparsers.add_parser("list", help="List baselines.")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=handle_baseline_list)

    diff_parser = subparsers.add_parser("diff", help="Diff a baseline against current approved requirements.")
    diff_parser.add_argument("baseline_id")
    diff_parser.add_argument("--json", action="store_true")
    diff_parser.set_defaults(handler=handle_baseline_diff)


def handle_init(args: argparse.Namespace) -> int:
    root = project_root()
    project_key = str(args.project_key or default_project_key(root))
    result = initialize_project(root, project_key)
    if bool(args.json):
        print(json.dumps(success_envelope("loom.charter.init.v1", result, project=project_key)))
    else:
        status = "created" if result["created"] else "already initialized"
        print(f"Charter store {status}: {result['db_path']}")
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    root = project_root()
    result = inspect_project(root)
    project = result["project_key"] if isinstance(result["project_key"], str) else None
    if bool(args.json):
        print(json.dumps(success_envelope("loom.charter.doctor.v1", result, project=project)))
    else:
        status = "initialized" if result["initialized"] else "not initialized"
        print(f"Charter project {status}: {result['db_path']}")
    return 0


def handle_req_add(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.requirement_draft.v1",
        lambda service: _draft_dict(
            service.create_requirement(str(args.title), str(args.statement), actor=str(args.actor))
        ),
    )


def handle_req_edit(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.requirement_draft.v1",
        lambda service: _draft_dict(
            service.update_draft(
                str(args.requirement_id),
                actor=str(args.actor),
                title=args.title if isinstance(args.title, str) else None,
                statement=args.statement if isinstance(args.statement, str) else None,
                expected_draft_revision=args.expected_draft_revision
                if isinstance(args.expected_draft_revision, int)
                else None,
            )
        ),
    )


def handle_req_show(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.requirement.v1",
        lambda service: _record_dict(service.get_requirement(str(args.requirement_id))),
    )


def handle_req_search(args: argparse.Namespace) -> int:
    return _handle_service_list(
        args,
        "loom.charter.requirement_list.v1",
        lambda service: [_record_dict(item) for item in service.search_requirements(_optional_str(args.query))],
    )


def handle_req_approve(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.requirement_version.v1",
        lambda service: _version_dict(
            service.approve_requirement(
                str(args.requirement_id),
                actor=str(args.actor),
                expected_version=int(args.expected_version),
                idempotency_key=_optional_str(args.idempotency_key),
            )
        ),
    )


def handle_req_supersede(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.requirement_version.v1",
        lambda service: _version_dict(
            service.supersede_requirement(
                str(args.requirement_id),
                title=str(args.title),
                statement=str(args.statement),
                actor=str(args.actor),
                expected_version=int(args.expected_version),
                idempotency_key=_optional_str(args.idempotency_key),
            )
        ),
    )


def handle_req_deprecate(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.requirement.v1",
        lambda service: _record_dict(
            service.deprecate_requirement(
                str(args.requirement_id),
                actor=str(args.actor),
                expected_version=int(args.expected_version),
                idempotency_key=_optional_str(args.idempotency_key),
            )
        ),
    )


def handle_req_reject(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.requirement.v1",
        lambda service: _record_dict(
            service.reject_requirement(
                str(args.requirement_id),
                actor=str(args.actor),
                expected_version=int(args.expected_version),
                reason=str(args.reason),
            )
        ),
    )


def handle_criterion_add(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.acceptance_criterion.v1",
        lambda service: _criterion_dict(
            service.add_acceptance_criterion(
                str(args.requirement_id),
                str(args.text),
                actor=str(args.actor),
                position=args.position if isinstance(args.position, int) else None,
            )
        ),
    )


def handle_criterion_list(args: argparse.Namespace) -> int:
    return _handle_service_list(
        args,
        "loom.charter.acceptance_criterion_list.v1",
        lambda service: [
            _criterion_dict(item)
            for item in service.list_acceptance_criteria(
                str(args.requirement_id),
                version=args.version if isinstance(args.version, int) else None,
            )
        ],
    )


def handle_trace_propose(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.trace_link.v1",
        lambda service: _trace_dict(
            service.propose_trace_link(
                TraceRef(str(args.from_kind), str(args.from_id)),
                str(args.relation),
                TraceRef(str(args.to_kind), str(args.to_id)),
                actor=str(args.actor),
                confidence=args.confidence if isinstance(args.confidence, float) else None,
            )
        ),
    )


def handle_trace_accept(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.trace_link.v1",
        lambda service: _trace_dict(service.accept_trace_link(str(args.link_id), actor=str(args.actor))),
    )


def handle_trace_reject(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.trace_link.v1",
        lambda service: _trace_dict(
            service.reject_trace_link(str(args.link_id), actor=str(args.actor), reason=str(args.reason))
        ),
    )


def handle_trace_list(args: argparse.Namespace) -> int:
    requirement_id = _optional_str(args.requirement)
    state = _optional_str(args.state)
    return _handle_service_list(
        args,
        "loom.charter.trace_link_list.v1",
        lambda service: [_trace_dict(item) for item in service.trace_for(requirement_id=requirement_id, state=state)],
    )


def handle_baseline_create(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.baseline.v1",
        lambda service: _baseline_dict(
            service.create_baseline(
                str(args.name),
                actor=str(args.actor),
                description=args.description if isinstance(args.description, str) else None,
            )
        ),
    )


def handle_baseline_show(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.baseline.v1",
        lambda service: _baseline_dict(service.show_baseline(str(args.baseline_id))),
    )


def handle_baseline_list(args: argparse.Namespace) -> int:
    return _handle_service_list(
        args,
        "loom.charter.baseline_list.v1",
        lambda service: [_baseline_dict(item) for item in service.list_baselines()],
    )


def handle_baseline_diff(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "loom.charter.baseline_diff.v1",
        lambda service: _baseline_diff_dict(service.diff_baseline(str(args.baseline_id))),
    )


def initialize_project(root: Path, project_key: str) -> dict[str, object]:
    db_path = charter_db_path(root)
    created = not db_path.exists()
    migrate(db_path, project_key=project_key)
    with connect(db_path) as connection:
        metadata = read_schema_meta(connection)
    return {
        "created": created,
        "project_key": metadata["project_key"],
        "schema_version": int(metadata["schema_version"]),
        "db_path": str(db_path),
    }


def inspect_project(root: Path) -> dict[str, object]:
    db_path = charter_db_path(root)
    if not db_path.exists():
        return {
            "initialized": False,
            "project_key": None,
            "schema_version": None,
            "db_path": str(db_path),
        }
    with connect(db_path) as connection:
        metadata = read_schema_meta(connection)
    return {
        "initialized": True,
        "project_key": metadata.get("project_key"),
        "schema_version": int(metadata["schema_version"]) if "schema_version" in metadata else None,
        "db_path": str(db_path),
    }


def _handle_service_result(
    args: argparse.Namespace,
    schema: str,
    action: Any,
) -> int:
    return _handle_output(
        args,
        lambda service: success_envelope(schema, action(service), project=_current_project_key()),
    )


def _handle_service_list(
    args: argparse.Namespace,
    schema: str,
    action: Any,
) -> int:
    return _handle_output(args, lambda service: list_envelope(schema, action(service), project=_current_project_key()))


def _handle_output(args: argparse.Namespace, action: Any) -> int:
    try:
        envelope = action(_service())
    except CharterError as exc:
        return _emit_error(args, exc)
    if bool(args.json):
        print(json.dumps(envelope))
    else:
        print(json.dumps(envelope["data"]))
    return 0


def _emit_error(args: argparse.Namespace, exc: CharterError) -> int:
    envelope = error_envelope(
        exc.code,
        exc.message,
        recoverable=exc.recoverable,
        hint=exc.hint,
        details=exc.details,
        project=_current_project_key(),
    )
    if bool(args.json):
        print(json.dumps(envelope))
    else:
        print(f"{exc.code.value}: {exc.message}")
    return 4 if exc.code == ErrorCode.INTERNAL else 2


def _service() -> CharterService:
    db_path = charter_db_path(project_root())
    if not db_path.exists():
        raise CharterError(
            ErrorCode.NOT_FOUND,
            "Charter project is not initialized",
            recoverable=True,
            hint="Run `charter init` in this project and retry.",
            details={"db_path": str(db_path)},
        )
    return CharterService(db_path)


def _current_project_key() -> str | None:
    metadata = inspect_project(project_root())
    return metadata["project_key"] if isinstance(metadata["project_key"], str) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _draft_dict(draft: RequirementDraft) -> dict[str, object]:
    return {
        "requirement_id": draft.requirement_id,
        "id": draft.id,
        "stable_id": draft.stable_id,
        "draft_id": draft.draft_id,
        "base_version": draft.base_version,
        "draft_revision": draft.draft_revision,
        "title": draft.title,
        "statement": draft.statement,
        "status": draft.status,
    }


def _version_dict(version: RequirementVersion) -> dict[str, object]:
    return {
        "requirement_id": version.requirement_id,
        "id": version.id,
        "stable_id": version.stable_id,
        "version": version.version,
        "title": version.title,
        "statement": version.statement,
        "statement_hash": version.statement_hash,
        "status": version.status,
        "approved_by": version.approved_by,
        "approved_at": version.approved_at,
    }


def _record_dict(record: RequirementRecord) -> dict[str, object]:
    return {
        "requirement_id": record.requirement_id,
        "id": record.id,
        "stable_id": record.stable_id,
        "current_version": record.current_version,
        "active_draft_id": record.active_draft_id,
        "status": record.status,
        "current_version_record": _version_dict(record.current_version_record)
        if record.current_version_record is not None
        else None,
    }


def _criterion_dict(criterion: AcceptanceCriterion) -> dict[str, object]:
    return {
        "id": criterion.id,
        "requirement_id": criterion.requirement_id,
        "draft_id": criterion.draft_id,
        "version": criterion.version,
        "position": criterion.position,
        "text": criterion.text,
        "status": criterion.status,
        "created_by": criterion.created_by,
        "created_at": criterion.created_at,
    }


def _trace_dict(link: TraceLink) -> dict[str, object]:
    return {
        "id": link.id,
        "state": link.state,
        "from": {"kind": link.from_ref.kind, "id": link.from_ref.id},
        "relation": link.relation,
        "to": {"kind": link.to_ref.kind, "id": link.to_ref.id},
        "authority": link.authority,
        "freshness": link.freshness,
        "confidence": link.confidence,
        "created_by": link.created_by,
        "accepted_by": link.accepted_by,
        "target_snapshot": link.target_snapshot,
    }


def _baseline_member_dict(member: BaselineMember) -> dict[str, object]:
    return {
        "requirement_id": member.requirement_id,
        "id": member.id,
        "stable_id": member.stable_id,
        "version": member.version,
        "statement_hash": member.statement_hash,
        "status_at_baseline": member.status_at_baseline,
    }


def _baseline_dict(baseline: Baseline) -> dict[str, object]:
    return {
        "id": baseline.id,
        "name": baseline.name,
        "description": baseline.description,
        "locked": baseline.locked,
        "created_by": baseline.created_by,
        "created_at": baseline.created_at,
        "members": [_baseline_member_dict(member) for member in baseline.members],
    }


def _baseline_diff_item_dict(item: BaselineDiffItem) -> dict[str, object]:
    return {
        "requirement_id": item.requirement_id,
        "id": item.id,
        "stable_id": item.stable_id,
        "baseline_version": item.baseline_version,
        "current_version": item.current_version,
        "status": item.status,
        "baseline_statement_hash": item.baseline_statement_hash,
        "current_statement_hash": item.current_statement_hash,
    }


def _baseline_diff_dict(diff: BaselineDiff) -> dict[str, object]:
    return {
        "baseline_id": diff.baseline_id,
        "summary": diff.summary,
        "items": [_baseline_diff_item_dict(item) for item in diff.items],
    }
