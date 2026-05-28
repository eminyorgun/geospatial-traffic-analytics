import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DAY_NAME_TO_INT, DAY_OF_WEEK, FUNCTIONAL_CLASS_NAMES
from app.db import get_db
from app.models import Road, VolumeEstimate
from app.schemas import RoadWithVolume, VolumePoint

router = APIRouter(tags=["volume"])


@router.get("/roads/{road_id}/volume", response_model=list[VolumePoint])
def get_road_volume(
    road_id: str,
    day: Optional[str] = Query(None, description="Filter by day name e.g. Monday"),
    hour: Optional[int] = Query(None, ge=0, le=23, description="Filter by hour 0–23"),
    db: Session = Depends(get_db),
):
    road_exists = db.execute(select(Road.road_id).where(Road.road_id == road_id)).first()
    if road_exists is None:
        raise HTTPException(status_code=404, detail=f"Road '{road_id}' not found")

    stmt = select(
        VolumeEstimate.hour_of_day,
        VolumeEstimate.day_of_week,
        VolumeEstimate.estimated_volume,
    ).where(VolumeEstimate.road_id == road_id)

    if day is not None:
        dow = DAY_NAME_TO_INT.get(day)
        if dow is None:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid day '{day}'. Valid: {list(DAY_NAME_TO_INT.keys())}",
            )
        stmt = stmt.where(VolumeEstimate.day_of_week == dow)

    if hour is not None:
        stmt = stmt.where(VolumeEstimate.hour_of_day == hour)

    rows = db.execute(
        stmt.order_by(VolumeEstimate.day_of_week, VolumeEstimate.hour_of_day)
    ).all()

    return [
        {
            "hour_of_day": r.hour_of_day,
            "day_of_week": r.day_of_week,
            "day_name": DAY_OF_WEEK[r.day_of_week],
            "estimated_volume": r.estimated_volume,
        }
        for r in rows
    ]


@router.get("/volume/", response_model=list[RoadWithVolume])
def volume_by_time(
    day: str = Query(..., description="Day name e.g. Monday"),
    hour: int = Query(..., ge=0, le=23, description="Hour of day 0–23"),
    functional_class: Optional[int] = Query(None, description="Filter by F_SYSTEM code 1–7"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    dow = DAY_NAME_TO_INT.get(day)
    if dow is None:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid day '{day}'. Valid: {list(DAY_NAME_TO_INT.keys())}",
        )

    stmt = (
        select(
            Road.road_id,
            Road.road_name,
            Road.functional_class,
            ST_AsGeoJSON(Road.geometry).label("geometry"),
            VolumeEstimate.estimated_volume,
        )
        .join(VolumeEstimate, VolumeEstimate.road_id == Road.road_id)
        .where(
            VolumeEstimate.day_of_week == dow,
            VolumeEstimate.hour_of_day == hour,
        )
    )

    if functional_class is not None:
        stmt = stmt.where(Road.functional_class == functional_class)

    rows = db.execute(stmt.limit(limit)).all()

    return [
        {
            "road_id": r.road_id,
            "road_name": r.road_name,
            "functional_class": r.functional_class,
            "functional_class_name": FUNCTIONAL_CLASS_NAMES.get(r.functional_class),
            "estimated_volume": r.estimated_volume,
            "geometry": json.loads(r.geometry),
        }
        for r in rows
    ]
