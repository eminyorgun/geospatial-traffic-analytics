from pathlib import Path

import fiona
import geopandas as gpd
import pyarrow.parquet as pq
from prefect import task, get_run_logger

from pipeline.config import pipeline_settings

REQUIRED_HPMS_COLS = {"f_system", "aadt", "geometry"}
REQUIRED_OVERTURE_COLS = {"id", "names", "class", "geometry"}
REQUIRED_FACTOR_GROUPS = {"interstate", "arterial", "collector", "local"}

MIN_HPMS_ROWS = 1_000
MIN_OVERTURE_ROWS = 5_000


@task(name="validate_hpms")
def validate_hpms(shp_path: Path) -> Path:
    logger = get_run_logger()

    if not shp_path.exists():
        raise FileNotFoundError(f"HPMS shapefile not found: {shp_path}")

    state = pipeline_settings.hpms_state.upper()
    available = fiona.listlayers(str(shp_path))
    layer = next((l for l in available if f"_{state}_" in l), None)
    if layer is None:
        raise ValueError(f"No HPMS layer found for state '{state}' in {shp_path}")
    gdf = gpd.read_file(shp_path, layer=layer)
    row_count = len(gdf)

    if row_count < MIN_HPMS_ROWS:
        raise ValueError(f"HPMS has {row_count} rows, expected at least {MIN_HPMS_ROWS}")

    missing_cols = REQUIRED_HPMS_COLS - set(gdf.columns)
    if missing_cols:
        raise ValueError(f"HPMS missing required columns: {missing_cols}")

    if gdf.crs is None:
        raise ValueError("HPMS shapefile has no CRS defined")

    null_geoms = gdf.geometry.isna().sum()
    if null_geoms > 0:
        logger.warning(f"{null_geoms} HPMS rows have null geometry; they will be dropped in transform")

    logger.info(f"HPMS validation passed: {row_count} rows, CRS={gdf.crs.to_epsg()}")
    return shp_path


@task(name="validate_overture")
def validate_overture(parquet_path: Path) -> Path:
    logger = get_run_logger()

    if not parquet_path.exists():
        raise FileNotFoundError(f"Overture parquet not found: {parquet_path}")

    pf = pq.ParquetFile(parquet_path)
    meta = pf.metadata
    row_count = meta.num_rows
    cols = set(pf.schema_arrow.names)

    if row_count < MIN_OVERTURE_ROWS:
        raise ValueError(f"Overture has {row_count} rows, expected at least {MIN_OVERTURE_ROWS}")

    missing_cols = REQUIRED_OVERTURE_COLS - cols
    if missing_cols:
        raise ValueError(f"Overture parquet missing required columns: {missing_cols}")

    geom_nulls = sum(
        pf.read_row_group(i, columns=["geometry"]).column("geometry").null_count
        for i in range(meta.num_row_groups)
    )
    if geom_nulls == row_count:
        raise ValueError("Overture geometry column is entirely null")

    logger.info(f"Overture validation passed: {row_count} rows")
    return parquet_path


@task(name="validate_tvt_factors")
def validate_tvt_factors(tvt: dict) -> dict:
    logger = get_run_logger()

    missing_groups = REQUIRED_FACTOR_GROUPS - set(tvt["hourly_factors"].keys())
    if missing_groups:
        raise ValueError(f"TVT hourly factors missing groups: {missing_groups}")

    for group, factors in tvt["hourly_factors"].items():
        if len(factors) != 24:
            raise ValueError(
                f"TVT hourly factors for '{group}' has {len(factors)} values, expected 24"
            )
        if any(f <= 0 for f in factors):
            raise ValueError(
                f"TVT hourly factors for '{group}' contain non-positive values"
            )

    for group, dow in tvt["dow_factors"].items():
        if set(dow.keys()) != {1, 2, 3, 4, 5, 6, 7}:
            raise ValueError(
                f"TVT day-of-week factors for '{group}' must have keys 1–7"
            )
        if any(f <= 0 for f in dow.values()):
            raise ValueError(
                f"TVT day-of-week factors for '{group}' contain non-positive values"
            )

    logger.info(f"TVT validation passed: {len(tvt['hourly_factors'])} road classes verified")
    return tvt
