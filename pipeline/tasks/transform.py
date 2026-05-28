from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq
from prefect import task, get_run_logger
from shapely.geometry import MultiLineString
from shapely.wkb import loads as wkb_loads
from sqlalchemy import text

import fiona

from pipeline.config import (
    DOW_FACTORS,
    FUNCTIONAL_CLASS_TO_FACTOR_GROUP,
    HOURLY_FACTORS,
    pipeline_settings,
)
from pipeline.db import get_engine


def _to_multilinestring(geom):
    if geom is None:
        return None
    if geom.geom_type == "MultiLineString":
        return geom
    if geom.geom_type == "LineString":
        return MultiLineString([geom])
    return None


CHUNK_SIZE = 10_000


@task(name="transform_hpms")
def transform_hpms(shp_path: Path) -> str:
    logger = get_run_logger()

    state = pipeline_settings.hpms_state.upper()
    available = fiona.listlayers(str(shp_path))
    layer = next((l for l in available if f"_{state}_" in l), None)
    if layer is None:
        raise ValueError(
            f"No HPMS layer found for state '{state}' in {shp_path}. "
            f"Available layers: {available}"
        )

    col_map = {
        "route_id":      "route_id",
        "begin_point":   "begin_point",
        "end_point":     "end_point",
        "f_system":      "functional_class",
        "aadt":          "aadt",
        "speed_limit":   "speed_limit",
        "through_lanes": "lanes",
        "county_id":     "county_code",
        "state_id":      "state_code",
    }
    keep = ["road_id", "route_id", "functional_class", "aadt", "speed_limit",
            "lanes", "county_code", "state_code", "geometry"]

    with fiona.open(str(shp_path), layer=layer) as src:
        total = len(src)

    sample = pipeline_settings.hpms_sample
    if sample:
        total = min(total, sample)

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE raw.hpms_roads"))
        conn.commit()

    rows_loaded = 0
    for start in range(0, total, CHUNK_SIZE):
        chunk = gpd.read_file(shp_path, layer=layer, rows=slice(start, start + CHUNK_SIZE))

        if chunk.crs.to_epsg() != 4326:
            chunk = chunk.to_crs(4326)

        chunk = chunk.rename(columns={k: v for k, v in col_map.items() if k in chunk.columns})

        chunk["road_id"] = (
            chunk["route_id"].astype(str) + "_"
            + chunk["begin_point"].astype(str) + "_"
            + chunk["end_point"].astype(str)
        )

        chunk = chunk[[c for c in keep if c in chunk.columns]].copy()
        chunk = chunk[chunk.geometry.notna()].copy()
        chunk["geometry"] = chunk["geometry"].apply(_to_multilinestring)
        chunk = chunk[chunk.geometry.notna()].copy()
        if "county_code" in chunk.columns:
            chunk["county_code"] = chunk["county_code"].apply(
                lambda v: str(int(v)) if pd.notna(v) else None
            )

        chunk.to_postgis("hpms_roads", engine, schema="raw", if_exists="append", index=False)
        rows_loaded += len(chunk)

    logger.info(f"Loaded {rows_loaded} rows into raw.hpms_roads from GDB layer '{layer}'")
    return "raw.hpms_roads"


@task(name="transform_overture")
def transform_overture(parquet_path: Path) -> str:
    logger = get_run_logger()

    def _extract_primary_name(names_val):
        if names_val is None:
            return None
        if isinstance(names_val, dict):
            return names_val.get("primary")
        return None

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE raw.overture_roads"))
        conn.commit()

    pf = pq.ParquetFile(parquet_path)
    rows_loaded = 0
    for batch in pf.iter_batches(batch_size=CHUNK_SIZE, columns=["id", "names", "class", "geometry"]):
        df = batch.to_pandas()
        df["geometry"] = df["geometry"].apply(
            lambda b: wkb_loads(bytes(b)) if b is not None else None
        )
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=4326)
        gdf = gdf[gdf.geometry.notna()].copy()
        gdf = gdf.rename(columns={"id": "overture_id", "class": "road_class"})
        gdf["road_name"] = gdf["names"].apply(_extract_primary_name)
        gdf[["overture_id", "road_name", "road_class", "geometry"]].to_postgis(
            "overture_roads", engine, schema="raw", if_exists="append", index=False
        )
        rows_loaded += len(gdf)

    logger.info(f"Loaded {rows_loaded} rows into raw.overture_roads")
    return "raw.overture_roads"


@task(name="transform_tvt")
def transform_tvt(tvt: dict) -> str:
    logger = get_run_logger()

    rows = []
    for fc_code, group in tvt["fc_to_group"].items():
        for hour in range(24):
            for day in range(1, 8):
                rows.append({
                    "functional_class": fc_code,
                    "hour_of_day": hour,
                    "day_of_week": day,
                    "factor": tvt["hourly_factors"][group][hour] * tvt["dow_factors"][group][day],
                })

    df = pd.DataFrame(rows)
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE raw.tvt_factors"))
        conn.commit()

    df.to_sql("tvt_factors", engine, schema="raw", if_exists="append", index=False)
    logger.info(f"Loaded {len(df)} rows into raw.tvt_factors")
    return "raw.tvt_factors"


@task(name="enrich_roads")
def enrich_roads(hpms_done: str, overture_done: str) -> str:
    # hpms_done and overture_done are Prefect dependency anchors; their values are not used here.
    logger = get_run_logger()

    engine = get_engine()
    hpms_gdf = gpd.read_postgis("SELECT * FROM raw.hpms_roads", engine, geom_col="geometry")
    overture_gdf = gpd.read_postgis(
        "SELECT road_name, geometry FROM raw.overture_roads",
        engine, geom_col="geometry",
    )
    logger.info(f"Joining {len(hpms_gdf)} HPMS segments with {len(overture_gdf)} Overture segments")

    joined = gpd.sjoin_nearest(
        hpms_gdf,
        overture_gdf[["road_name", "geometry"]],
        how="left",
        distance_col="_dist",
    ).drop(columns=["index_right", "_dist"])

    keep = ["road_id", "functional_class", "aadt", "speed_limit",
            "lanes", "county_code", "state_code", "road_name", "geometry"]
    result = joined[[c for c in keep if c in joined.columns]].copy()
    result = result.drop_duplicates(subset=["road_id"])

    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE staging.volume_estimates, staging.roads"))
        conn.commit()

    result.to_postgis("roads", engine, schema="staging", if_exists="append", index=False)
    logger.info(f"Loaded {len(result)} rows into staging.roads")
    return "staging.roads"


@task(name="compute_volume_estimates")
def compute_volume_estimates(roads_done: str) -> str:
    # roads_done is a Prefect dependency anchor; its value is not used here.
    logger = get_run_logger()

    engine = get_engine()
    roads_df = pd.read_sql(
        "SELECT road_id, aadt, functional_class FROM staging.roads WHERE aadt IS NOT NULL",
        engine,
    )
    logger.info(f"Computing volume estimates for {len(roads_df)} roads")

    rows = []
    for _, road in roads_df.iterrows():
        fc = int(road["functional_class"]) if pd.notna(road["functional_class"]) else 7
        group = FUNCTIONAL_CLASS_TO_FACTOR_GROUP.get(fc, "local")
        base = road["aadt"] / 24

        for hour in range(24):
            for day in range(1, 8):
                rows.append({
                    "road_id": road["road_id"],
                    "hour_of_day": hour,
                    "day_of_week": day,
                    "estimated_volume": round(base * HOURLY_FACTORS[group][hour] * DOW_FACTORS[group][day], 1),
                })

    df = pd.DataFrame(rows)

    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE staging.volume_estimates"))
        conn.commit()

    batch_size = 50_000
    for i in range(0, len(df), batch_size):
        df.iloc[i : i + batch_size].to_sql(
            "volume_estimates", engine, schema="staging", if_exists="append", index=False
        )
        logger.info(f"Inserted batch {i}–{min(i + batch_size, len(df))}")

    logger.info(f"Loaded {len(df)} rows into staging.volume_estimates")
    return "staging.volume_estimates"
