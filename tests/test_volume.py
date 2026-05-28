import os
import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)


# ---------------------------------------------------------------------------
# GET /roads/{road_id}/volume
# ---------------------------------------------------------------------------

def test_road_volume_all_points(client):
    # 24 hours × 7 days = 168 rows
    r = client.get("/roads/road-i95-001/volume")
    assert r.status_code == 200
    assert len(r.json()) == 168


def test_road_volume_filter_day(client):
    # 24 hours for Monday
    r = client.get("/roads/road-i95-001/volume", params={"day": "Monday"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 24
    assert all(row["day_name"] == "Monday" for row in data)
    assert all(row["day_of_week"] == 2 for row in data)


def test_road_volume_filter_day_and_hour(client):
    r = client.get("/roads/road-i95-001/volume", params={"day": "Monday", "hour": 8})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["hour_of_day"] == 8
    assert data[0]["day_of_week"] == 2
    assert data[0]["estimated_volume"] == 200.0


def test_road_volume_response_shape(client):
    r = client.get("/roads/road-i95-001/volume", params={"day": "Sunday", "hour": 0})
    row = r.json()[0]
    for key in ("hour_of_day", "day_of_week", "day_name", "estimated_volume"):
        assert key in row


def test_road_volume_not_found(client):
    r = client.get("/roads/does-not-exist/volume")
    assert r.status_code == 404


def test_road_volume_invalid_day(client):
    r = client.get("/roads/road-i95-001/volume", params={"day": "Blursday"})
    assert r.status_code == 422


def test_road_volume_all_seven_days_present(client):
    r = client.get("/roads/road-i95-001/volume")
    data = r.json()
    days_seen = {row["day_of_week"] for row in data}
    assert days_seen == {1, 2, 3, 4, 5, 6, 7}


# ---------------------------------------------------------------------------
# GET /volume/
# ---------------------------------------------------------------------------

def test_volume_by_time_returns_all_roads(client):
    r = client.get("/volume/", params={"day": "Monday", "hour": 8})
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_volume_by_time_filter_functional_class(client):
    r = client.get("/volume/", params={"day": "Monday", "hour": 8, "functional_class": 1})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["road_id"] == "road-i95-001"


def test_volume_by_time_limit(client):
    r = client.get("/volume/", params={"day": "Monday", "hour": 8, "limit": 2})
    assert r.status_code == 200
    assert len(r.json()) <= 2


def test_volume_by_time_response_shape(client):
    r = client.get("/volume/", params={"day": "Monday", "hour": 8, "functional_class": 1})
    row = r.json()[0]
    for key in ("road_id", "road_name", "functional_class", "functional_class_name",
                "estimated_volume", "geometry"):
        assert key in row
    assert isinstance(row["geometry"], dict)


def test_volume_by_time_peak_hour_volume(client):
    # Hour 8 was seeded with 200.0; all other hours with 100.0
    r = client.get("/volume/", params={"day": "Monday", "hour": 8, "functional_class": 1})
    assert r.json()[0]["estimated_volume"] == 200.0

    r2 = client.get("/volume/", params={"day": "Monday", "hour": 0, "functional_class": 1})
    assert r2.json()[0]["estimated_volume"] == 100.0


def test_volume_by_time_invalid_day(client):
    r = client.get("/volume/", params={"day": "Blursday", "hour": 8})
    assert r.status_code == 422


def test_volume_by_time_missing_required_params(client):
    r = client.get("/volume/")
    assert r.status_code == 422
