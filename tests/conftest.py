"""
Shared fixtures for API integration tests.

Requires TEST_DATABASE_URL to be set (e.g. postgresql://geotraffic:geotraffic@localhost:5432/traffic_test).
All fixtures are session-scoped so the database is set up once per pytest run.
"""
import os

# Set DATABASE_URL before importing app modules so the engine is pointed at the test DB.
_TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
if _TEST_DB:
    os.environ["DATABASE_URL"] = _TEST_DB

import pytest  # noqa: E402
from datetime import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from geoalchemy2 import WKTElement  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import PipelineRun, Road, VolumeEstimate  # noqa: E402

# ---------------------------------------------------------------------------
# Seed geometry: simple MultiLineStrings in South Carolina (SRID 4326)
# ---------------------------------------------------------------------------
# Road 1: central SC, NOT inside Charleston bbox [-80.05, 32.70, -79.85, 32.85]
GEOM_I95 = WKTElement("MULTILINESTRING((-81.0 33.5, -80.95 33.55, -80.9 33.6))", srid=4326)
# Road 2 & 3: inside Charleston bbox
GEOM_US17 = WKTElement("MULTILINESTRING((-79.95 32.75, -79.92 32.78, -79.90 32.80))", srid=4326)
GEOM_LOCAL = WKTElement("MULTILINESTRING((-79.93 32.77, -79.91 32.79))", srid=4326)

SEED_ROADS = [
    {
        "road_id": "road-i95-001",
        "road_name": "I-95",
        "aadt": 120000,
        "speed_limit": 70,
        "lanes": 4,
        "functional_class": 1,
        "county_code": "45019",
        "state_code": "SC",
        "geometry": GEOM_I95,
    },
    {
        "road_id": "road-art-001",
        "road_name": "US-17",
        "aadt": 35000,
        "speed_limit": 55,
        "lanes": 2,
        "functional_class": 4,
        "county_code": "45019",
        "state_code": "SC",
        "geometry": GEOM_US17,
    },
    {
        "road_id": "road-loc-001",
        "road_name": None,
        "aadt": 5000,
        "speed_limit": 30,
        "lanes": 2,
        "functional_class": 7,
        "county_code": "45035",
        "state_code": "SC",
        "geometry": GEOM_LOCAL,
    },
]


def _make_volume_rows(road_id: str) -> list[VolumeEstimate]:
    """168 rows per road. Hour 8 gets double volume to ensure it's the peak hour."""
    rows = []
    for day in range(1, 8):
        for hour in range(24):
            rows.append(
                VolumeEstimate(
                    road_id=road_id,
                    hour_of_day=hour,
                    day_of_week=day,
                    estimated_volume=200.0 if hour == 8 else 100.0,
                )
            )
    return rows


@pytest.fixture(scope="session")
def db_engine():
    if not _TEST_DB:
        pytest.skip("TEST_DATABASE_URL not set; skipping API integration tests")

    engine = create_engine(_TEST_DB)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def seeded_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()

    # Clean out anything left from a previous run
    session.execute(
        text("TRUNCATE TABLE public.volume_estimates, public.roads, public.pipeline_runs RESTART IDENTITY CASCADE")
    )
    session.commit()

    for road_data in SEED_ROADS:
        session.add(Road(**road_data))
    session.commit()

    for road_data in SEED_ROADS:
        session.add_all(_make_volume_rows(road_data["road_id"]))
    session.commit()

    session.add(
        PipelineRun(
            started_at=datetime(2024, 1, 1, 0, 0, 0),
            completed_at=datetime(2024, 1, 1, 0, 15, 0),
            status="success",
            rows_loaded=50000,
            notes=None,
        )
    )
    session.commit()

    yield session
    session.close()


@pytest.fixture(scope="session")
def client(seeded_session, db_engine):
    Session = sessionmaker(bind=db_engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
