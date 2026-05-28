"""
Sanity checks for embedded pipeline constants.
These catch accidental edits that would corrupt the TVT factor tables.
No DB or network required.
"""
import pytest

from pipeline.config import (
    DOW_FACTORS,
    FUNCTIONAL_CLASS_TO_FACTOR_GROUP,
    HOURLY_FACTORS,
    SC_BBOX,
)

EXPECTED_GROUPS = {"interstate", "arterial", "collector", "local"}


def test_sc_bbox_has_four_values():
    assert len(SC_BBOX) == 4


def test_sc_bbox_valid_lon_lat():
    min_lon, min_lat, max_lon, max_lat = SC_BBOX
    assert -180 <= min_lon < max_lon <= 180
    assert -90 <= min_lat < max_lat <= 90


def test_hourly_factors_has_all_groups():
    assert set(HOURLY_FACTORS.keys()) == EXPECTED_GROUPS


@pytest.mark.parametrize("group", list(EXPECTED_GROUPS))
def test_hourly_factors_24_values(group):
    assert len(HOURLY_FACTORS[group]) == 24, f"{group}: expected 24 hourly factors"


@pytest.mark.parametrize("group", list(EXPECTED_GROUPS))
def test_hourly_factors_all_positive(group):
    assert all(v > 0 for v in HOURLY_FACTORS[group]), f"{group}: all hourly factors must be positive"


def test_dow_factors_has_all_groups():
    assert set(DOW_FACTORS.keys()) == EXPECTED_GROUPS


@pytest.mark.parametrize("group", list(EXPECTED_GROUPS))
def test_dow_factors_keys_1_to_7(group):
    assert set(DOW_FACTORS[group].keys()) == {1, 2, 3, 4, 5, 6, 7}


@pytest.mark.parametrize("group", list(EXPECTED_GROUPS))
def test_dow_factors_all_positive(group):
    assert all(v > 0 for v in DOW_FACTORS[group].values())


def test_fc_to_group_covers_all_functional_classes():
    assert set(FUNCTIONAL_CLASS_TO_FACTOR_GROUP.keys()) == {1, 2, 3, 4, 5, 6, 7}


def test_fc_to_group_values_are_valid_groups():
    assert set(FUNCTIONAL_CLASS_TO_FACTOR_GROUP.values()).issubset(EXPECTED_GROUPS)


def test_fc_1_and_2_map_to_interstate():
    assert FUNCTIONAL_CLASS_TO_FACTOR_GROUP[1] == "interstate"
    assert FUNCTIONAL_CLASS_TO_FACTOR_GROUP[2] == "interstate"


def test_fc_7_maps_to_local():
    assert FUNCTIONAL_CLASS_TO_FACTOR_GROUP[7] == "local"
