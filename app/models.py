from datetime import datetime
from typing import Optional

from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, Index, Integer, String, DateTime, Text
from sqlalchemy.orm import mapped_column, Mapped

from app.db import Base


# ---------------------------------------------------------------------------
# Raw layer: source data loaded without modification
# ---------------------------------------------------------------------------

class RawHpmsRoad(Base):
    __tablename__ = "hpms_roads"
    __table_args__ = {"schema": "raw"}

    road_id: Mapped[str] = mapped_column(String, primary_key=True)
    route_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    geometry: Mapped[object] = mapped_column(Geometry("GEOMETRY", srid=4326), nullable=False)
    aadt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lanes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    functional_class: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    county_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class RawOvertureRoad(Base):
    __tablename__ = "overture_roads"
    __table_args__ = {"schema": "raw"}

    overture_id: Mapped[str] = mapped_column(String, primary_key=True)
    geometry: Mapped[object] = mapped_column(Geometry("GEOMETRY", srid=4326), nullable=False)
    road_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    road_class: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class RawTvtFactor(Base):
    __tablename__ = "tvt_factors"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    functional_class: Mapped[int] = mapped_column(Integer, nullable=False)
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    factor: Mapped[float] = mapped_column(Float, nullable=False)


# ---------------------------------------------------------------------------
# Staging layer: transformed and spatially joined
# ---------------------------------------------------------------------------

class StagingRoad(Base):
    __tablename__ = "roads"
    __table_args__ = {"schema": "staging"}

    road_id: Mapped[str] = mapped_column(String, primary_key=True)
    geometry: Mapped[object] = mapped_column(Geometry("MULTILINESTRING", srid=4326), nullable=False)
    road_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    aadt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lanes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    functional_class: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    county_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class StagingVolumeEstimate(Base):
    __tablename__ = "volume_estimates"
    __table_args__ = (
        Index("ix_staging_vol_road_hour_day", "road_id", "hour_of_day", "day_of_week"),
        {"schema": "staging"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    road_id: Mapped[str] = mapped_column(String, ForeignKey("staging.roads.road_id"), nullable=False)
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_volume: Mapped[float] = mapped_column(Float, nullable=False)


# ---------------------------------------------------------------------------
# Public layer: serving layer, read by the API
# ---------------------------------------------------------------------------

class Road(Base):
    __tablename__ = "roads"
    __table_args__ = (
        Index("ix_roads_geometry", "geometry", postgresql_using="gist"),
        Index("ix_roads_functional_class", "functional_class"),
        Index("ix_roads_county", "county_code"),
    )

    road_id: Mapped[str] = mapped_column(String, primary_key=True)
    geometry: Mapped[object] = mapped_column(Geometry("MULTILINESTRING", srid=4326), nullable=False)
    road_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    aadt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lanes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    functional_class: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    county_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class VolumeEstimate(Base):
    __tablename__ = "volume_estimates"
    __table_args__ = (
        Index("ix_vol_road_hour_day", "road_id", "hour_of_day", "day_of_week"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    road_id: Mapped[str] = mapped_column(String, ForeignKey("roads.road_id"), nullable=False)
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_volume: Mapped[float] = mapped_column(Float, nullable=False)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    rows_loaded: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
