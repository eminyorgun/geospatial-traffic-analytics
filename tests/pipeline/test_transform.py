"""Unit tests for pipeline transform helper functions. No DB or network required."""
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon

from pipeline.tasks.transform import _to_multilinestring


def test_none_returns_none():
    assert _to_multilinestring(None) is None


def test_linestring_becomes_multilinestring():
    line = LineString([(0, 0), (1, 1)])
    result = _to_multilinestring(line)
    assert isinstance(result, MultiLineString)
    assert list(result.geoms)[0].equals(line)


def test_multilinestring_returned_unchanged():
    mls = MultiLineString([[(0, 0), (1, 1)], [(2, 2), (3, 3)]])
    result = _to_multilinestring(mls)
    assert result is mls


def test_unsupported_type_returns_none():
    assert _to_multilinestring(Point(0, 0)) is None
    assert _to_multilinestring(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])) is None


def test_resulting_multilinestring_has_correct_coordinates():
    line = LineString([(10, 20), (30, 40)])
    result = _to_multilinestring(line)
    coords = list(list(result.geoms)[0].coords)
    assert coords == [(10, 20), (30, 40)]
