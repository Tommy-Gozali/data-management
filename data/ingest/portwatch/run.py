"""Ingest data from portwatch."""

from duckdb import connect
from httpx import get
from pandas import DataFrame, concat, Series
from tempfile import gettempdir
from os import path
from json import dumps
from pathlib import Path

cf = Path(__file__)
data_path = cf.parent.relative_to(cf.parents[3])  # data/ingest/portwatch
table_name = cf.parent.name
url = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/PortWatch_ports_database/FeatureServer/0/query?outFields=*&where=1=1&f=geojson"

def connection(data_path = data_path):
    con = connect()
    con.execute("INSTALL ducklake")
    con.execute("LOAD ducklake")
    con.execute("INSTALL sqlite")
    con.execute("LOAD sqlite")
    con.execute(f"ATTACH 'ducklake:sqlite:{data_path}/metadata/metadata.sqlite' AS lake (DATA_PATH '{data_path}/parquet/')")
    con.execute("USE lake")
    return con

if __name__ == "__main__":
    r = get(url)
    tmp = path.join(gettempdir(), "f{table_name}.json").replace("\\", "/")
    with open(tmp, "w") as f:
        f.write(dumps(r.json()["features"]))

    conn = connection()
    data = conn.sql(
        f"""
        SELECT unnest(properties) 
            FROM (
                    SELECT * 
                    FROM read_json_auto('{tmp}'))
                    
        """)
    conn.register("data", data)
    conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM data")
