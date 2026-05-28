"""
Unit tests for extract tasks.
extract_tvt_factors is so thin (3 lines that return constants) that the
meaningful coverage lives in test_config.py. These tests verify the dict
shape the function promises to callers. No DB or network required.
"""
from unittest.mock import MagicMock, patch

from pipeline.config import DOW_FACTORS, FUNCTIONAL_CLASS_TO_FACTOR_GROUP, HOURLY_FACTORS
from pipeline.tasks.extract import extract_tvt_factors


def test_extract_tvt_factors_returns_dict():
    with patch("pipeline.tasks.extract.get_run_logger", return_value=MagicMock()):
        result = extract_tvt_factors.fn()
    assert isinstance(result, dict)


def test_extract_tvt_factors_has_required_keys():
    with patch("pipeline.tasks.extract.get_run_logger", return_value=MagicMock()):
        result = extract_tvt_factors.fn()
    assert {"hourly_factors", "dow_factors", "fc_to_group"} == set(result.keys())


def test_extract_tvt_factors_returns_config_constants():
    with patch("pipeline.tasks.extract.get_run_logger", return_value=MagicMock()):
        result = extract_tvt_factors.fn()
    assert result["hourly_factors"] is HOURLY_FACTORS
    assert result["dow_factors"] is DOW_FACTORS
    assert result["fc_to_group"] is FUNCTIONAL_CLASS_TO_FACTOR_GROUP
