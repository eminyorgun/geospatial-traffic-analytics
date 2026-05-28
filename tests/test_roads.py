import os
import pytest

if not os.environ.get("TEST_DATABASE_URL"):
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)


# ---------------------------------------------------------------------------
# GET /roads/
# ---------------------------------------------------------------------------

def test_list_roads_returns_all(client):
    r = client.get("/roads/")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3


def test_list_roads_filter_functional_class(client):
    r = client.get("/roads/", params={"functional_class": 1})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["road_id"] == "road-i95-001"
    assert data[0]["functional_class"] == 1
    assert data[0]["functional_class_name"] == "Interstate"


def test_list_roads_filter_county(client):
    r = client.get("/roads/", params={"county": "45019"})
    assert r.status_code == 200
    road_ids = {d["road_id"] for d in r.json()}
    assert road_ids == {"road-i95-001", "road-art-001"}


def test_list_roads_limit(client):
    r = client.get("/roads/", params={"limit": 1})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_list_roads_no_match(client):
    r = client.get("/roads/", params={"county": "00000"})
    assert r.status_code == 200
    assert r.json() == []


def test_list_roads_response_shape(client):
    r = client.get("/roads/", params={"functional_class": 1})
    road = r.json()[0]
    for key in ("road_id", "road_name", "aadt", "speed_limit", "lanes",
                "functional_class", "functional_class_name", "county_code",
                "state_code", "geometry"):
        assert key in road, f"Missing key: {key}"
    # geometry must be a GeoJSON dict
    assert isinstance(road["geometry"], dict)
    assert road["geometry"]["type"] in ("LineString", "MultiLineString")


# ---------------------------------------------------------------------------
# GET /roads/{road_id}
# ---------------------------------------------------------------------------

def test_get_road_found(client):
    r = client.get("/roads/road-i95-001")
    assert r.status_code == 200
    data = r.json()
    assert data["road_id"] == "road-i95-001"
    assert data["road_name"] == "I-95"
    assert data["aadt"] == 120000


def test_get_road_null_name(client):
    r = client.get("/roads/road-loc-001")
    assert r.status_code == 200
    assert r.json()["road_name"] is None


def test_get_road_not_found(client):
    r = client.get("/roads/does-not-exist")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /roads/spatial_filter/
# ---------------------------------------------------------------------------

def test_spatial_filter_charleston_bbox(client):
    # Roads 2 and 3 are inside Charleston bbox; Road 1 is not
    r = client.post(
        "/roads/spatial_filter/",
        json={"bbox": [-80.05, 32.70, -79.85, 32.85]},
    )
    assert r.status_code == 200
    road_ids = {d["road_id"] for d in r.json()}
    assert road_ids == {"road-art-001", "road-loc-001"}


def test_spatial_filter_no_match(client):
    # Ocean off South Carolina coast, no roads
    r = client.post(
        "/roads/spatial_filter/",
        json={"bbox": [-77.0, 32.0, -76.0, 32.5]},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_spatial_filter_wrong_bbox_length(client):
    r = client.post(
        "/roads/spatial_filter/",
        json={"bbox": [-80.0, 33.0]},
    )
    assert r.status_code == 422
