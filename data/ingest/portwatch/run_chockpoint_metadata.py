"""Ingest data from portwatch to get chockpoint metadata reference."""

from httpx import get
from pathlib import Path
from sys import path

cf = Path(__file__)
relative_path = cf.parents[3]
path.insert(0, str(relative_path))

from data.ingest.utilities import lake_connection, write_temp, create_or_upsert_table  # noqa: E402

cf = Path(__file__)
data_path = cf.parent.relative_to(relative_path)  # data/ingest/portwatch
table_name = cf.parent.name + "_chockpoint_metadata" 
url = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/PortWatch_chokepoints_database/FeatureServer/0/query?outFields=*&where=1=1&f=geojson"

SCHEMA = {
        "table": table_name,
        "columns": {
            "portid": "VARCHAR",
            "portname": "VARCHAR",
            "country": "VARCHAR",
            "ISO3": "VARCHAR",
            "continent": "VARCHAR",
            "fullname": "VARCHAR",
            "lat": "FLOAT",
            "lon": "FLOAT",
            "vessel_count_total": "FLOAT",
            "vessel_count_container": "FLOAT",
            "vessel_count_dry_bulk": "FLOAT",
            "vessel_count_general_cargo": "FLOAT",
            "vessel_count_RoRo": "FLOAT",
            "vessel_count_tanker": "FLOAT",
            "industry_top1": "VARCHAR",
            "industry_top2": "VARCHAR",
            "industry_top3": "VARCHAR",
            "share_country_maritime_import": "FLOAT",
            "LOCODE": "VARCHAR",
            "pageid": "VARCHAR",
            "countrynoaccents": "VARCHAR",
            "ObjectId": "VARCHAR",
            # "bbox_geojson": "JSON",
        }}

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

    create_or_upsert_table(con=conn, schema=SCHEMA, data=data)