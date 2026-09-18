# Data Tables

`client.tables` manages workspace data tables — structured rows you can insert,
update, query with SQL, and import/export as CSV. Great for staging data a
workflow or agent will read.

## Create a table

```python
from noxus_sdk.resources.tables import TableColumn

table = client.tables.create(
    name="Customers",
    columns=[
        TableColumn(name="email", type="string"),
        TableColumn(name="signups", type="number"),
        {"name": "active", "type": "boolean"},     # dicts work too
    ],
    description="CRM export",
    id_type="uuid",        # "uuid" (default) or "serial" (autoincrement)
)
```

Column `type` is one of `string | number | boolean | datetime | file`. Every
table has an implicit `id` primary key (don't declare it).

## Manage tables

```python
client.tables.list()                    # -> list[Table]  (incl. read-only platform views)
client.tables.get(table_id)             # -> Table
client.tables.delete(table_id)          # -> bool
```

## Columns (on a `Table` object)

```python
table.add_column(name="phone", type="string", label="Phone")
table.rename_column("phone", "mobile")
table.drop_column("mobile")
```

## Rows (on a `Table` object)

Rows are plain dicts keyed by column name (`RowValues`).

```python
table.insert({"email": "a@b.com", "signups": 3, "active": True})   # -> the row
table.insert_rows([{...}, {...}])                                  # bulk, -> count
table.update_row(row_id, {"signups": 4})
table.delete_row(row_id)
table.clear()                                                      # delete all rows -> count

# read
table.list_rows(limit=50, offset=0, search="a@b.com")
for row in table.iter_rows(page_size=500, search=None):            # auto-paginate every row
    print(row)
```

## SQL query

Run read-only SQL across the workspace's tables:

```python
result = client.tables.query("SELECT email, signups FROM customers WHERE active")
print(result.columns)     # list[str]
for row in result.rows:   # list[dict]
    print(row)
```

The query is guarded server-side (read-only, per-tenant). Use the table's
`sql_name` (lowercased name) as the SQL identifier.

## Stats & CSV

```python
stats = table.stats()               # TableStats: row_count, size_bytes, column_count
csv_bytes = table.export_csv()      # -> bytes
```

Every method has an `a`-prefixed async twin (`acreate`, `aquery`, `ainsert`,
`aiter_rows`, …).
