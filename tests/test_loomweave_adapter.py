from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest

from plainweave.loomweave_adapter import LoomweaveAdapter, LoomweaveIdentityError
from tests.loomweave_test_utils import create_loomweave_db, insert_loomweave_entity, seed_loomweave_catalog

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "contracts" / "loomweave"


def _identity_fixture(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8")))


def test_catalog_lists_modules_and_explicit_public_surfaces(tmp_path: Path) -> None:
    seed = seed_loomweave_catalog(tmp_path)

    page = LoomweaveAdapter(tmp_path).list_catalog(limit=10, offset=0)

    assert page.adapter_status["status"] == "available"
    assert page.adapter_status["db_path"] == seed["db_path"]
    assert [item.locator for item in page.items] == [
        "python:function:pkg.main",
        "python:function:pkg.public_api",
        "python:module:pkg",
    ]
    public = next(item for item in page.items if item.locator == seed["public_locator"])
    assert public.sei == seed["public_sei"]
    assert public.kind == "function"
    assert public.tags == ["exported-api"]
    assert public.source.path is not None
    assert public.source.path.endswith("pkg/api.py")
    assert public.source.line_start == 10
    assert public.source.line_end == 12
    assert public.source.byte_start == 100
    assert public.source.byte_end == 180
    assert public.content_hash == "hash-public-v1"
    assert public.content_hash_at_attach == "hash-public-v1"
    assert public.public_signal["state"] == "explicit_public_tag"
    assert public.briefing_blocked is False
    assert public.lineage_status == "alive"
    assert public.freshness == "current"
    assert any(item["code"] == "visibility_unknown" for item in public.signals)
    assert all(item["code"] != "visibility_unknown" for item in public.degraded)
    # The seeded catalog only carries `exported-api` and `entry-point` tags, so the
    # public-surface enumeration is incomplete and must say so rather than masquerade
    # as a clean, complete listing.
    assert page.coverage["complete"] is False
    assert set(cast(list[str], page.coverage["absent_tags"])) == {"http-route", "cli-command"}
    assert any(item["code"] == "public_surface_tags_incomplete" for item in page.degraded)


def test_catalog_connections_are_read_only(tmp_path: Path) -> None:
    seed_loomweave_catalog(tmp_path)
    adapter = LoomweaveAdapter(tmp_path)

    with adapter._connect() as connection, pytest.raises(sqlite3.OperationalError):
        connection.execute("create table intrusion(x integer)")


def test_catalog_read_never_mutates_the_loomweave_database(tmp_path: Path) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    db_path = Path(seed["db_path"])
    before = db_path.read_bytes()
    adapter = LoomweaveAdapter(tmp_path)

    adapter.list_catalog(limit=10, offset=0)
    adapter.resolve_identity(seed["public_locator"])
    adapter.resolve_identity(seed["public_sei"])

    assert db_path.read_bytes() == before


def test_full_public_surface_tag_coverage_reports_complete(tmp_path: Path) -> None:
    db_path = create_loomweave_db(tmp_path)
    for tag in ("exported-api", "entry-point", "http-route", "cli-command"):
        insert_loomweave_entity(
            db_path,
            entity_id=f"python:function:pkg.{tag.replace('-', '_')}",
            kind="function",
            name=f"pkg.{tag}",
            path=str(tmp_path / "pkg.py"),
            line_start=1,
            line_end=2,
            byte_start=0,
            byte_end=10,
            content_hash=f"hash-{tag}",
            sei=f"loomweave:eid:{tag.replace('-', '')}0000000000000000000000",
            tags=[tag],
        )

    page = LoomweaveAdapter(tmp_path).list_catalog(limit=10, offset=0)

    assert page.coverage["complete"] is True
    assert page.coverage["absent_tags"] == []
    assert all(item["code"] != "public_surface_tags_incomplete" for item in page.degraded)


def test_resolve_identity_local_never_uses_http(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://127.0.0.1:9")
    adapter = LoomweaveAdapter(tmp_path)

    def fail_http(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("resolve_identity_local must not make HTTP calls")

    monkeypatch.setattr(adapter, "_http_json", fail_http)

    resolved = adapter.resolve_identity_local(seed["public_locator"])

    assert resolved.sei == seed["public_sei"]
    assert resolved.locator == seed["public_locator"]


def test_catalog_reports_absent_database_as_degraded(tmp_path: Path) -> None:
    page = LoomweaveAdapter(tmp_path).list_catalog(limit=10, offset=0)

    assert page.items == []
    assert page.adapter_status["status"] == "unavailable"
    assert page.degraded[0]["code"] == "loomweave_db_missing"


def test_catalog_reports_missing_schema_as_degraded(tmp_path: Path) -> None:
    db_path = tmp_path / ".weft" / "loomweave" / "loomweave.db"
    db_path.parent.mkdir(parents=True)
    sqlite3.connect(db_path).close()

    page = LoomweaveAdapter(tmp_path).list_catalog(limit=10, offset=0)

    assert page.items == []
    assert page.adapter_status["status"] == "degraded"
    assert page.degraded[0]["code"] == "loomweave_schema_missing"


def test_catalog_reports_missing_sei_support_without_inventing_identities(tmp_path: Path) -> None:
    db_path = create_loomweave_db(tmp_path, with_sei=False)
    insert_loomweave_entity(
        db_path,
        entity_id="python:module:pkg",
        kind="module",
        name="pkg",
        path=str(tmp_path / "pkg.py"),
        line_start=1,
        line_end=5,
        byte_start=0,
        byte_end=50,
        content_hash="hash-module",
        sei=None,
    )

    page = LoomweaveAdapter(tmp_path).list_catalog(limit=10, offset=0)

    assert page.adapter_status["status"] == "degraded"
    assert page.items[0].sei is None
    assert any(item["code"] == "sei_support_missing" for item in page.items[0].degraded)
    assert any(item["code"] == "sei_support_missing" for item in page.degraded)


def test_identity_resolution_accepts_locators_and_seis(tmp_path: Path) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    adapter = LoomweaveAdapter(tmp_path)

    by_locator = adapter.resolve_identity(seed["public_locator"])
    by_sei = adapter.resolve_identity(seed["public_sei"])

    assert by_locator.sei == seed["public_sei"]
    assert by_locator.locator == seed["public_locator"]
    assert by_locator.content_hash == "hash-public-v1"
    assert by_locator.lineage_status == "alive"
    assert by_locator.freshness == "current"
    assert by_sei.sei == by_locator.sei
    assert by_sei.locator == by_locator.locator


def test_identity_resolution_rejects_unknown_or_orphaned_identities(tmp_path: Path) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    adapter = LoomweaveAdapter(tmp_path)
    with sqlite3.connect(seed["db_path"]) as connection:
        connection.execute(
            "update sei_bindings set status = 'orphaned', current_locator = null where sei = ?",
            (seed["public_sei"],),
        )

    with pytest.raises(LoomweaveIdentityError) as missing:
        adapter.resolve_identity("python:function:pkg.missing")
    with pytest.raises(LoomweaveIdentityError) as orphaned:
        adapter.resolve_identity(seed["public_sei"])

    assert missing.value.reason == "not_found"
    assert orphaned.value.reason == "orphaned"


def test_identity_resolution_fails_closed_when_configured_http_is_unreachable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://127.0.0.1:9")

    with pytest.raises(LoomweaveIdentityError) as exc_info:
        LoomweaveAdapter(tmp_path).resolve_identity(seed["public_locator"])

    assert exc_info.value.reason == "unreachable"


def test_identity_resolution_over_http_returns_alive_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")
    adapter = LoomweaveAdapter(tmp_path)

    alive_body = {
        "alive": True,
        "current_locator": seed["public_locator"],
        "sei": seed["public_sei"],
        "content_hash": "hash-public-v1",
    }

    def fake_http_json(method: str, path: str, payload: object | None = None) -> dict[str, object]:
        return alive_body

    monkeypatch.setattr(adapter, "_http_json", fake_http_json)

    by_sei = adapter.resolve_identity(seed["public_sei"])
    by_locator = adapter.resolve_identity(seed["public_locator"])

    assert by_sei.sei == seed["public_sei"]
    assert by_sei.locator == seed["public_locator"]
    assert by_sei.lineage_status == "alive"
    assert by_locator.sei == seed["public_sei"]
    assert by_locator.content_hash == "hash-public-v1"


def test_identity_resolution_over_http_matches_the_pinned_contract_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")
    adapter = LoomweaveAdapter(tmp_path)
    sei_body = cast("dict[str, object]", _identity_fixture("identity-sei.json")["response"])
    resolve_body = cast("dict[str, object]", _identity_fixture("identity-resolve.json")["response"])

    def fake_http_json(method: str, path: str, payload: object | None = None) -> dict[str, object]:
        return sei_body if path.startswith("/api/v1/identity/sei/") else resolve_body

    monkeypatch.setattr(adapter, "_http_json", fake_http_json)

    by_sei = adapter.resolve_identity(seed["public_sei"])
    by_locator = adapter.resolve_identity(seed["public_locator"])

    assert by_sei.sei == seed["public_sei"]
    assert by_sei.locator == seed["public_locator"]
    assert by_sei.content_hash == "hash-public-v1"
    assert by_locator.sei == seed["public_sei"]
    assert by_locator.lineage_status == "alive"


def test_identity_resolution_over_http_reports_orphaned_when_not_alive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = seed_loomweave_catalog(tmp_path)
    monkeypatch.setenv("WEFT_LOOMWEAVE_URL", "http://loomweave.test")
    adapter = LoomweaveAdapter(tmp_path)

    def fake_http_json(method: str, path: str, payload: object | None = None) -> dict[str, object]:
        return {"alive": False, "lineage": [{"event": "renamed"}]}

    monkeypatch.setattr(adapter, "_http_json", fake_http_json)

    with pytest.raises(LoomweaveIdentityError) as by_sei:
        adapter.resolve_identity(seed["public_sei"])
    with pytest.raises(LoomweaveIdentityError) as by_locator:
        adapter.resolve_identity(seed["public_locator"])

    assert by_sei.value.reason == "orphaned"
    assert by_locator.value.reason == "not_found"
