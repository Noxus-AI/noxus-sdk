"""Unit tests for the tables SDK resource."""

from __future__ import annotations

import json

import httpx
import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.tables import ImportColumn, RowFilter, Table, TableColumn

_TABLE = {
    "id": "t-1",
    "name": "contacts",
    "sql_name": "contacts",
    "description": None,
    "id_type": "autoincrement",
    "source": "custom",
    "columns": [{"name": "email", "type": "string", "label": None}],
    "row_count": 2,
}


def _client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def _table(handler) -> Table:
    return Table(client=_client(handler), **_TABLE)


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode())


def test_create_table_sends_columns_and_id_type() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json=_TABLE)

    table = _client(handler).tables.create(
        "contacts",
        columns=[TableColumn(name="email", type="string")],
        description="people",
    )
    assert captured["path"] == "/v1/tables"
    assert captured["body"]["name"] == "contacts"
    assert captured["body"]["id_type"] == "uuid"
    assert captured["body"]["description"] == "people"
    assert captured["body"]["columns"] == [
        {"name": "email", "type": "string", "label": None}
    ]
    assert table.name == "contacts"
    assert table.sql_name == "contacts"
    assert table.id_type == "autoincrement"
    assert "contacts" in repr(table)


def test_create_accepts_plain_dict_columns() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(200, json=_TABLE)

    _client(handler).tables.create("t", columns=[{"name": "n", "type": "number"}])
    assert captured["body"]["columns"] == [{"name": "n", "type": "number"}]


def test_list_and_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/tables":
            return httpx.Response(200, json=[_TABLE])
        return httpx.Response(200, json=_TABLE)

    client = _client(handler)
    assert [t.id for t in client.tables.list()] == ["t-1"]
    assert client.tables.get("t-1").row_count == 2


def test_insert_returns_row() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json={"row": {"id": "r1", "email": "a@b.com"}})

    row = _table(handler).insert({"email": "a@b.com"})
    assert captured["path"] == "/v1/tables/t-1/rows"
    assert captured["body"] == {"values": {"email": "a@b.com"}}
    assert row["email"] == "a@b.com"


def test_update_and_delete_row() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH":
            return httpx.Response(200, json={"row": {"id": "r1", "email": "z@z.com"}})
        return httpx.Response(200, json={"success": True})

    table = _table(handler)
    assert table.update_row("r1", {"email": "z@z.com"})["email"] == "z@z.com"
    assert table.delete_row("r1") is True


def test_clear_returns_deleted_count() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"deleted": 7})

    assert _table(handler).clear() == 7


def test_iter_rows_paginates_until_short_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", "0"))
        limit = int(request.url.params.get("limit", "500"))
        if offset == 0:
            rows = [{"id": i} for i in range(limit)]  # full page
        elif offset == limit:
            rows = [{"id": "last"}]  # partial → stop
        else:
            rows = []
        return httpx.Response(
            200, json={"rows": rows, "limit": limit, "offset": offset, "total": 0}
        )

    rows = list(_table(handler).iter_rows(page_size=50))
    assert len(rows) == 51


def test_insert_rows_bulk_returns_count() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json={"inserted": 3})

    n = _table(handler).insert_rows([{"a": 1}, {"a": 2}, {"a": 3}])
    assert captured["path"] == "/v1/tables/t-1/rows/bulk"
    assert captured["body"] == {"rows": [{"a": 1}, {"a": 2}, {"a": 3}]}
    assert n == 3


def test_export_csv_returns_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/tables/t-1/export"
        return httpx.Response(200, content=b"a,b\n1,2\n")

    assert _table(handler).export_csv() == b"a,b\n1,2\n"


def test_query_returns_columns_and_rows() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(200, json={"columns": ["n"], "rows": [{"n": 2}]})

    result = _client(handler).tables.query("select count(*) as n from contacts")
    assert captured["body"] == {"sql": "select count(*) as n from contacts"}
    assert result.columns == ["n"]
    assert result.rows == [{"n": 2}]


def test_add_and_drop_column() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.setdefault("paths", []).append(f"{request.method} {request.url.path}")
        if request.method == "POST":
            captured["body"] = _body(request)
        return httpx.Response(200, json=_TABLE)

    table = _table(handler)
    table.add_column("age", "number", label="Age")
    table.drop_column("age")
    assert captured["body"] == {
        "column": {"name": "age", "type": "number", "label": "Age"}
    }
    assert "POST /v1/tables/t-1/columns" in captured["paths"]
    assert "DELETE /v1/tables/t-1/columns/age" in captured["paths"]


def test_list_rows_page_sends_sort_and_filters_and_returns_total() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200, json={"rows": [{"id": "r1"}], "limit": 10, "offset": 0, "total": 42}
        )

    page = _table(handler).list_rows_page(
        limit=10,
        order_by="score",
        descending=True,
        filters=[RowFilter(field="score", op="between", value=1, value2=5)],
    )
    assert captured["params"]["order_by"] == "score"
    assert captured["params"]["descending"] == "true"
    assert json.loads(captured["params"]["filters"]) == [
        {"field": "score", "op": "between", "value": 1, "value2": 5}
    ]
    assert page.total == 42
    assert page.rows == [{"id": "r1"}]


def test_export_csv_sends_search_and_filters() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, content=b"a\n")

    _table(handler).export_csv(
        search="x", filters=[RowFilter(field="tag", op="in", value=["a", "b"])]
    )
    assert captured["params"]["search"] == "x"
    assert json.loads(captured["params"]["filters"])[0]["value"] == ["a", "b"]


def test_query_pages_and_returns_total() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(
            200, json={"columns": ["n"], "rows": [{"n": 1}], "total": 9}
        )

    result = _client(handler).tables.query(
        "select n from t", limit=1, offset=3, include_total=False
    )
    assert captured["body"] == {
        "sql": "select n from t",
        "limit": 1,
        "offset": 3,
        "include_total": False,
    }
    assert result.total == 9


def test_column_reorder_type_and_label_requests() -> None:
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, _body(request)))
        return httpx.Response(200, json=_TABLE)

    table = _table(handler)
    table.reorder_columns(["email", "age"])
    table.change_column_type("age", "string")
    table.set_column_label("age", "Age")
    assert calls == [
        ("PATCH", "/v1/tables/t-1/columns/reorder", {"column_names": ["email", "age"]}),
        ("PATCH", "/v1/tables/t-1/columns/age/type", {"new_type": "string"}),
        ("PATCH", "/v1/tables/t-1/columns/age/label", {"label": "Age"}),
    ]


def test_import_xlsx_sends_spreadsheet_type_and_sheet(tmp_path) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content"] = request.read()
        return httpx.Response(200, json=_TABLE)

    path = tmp_path / "people.xlsx"
    path.write_bytes(b"PK")
    _client(handler).tables.import_csv(
        path,
        "people",
        [ImportColumn(index=0, name="email", type="string")],
        sheet="Q3",
        skip_rows=2,
    )
    assert b"spreadsheetml.sheet" in captured["content"]
    assert b'"sheet":"Q3"' in captured["content"]
    assert b'"skip_rows":2' in captured["content"]


def test_import_csv_sends_file_and_spec(tmp_path) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["content"] = request.read()
        return httpx.Response(200, json=_TABLE)

    path = tmp_path / "people.csv"
    path.write_bytes(b"email\na@b.com\n")
    _client(handler).tables.import_csv(
        path,
        "people",
        [ImportColumn(index=0, name="email", type="string")],
        id_type="autoincrement",
    )
    assert captured["path"] == "/v1/tables/import"
    assert b'filename="people.csv"' in captured["content"]
    assert b"a@b.com" in captured["content"]
    assert b'"id_type":"autoincrement"' in captured["content"]
    assert b'"name":"people"' in captured["content"]


@pytest.mark.asyncio
async def test_async_insert_and_query() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json={"columns": ["n"], "rows": [{"n": 1}]})
        return httpx.Response(200, json={"row": {"id": "r1"}})

    client = _client(handler)
    table = Table(client=client, **_TABLE)
    assert (await table.ainsert({"email": "x"}))["id"] == "r1"
    assert (await client.tables.aquery("select 1 as n")).rows == [{"n": 1}]
    await client.aclose()
