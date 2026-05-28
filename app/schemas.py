from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class RoadFeature(BaseModel):
    road_id: str
    road_name: Optional[str] = None
    aadt: Optional[int] = None
    speed_limit: Optional[int] = None
    lanes: Optional[int] = None
    functional_class: Optional[int] = None
    functional_class_name: Optional[str] = None
    county_code: Optional[str] = None
    state_code: Optional[str] = None
    geometry: Any  # GeoJSON geometry dict

    model_config = {"from_attributes": True}


class VolumePoint(BaseModel):
    hour_of_day: int
    day_of_week: int
    day_name: str
    estimated_volume: float


class RoadWithVolume(BaseModel):
    road_id: str
    road_name: Optional[str] = None
    functional_class: Optional[int] = None
    functional_class_name: Optional[str] = None
    estimated_volume: float
    geometry: Any

    model_config = {"from_attributes": True}


class SpatialFilterRequest(BaseModel):
    bbox: list[float]  # [min_lon, min_lat, max_lon, max_lat]


class HighVolumeRoad(BaseModel):
    road_id: str
    road_name: Optional[str] = None
    aadt: int
    functional_class: Optional[int] = None
    functional_class_name: Optional[str] = None
    county_code: Optional[str] = None
    geometry: Any

    model_config = {"from_attributes": True}


class PeakHourSummary(BaseModel):
    functional_class: int
    functional_class_name: str
    peak_hour: int
    avg_estimated_volume: float


class PipelineRunResponse(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    rows_loaded: Optional[int] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
