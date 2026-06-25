from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.models import RequirementDraft, RequirementRecord
from plainweave.web import views

if TYPE_CHECKING:
    from plainweave.service import PlainweaveService


def _pending_count(service: PlainweaveService) -> int:
    return len(views.pending_items(service))


def _draft_ctx(service: PlainweaveService, req_id: str) -> tuple[RequirementRecord, RequirementDraft]:
    rec = service.get_requirement(req_id)
    draft = service.requirement_dossier(req_id).requirement.active_draft
    if draft is None:
        raise PlainweaveError(
            ErrorCode.POLICY_REQUIRED,
            f"requirement {req_id!r} has no active draft",
            recoverable=False,
            hint="ensure the requirement has an active draft before approving",
        )
    return rec, draft


async def review(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    items = views.pending_items(ctx.service)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "review.html",
        {
            "items": items,
            "pending_count": len(items),
            "operator": ctx.operator,
            "active_page": "review",
        },
    )


async def approve_confirm(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id: str = request.path_params["req_id"]
    rec, draft = _draft_ctx(ctx.service, req_id)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "_partials/draft_approve_confirm.html",
        {
            "req_id": req_id,
            "title": draft.title,
            "current_version": rec.current_version,
            "next_version": rec.current_version + 1,
            "error": None,
        },
    )


async def approve_post(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id: str = request.path_params["req_id"]
    form = await request.form()
    expected = int(str(form["expected_version"]))
    rec, draft = _draft_ctx(ctx.service, req_id)
    templates: Jinja2Templates = request.app.state.templates
    try:
        ctx.service.approve_requirement(req_id, actor=ctx.operator.actor_id, expected_version=expected)
    except PlainweaveError as exc:
        if exc.code is not ErrorCode.CONFLICT:
            raise
        return templates.TemplateResponse(
            request,
            "_partials/draft_approve_confirm.html",
            {
                "req_id": req_id,
                "title": draft.title,
                "current_version": rec.current_version,
                "next_version": rec.current_version + 1,
                "error": "Draft changed since you loaded this. Reopen to see the latest.",
            },
            status_code=200,
        )
    remaining = _pending_count(ctx.service)
    return templates.TemplateResponse(
        request,
        "_partials/queue_action_result.html",
        {
            "action_label": "Approved",
            "item_desc": draft.title,
            "remaining_count": remaining,
        },
    )


async def draft_card(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    req_id: str = request.path_params["req_id"]
    rec, draft = _draft_ctx(ctx.service, req_id)
    item = views.DraftItem(
        kind="draft",
        req_id=req_id,
        display_id=rec.id,
        title=draft.title,
        statement=draft.statement,
        current_version=rec.current_version,
    )
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "_partials/queue_item_draft.html",
        {"item": item},
    )


def _link_item(service: PlainweaveService, link_id: str) -> views.LinkItem:
    for link in service.trace_for(state="proposed"):
        if link.id == link_id:
            return views.LinkItem(
                "link",
                link.id,
                link.from_ref.id,
                link.relation,
                link.to_ref.id,
                link.created_by,
                link.confidence,
                link.freshness != "current",
            )
    raise PlainweaveError(
        ErrorCode.NOT_FOUND,
        f"proposed link {link_id!r} not found",
        recoverable=False,
        hint="It may have already been accepted or rejected.",
    )


async def reject_form(request: Request) -> Response:
    link_id: str = request.path_params["link_id"]
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "_partials/link_reject_form.html",
        {"link_id": link_id, "submitted_reason": "", "error": None},
    )


async def reject_post(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    link_id: str = request.path_params["link_id"]
    form = await request.form()
    reason = str(form.get("reason", "")).strip()
    templates: Jinja2Templates = request.app.state.templates
    if not reason:
        return templates.TemplateResponse(
            request,
            "_partials/link_reject_form.html",
            {
                "link_id": link_id,
                "submitted_reason": "",
                "error": "Reason is required — explain why this link should be rejected.",
            },
            status_code=200,
        )
    item = _link_item(ctx.service, link_id)
    ctx.service.reject_trace_link(link_id, actor=ctx.operator.actor_id, reason=reason)
    remaining = _pending_count(ctx.service)
    return templates.TemplateResponse(
        request,
        "_partials/queue_action_result.html",
        {
            "action_label": "Rejected",
            "item_desc": f"{item.from_label} {item.relation} {item.to_label}",
            "remaining_count": remaining,
        },
    )


async def accept_post(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    link_id: str = request.path_params["link_id"]
    item = _link_item(ctx.service, link_id)
    ctx.service.accept_trace_link(link_id, actor=ctx.operator.actor_id)
    remaining = _pending_count(ctx.service)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "_partials/queue_action_result.html",
        {
            "action_label": "Accepted",
            "item_desc": f"{item.from_label} {item.relation} {item.to_label}",
            "remaining_count": remaining,
        },
    )


async def link_card(request: Request) -> Response:
    ctx = request.app.state.ctx_factory()
    item = _link_item(ctx.service, request.path_params["link_id"])
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "_partials/queue_item_link.html",
        {"item": item},
    )


def register(app: Starlette) -> None:
    app.router.routes.append(Route("/review", review, name="review"))
    app.router.routes.append(Route("/req/{req_id}/approve-confirm", approve_confirm))
    app.router.routes.append(Route("/req/{req_id}/approve", approve_post, methods=["POST"]))
    app.router.routes.append(Route("/req/{req_id}/draft-card", draft_card))
    app.router.routes.append(Route("/trace/{link_id}/accept", accept_post, methods=["POST"]))
    app.router.routes.append(Route("/trace/{link_id}/reject-form", reject_form))
    app.router.routes.append(Route("/trace/{link_id}/reject", reject_post, methods=["POST"]))
    app.router.routes.append(Route("/trace/{link_id}/card", link_card))
