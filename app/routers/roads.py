import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2.functions import ST_AsGeoJSON, ST_Intersects, ST_MakeEnvelope
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import FUNCTIONAL_CLASS_NAMES
from app.db import get_db
from app.models import Road
from app.schemas import RoadFeature, SpatialFilterRequest

router = APIRouter(prefix="/roads", tags=["roads"])


def _serialize(row) -> dict:
    return {
        "road_id": row.road_id,
        "road_name": row.road_name,
        "aadt": row.aadt,
        "speed_limit": row.speed_limit,
        "lanes": row.lanes,
        "functional_class": row.functional_class,
        "functional_class_name": FUNCTIONAL_CLASS_NAMES.get(row.functional_class),
        "county_code": row.county_code,
        "state_code": row.state_code,
        "geometry": json.loads(row.geometry),
    }


def _base_select():
    return select(
        Road.road_id,
        Road.road_name,
        Road.aadt,
        Road.speed_limit,
        Road.lanes,
        Road.functional_class,
        Road.county_code,
        Road.state_code,
        ST_AsGeoJSON(Road.geometry).label("geometry"),
    )


@router.get("/", response_model=list[RoadFeature])
def list_roads(
    functional_class: Optional[int] = Query(None, description="HPMS F_SYSTEM code 1–7"),
    county: Optional[str] = Query(None, description="County FIPS code"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    stmt = _base_select()

    if functional_class is not None:
        stmt = stmt.where(Road.functional_class == functional_class)
    if county is not None:
        stmt = stmt.where(Road.county_code == county)

    rows = db.execute(stmt.limit(limit)).all()
    return [_serialize(r) for r in rows]


@router.get("/{road_id}", response_model=RoadFeature)
def get_road(road_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        _base_select().where(Road.road_id == road_id)
    ).first()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Road '{road_id}' not found")

    return _serialize(row)


@router.post("/spatial_filter/", response_model=list[RoadFeature])
def spatial_filter(body: SpatialFilterRequest, db: Session = Depends(get_db)):
    if len(body.bbox) != 4:
        raise HTTPException(
            status_code=422,
            detail="bbox must have exactly 4 values: [min_lon, min_lat, max_lon, max_lat]",
        )

    min_lon, min_lat, max_lon, max_lat = body.bbox
    envelope = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)

    rows = db.execute(
        _base_select().where(ST_Intersects(Road.geometry, envelope))
    ).all()

    return [_serialize(r) for r in rows]
