from datetime import datetime, timezone

from prefect import flow, get_run_logger

from pipeline.tasks.extract import locate_hpms, locate_overture, extract_tvt_factors
from pipeline.tasks.load import load_serving_layer, log_pipeline_run, validate_load
from pipeline.tasks.transform import (
    compute_volume_estimates,
    enrich_roads,
    transform_hpms,
    transform_overture,
    transform_tvt,
)
from pipeline.tasks.validate import (
    validate_hpms,
    validate_overture,
    validate_tvt_factors,
)


@flow(name="ingest", log_prints=True)
def ingest_flow():
    logger = get_run_logger()
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    counts = {"roads": 0, "volume_estimates": 0}
    status = "failed"
    notes = None

    try:
        # ------------------------------------------------------------------
        # Stage 1: Extract (three sources run in parallel)
        # ------------------------------------------------------------------
        logger.info("Stage 1: Extract")
        shp_path = locate_hpms.submit()
        parquet_path = locate_overture.submit()
        tvt = extract_tvt_factors.submit()

        # ------------------------------------------------------------------
        # Stage 2: Validate raw sources (each waits on its own extract)
        # ------------------------------------------------------------------
        logger.info("Stage 2: Validate raw sources")
        validated_shp = validate_hpms.submit(shp_path)
        validated_parquet = validate_overture.submit(parquet_path)
        validated_tvt = validate_tvt_factors.submit(tvt)

        # ------------------------------------------------------------------
        # Stage 3: Transform into raw schema (parallel per source)
        # ------------------------------------------------------------------
        logger.info("Stage 3: Transform into raw schema")
        hpms_done = transform_hpms.submit(validated_shp)
        overture_done = transform_overture.submit(validated_parquet)
        transform_tvt.submit(validated_tvt)  # raw schema only; failure does not block the pipeline

        # ------------------------------------------------------------------
        # Stage 4: Enrich and stage (sequential, each depends on prior)
        # ------------------------------------------------------------------
        logger.info("Stage 4: Enrich and stage")
        roads_done = enrich_roads(hpms_done, overture_done)
        volume_done = compute_volume_estimates(roads_done)

        # ------------------------------------------------------------------
        # Stage 5: Load to serving layer and validate
        # ------------------------------------------------------------------
        logger.info("Stage 5: Load to serving layer")
        counts = load_serving_layer(roads_done, volume_done)
        validate_load(counts)

        status = "success"
        logger.info("Pipeline completed successfully")

    except Exception as e:
        notes = str(e)
        logger.error(f"Pipeline failed: {e}")
        raise

    finally:
        log_pipeline_run(started_at, counts, status, notes)


if __name__ == "__main__":
    from app.db import init_db

    init_db()
    ingest_flow()
