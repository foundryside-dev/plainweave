from __future__ import annotations

from pathlib import Path

import pytest

from plainweave.errors import ErrorCode, PlainweaveError
from plainweave.store import connect
from plainweave.web import context as ctx


def test_operator_self_registers_at_genesis(project_root: Path) -> None:
    rc = ctx.RequestContext.from_root(project_root, actor="human:alice")
    assert rc.operator.actor_id == "human:alice"
    assert rc.operator.kind == "human"
    # The actor is now a registered human in the store.
    with connect(rc.service.db_path) as conn:
        row = conn.execute("select kind from actors where actor_id = ?", ("human:alice",)).fetchone()
    assert row is not None
    assert str(row["kind"]) == "human"


def test_default_operator_used_when_actor_omitted(project_root: Path) -> None:
    rc = ctx.RequestContext.from_root(project_root, actor=None)
    assert rc.operator.actor_id == ctx.DEFAULT_OPERATOR_ID


def test_from_root_is_idempotent(project_root: Path) -> None:
    # Calling from_root twice with the same actor should succeed (re-register is ok).
    rc1 = ctx.RequestContext.from_root(project_root, actor="human:alice")
    rc2 = ctx.RequestContext.from_root(project_root, actor="human:alice")
    assert rc1.operator.actor_id == rc2.operator.actor_id


def test_second_actor_cannot_self_register_after_genesis(project_root: Path) -> None:
    # Once a genesis attester exists, a different unregistered actor cannot self-register.
    ctx.RequestContext.from_root(project_root, actor="human:alice")  # genesis
    with pytest.raises(PlainweaveError) as exc:
        ctx.RequestContext.from_root(project_root, actor="human:bob")
    assert exc.value.code == ErrorCode.POLICY_REQUIRED


def test_csrf_roundtrip() -> None:
    token = ctx.new_csrf_token()
    assert ctx.csrf_ok(token, token) is True
    assert ctx.csrf_ok(token, "other") is False
    assert ctx.csrf_ok(None, token) is False
