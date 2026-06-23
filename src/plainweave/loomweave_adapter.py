from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]

PUBLIC_SURFACE_TAGS = frozenset({"exported-api", "entry-point", "http-route", "cli-command"})
LOOMWEAVE_SEI_PREFIX = "loomweave:eid:"


@dataclass(frozen=True)
class LoomweaveSourceSpan:
    path: str | None
    line_start: int | None
    line_end: int | None
    byte_start: int | None
    byte_end: int | None

    def to_dict(self) -> JsonObject:
        return {
            "path": self.path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
        }


@dataclass(frozen=True)
class LoomweaveCatalogEntity:
    sei: str | None
    locator: str
    kind: str
    tags: list[str]
    source: LoomweaveSourceSpan
    content_hash: str | None
    content_hash_at_attach: str | None
    public_signal: JsonObject
    briefing_blocked: bool
    lineage_status: str
    freshness: str
    observed_at: str
    degraded: list[JsonObject]
    signals: list[JsonObject]

    def to_dict(self) -> JsonObject:
        return {
            "sei": self.sei,
            "locator": self.locator,
            "kind": self.kind,
            "tags": list(self.tags),
            "source": self.source.to_dict(),
            "content_hash": self.content_hash,
            "content_hash_at_attach": self.content_hash_at_attach,
            "public_signal": dict(self.public_signal),
            "briefing_blocked": self.briefing_blocked,
            "lineage_status": self.lineage_status,
            "freshness": self.freshness,
            "observed_at": self.observed_at,
            "degraded": [dict(item) for item in self.degraded],
            "signals": [dict(item) for item in self.signals],
        }


@dataclass(frozen=True)
class LoomweaveCatalogPage:
    items: list[LoomweaveCatalogEntity]
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None
    adapter_status: JsonObject
    degraded: list[JsonObject]
    coverage: JsonObject


# Not frozen: an exception must allow Python to set ``__traceback__`` as it
# propagates (a frozen dataclass blocks that and raises FrozenInstanceError when
# re-raised through a generator-based context manager).
@dataclass
class LoomweaveIdentityError(Exception):
    reason: str
    message: str
    degraded: list[JsonObject]

    def __str__(self) -> str:
        return self.message


class LoomweaveAdapter:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.loomweave_dir = self.root / ".weft" / "loomweave"
        self.db_path = self.loomweave_dir / "loomweave.db"
        self.http_url = self._resolve_http_url()

    def list_catalog(self, *, limit: int, offset: int) -> LoomweaveCatalogPage:
        schema = self._schema_state()
        adapter_status = self._adapter_status(schema)
        degraded = self._schema_degraded(schema)
        if schema["status"] == "unavailable" or not bool(schema["entities_present"]):
            return LoomweaveCatalogPage(
                [], limit, offset, False, None, adapter_status, degraded, self._coverage_unknown()
            )

        sei_supported = bool(schema["sei_supported"])
        sei_join = (
            "sei_bindings"
            if sei_supported
            else "(select null as sei, null as current_locator, null as status, null as body_hash)"
        )
        placeholders = ",".join("?" for _ in PUBLIC_SURFACE_TAGS)
        public_tags = tuple(sorted(PUBLIC_SURFACE_TAGS))
        with self._connect() as connection:
            present_tags = {
                str(row["tag"])
                for row in connection.execute(
                    f"select distinct tag from entity_tags where tag in ({placeholders})",
                    public_tags,
                )
            }
            # Fetch one extra row to detect `has_more` without materialising the
            # whole catalog (the full-scan-then-slice pattern is replaced here).
            rows = connection.execute(
                f"""
                select e.*,
                       sb.sei as sei,
                       sb.status as sei_status,
                       sb.body_hash as sei_body_hash,
                       (
                         select group_concat(tag, char(31))
                         from (
                           select tag from entity_tags
                           where entity_id = e.id
                           order by tag
                         )
                       ) as tags
                from entities e
                left join {sei_join} sb
                  on sb.current_locator = e.id and sb.status = 'alive'
                where e.kind = 'module'
                   or exists (
                     select 1 from entity_tags t
                     where t.entity_id = e.id
                       and t.tag in ({placeholders})
                   )
                order by e.id
                limit ? offset ?
                """,
                (*public_tags, limit + 1, offset),
            ).fetchall()
        has_more = len(rows) > limit
        page = [self._entity_from_row(row, sei_supported=sei_supported) for row in rows[:limit]]
        next_offset = offset + limit if has_more else None
        coverage = self._public_surface_coverage(present_tags)
        if not coverage["complete"]:
            degraded = [*degraded, self._public_surface_incomplete_degraded(coverage)]
        return LoomweaveCatalogPage(
            page,
            limit,
            offset,
            has_more,
            next_offset,
            adapter_status,
            degraded,
            coverage,
        )

    def _public_surface_coverage(self, present_tags: set[str]) -> JsonObject:
        absent = sorted(PUBLIC_SURFACE_TAGS - present_tags)
        return {
            "public_surface_tags": sorted(PUBLIC_SURFACE_TAGS),
            "present_tags": sorted(present_tags & PUBLIC_SURFACE_TAGS),
            "absent_tags": absent,
            "complete": not absent,
        }

    def _coverage_unknown(self) -> JsonObject:
        return {
            "public_surface_tags": sorted(PUBLIC_SURFACE_TAGS),
            "present_tags": [],
            "absent_tags": [],
            "complete": False,
        }

    def _public_surface_incomplete_degraded(self, coverage: JsonObject) -> JsonObject:
        absent = cast(list[str], coverage["absent_tags"])
        return self._degraded(
            "public_surface_tags_incomplete",
            (
                "Some public-surface tag classes are absent from the local Loomweave catalog, so this "
                "enumeration may under-report exported entities. Absent tag classes: " + ", ".join(absent)
            ),
        )

    def adapter_capability(self) -> JsonObject:
        schema = self._schema_state()
        return {
            "adapter_status": self._adapter_status(schema),
            "degraded": self._schema_degraded(schema),
        }

    def resolve_identity(self, value: str) -> LoomweaveCatalogEntity:
        if self.http_url is not None:
            return self._resolve_identity_http(value)
        return self._resolve_identity_sqlite(value)

    def resolve_identity_local(self, value: str) -> LoomweaveCatalogEntity:
        """Resolve identity using only the local catalog, never a live peer call.

        Callers that must honour a ``local_only`` / ``live_peer_calls: False``
        boundary use this instead of :meth:`resolve_identity`, which may route to
        the HTTP identity endpoint when one is configured.
        """
        return self._resolve_identity_sqlite(value)

    def snapshot_error(self, error: LoomweaveIdentityError) -> JsonObject:
        code_by_reason = {
            "not_found": "identity_not_found",
            "orphaned": "identity_orphaned",
            "unreachable": "identity_unreachable",
            "unsupported": "identity_unsupported",
        }
        code = code_by_reason.get(error.reason, "identity_degraded")
        return {"code": code, "message": error.message}

    def _resolve_identity_http(self, value: str) -> LoomweaveCatalogEntity:
        if value.startswith(LOOMWEAVE_SEI_PREFIX):
            quoted = urllib.parse.quote(value, safe="")
            body = self._http_json("GET", f"/api/v1/identity/sei/{quoted}")
            if not bool(body.get("alive")):
                lineage = body.get("lineage")
                reason = "orphaned" if isinstance(lineage, list) and lineage else "not_found"
                raise LoomweaveIdentityError(
                    reason,
                    f"Loomweave SEI is not alive: {value}",
                    [{"code": f"identity_{reason}", "message": f"Loomweave SEI is not alive: {value}"}],
                )
            locator = self._required_str(body, "current_locator")
            sei = self._required_str(body, "sei")
            content_hash = self._optional_str(body.get("content_hash"))
        else:
            body = self._http_json("POST", "/api/v1/identity/resolve", {"locator": value})
            if not bool(body.get("alive")):
                raise LoomweaveIdentityError(
                    "not_found",
                    f"Loomweave locator was not found: {value}",
                    [{"code": "identity_not_found", "message": f"Loomweave locator was not found: {value}"}],
                )
            locator = self._required_str(body, "current_locator")
            sei = self._required_str(body, "sei")
            content_hash = self._optional_str(body.get("content_hash"))
        return self._snapshot_for_alive_identity(locator, sei, content_hash)

    def _resolve_identity_sqlite(self, value: str) -> LoomweaveCatalogEntity:
        schema = self._schema_state()
        if schema["status"] == "unavailable":
            raise LoomweaveIdentityError(
                "unreachable",
                f"Loomweave database is unavailable: {self.db_path}",
                [self._degraded("loomweave_db_missing", f"Loomweave database is missing: {self.db_path}")],
            )
        if not bool(schema["sei_supported"]):
            raise LoomweaveIdentityError(
                "unsupported",
                "Loomweave SEI support is missing from the local catalog.",
                [self._degraded("sei_support_missing", "Loomweave SEI tables are missing.")],
            )
        with self._connect() as connection:
            if value.startswith(LOOMWEAVE_SEI_PREFIX):
                binding = connection.execute(
                    "select * from sei_bindings where sei = ?",
                    (value,),
                ).fetchone()
                if binding is None:
                    raise LoomweaveIdentityError(
                        "not_found",
                        f"Loomweave SEI was not found: {value}",
                        [self._degraded("identity_not_found", f"Loomweave SEI was not found: {value}")],
                    )
                if str(binding["status"]) != "alive" or not isinstance(binding["current_locator"], str):
                    raise LoomweaveIdentityError(
                        "orphaned",
                        f"Loomweave SEI is not alive: {value}",
                        [self._degraded("identity_orphaned", f"Loomweave SEI is not alive: {value}")],
                    )
                locator = str(binding["current_locator"])
                row = self._entity_row(connection, locator)
                return self._entity_from_row_with_binding(row, binding)

            row = connection.execute(
                """
                select e.*, sb.sei as sei, sb.status as sei_status, sb.body_hash as sei_body_hash,
                       (
                         select group_concat(tag, char(31))
                         from (
                           select tag from entity_tags
                           where entity_id = e.id
                           order by tag
                         )
                       ) as tags
                from entities e
                join sei_bindings sb
                  on sb.current_locator = e.id
                 and sb.status = 'alive'
                where e.id = ?
                """,
                (value,),
            ).fetchone()
        if row is None:
            raise LoomweaveIdentityError(
                "not_found",
                f"Loomweave locator was not found: {value}",
                [self._degraded("identity_not_found", f"Loomweave locator was not found: {value}")],
            )
        return self._entity_from_row(row, sei_supported=True)

    def _snapshot_for_alive_identity(
        self,
        locator: str,
        sei: str,
        content_hash: str | None,
    ) -> LoomweaveCatalogEntity:
        schema = self._schema_state()
        if not bool(schema["entities_present"]):
            raise LoomweaveIdentityError(
                "unreachable",
                "Loomweave catalog is unavailable for identity snapshot enrichment.",
                [self._degraded("loomweave_schema_missing", "Loomweave entities table is missing.")],
            )
        with self._connect() as connection:
            row = connection.execute(
                """
                select e.*, ? as sei, 'alive' as sei_status, ? as sei_body_hash,
                       (
                         select group_concat(tag, char(31))
                         from (
                           select tag from entity_tags
                           where entity_id = e.id
                           order by tag
                         )
                       ) as tags
                from entities e
                where e.id = ?
                """,
                (sei, content_hash, locator),
            ).fetchone()
        if row is None:
            raise LoomweaveIdentityError(
                "not_found",
                f"Loomweave locator was not found in the local catalog: {locator}",
                [self._degraded("identity_not_found", f"Loomweave locator was not found: {locator}")],
            )
        return self._entity_from_row(row, sei_supported=True)

    def _entity_row(self, connection: sqlite3.Connection, locator: str) -> sqlite3.Row:
        row = connection.execute(
            """
            select e.*,
                   (
                     select group_concat(tag, char(31))
                     from (
                       select tag from entity_tags
                       where entity_id = e.id
                       order by tag
                     )
                   ) as tags
            from entities e
            where e.id = ?
            """,
            (locator,),
        ).fetchone()
        if row is None:
            raise LoomweaveIdentityError(
                "not_found",
                f"Loomweave locator was not found: {locator}",
                [self._degraded("identity_not_found", f"Loomweave locator was not found: {locator}")],
            )
        return cast(sqlite3.Row, row)

    def _entity_from_row_with_binding(
        self,
        row: sqlite3.Row,
        binding: sqlite3.Row,
    ) -> LoomweaveCatalogEntity:
        merged = dict(row)
        merged["sei"] = str(binding["sei"])
        merged["sei_status"] = str(binding["status"])
        merged["sei_body_hash"] = binding["body_hash"] if isinstance(binding["body_hash"], str) else None
        return self._entity_from_mapping(merged, sei_supported=True)

    def _entity_from_row(self, row: sqlite3.Row, *, sei_supported: bool) -> LoomweaveCatalogEntity:
        return self._entity_from_mapping(dict(row), sei_supported=sei_supported)

    def _entity_from_mapping(self, row: dict[str, object], *, sei_supported: bool) -> LoomweaveCatalogEntity:
        tags = self._split_tags(row.get("tags"))
        public_signal = self._public_signal(str(row["kind"]), tags)
        # `visibility_unknown` is a permanent signal (Loomweave does not expose a
        # public/internal verdict), not a degradation — keeping it out of `degraded`
        # means an "is anything degraded?" check is not tripped by every healthy entity.
        signals = [self._signal("visibility_unknown", "Loomweave did not report public/internal visibility.")]
        degraded: list[JsonObject] = []
        if not sei_supported:
            degraded.append(self._degraded("sei_support_missing", "Loomweave SEI tables are missing."))
        if sei_supported and not isinstance(row.get("sei"), str):
            degraded.append(
                self._degraded("identity_missing", "No alive Loomweave SEI binding exists for this entity.")
            )
        content_hash = self._optional_str(row.get("content_hash"))
        body_hash = self._optional_str(row.get("sei_body_hash"))
        freshness = "current"
        if body_hash is not None and content_hash is not None and body_hash != content_hash:
            freshness = "stale"
            degraded.append(
                self._degraded("content_hash_drift", "Loomweave content hash differs from the SEI binding.")
            )
        lineage_status = str(row.get("sei_status") or ("unsupported" if not sei_supported else "unknown"))
        return LoomweaveCatalogEntity(
            self._optional_str(row.get("sei")),
            str(row["id"]),
            str(row["kind"]),
            tags,
            LoomweaveSourceSpan(
                self._optional_str(row.get("source_file_path")),
                self._optional_int(row.get("source_line_start")),
                self._optional_int(row.get("source_line_end")),
                self._optional_int(row.get("source_byte_start")),
                self._optional_int(row.get("source_byte_end")),
            ),
            content_hash,
            body_hash or content_hash,
            public_signal,
            self._briefing_blocked(row.get("properties")),
            lineage_status,
            freshness,
            self._now(),
            degraded,
            signals,
        )

    def _adapter_status(self, schema: dict[str, object]) -> JsonObject:
        return {
            "status": schema["status"],
            "db_path": str(self.db_path),
            "http_url": self.http_url,
            "identity_http": "configured" if self.http_url is not None else "not_configured",
            "sei_supported": bool(schema["sei_supported"]),
        }

    def _schema_degraded(self, schema: dict[str, object]) -> list[JsonObject]:
        degraded = schema.get("degraded")
        if not isinstance(degraded, list):
            return []
        return [dict(item) for item in degraded if isinstance(item, dict)]

    def _schema_state(self) -> dict[str, object]:
        if not self.db_path.exists():
            return {
                "status": "unavailable",
                "entities_present": False,
                "sei_supported": False,
                "degraded": [self._degraded("loomweave_db_missing", f"Loomweave database is missing: {self.db_path}")],
            }
        try:
            with self._connect() as connection:
                table_rows = connection.execute("select name from sqlite_master where type = 'table'").fetchall()
        except sqlite3.Error as exc:
            return {
                "status": "unavailable",
                "entities_present": False,
                "sei_supported": False,
                "degraded": [self._degraded("loomweave_db_unreadable", f"Loomweave database is unreadable: {exc}")],
            }
        tables = {str(row["name"]) for row in table_rows}
        degraded: list[JsonObject] = []
        entities_present = {"entities", "entity_tags"}.issubset(tables)
        if not entities_present:
            degraded.append(self._degraded("loomweave_schema_missing", "Loomweave catalog tables are missing."))
        sei_supported = {"sei_bindings", "sei_lineage"}.issubset(tables)
        if entities_present and not sei_supported:
            degraded.append(self._degraded("sei_support_missing", "Loomweave SEI tables are missing."))
        status = "available" if entities_present and sei_supported else "degraded"
        return {
            "status": status,
            "entities_present": entities_present,
            "sei_supported": sei_supported,
            "degraded": degraded,
        }

    def _http_json(self, method: str, path: str, payload: JsonObject | None = None) -> JsonObject:
        if self.http_url is None:
            raise LoomweaveIdentityError(
                "unreachable",
                "Loomweave HTTP identity endpoint is not configured.",
                [self._degraded("identity_unreachable", "Loomweave HTTP identity endpoint is not configured.")],
            )
        url = self.http_url.rstrip("/") + path
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, OSError, urllib.error.URLError) as exc:
            raise LoomweaveIdentityError(
                "unreachable",
                f"Loomweave HTTP identity endpoint is unreachable: {url}",
                [self._degraded("identity_unreachable", f"Loomweave HTTP identity endpoint is unreachable: {exc}")],
            ) from exc
        if not isinstance(decoded, dict):
            raise LoomweaveIdentityError(
                "unsupported",
                "Loomweave HTTP identity endpoint returned a non-object response.",
                [self._degraded("identity_contract", "Loomweave HTTP identity response was not an object.")],
            )
        return cast(JsonObject, decoded)

    def _resolve_http_url(self) -> str | None:
        env_url = os.environ.get("WEFT_LOOMWEAVE_URL")
        if env_url is not None and env_url.strip():
            return env_url.strip().rstrip("/")
        port_path = self.loomweave_dir / "ephemeral.port"
        try:
            port = port_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not port.isdigit():
            return None
        return f"http://127.0.0.1:{port}"

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        # Open read-only: Plainweave never mutates the Loomweave catalog, and the
        # connection is closed deterministically rather than left to GC.
        connection = sqlite3.connect(f"{self.db_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _public_signal(self, kind: str, tags: list[str]) -> JsonObject:
        public_tags = sorted(PUBLIC_SURFACE_TAGS.intersection(tags))
        if public_tags:
            return {"state": "explicit_public_tag", "basis": f"tag:{public_tags[0]}", "visibility": "unknown"}
        if kind == "module":
            return {"state": "module_default", "basis": "kind:module", "visibility": "unknown"}
        return {"state": "unknown", "basis": None, "visibility": "unknown"}

    def _briefing_blocked(self, properties_json: object) -> bool:
        if not isinstance(properties_json, str):
            return False
        try:
            properties = json.loads(properties_json)
        except json.JSONDecodeError:
            return False
        if not isinstance(properties, dict):
            return False
        value = properties.get("briefing_blocked")
        return bool(value)

    def _split_tags(self, raw: object) -> list[str]:
        if not isinstance(raw, str) or raw == "":
            return []
        return [tag for tag in raw.split(chr(31)) if tag]

    def _degraded(self, code: str, message: str) -> JsonObject:
        return {"code": code, "message": message}

    def _signal(self, code: str, message: str) -> JsonObject:
        return {"code": code, "message": message}

    def _required_str(self, data: JsonObject, key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise LoomweaveIdentityError(
                "unsupported",
                f"Loomweave identity response is missing {key}.",
                [self._degraded("identity_contract", f"Loomweave identity response is missing {key}.")],
            )
        return value

    def _optional_str(self, value: object) -> str | None:
        return value if isinstance(value, str) else None

    def _optional_int(self, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        return int(value) if isinstance(value, int) else None

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()
