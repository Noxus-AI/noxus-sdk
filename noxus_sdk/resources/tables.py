"""Tables: structured data you can query with SQL.

table = client.tables.create("contacts", columns=[{"name": "email", "type": "string"}])
table.insert({"email": "a@b.com"})
for row in table.iter_rows():
    print(row)

result = client.tables.query(f"select count(*) from {table.sql_name}")
"""

from __future__ import annotations

import builtins
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any, Literal

import aiofiles
from pydantic import BaseModel

from noxus_sdk.resources.base import BaseResource, BaseService

RowValues = dict[str, Any]
TableIdType = Literal["uuid", "autoincrement"]
TableSource = Literal["custom", "platform"]
ColumnType = Literal["string", "number", "boolean", "datetime", "file", "reference"]
ImportColumnType = Literal["string", "number", "boolean"]
ImportDelimiter = Literal[",", ";", "\t"]
ImportEncoding = Literal["utf-8", "latin-1"]
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
RowFilterOp = Literal[
    "contains",
    "is",
    "is_not",
    "gt",
    "lt",
    "gte",
    "lte",
    "eq",
    "between",
    "in",
    "not_in",
]


class TableColumn(BaseModel):
    name: str
    type: str
    label: str | None = None


class RowFilter(BaseModel):
    field: str
    op: RowFilterOp
    value: str | float | builtins.list[str]
    value2: float | None = None


class ImportColumn(BaseModel):
    index: int
    name: str
    type: ImportColumnType
    label: str | None = None


class TableStats(BaseModel):
    row_count: int
    size_bytes: int
    column_count: int


class QueryResult(BaseModel):
    columns: builtins.list[str]
    rows: builtins.list[RowValues]
    total: int | None = None


class RowsPage(BaseModel):
    rows: builtins.list[RowValues]
    limit: int
    offset: int
    total: int


def _view_params(
    search: str | None, filters: builtins.list[RowFilter] | None
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if search is not None:
        params["search"] = search
    if filters:
        params["filters"] = json.dumps([f.model_dump() for f in filters])
    return params


def _rows_params(
    limit: int,
    offset: int,
    search: str | None,
    order_by: str | None,
    descending: bool,
    filters: builtins.list[RowFilter] | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if order_by is not None:
        params["order_by"] = order_by
        params["descending"] = descending
    return params | _view_params(search, filters)


def _query_body(
    sql: str, limit: int | None, offset: int, include_total: bool
) -> dict[str, Any]:
    if limit is None:
        return {"sql": sql}
    return {
        "sql": sql,
        "limit": limit,
        "offset": offset,
        "include_total": include_total,
    }


class _ImportSpec(BaseModel):
    name: str
    columns: builtins.list[ImportColumn]
    id_type: TableIdType
    has_header: bool
    delimiter: ImportDelimiter
    encoding: ImportEncoding
    sheet: str | None
    skip_rows: int


def _import_parts(content: bytes, file_name: str, spec: _ImportSpec) -> dict[str, Any]:
    mime = _XLSX_MIME if file_name.lower().endswith(".xlsx") else "text/csv"
    return {
        "file": (file_name, content, mime),
        "spec": (None, spec.model_dump_json()),
    }


class Table(BaseResource):
    model_config = {"extra": "allow", "arbitrary_types_allowed": True}

    id: str
    name: str
    sql_name: str
    description: str | None = None
    id_type: TableIdType = "uuid"
    source: TableSource = "custom"
    columns: builtins.list[TableColumn] = []
    row_count: int = 0

    def __repr__(self) -> str:
        return f"Table(id={self.id!r}, name={self.name!r}, rows={self.row_count})"

    # ── lifecycle ──────────────────────────────────────────────────────
    def refresh(self) -> "Table":
        return Table(client=self.client, **self.client.get(f"/v1/tables/{self.id}"))

    async def arefresh(self) -> "Table":
        return Table(
            client=self.client, **await self.client.aget(f"/v1/tables/{self.id}")
        )

    def update(
        self, name: str | None = None, description: str | None = None
    ) -> "Table":
        body = {"name": name, "description": description}
        return Table(
            client=self.client, **self.client.patch(f"/v1/tables/{self.id}", body)
        )

    async def aupdate(
        self, name: str | None = None, description: str | None = None
    ) -> "Table":
        body = {"name": name, "description": description}
        return Table(
            client=self.client,
            **await self.client.apatch(f"/v1/tables/{self.id}", body),
        )

    def delete(self) -> bool:
        return self.client.delete(f"/v1/tables/{self.id}")["success"]

    async def adelete(self) -> bool:
        return (await self.client.adelete(f"/v1/tables/{self.id}"))["success"]

    def stats(self) -> TableStats:
        return TableStats(**self.client.get(f"/v1/tables/{self.id}/stats"))

    async def astats(self) -> TableStats:
        return TableStats(**await self.client.aget(f"/v1/tables/{self.id}/stats"))

    # ── columns ────────────────────────────────────────────────────────
    def add_column(self, name: str, type: str, label: str | None = None) -> "Table":
        body = {"column": {"name": name, "type": type, "label": label}}
        return Table(
            client=self.client,
            **self.client.post(f"/v1/tables/{self.id}/columns", body),
        )

    async def aadd_column(
        self, name: str, type: str, label: str | None = None
    ) -> "Table":
        body = {"column": {"name": name, "type": type, "label": label}}
        return Table(
            client=self.client,
            **await self.client.apost(f"/v1/tables/{self.id}/columns", body),
        )

    def rename_column(self, name: str, new_name: str) -> "Table":
        return Table(
            client=self.client,
            **self.client.patch(
                f"/v1/tables/{self.id}/columns/{name}/rename", {"new_name": new_name}
            ),
        )

    async def arename_column(self, name: str, new_name: str) -> "Table":
        return Table(
            client=self.client,
            **await self.client.apatch(
                f"/v1/tables/{self.id}/columns/{name}/rename", {"new_name": new_name}
            ),
        )

    def change_column_type(self, name: str, new_type: ColumnType) -> "Table":
        return Table(
            client=self.client,
            **self.client.patch(
                f"/v1/tables/{self.id}/columns/{name}/type", {"new_type": new_type}
            ),
        )

    async def achange_column_type(self, name: str, new_type: ColumnType) -> "Table":
        return Table(
            client=self.client,
            **await self.client.apatch(
                f"/v1/tables/{self.id}/columns/{name}/type", {"new_type": new_type}
            ),
        )

    def set_column_label(self, name: str, label: str | None) -> "Table":
        return Table(
            client=self.client,
            **self.client.patch(
                f"/v1/tables/{self.id}/columns/{name}/label", {"label": label}
            ),
        )

    async def aset_column_label(self, name: str, label: str | None) -> "Table":
        return Table(
            client=self.client,
            **await self.client.apatch(
                f"/v1/tables/{self.id}/columns/{name}/label", {"label": label}
            ),
        )

    def reorder_columns(self, column_names: builtins.list[str]) -> "Table":
        return Table(
            client=self.client,
            **self.client.patch(
                f"/v1/tables/{self.id}/columns/reorder",
                {"column_names": column_names},
            ),
        )

    async def areorder_columns(self, column_names: builtins.list[str]) -> "Table":
        return Table(
            client=self.client,
            **await self.client.apatch(
                f"/v1/tables/{self.id}/columns/reorder",
                {"column_names": column_names},
            ),
        )

    def drop_column(self, name: str) -> "Table":
        return Table(
            client=self.client,
            **self.client.delete(f"/v1/tables/{self.id}/columns/{name}"),
        )

    async def adrop_column(self, name: str) -> "Table":
        return Table(
            client=self.client,
            **await self.client.adelete(f"/v1/tables/{self.id}/columns/{name}"),
        )

    # ── rows ───────────────────────────────────────────────────────────
    def insert(self, values: RowValues) -> RowValues:
        return self.client.post(f"/v1/tables/{self.id}/rows", {"values": values})["row"]

    async def ainsert(self, values: RowValues) -> RowValues:
        response = await self.client.apost(
            f"/v1/tables/{self.id}/rows", {"values": values}
        )
        return response["row"]

    def insert_rows(self, rows: builtins.list[RowValues]) -> int:
        """Bulk-insert rows in one fast load (max 1000); returns the count."""
        return self.client.post(f"/v1/tables/{self.id}/rows/bulk", {"rows": rows})[
            "inserted"
        ]

    async def ainsert_rows(self, rows: builtins.list[RowValues]) -> int:
        response = await self.client.apost(
            f"/v1/tables/{self.id}/rows/bulk", {"rows": rows}
        )
        return response["inserted"]

    def export_csv(
        self,
        *,
        search: str | None = None,
        filters: builtins.list[RowFilter] | None = None,
    ) -> bytes:
        """Export the table's rows as CSV bytes."""
        return self.client._request(
            "GET",
            f"/v1/tables/{self.id}/export",
            params=_view_params(search, filters),
        ).content

    async def aexport_csv(
        self,
        *,
        search: str | None = None,
        filters: builtins.list[RowFilter] | None = None,
    ) -> bytes:
        response = await self.client._arequest(
            "GET",
            f"/v1/tables/{self.id}/export",
            params=_view_params(search, filters),
        )
        return response.content

    def update_row(self, row_id: str, values: RowValues) -> RowValues:
        return self.client.patch(
            f"/v1/tables/{self.id}/rows/{row_id}", {"values": values}
        )["row"]

    async def aupdate_row(self, row_id: str, values: RowValues) -> RowValues:
        response = await self.client.apatch(
            f"/v1/tables/{self.id}/rows/{row_id}", {"values": values}
        )
        return response["row"]

    def delete_row(self, row_id: str) -> bool:
        return self.client.delete(f"/v1/tables/{self.id}/rows/{row_id}")["success"]

    async def adelete_row(self, row_id: str) -> bool:
        response = await self.client.adelete(f"/v1/tables/{self.id}/rows/{row_id}")
        return response["success"]

    def clear(self) -> int:
        return self.client.delete(f"/v1/tables/{self.id}/rows")["deleted"]

    async def aclear(self) -> int:
        return (await self.client.adelete(f"/v1/tables/{self.id}/rows"))["deleted"]

    def list_rows_page(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        search: str | None = None,
        order_by: str | None = None,
        descending: bool = False,
        filters: builtins.list[RowFilter] | None = None,
    ) -> RowsPage:
        params = _rows_params(limit, offset, search, order_by, descending, filters)
        return RowsPage(**self.client.get(f"/v1/tables/{self.id}/rows", params=params))

    async def alist_rows_page(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        search: str | None = None,
        order_by: str | None = None,
        descending: bool = False,
        filters: builtins.list[RowFilter] | None = None,
    ) -> RowsPage:
        params = _rows_params(limit, offset, search, order_by, descending, filters)
        return RowsPage(
            **await self.client.aget(f"/v1/tables/{self.id}/rows", params=params)
        )

    def list_rows(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        *,
        order_by: str | None = None,
        descending: bool = False,
        filters: builtins.list[RowFilter] | None = None,
    ) -> builtins.list[RowValues]:
        return self.list_rows_page(
            limit,
            offset,
            search=search,
            order_by=order_by,
            descending=descending,
            filters=filters,
        ).rows

    async def alist_rows(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        *,
        order_by: str | None = None,
        descending: bool = False,
        filters: builtins.list[RowFilter] | None = None,
    ) -> builtins.list[RowValues]:
        page = await self.alist_rows_page(
            limit,
            offset,
            search=search,
            order_by=order_by,
            descending=descending,
            filters=filters,
        )
        return page.rows

    def iter_rows(
        self,
        *,
        page_size: int = 500,
        search: str | None = None,
        order_by: str | None = None,
        descending: bool = False,
        filters: builtins.list[RowFilter] | None = None,
    ) -> Iterator[RowValues]:
        """Yield every row, auto-paginating."""
        offset = 0
        while True:
            batch = self.list_rows(
                page_size,
                offset,
                search,
                order_by=order_by,
                descending=descending,
                filters=filters,
            )
            yield from batch
            if len(batch) < page_size:
                return
            offset += page_size

    async def aiter_rows(
        self,
        *,
        page_size: int = 500,
        search: str | None = None,
        order_by: str | None = None,
        descending: bool = False,
        filters: builtins.list[RowFilter] | None = None,
    ) -> AsyncIterator[RowValues]:
        offset = 0
        while True:
            batch = await self.alist_rows(
                page_size,
                offset,
                search,
                order_by=order_by,
                descending=descending,
                filters=filters,
            )
            for row in batch:
                yield row
            if len(batch) < page_size:
                return
            offset += page_size


class TableService(BaseService[Table]):
    def create(
        self,
        name: str,
        columns: builtins.list[TableColumn | dict[str, Any]] | None = None,
        *,
        description: str | None = None,
        id_type: TableIdType = "uuid",
    ) -> Table:
        body = {
            "name": name,
            "id_type": id_type,
            "description": description,
            "columns": [
                c.model_dump() if isinstance(c, TableColumn) else c
                for c in (columns or [])
            ],
        }
        return Table(client=self.client, **self.client.post("/v1/tables", body))

    async def acreate(
        self,
        name: str,
        columns: builtins.list[TableColumn | dict[str, Any]] | None = None,
        *,
        description: str | None = None,
        id_type: TableIdType = "uuid",
    ) -> Table:
        body = {
            "name": name,
            "id_type": id_type,
            "description": description,
            "columns": [
                c.model_dump() if isinstance(c, TableColumn) else c
                for c in (columns or [])
            ],
        }
        return Table(client=self.client, **await self.client.apost("/v1/tables", body))

    def import_csv(
        self,
        path: str | Path,
        name: str,
        columns: builtins.list[ImportColumn],
        *,
        id_type: TableIdType = "uuid",
        has_header: bool = True,
        delimiter: ImportDelimiter = ",",
        encoding: ImportEncoding = "utf-8",
        sheet: str | None = None,
        skip_rows: int = 0,
    ) -> Table:
        """Create a table from a CSV or .xlsx file, importing the given source columns."""
        content = Path(path).read_bytes()
        spec = _ImportSpec(
            name=name,
            columns=columns,
            id_type=id_type,
            has_header=has_header,
            delimiter=delimiter,
            encoding=encoding,
            sheet=sheet,
            skip_rows=skip_rows,
        )
        parts = _import_parts(content, Path(path).name, spec)
        return Table(
            client=self.client, **self.client.post("/v1/tables/import", files=parts)
        )

    async def aimport_csv(
        self,
        path: str | Path,
        name: str,
        columns: builtins.list[ImportColumn],
        *,
        id_type: TableIdType = "uuid",
        has_header: bool = True,
        delimiter: ImportDelimiter = ",",
        encoding: ImportEncoding = "utf-8",
        sheet: str | None = None,
        skip_rows: int = 0,
    ) -> Table:
        async with aiofiles.open(str(path), "rb") as f:
            content = await f.read()
        spec = _ImportSpec(
            name=name,
            columns=columns,
            id_type=id_type,
            has_header=has_header,
            delimiter=delimiter,
            encoding=encoding,
            sheet=sheet,
            skip_rows=skip_rows,
        )
        parts = _import_parts(content, Path(path).name, spec)
        return Table(
            client=self.client,
            **await self.client.apost("/v1/tables/import", files=parts),
        )

    def list(self) -> builtins.list[Table]:
        return [Table(client=self.client, **t) for t in self.client.get("/v1/tables")]

    async def alist(self) -> builtins.list[Table]:
        return [
            Table(client=self.client, **t) for t in await self.client.aget("/v1/tables")
        ]

    def get(self, table_id: str) -> Table:
        return Table(client=self.client, **self.client.get(f"/v1/tables/{table_id}"))

    async def aget(self, table_id: str) -> Table:
        return Table(
            client=self.client, **await self.client.aget(f"/v1/tables/{table_id}")
        )

    def delete(self, table_id: str) -> bool:
        return self.client.delete(f"/v1/tables/{table_id}")["success"]

    async def adelete(self, table_id: str) -> bool:
        return (await self.client.adelete(f"/v1/tables/{table_id}"))["success"]

    def query(
        self,
        sql: str,
        *,
        limit: int | None = None,
        offset: int = 0,
        include_total: bool = True,
    ) -> QueryResult:
        """Run read-only SQL; counting re-runs the query, so page with include_total once."""
        body = _query_body(sql, limit, offset, include_total)
        return QueryResult(**self.client.post("/v1/tables/query", body))

    async def aquery(
        self,
        sql: str,
        *,
        limit: int | None = None,
        offset: int = 0,
        include_total: bool = True,
    ) -> QueryResult:
        body = _query_body(sql, limit, offset, include_total)
        return QueryResult(**await self.client.apost("/v1/tables/query", body))
