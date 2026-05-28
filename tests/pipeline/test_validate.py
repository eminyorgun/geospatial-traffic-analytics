"""
Unit tests for pipeline validate tasks.
All external I/O (file reads, logger) is mocked; no DB or network required.
"""
import copy
from pathlib import Path
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from pipeline.config import DOW_FACTORS, FUNCTIONAL_CLASS_TO_FACTOR_GROUP, HOURLY_FACTORS
from pipeline.tasks.validate import (
    MIN_HPMS_ROWS,
    MIN_OVERTURE_ROWS,
    validate_hpms,
    validate_overture,
    validate_tvt_factors,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hpms_gdf(n=MIN_HPMS_ROWS + 100, cols=None, crs=4326):
    include = cols if cols is not None else {"f_system", "aadt", "geometry"}
    data = {}
    if "f_system" in include:
        data["f_system"] = [1] * n
    if "aadt" in include:
        data["aadt"] = [10000] * n
    geoms = gpd.GeoSeries([LineString([(0, 0), (1, 1)])] * n)
    gdf = gpd.GeoDataFrame(data, geometry=geoms)
    if crs:
        gdf = gdf.set_crs(epsg=crs)
    return gdf


def _make_mock_overture_file(n=MIN_OVERTURE_ROWS + 100, cols=None, geom_nulls=0):
    if cols is None:
        cols = ["id", "names", "class", "geometry"]
    mock_pf = MagicMock()
    mock_pf.metadata.num_rows = n
    mock_pf.metadata.num_row_groups = 1
    mock_pf.schema_arrow.names = cols
    mock_geom_col = MagicMock()
    mock_geom_col.null_count = geom_nulls
    mock_pf.read_row_group.return_value.column.return_value = mock_geom_col
    return mock_pf


def _valid_tvt():
    """Build a valid TVT dict directly from config constants (avoids duckdb import chain).
    Deep-copies mutable dicts so each test gets an independent copy to mutate.
    """
    return {
        "hourly_factors": copy.deepcopy(HOURLY_FACTORS),
        "dow_factors": copy.deepcopy(DOW_FACTORS),
        "fc_to_group": FUNCTIONAL_CLASS_TO_FACTOR_GROUP,
    }


# ---------------------------------------------------------------------------
# validate_hpms
# ---------------------------------------------------------------------------

class TestValidateHpms:
    def test_file_not_found_raises(self):
        missing = Path("/tmp/does_not_exist_abc123.shp")
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            with pytest.raises(FileNotFoundError):
                validate_hpms.fn(missing)

    def test_too_few_rows_raises(self, tmp_path):
        gdb = tmp_path / "test.gdb"
        gdb.touch()
        gdf = _make_hpms_gdf(n=MIN_HPMS_ROWS - 1)
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.fiona.listlayers", return_value=["HPMS_FULL_SC_2024"]),
            patch("pipeline.tasks.validate.gpd.read_file", return_value=gdf),
        ):
            with pytest.raises(ValueError, match="rows"):
                validate_hpms.fn(gdb)

    def test_missing_column_raises(self, tmp_path):
        gdb = tmp_path / "test.gdb"
        gdb.touch()
        gdf = _make_hpms_gdf(cols={"aadt", "geometry"})  # no f_system
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.fiona.listlayers", return_value=["HPMS_FULL_SC_2024"]),
            patch("pipeline.tasks.validate.gpd.read_file", return_value=gdf),
        ):
            with pytest.raises(ValueError, match="column"):
                validate_hpms.fn(gdb)

    def test_no_crs_raises(self, tmp_path):
        gdb = tmp_path / "test.gdb"
        gdb.touch()
        gdf = _make_hpms_gdf(crs=None)
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.fiona.listlayers", return_value=["HPMS_FULL_SC_2024"]),
            patch("pipeline.tasks.validate.gpd.read_file", return_value=gdf),
        ):
            with pytest.raises(ValueError, match="CRS"):
                validate_hpms.fn(gdb)

    def test_valid_data_returns_path(self, tmp_path):
        gdb = tmp_path / "test.gdb"
        gdb.touch()
        gdf = _make_hpms_gdf()
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.fiona.listlayers", return_value=["HPMS_FULL_SC_2024"]),
            patch("pipeline.tasks.validate.gpd.read_file", return_value=gdf),
        ):
            result = validate_hpms.fn(gdb)
        assert result == gdb


# ---------------------------------------------------------------------------
# validate_overture
# ---------------------------------------------------------------------------

class TestValidateOverture:
    def test_file_not_found_raises(self):
        missing = Path("/tmp/does_not_exist_xyz.parquet")
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            with pytest.raises(FileNotFoundError):
                validate_overture.fn(missing)

    def test_too_few_rows_raises(self, tmp_path):
        pq_file = tmp_path / "test.parquet"
        pq_file.touch()
        mock_pf = _make_mock_overture_file(n=MIN_OVERTURE_ROWS - 1)
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.pq.ParquetFile", return_value=mock_pf),
        ):
            with pytest.raises(ValueError, match="rows"):
                validate_overture.fn(pq_file)

    def test_missing_column_raises(self, tmp_path):
        pq_file = tmp_path / "test.parquet"
        pq_file.touch()
        mock_pf = _make_mock_overture_file(cols=["id", "names"])
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.pq.ParquetFile", return_value=mock_pf),
        ):
            with pytest.raises(ValueError, match="column"):
                validate_overture.fn(pq_file)

    def test_all_null_geometry_raises(self, tmp_path):
        pq_file = tmp_path / "test.parquet"
        pq_file.touch()
        n = MIN_OVERTURE_ROWS + 100
        mock_pf = _make_mock_overture_file(n=n, geom_nulls=n)
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.pq.ParquetFile", return_value=mock_pf),
        ):
            with pytest.raises(ValueError, match="geometry"):
                validate_overture.fn(pq_file)

    def test_valid_data_returns_path(self, tmp_path):
        pq_file = tmp_path / "test.parquet"
        pq_file.touch()
        mock_pf = _make_mock_overture_file()
        with (
            patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()),
            patch("pipeline.tasks.validate.pq.ParquetFile", return_value=mock_pf),
        ):
            result = validate_overture.fn(pq_file)
        assert result == pq_file


# ---------------------------------------------------------------------------
# validate_tvt_factors
# ---------------------------------------------------------------------------

class TestValidateTvtFactors:
    def test_valid_constants_pass(self):
        tvt = _valid_tvt()
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            result = validate_tvt_factors.fn(tvt)
        assert result is tvt

    def test_missing_group_raises(self):
        tvt = _valid_tvt()
        del tvt["hourly_factors"]["interstate"]
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            with pytest.raises(ValueError, match="group"):
                validate_tvt_factors.fn(tvt)

    def test_wrong_hour_count_raises(self):
        tvt = _valid_tvt()
        tvt["hourly_factors"]["interstate"] = [1.0] * 12
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            with pytest.raises(ValueError, match="24"):
                validate_tvt_factors.fn(tvt)

    def test_non_positive_hourly_factor_raises(self):
        tvt = _valid_tvt()
        tvt["hourly_factors"]["interstate"][0] = -0.5
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            with pytest.raises(ValueError, match="non-positive"):
                validate_tvt_factors.fn(tvt)

    def test_missing_dow_key_raises(self):
        tvt = _valid_tvt()
        del tvt["dow_factors"]["arterial"][7]
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            with pytest.raises(ValueError, match="1–7"):
                validate_tvt_factors.fn(tvt)

    def test_non_positive_dow_factor_raises(self):
        tvt = _valid_tvt()
        tvt["dow_factors"]["local"][1] = 0.0
        with patch("pipeline.tasks.validate.get_run_logger", return_value=MagicMock()):
            with pytest.raises(ValueError, match="non-positive"):
                validate_tvt_factors.fn(tvt)
