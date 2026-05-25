"""Utilities function to write into tables."""

from duckdb import connect
from httpx import Response
from tempfile import gettempdir
from os import path
from json import dumps
from pathlib import Path

def lake_connection(data_path: Path):
    con = connect()
    con.execute("INSTALL ducklake")
    con.execute("LOAD ducklake")
    con.execute("INSTALL sqlite")
    con.execute("LOAD sqlite")
    con.execute(f"ATTACH 'ducklake:sqlite:{data_path}/metadata/metadata.sqlite' AS lake (DATA_PATH '{data_path}/parquet/')")
    con.execute("USE lake")
    return con

def write_temp(response: Response, table_name: str, schema: str) -> str:
    tmp = path.join(gettempdir(), "f{table_name}.json").replace("\\", "/")
    if schema:
        with open(tmp, "w") as f:
            f.write(dumps(response.json()[schema]))
    else:
        with open(tmp, "w") as f:
            f.write(dumps(response.json()))
    return tmp
