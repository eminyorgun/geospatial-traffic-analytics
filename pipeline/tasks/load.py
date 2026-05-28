from datetime import datetime, timezone
from typing import Optional

from prefect import task, get_run_logger
from sqlalchemy import text

from pipeline.db import get_engine


@task(name="load_serving_layer")
def load_serving_layer(roads_done: str, volume_done: str) -> dict:
    # roads_done and volume_done are Prefect dependency anchors; their values are not used here.
    logger = get_run_logger()
    engine = get_engine()

    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE public.volume_estimates, public.roads"))

        conn.execute(text("""
            INSERT INTO public.roads
                (road_id, geometry, road_name, aadt, speed_limit, lanes,
                 functional_class, county_code, state_code)
            SELECT road_id, geometry, road_name, aadt, speed_limit, lanes,
                   functional_class, county_code, state_code
            FROM staging.roads
        """))

        conn.execute(text("""
            INSERT INTO public.volume_estimates
                (road_id, hour_of_day, day_of_week, estimated_volume)
            SELECT road_id, hour_of_day, day_of_week, estimated_volume
            FROM staging.volume_estimates
        """))

        road_count = conn.execute(text("SELECT COUNT(*) FROM public.roads")).scalar()
        vol_count = conn.execute(text("SELECT COUNT(*) FROM public.volume_estimates")).scalar()
        conn.commit()

    logger.info(f"Promoted {road_count} roads and {vol_count} volume estimates to public layer")
    return {"roads": road_count, "volume_estimates": vol_count}


@task(name="validate_load")
def validate_load(counts: dict) -> int:
    logger = get_run_logger()
    engine = get_engine()

    with engine.connect() as conn:
        staging_roads = conn.execute(text("SELECT COUNT(*) FROM staging.roads")).scalar()
        public_roads = conn.execute(text("SELECT COUNT(*) FROM public.roads")).scalar()

        if public_roads != staging_roads:
            raise ValueError(
                f"Row count mismatch: staging.roads={staging_roads}, public.roads={public_roads}"
            )

        null_geoms = conn.execute(
            text("SELECT COUNT(*) FROM public.roads WHERE geometry IS NULL")
        ).scalar()
        if null_geoms > 0:
            raise ValueError(f"public.roads has {null_geoms} rows with null geometry")

        if counts["volume_estimates"] == 0:
            raise ValueError("No volume estimates were loaded into the public layer")

        roads_with_estimates = conn.execute(
            text("SELECT COUNT(DISTINCT road_id) FROM public.volume_estimates")
        ).scalar()

    logger.info(
        f"Post-load validation passed: {public_roads} roads, "
        f"{counts['volume_estimates']} volume estimates across {roads_with_estimates} roads"
    )
    return public_roads


@task(name="log_pipeline_run")
def log_pipeline_run(
    started_at: datetime,
    counts: dict,
    status: str,
    notes: Optional[str] = None,
) -> None:
    logger = get_run_logger()
    engine = get_engine()

    total_rows = counts.get("roads", 0) + counts.get("volume_estimates", 0)

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO public.pipeline_runs
                    (started_at, completed_at, status, rows_loaded, notes)
                VALUES
                    (:started_at, :completed_at, :status, :rows_loaded, :notes)
            """),
            {
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "status": status,
                "rows_loaded": total_rows,
                "notes": notes,
            },
        )
        conn.commit()

    logger.info(f"Pipeline run logged: status={status}, rows_loaded={total_rows}")
