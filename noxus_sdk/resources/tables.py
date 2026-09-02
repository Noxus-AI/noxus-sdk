"""Tables: structured data you can query with SQL.

table = client.tables.create("contacts", columns=[{"name": "email", "type": "text"}])
table.insert({"email": "a@b.com"})
for row in table.iter_rows():
    print(row)

result = client.tables.query("select count(*) from contacts")
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any, Literal

from pydantic import BaseModel

from noxus_sdk.resources.base import BaseResource, BaseService

RowValues = dict[str, Any]
TableIdType = Literal["uuid", "serial"]


class TableColumn(BaseModel):
    name: str
    type: str
    label: str | None = None


class TableStats(BaseModel):
    row_count: int
    size_bytes: int
    column_count: int


class QueryResult(BaseModel):
    columns: builtins.list[str]
    rows: builtins.list[RowValues]


class Table(BaseResource):
    model_config = {"extra": "allow", "arbitrary_types_allowed": True}

    id: str
    name: str
    description: str | None = None
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

    def drop_column(self, name: str) -> "Table":
        return Table(
            client=self.client,
            **self.client.delete(f"/v1/tables/{self.id}/columns/{name}"),
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

    def export_csv(self) -> bytes:
        """Export the table's rows as CSV bytes (capped at 10k rows)."""
        return self.client._request("GET", f"/v1/tables/{self.id}/export").content

    async def aexport_csv(self) -> bytes:
        response = await self.client._arequest("GET", f"/v1/tables/{self.id}/export")
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

    def list_rows(
        self, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> builtins.list[RowValues]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search is not None:
            params["search"] = search
        return self.client.get(f"/v1/tables/{self.id}/rows", params=params)["rows"]

    async def alist_rows(
        self, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> builtins.list[RowValues]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search is not None:
            params["search"] = search
        response = await self.client.aget(f"/v1/tables/{self.id}/rows", params=params)
        return response["rows"]

    def iter_rows(
        self, *, page_size: int = 500, search: str | None = None
    ) -> Iterator[RowValues]:
        """Yield every row, auto-paginating."""
        offset = 0
        while True:
            batch = self.list_rows(limit=page_size, offset=offset, search=search)
            yield from batch
            if len(batch) < page_size:
                return
            offset += page_size

    async def aiter_rows(
        self, *, page_size: int = 500, search: str | None = None
    ) -> AsyncIterator[RowValues]:
        offset = 0
        while True:
            batch = await self.alist_rows(limit=page_size, offset=offset, search=search)
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

    def query(self, sql: str) -> QueryResult:
        """Run a read-only SQL query across this workspace's tables."""
        return QueryResult(**self.client.post("/v1/tables/query", {"sql": sql}))

    async def aquery(self, sql: str) -> QueryResult:
        return QueryResult(**await self.client.apost("/v1/tables/query", {"sql": sql}))
