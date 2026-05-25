"""Ingest data from portwatch."""

from httpx import get
from pathlib import Path
from sys import path

cf = Path(__file__)
relative_path = cf.parents[3]
path.insert(0, str(relative_path))

from data.ingest.utilities import lake_connection, write_temp  # noqa: E402

cf = Path(__file__)
data_path = cf.parent.relative_to(relative_path)  # data/ingest/portwatch
table_name = cf.parent.name
url = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/PortWatch_ports_database/FeatureServer/0/query?outFields=*&where=1=1&f=geojson"

if __name__ == "__main__":
    r = get(url)
    tmp = write_temp(response=r, table_name=table_name, schema = "features")

    conn = lake_connection(data_path=data_path)
    data = conn.sql(
        f"""
        SELECT unnest(properties) 
            FROM (
                    SELECT * 
                    FROM read_json_auto('{tmp}'))
                    
        """)
    conn.register("data", data)
    conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM data")
