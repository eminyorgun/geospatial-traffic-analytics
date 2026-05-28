import zipfile
from pathlib import Path

from prefect import task, get_run_logger

from pipeline.config import (
    DATA_DIR,
    DOW_FACTORS,
    FUNCTIONAL_CLASS_TO_FACTOR_GROUP,
    HOURLY_FACTORS,
)


@task(name="locate_hpms")
def locate_hpms() -> Path:
    logger = get_run_logger()
    zip_path = DATA_DIR / "hpms.zip"
    extract_dir = DATA_DIR / "hpms"

    gdb_files = list(extract_dir.glob("*.gdb"))
    if not extract_dir.exists() or not gdb_files:
        if not zip_path.exists():
            raise FileNotFoundError(
                f"HPMS data not found at {zip_path}. "
                "See README (Data Setup) for download instructions."
            )
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        logger.info(f"Extracted {zip_path} to {extract_dir}")
        gdb_files = list(extract_dir.glob("*.gdb"))
    else:
        logger.info(f"Using extracted HPMS data in {extract_dir}")

    if not gdb_files:
        raise FileNotFoundError(f"No .gdb file found in {extract_dir}")

    logger.info(f"HPMS data ready: {gdb_files[0]}")
    return gdb_files[0]


@task(name="locate_overture")
def locate_overture() -> Path:
    logger = get_run_logger()
    out_path = DATA_DIR / "overture_roads.parquet"

    if not out_path.exists():
        raise FileNotFoundError(
            f"Overture road data not found at {out_path}. "
            "See README (Data Setup) for download instructions."
        )

    logger.info(f"Overture data ready: {out_path}")
    return out_path


@task(name="extract_tvt_factors")
def extract_tvt_factors() -> dict:
    logger = get_run_logger()
    logger.info("Loading TVT factors from embedded constants")
    return {
        "hourly_factors": HOURLY_FACTORS,
        "dow_factors": DOW_FACTORS,
        "fc_to_group": FUNCTIONAL_CLASS_TO_FACTOR_GROUP,
    }
