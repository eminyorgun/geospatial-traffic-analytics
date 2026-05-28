import os
import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)


# ---------------------------------------------------------------------------
# GET /patterns/high_volume/
# ---------------------------------------------------------------------------

def test_high_volume_threshold_50k(client):
    # Only I-95 (aadt=120000) exceeds 50,000
    r = client.get("/patterns/high_volume/", params={"threshold": 50000})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["road_id"] == "road-i95-001"
    assert data[0]["aadt"] == 120000


def test_high_volume_threshold_10k(client):
    # I-95 (120k) and US-17 (35k) exceed 10,000
    r = client.get("/patterns/high_volume/", params={"threshold": 10000})
    assert r.status_code == 200
    road_ids = {d["road_id"] for d in r.json()}
    assert road_ids == {"road-i95-001", "road-art-001"}


def test_high_volume_threshold_none_match(client):
    r = client.get("/patterns/high_volume/", params={"threshold": 200000})
    assert r.status_code == 200
    assert r.json() == []


def test_high_volume_ordered_by_aadt_desc(client):
    r = client.get("/patterns/high_volume/", params={"threshold": 0})
    data = r.json()
    aadts = [d["aadt"] for d in data]
    assert aadts == sorted(aadts, reverse=True)


def test_high_volume_filter_functional_class(client):
    r = client.get("/patterns/high_volume/", params={"threshold": 0, "functional_class": 1})
    assert r.status_code == 200
    data = r.json()
    assert all(d["functional_class"] == 1 for d in data)


def test_high_volume_filter_county(client):
    r = client.get("/patterns/high_volume/", params={"threshold": 0, "county": "45019"})
    assert r.status_code == 200
    road_ids = {d["road_id"] for d in r.json()}
    assert road_ids == {"road-i95-001", "road-art-001"}


def test_high_volume_response_shape(client):
    r = client.get("/patterns/high_volume/", params={"threshold": 50000})
    row = r.json()[0]
    for key in ("road_id", "road_name", "aadt", "functional_class",
                "functional_class_name", "county_code", "geometry"):
        assert key in row
    assert isinstance(row["geometry"], dict)
    assert row["functional_class_name"] == "Interstate"


def test_high_volume_missing_threshold(client):
    r = client.get("/patterns/high_volume/")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /patterns/peak_hours/
# ---------------------------------------------------------------------------

def test_peak_hours_all_classes(client):
    r = client.get("/patterns/peak_hours/")
    assert r.status_code == 200
    data = r.json()
    # Seed data has functional classes 1, 4, 7; one entry per class
    classes = {d["functional_class"] for d in data}
    assert classes == {1, 4, 7}


def test_peak_hours_is_hour_8(client):
    # Volume was seeded with hour=8 at 200.0 and all others at 100.0
    r = client.get("/patterns/peak_hours/")
    assert r.status_code == 200
    for entry in r.json():
        assert entry["peak_hour"] == 8, (
            f"Expected peak_hour=8 for fc={entry['functional_class']}, "
            f"got {entry['peak_hour']}"
        )


def test_peak_hours_filter_functional_class(client):
    r = client.get("/patterns/peak_hours/", params={"functional_class": 1})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["functional_class"] == 1
    assert data[0]["functional_class_name"] == "Interstate"


def test_peak_hours_response_shape(client):
    r = client.get("/patterns/peak_hours/")
    row = r.json()[0]
    for key in ("functional_class", "functional_class_name", "peak_hour", "avg_estimated_volume"):
        assert key in row
    assert 0 <= row["peak_hour"] <= 23
    assert row["avg_estimated_volume"] > 0
