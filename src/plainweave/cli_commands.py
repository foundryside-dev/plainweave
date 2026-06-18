from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from plainweave.envelopes import error_envelope, list_envelope, success_envelope
from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.models import (
    AcceptanceCriterion,
    Actor,
    Baseline,
    BaselineDiff,
    BaselineDiffItem,
    BaselineMember,
    DossierAcceptanceCriteriaSection,
    DossierAuthoritySummary,
    DossierBaselineExposure,
    DossierBaselineExposureItem,
    DossierComputedGap,
    DossierNextAction,
    DossierPeerFacts,
    DossierRequirementSection,
    DossierTraceSection,
    RequirementDossier,
    RequirementDraft,
    RequirementRecord,
    RequirementVerificationStatus,
    RequirementVersion,
    TraceLink,
    TraceRef,
    VerificationEvidence,
    VerificationMethod,
    VerificationReason,
)
from plainweave.paths import default_project_key, plainweave_db_path, project_root
from plainweave.service import PlainweaveService
from plainweave.store import connect, migrate, read_schema_meta


def register_commands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init_parser = subparsers.add_parser("init", help="Initialize a local Plainweave store.")
    init_parser.add_argument("--project-key", help="Stable project key for requirement IDs.")
    init_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    init_parser.set_defaults(handler=handle_init)

    doctor_parser = subparsers.add_parser("doctor", help="Report local Plainweave project health.")
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

    actor_parser = subparsers.add_parser("actor", help="Manage the project actor registry.")
    actor_subparsers = actor_parser.add_subparsers(dest="actor_command", required=True)
    _register_actor_commands(actor_subparsers)

    verify_parser = subparsers.add_parser("verify", help="Manage verification methods and evidence.")
    verify_subparsers = verify_parser.add_subparsers(dest="verify_command", required=True)
    _register_verify_commands(verify_subparsers)

    status_parser = subparsers.add_parser("status", help="Report requirement verification status.")
    status_subparsers = status_parser.add_subparsers(dest="status_command", required=True)
    _register_status_commands(status_subparsers)

    dossier_parser = subparsers.add_parser("dossier", help="Show a requirement dossier.")
    dossier_parser.add_argument("requirement_id")
    dossier_parser.add_argument("--json", action="store_true", help="Emit a JSON envelope.")
    dossier_parser.set_defaults(handler=handle_dossier)


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


def _register_actor_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    register_parser = subparsers.add_parser("register", help="Register an actor identity and its attestation kind.")
    register_parser.add_argument("actor_id")
    register_parser.add_argument("--kind", required=True, choices=["human", "agent", "attester"])
    register_parser.add_argument("--display-name", default=None)
    register_parser.add_argument("--actor", default="")
    register_parser.add_argument("--json", action="store_true")
    register_parser.set_defaults(handler=handle_actor_register)


def _register_verify_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    method_parser = subparsers.add_parser("method", help="Manage verification methods.")
    method_subparsers = method_parser.add_subparsers(dest="verify_method_command", required=True)

    add_parser = method_subparsers.add_parser("add", help="Add a verification method.")
    add_parser.add_argument("requirement_id")
    add_parser.add_argument("--method", required=True)
    add_parser.add_argument("--target", required=True)
    add_parser.add_argument("--actor", default="")
    add_parser.add_argument("--json", action="store_true")
    add_parser.set_defaults(handler=handle_verify_method_add)

    evidence_parser = subparsers.add_parser("evidence", help="Manage verification evidence.")
    evidence_subparsers = evidence_parser.add_subparsers(dest="verify_evidence_command", required=True)

    record_parser = evidence_subparsers.add_parser("record", help="Record verification evidence.")
    record_parser.add_argument("method_id")
    record_parser.add_argument("--status", required=True)
    record_parser.add_argument("--evidence-ref", required=True)
    record_parser.add_argument("--actor", default="")
    record_parser.add_argument("--json", action="store_true")
    record_parser.set_defaults(handler=handle_verify_evidence_record)

    status_parser = subparsers.add_parser("status", help="Show verification status for a requirement.")
    status_parser.add_argument("requirement_id")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(handler=handle_verify_status)


def _register_status_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    requirement_parser = subparsers.add_parser("requirement", help="Show verification status for a requirement.")
    requirement_parser.add_argument("requirement_id")
    requirement_parser.add_argument("--json", action="store_true")
    requirement_parser.set_defaults(handler=handle_status_requirement)

    unverified_parser = subparsers.add_parser("unverified", help="List unverified requirements.")
    unverified_parser.add_argument("--json", action="store_true")
    unverified_parser.set_defaults(handler=handle_status_unverified)

    stale_parser = subparsers.add_parser("stale", help="List requirements with stale verification evidence.")
    stale_parser.add_argument("--json", action="store_true")
    stale_parser.set_defaults(handler=handle_status_stale)


def handle_init(args: argparse.Namespace) -> int:
    root = project_root()
    project_key = str(args.project_key or default_project_key(root))
    result = initialize_project(root, project_key)
    if bool(args.json):
        print(json.dumps(success_envelope("weft.plainweave.init.v1", result, project=project_key)))
    else:
        status = "created" if result["created"] else "already initialized"
        print(f"Plainweave store {status}: {result['db_path']}")
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    root = project_root()
    result = inspect_project(root)
    project = result["project_key"] if isinstance(result["project_key"], str) else None
    if bool(args.json):
        print(json.dumps(success_envelope("weft.plainweave.doctor.v1", result, project=project)))
    else:
        status = "initialized" if result["initialized"] else "not initialized"
        print(f"Plainweave project {status}: {result['db_path']}")
    return 0


def handle_req_add(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.requirement_draft.v1",
        lambda service: _draft_dict(
            service.create_requirement(str(args.title), str(args.statement), actor=str(args.actor))
        ),
    )


def handle_req_edit(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.requirement_draft.v1",
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
        "weft.plainweave.requirement.v1",
        lambda service: _record_dict(service.get_requirement(str(args.requirement_id))),
    )


def handle_req_search(args: argparse.Namespace) -> int:
    return _handle_service_list(
        args,
        "weft.plainweave.requirement_list.v1",
        lambda service: [_record_dict(item) for item in service.search_requirements(_optional_str(args.query))],
    )


def handle_req_approve(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.requirement_version.v1",
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
        "weft.plainweave.requirement_version.v1",
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
        "weft.plainweave.requirement.v1",
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
        "weft.plainweave.requirement.v1",
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
        "weft.plainweave.acceptance_criterion.v1",
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
        "weft.plainweave.acceptance_criterion_list.v1",
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
        "weft.plainweave.trace_link.v1",
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
        "weft.plainweave.trace_link.v1",
        lambda service: _trace_dict(service.accept_trace_link(str(args.link_id), actor=str(args.actor))),
    )


def handle_trace_reject(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.trace_link.v1",
        lambda service: _trace_dict(
            service.reject_trace_link(str(args.link_id), actor=str(args.actor), reason=str(args.reason))
        ),
    )


def handle_trace_list(args: argparse.Namespace) -> int:
    requirement_id = _optional_str(args.requirement)
    state = _optional_str(args.state)
    return _handle_service_list(
        args,
        "weft.plainweave.trace_link_list.v1",
        lambda service: [_trace_dict(item) for item in service.trace_for(requirement_id=requirement_id, state=state)],
    )


def handle_baseline_create(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.baseline.v1",
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
        "weft.plainweave.baseline.v1",
        lambda service: _baseline_dict(service.show_baseline(str(args.baseline_id))),
    )


def handle_baseline_list(args: argparse.Namespace) -> int:
    return _handle_service_list(
        args,
        "weft.plainweave.baseline_list.v1",
        lambda service: [_baseline_dict(item) for item in service.list_baselines()],
    )


def handle_baseline_diff(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.baseline_diff.v1",
        lambda service: _baseline_diff_dict(service.diff_baseline(str(args.baseline_id))),
    )


def handle_actor_register(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.actor.v1",
        lambda service: _actor_dict(
            service.register_actor(
                str(args.actor_id),
                kind=str(args.kind),
                display_name=args.display_name if args.display_name is None else str(args.display_name),
                actor=str(args.actor),
            )
        ),
    )


def handle_verify_method_add(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.verification_method.v1",
        lambda service: _verification_method_dict(
            service.add_verification_method(
                str(args.requirement_id),
                method=str(args.method),
                target=str(args.target),
                actor=str(args.actor),
            )
        ),
    )


def handle_verify_evidence_record(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.verification_evidence.v1",
        lambda service: _verification_evidence_dict(
            service.record_verification_evidence(
                str(args.method_id),
                status=str(args.status),
                evidence_ref=str(args.evidence_ref),
                actor=str(args.actor),
            )
        ),
    )


def handle_verify_status(args: argparse.Namespace) -> int:
    return _handle_service_result(
        args,
        "weft.plainweave.requirement_verification_status.v1",
        lambda service: _requirement_verification_status_dict(service.verification_status(str(args.requirement_id))),
    )


def handle_status_requirement(args: argparse.Namespace) -> int:
    return handle_verify_status(args)


def handle_status_unverified(args: argparse.Namespace) -> int:
    return _handle_service_list(
        args,
        "weft.plainweave.requirement_verification_status_list.v1",
        lambda service: [
            _requirement_verification_status_dict(item) for item in service.list_unverified_requirements()
        ],
    )


def handle_status_stale(args: argparse.Namespace) -> int:
    return _handle_service_list(
        args,
        "weft.plainweave.requirement_verification_status_list.v1",
        lambda service: [_requirement_verification_status_dict(item) for item in service.list_stale_requirements()],
    )


def handle_dossier(args: argparse.Namespace) -> int:
    try:
        dossier = _service().requirement_dossier(str(args.requirement_id))
    except PlainweaveError as exc:
        return _emit_error(args, exc)
    dossier_data = _dossier_dict(dossier)
    if bool(args.json):
        print(
            json.dumps(
                success_envelope(
                    "weft.plainweave.requirement_dossier.v1",
                    dossier_data,
                    project=_current_project_key(),
                )
            )
        )
    else:
        print(_render_dossier(dossier_data))
    return 0


def initialize_project(root: Path, project_key: str) -> dict[str, object]:
    db_path = plainweave_db_path(root)
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
    db_path = plainweave_db_path(root)
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
    except PlainweaveError as exc:
        return _emit_error(args, exc)
    if bool(args.json):
        print(json.dumps(envelope))
    else:
        print(json.dumps(envelope["data"]))
    return 0


def _emit_error(args: argparse.Namespace, exc: PlainweaveError) -> int:
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


def _service() -> PlainweaveService:
    db_path = plainweave_db_path(project_root())
    if not db_path.exists():
        raise PlainweaveError(
            ErrorCode.NOT_FOUND,
            "Plainweave project is not initialized",
            recoverable=True,
            hint="Run `plainweave init` in this project and retry.",
            details={"db_path": str(db_path)},
        )
    return PlainweaveService(db_path)


def _current_project_key() -> str | None:
    metadata = inspect_project(project_root())
    return metadata["project_key"] if isinstance(metadata["project_key"], str) else None


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _actor_dict(actor: Actor) -> dict[str, object]:
    return {
        "actor_id": actor.actor_id,
        "kind": actor.kind,
        "display_name": actor.display_name,
    }


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


def _verification_method_dict(method: VerificationMethod) -> dict[str, object]:
    return {
        "id": method.id,
        "requirement_id": method.requirement_id,
        "requirement_version": method.requirement_version,
        "method": method.method,
        "target": method.target,
        "status": method.status,
        "created_by": method.created_by,
        "created_at": method.created_at,
    }


def _verification_evidence_dict(evidence: VerificationEvidence) -> dict[str, object]:
    return {
        "id": evidence.id,
        "method_id": evidence.method_id,
        "requirement_id": evidence.requirement_id,
        "requirement_version": evidence.requirement_version,
        "status": evidence.status,
        "evidence_ref": evidence.evidence_ref,
        "authority": evidence.authority,
        "freshness": evidence.freshness,
        "recorded_by": evidence.recorded_by,
        "recorded_at": evidence.recorded_at,
        "payload": evidence.payload,
    }


def _verification_reason_dict(reason: VerificationReason) -> dict[str, object]:
    return {
        "code": reason.code,
        "message": reason.message,
        "evidence_id": reason.evidence_id,
    }


def _verification_evidence_summary_dict(evidence: VerificationEvidence) -> dict[str, object]:
    return {
        "id": evidence.id,
        "method_id": evidence.method_id,
        "status": evidence.status,
        "authority": evidence.authority,
        "freshness": evidence.freshness,
        "evidence_ref": evidence.evidence_ref,
    }


def _requirement_verification_status_dict(status: RequirementVerificationStatus) -> dict[str, object]:
    return {
        "requirement_id": status.requirement_id,
        "id": status.id,
        "stable_id": status.stable_id,
        "current_version": status.current_version,
        "status": status.status,
        "reasons": [_verification_reason_dict(reason) for reason in status.reasons],
        "current_evidence": [_verification_evidence_summary_dict(evidence) for evidence in status.current_evidence],
        "stale_evidence": [_verification_evidence_summary_dict(evidence) for evidence in status.stale_evidence],
    }


def _dossier_authority_summary_dict(summary: DossierAuthoritySummary) -> dict[str, object]:
    return {
        "status": summary.status,
        "current_approved_version": summary.current_approved_version,
        "current_statement_hash": summary.current_statement_hash,
        "has_active_draft": summary.has_active_draft,
        "active_draft_id": summary.active_draft_id,
        "verification_status": summary.verification_status,
        "baseline_count": summary.baseline_count,
    }


def _dossier_requirement_section_dict(section: DossierRequirementSection) -> dict[str, object]:
    return {
        "record": _record_dict(section.record),
        "current_version": _version_dict(section.current_version) if section.current_version is not None else None,
        "active_draft": _draft_dict(section.active_draft) if section.active_draft is not None else None,
    }


def _dossier_acceptance_criteria_section_dict(section: DossierAcceptanceCriteriaSection) -> dict[str, object]:
    return {
        "current_version": [_criterion_dict(item) for item in section.current_version],
        "active_draft": [_criterion_dict(item) for item in section.active_draft],
    }


def _dossier_trace_section_dict(section: DossierTraceSection) -> dict[str, object]:
    return {
        "incoming": [_trace_dict(item) for item in section.incoming],
        "outgoing": [_trace_dict(item) for item in section.outgoing],
        "by_state": section.by_state,
        "by_relation": section.by_relation,
        "items": [_trace_dict(item) for item in section.items],
    }


def _dossier_baseline_exposure_item_dict(item: DossierBaselineExposureItem) -> dict[str, object]:
    return {
        "baseline_id": item.baseline_id,
        "name": item.name,
        "locked": item.locked,
        "created_by": item.created_by,
        "created_at": item.created_at,
        "baseline_version": item.baseline_version,
        "baseline_statement_hash": item.baseline_statement_hash,
        "current_version": item.current_version,
        "current_statement_hash": item.current_statement_hash,
        "state": item.state,
    }


def _dossier_baseline_exposure_dict(exposure: DossierBaselineExposure) -> dict[str, object]:
    return {
        "summary": exposure.summary,
        "items": [_dossier_baseline_exposure_item_dict(item) for item in exposure.items],
    }


def _dossier_computed_gap_dict(gap: DossierComputedGap) -> dict[str, object]:
    return {
        "code": gap.code,
        "severity": gap.severity,
        "message": gap.message,
        "source": gap.source,
    }


def _dossier_peer_facts_dict(peer_facts: DossierPeerFacts) -> dict[str, object]:
    return {
        "live_peer_calls": peer_facts.live_peer_calls,
        "sources": peer_facts.sources,
        "notes": peer_facts.notes,
    }


def _dossier_next_action_dict(action: DossierNextAction) -> dict[str, object]:
    return {
        "action": action.action,
        "priority": action.priority,
        "reason": action.reason,
        "command": action.command,
        "blocked_by": action.blocked_by,
    }


def _dossier_verification_dict(status: RequirementVerificationStatus) -> dict[str, object]:
    return {
        "status": status.status,
        "reasons": [_verification_reason_dict(reason) for reason in status.reasons],
        "current_evidence": [_verification_evidence_summary_dict(evidence) for evidence in status.current_evidence],
        "stale_evidence": [_verification_evidence_summary_dict(evidence) for evidence in status.stale_evidence],
    }


def _dossier_dict(dossier: RequirementDossier) -> dict[str, object]:
    return {
        "identity": dict(dossier.identity),
        "authority_summary": _dossier_authority_summary_dict(dossier.authority_summary),
        "requirement": _dossier_requirement_section_dict(dossier.requirement),
        "acceptance_criteria": _dossier_acceptance_criteria_section_dict(dossier.acceptance_criteria),
        "traces": _dossier_trace_section_dict(dossier.traces),
        "verification": _dossier_verification_dict(dossier.verification),
        "baseline_exposure": _dossier_baseline_exposure_dict(dossier.baseline_exposure),
        "computed_gaps": [_dossier_computed_gap_dict(gap) for gap in dossier.computed_gaps],
        "peer_facts": _dossier_peer_facts_dict(dossier.peer_facts),
        "next_actions": [_dossier_next_action_dict(action) for action in dossier.next_actions],
    }


def _render_dossier(dossier: dict[str, object]) -> str:
    identity = dossier["identity"]
    authority = dossier["authority_summary"]
    verification = dossier["verification"]
    baselines = dossier["baseline_exposure"]
    gaps = dossier["computed_gaps"]
    next_actions = dossier["next_actions"]
    if not isinstance(identity, dict) or not isinstance(authority, dict) or not isinstance(verification, dict):
        raise TypeError("invalid dossier shape")
    if not isinstance(baselines, dict) or not isinstance(gaps, list) or not isinstance(next_actions, list):
        raise TypeError("invalid dossier shape")

    requirement_id = str(identity["id"])
    current_version = identity.get("current_version")
    status = str(authority["status"])
    verification_status = str(verification["status"])
    lines = [f"{requirement_id} v{current_version} {status}", f"Verification: {verification_status}"]

    baseline_items = baselines.get("items")
    lines.append("Baselines:")
    if isinstance(baseline_items, list) and baseline_items:
        for item in baseline_items:
            if isinstance(item, dict):
                lines.append(f"- {item['baseline_id']} {item['name']} ({item['state']})")
    else:
        lines.append("- none")

    lines.append("Gaps:")
    if gaps:
        for gap in gaps:
            if isinstance(gap, dict):
                lines.append(f"- {gap['code']} [{gap['severity']}]: {gap['message']}")
    else:
        lines.append("- none")

    lines.append("Next actions:")
    if next_actions:
        for action in next_actions:
            if isinstance(action, dict):
                command = action.get("command")
                suffix = f" - {command}" if isinstance(command, str) and command else ""
                lines.append(f"- P{action['priority']} {action['action']}: {action['reason']}{suffix}")
    else:
        lines.append("- none")
    return "\n".join(lines)
