"""Main script."""

import glob
import pandas as pd
import kagglehub
import duckdb

# Download latest version
path = kagglehub.dataset_download("alistairking/weather-long-term-time-series-forecasting")
print("Path to dataset files:", path)

parquet_files = glob.glob(f"{path}/**/*.parquet", recursive=True)
if parquet_files:
    df = pd.concat([pd.read_parquet(f) for f in parquet_files], ignore_index=True)
else:
    csv_files = glob.glob(f"{path}/**/*.csv", recursive=True)
    df = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)
    df.to_parquet("data/weather-long-term-time-series-forecasting.parquet")


schema = {
    "date":     "datetime64[ns]",
    "p":        "float32",   # pressure (mbar)
    "T":        "float32",   # temperature (°C)
    "Tpot":     "float32",   # potential temperature (K)
    "Tdew":     "float32",   # dew point temperature (°C)
    "rh":       "float32",   # relative humidity (%)
    "VPmax":    "float32",   # saturation vapour pressure (mbar)
    "VPact":    "float32",   # vapour pressure (mbar)
    "VPdef":    "float32",   # vapour pressure deficit (mbar)
    "sh":       "float32",   # specific humidity (g/kg)
    "H2OC":     "float32",   # water vapour concentration (mmol/mol)
    "rho":      "float32",   # air density (g/m³)
    "wv":       "float32",   # wind velocity (m/s)
    "max. wv":  "float32",   # max wind velocity (m/s)
    "wd":       "float32",   # wind direction (°)
    "rain":     "float32",   # rain depth (mm)
    "raining":  "bool",      # raining flag
    "SWDR":     "float32",   # shortwave downward radiation (W/m²)
    "PAR":      "float32",   # photosynthetically active radiation (µmol/m²/s)
    "max. PAR": "float32",   # max PAR (µmol/m²/s)
    "Tlog":     "float32",   # logger temperature (°C)
}


def enforce_types(df: pd.DataFrame) -> pd.DataFrame:
    for col, dtype in schema.items():
        if col not in df.columns:
            continue
        if dtype == "datetime64[ns]":
            df[col] = pd.to_datetime(df[col])
        elif dtype == "bool":
            df[col] = df[col].astype(bool)
        else:
            df[col] = df[col].astype(dtype)
    return df

df_clean = enforce_types(df)

con = duckdb.connect()
con.execute("INSTALL ducklake")
con.execute("LOAD ducklake")
con.execute("INSTALL sqlite")
con.execute("LOAD sqlite")
con.execute("ATTACH 'ducklake:sqlite:data/metadata/metadata.sqlite' AS lake (DATA_PATH 'data/parquet/')")
con.execute("USE lake")
con.register("df_clean", df_clean)
con.execute("CREATE OR REPLACE TABLE weather AS SELECT * FROM df_clean")
con.close()