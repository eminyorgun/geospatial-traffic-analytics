import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import FUNCTIONAL_CLASS_NAMES
from app.db import get_db
from app.models import Road, VolumeEstimate
from app.schemas import HighVolumeRoad, PeakHourSummary

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("/high_volume/", response_model=list[HighVolumeRoad])
def high_volume(
    threshold: int = Query(..., ge=0, description="Return roads with AADT above this value"),
    functional_class: Optional[int] = Query(None, description="Filter by F_SYSTEM code 1–7"),
    county: Optional[str] = Query(None, description="Filter by county FIPS code"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = select(
        Road.road_id,
        Road.road_name,
        Road.aadt,
        Road.functional_class,
        Road.county_code,
        ST_AsGeoJSON(Road.geometry).label("geometry"),
    ).where(Road.aadt > threshold)

    if functional_class is not None:
        stmt = stmt.where(Road.functional_class == functional_class)
    if county is not None:
        stmt = stmt.where(Road.county_code == county)

    rows = db.execute(stmt.order_by(Road.aadt.desc()).limit(limit)).all()

    return [
        {
            "road_id": r.road_id,
            "road_name": r.road_name,
            "aadt": r.aadt,
            "functional_class": r.functional_class,
            "functional_class_name": FUNCTIONAL_CLASS_NAMES.get(r.functional_class),
            "county_code": r.county_code,
            "geometry": json.loads(r.geometry),
        }
        for r in rows
    ]


@router.get("/peak_hours/", response_model=list[PeakHourSummary])
def peak_hours(
    functional_class: Optional[int] = Query(None, description="Filter by F_SYSTEM code 1–7"),
    db: Session = Depends(get_db),
):
    avg_vol = func.avg(VolumeEstimate.estimated_volume).label("avg_vol")
    rnk = func.rank().over(
        partition_by=Road.functional_class,
        order_by=func.avg(VolumeEstimate.estimated_volume).desc(),
    ).label("rnk")

    inner = (
        select(Road.functional_class, VolumeEstimate.hour_of_day, avg_vol, rnk)
        .join(VolumeEstimate, Road.road_id == VolumeEstimate.road_id)
        .where(Road.functional_class.isnot(None))
        .group_by(Road.functional_class, VolumeEstimate.hour_of_day)
    )

    if functional_class is not None:
        inner = inner.where(Road.functional_class == functional_class)

    sub = inner.subquery()

    rows = db.execute(
        select(sub).where(sub.c.rnk == 1).order_by(sub.c.functional_class)
    ).all()

    return [
        {
            "functional_class": r.functional_class,
            "functional_class_name": FUNCTIONAL_CLASS_NAMES.get(r.functional_class, "Unknown"),
            "peak_hour": r.hour_of_day,
            "avg_estimated_volume": round(float(r.avg_vol), 1),
        }
        for r in rows
    ]
