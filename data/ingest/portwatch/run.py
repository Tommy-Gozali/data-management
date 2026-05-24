"""Ingest data from portwatch."""

from duckdb import connect
from httpx import get
from pandas import DataFrame, concat, Series
from json import loads, dumps
from pathlib import Path

name = Path(__file__).parent.relative_to(Path(__file__).parents[3])  # data/ingest/portwatch

url = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/PortWatch_ports_database/FeatureServer/0/query?outFields=*&where=1=1&f=geojson"
r = get(url)

geojson = loads(dumps(r.json()["features"]))
con = connect()
# con.execute("INSTALL spatial")
# con.execute("LOAD spatial")
con.execute("INSTALL ducklake")
con.execute("LOAD ducklake")
con.execute("INSTALL sqlite")
con.execute("LOAD sqlite")

def flatten_column(df: DataFrame, col: str) -> DataFrame:
    return concat([df, df.pop(col).apply(Series)], axis=1)

df = DataFrame(geojson)
df_clean = df.pipe(flatten_column, "geometry").pipe(flatten_column, "properties")


con.execute(f"ATTACH 'ducklake:sqlite:{name}/metadata/metadata.sqlite' AS lake (DATA_PATH '{name}/parquet/')")
con.execute("USE lake")
con.execute("CREATE TABLE IF NOT EXISTS portwatch AS SELECT * FROM df_clean")