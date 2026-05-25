"""Utilities function to write into tables."""

from duckdb import connect
from httpx import Response
from tempfile import gettempdir
from os import path
from json import dumps
from pathlib import Path
from duckdb import DuckDBPyConnection
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

def add_columns_if_not_exists(cursor, table_name: str, new_columns: dict):
    """
    Safely adds multiple columns to an existing DuckDB table only if they don't already exist.
    
    Parameters:
    - cursor: A duckdb connection object.
    - table_name (str): The name of the target table.
    - new_columns (dict): Dictionary of {column_name: data_type}.
    """
    if not new_columns:
        print("No columns provided.")
        return

    # 1. Query DuckDB's system catalog to get all existing columns for this table
    try:
        existing_cols_query = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}';
        """
        # Fetch the results as a set of lowercase strings for clean comparison
        existing_columns = {row[0].lower() for row in cursor.sql(existing_cols_query).fetchall()}
    except Exception as e:
        print(f"Could not fetch schema for table '{table_name}': {e}")
        return

    # 2. Filter out columns that already exist
    columns_to_add = {}
    for col_name, dtype in new_columns.items():
        if col_name.lower() in existing_columns:
            print(f"Skipping '{col_name}': Column already exists in '{table_name}'.")
        else:
            columns_to_add[col_name] = dtype

    # 3. If there are missing columns left, build and run the ALTER TABLE string
    if columns_to_add:
        column_definitions = [f"ADD COLUMN {col} {dtype}" for col, dtype in columns_to_add.items()]
        alter_clause = ",\n    ".join(column_definitions)
        
        sql_query = f"ALTER TABLE {table_name} \n{alter_clause};"
        
        try:
            cursor.sql(sql_query)
            print(f"Successfully added columns: {list(columns_to_add.keys())}")
        except Exception as e:
            print(f"Error altering table: {e}")
    else:
        print("All columns already exist. No changes made.")

def col_defs(columns: dict) -> str:
    return ",\n    ".join(f"{col} {dtype}" for col, dtype in columns.items())

def create_or_upsert_table(con: DuckDBPyConnection, schema: dict, data) -> None:
    """
    Create table if not exists (empty, typed), then upsert incoming data
    by row hash using a performant anti-join (no NOT IN).
    """
    table_name = schema["table"]
    columns = schema["columns"]
    data_name = "incoming"

    col_names = ", ".join(columns.keys())

    # ── 1. create typed empty table with unique row_hash if not exists ────────
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {col_defs(columns)},
            row_hash VARCHAR
        )
    """)

    # ── 2. register incoming data ─────────────────────────────────────────────
    con.register(data_name, data)

    # ── 3. upsert: insert new rows, update existing ones on hash conflict ─────
    con.execute(f"""
        WITH temp AS (
            SELECT 
                {col_names}, 
                md5(string_agg({data_name}::text, '')) AS row_hash
            FROM {data_name}
            GROUP BY {col_names}
        )
        INSERT INTO {table_name}
        SELECT * FROM temp
        WHERE temp.row_hash NOT IN (SELECT row_hash FROM {table_name})
    """)