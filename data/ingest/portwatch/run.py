"""Ingest data from portwatch."""

from duckdb import connect
from httpx import get
from pandas import DataFrame, concat, Series
from json import loads, dumps
from pathlib import Path

cf = Path(__file__)
data_path = cf.parent.relative_to(cf.parents[3])  # data/ingest/portwatch
table_name = cf.parent.name

# con.execute("INSTALL spatial")
# con.execute("LOAD spatial")
def connection(data_path = data_path):
    con = connect()
    con.execute("INSTALL ducklake")
    con.execute("LOAD ducklake")
    con.execute("INSTALL sqlite")
    con.execute("LOAD sqlite")
    con.execute(f"ATTACH 'ducklake:sqlite:{data_path}/metadata/metadata.sqlite' AS lake (DATA_PATH '{data_path}/parquet/')")
    con.execute("USE lake")
    return con

def flatten_column(df: DataFrame, col: str) -> DataFrame:
    return concat([df, df.pop(col).apply(Series)], axis=1)

url = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/PortWatch_ports_database/FeatureServer/0/query?outFields=*&where=1=1&f=geojson"

def get_data(url: str) -> DataFrame:
    r = get(url)
    geojson = loads(dumps(r.json()["features"]))
    df = DataFrame(geojson)
    df_clean = df.pipe(flatten_column, "geometry").pipe(flatten_column, "properties")
    return df_clean

if __name__ == "__main__":
    df_clean = get_data(url)
    connection.register("df_clean", df_clean)
    connection.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df_clean")
