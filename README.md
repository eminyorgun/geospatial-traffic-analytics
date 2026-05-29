# Geospatial Traffic Analytics

An ETL pipeline and geospatial REST API for road network traffic volume analysis. Ingests standardized US federal road data (HPMS GeoDatabase), enriches road segments with readable names via nearest-neighbor spatial join against Overture Maps, applies FHWA TVT adjustment factors to produce hourly vehicle count estimates, and serves the results through a PostGIS-backed REST API.

Built with Prefect for pipeline orchestration, GeoPandas for geospatial transforms, GeoAlchemy2 + SQLAlchemy ORM for PostGIS persistence, and FastAPI + Pydantic for the serving layer.

Built around standardized federal data. Swap two data files to run against any US state.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Data Sources                                  │
│                                                                      │
│  FHWA HPMS GeoDatabase   Overture Maps (parquet)   FHWA TVT Factors │
│  (roads + AADT)          (road names)              (embedded consts) │
└────────────┬─────────────────────┬──────────────────────────────────┘
             │                     │
         manually placed       manually placed
             │                     │
             ▼                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Prefect Pipeline                                 │
│                                                                      │
│  Locate → Validate → Transform → Enrich → Load                      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PostgreSQL + PostGIS                                         │   │
│  │                                                              │   │
│  │  raw schema         staging schema      public schema        │   │
│  │  (immutable)        (transformed)       (serving layer)      │   │
│  │  ─────────────      ───────────────     ─────────────────    │   │
│  │  hpms_roads         roads               roads                │   │
│  │  overture_roads     volume_estimates    volume_estimates      │   │
│  │  tvt_factors                            pipeline_runs         │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FastAPI  (port 8000)                                                │
│                                                                      │
│  GET  /roads/                    ← filter by class, county          │
│  GET  /roads/{road_id}           ← single road                      │
│  POST /roads/spatial_filter/     ← bbox intersection                │
│  GET  /roads/{road_id}/volume    ← hourly estimates for one road    │
│  GET  /volume/                   ← all roads at a given hour + day  │
│  GET  /patterns/high_volume/     ← roads exceeding AADT threshold   │
│  GET  /patterns/peak_hours/      ← busiest hour per road class      │
│  GET  /pipeline/runs             ← pipeline run history             │
│  GET  /health                                                        │
│  GET  /docs  (Swagger UI)                                           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

| Source | What it provides | Format |
|--------|-----------------|--------|
| **FHWA HPMS** | Road geometries, AADT, speed limits, lane counts, functional class | GeoDatabase (zip) |
| **Overture Maps** | Road names for segment enrichment | GeoParquet |
| **FHWA TVT Factors** | Hourly and day-of-week volume adjustment factors by road class | Embedded constants |

**AADT** (Annual Average Daily Traffic) is the estimated number of vehicles passing a point on a road on an average day. TVT factors convert AADT into hourly estimates by road class. Roads are grouped into four classes: `interstate` (F_SYSTEM 1–2), `arterial` (3–4), `collector` (5–6), `local` (7). Each group has its own 24-hour profile and day-of-week profile.

```
estimated_vehicles = (AADT ÷ 24) × hourly_factor × day_of_week_factor
```

---

## Data Setup

The pipeline does not download data automatically. Place the two data files below before starting the stack.

### 1. HPMS GeoDatabase → `./data/hpms.zip`

The HPMS GeoDatabase contains road geometries, AADT, functional class, speed limits, and lane counts for all 50 US states in a single file. Each state is a separate layer (e.g. `HPMS_FULL_SC_2024`).

Download from the FHWA HPMS ArcGIS item:
```
https://www.arcgis.com/sharing/rest/content/items/5e6a977c2d7c4ec1bdc82e684d3384f2/data
```

Place the downloaded zip at `./data/hpms.zip`. The pipeline extracts it automatically on first run.

> HPMS is a federal standard; all 50 states use the same column schema.

### 2. Overture Roads → `./data/overture_roads.parquet`

The Overture parquet provides road names used to enrich HPMS segments. Run this once from the project root:

```bash
pip install overturemaps
overturemaps download \
  --bbox=<min_lon>,<min_lat>,<max_lon>,<max_lat> \
  --type=segment \
  -f geoparquet \
  -o data/overture_roads.parquet
```

Replace `<min_lon>,<min_lat>,<max_lon>,<max_lat>` with the bounding box of the state you loaded. Look up any state's bounding box at https://boundingbox.klokantech.com. Select the state, choose **CSV** format, and copy the four numbers.

**Example bounding boxes:**

| State | `--bbox` value |
|-------|---------------|
| South Carolina | `-83.35,32.03,-78.54,35.22` |
| Texas | `-106.65,25.84,-93.51,36.50` |
| California | `-124.48,32.53,-114.13,42.01` |
| New York | `-79.76,40.50,-71.86,45.01` |
| Florida | `-87.63,24.40,-79.97,31.00` |

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Data files placed as described in **Data Setup** above
- `.env` file created from `.env.example` (see step 1 below)

### 1. Configure your state

Copy the example environment file and set the 2-letter state abbreviation you want to load:

```bash
cp .env.example .env
```

Open `.env` and set your values:

```
HPMS_STATE=SC
HPMS_SAMPLE=5000
```

- `HPMS_STATE`: 2-letter state abbreviation to load from the GDB (e.g. `SC`, `TX`, `CA`)
- `HPMS_SAMPLE`: limits how many road segments are loaded. `5000` is recommended for a first run; the pipeline finishes in under a minute. To load all segments for the state, remove this line or leave it empty.

### 2. Start the stack

```bash
docker compose up --build
```

The pipeline locates the data files, runs all transforms, and loads the serving layer. Subsequent runs reuse the extracted data.

| Service | URL |
|---------|-----|
| API + Swagger UI | http://localhost:8000/docs |
| Prefect UI | http://localhost:4200 |

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health

# Roads filtered by functional class (1 = Interstate)
curl "http://localhost:8000/roads/?functional_class=1&limit=5"

# Hourly volume for a specific road on Monday at 8am
curl "http://localhost:8000/roads/{road_id}/volume?day=Monday&hour=8"

# All arterials on Monday at 8am (AM peak)
curl "http://localhost:8000/volume/?day=Monday&hour=8&functional_class=4"

# Roads with AADT above 50,000
curl "http://localhost:8000/patterns/high_volume/?threshold=50000"

# Busiest hour per road class
curl "http://localhost:8000/patterns/peak_hours/"

# Pipeline run history
curl "http://localhost:8000/pipeline/runs"
```

### 4. Spatial filter (POST)

```bash
curl -X POST http://localhost:8000/roads/spatial_filter/ \
  -H "Content-Type: application/json" \
  -d '{"bbox": [-80.05, 32.70, -79.85, 32.85]}'
```

---

## Switching States

The HPMS GeoDatabase contains all 50 states; you do not need to re-download it. To switch states:

1. Open `.env` and change `HPMS_STATE` to the new 2-letter code (e.g. `TX`)
2. Replace the Overture parquet with one covering the new state's bounding box:
   ```bash
   rm ./data/overture_roads.parquet
   overturemaps download --bbox=<new_bbox> --type=segment -f geoparquet -o data/overture_roads.parquet
   ```
3. Run `docker compose up --build`

---

## API Reference

### Time encoding

| `day` param | Meaning |
|-------------|---------|
| `Sunday` | 1 |
| `Monday` | 2 |
| … | … |
| `Saturday` | 7 |

Hours are 0–23 (24-hour clock).

### Functional class codes (HPMS F_SYSTEM)

| Code | Name |
|------|------|
| 1 | Interstate |
| 2 | Principal Arterial - Freeway |
| 3 | Principal Arterial - Other |
| 4 | Minor Arterial |
| 5 | Major Collector |
| 6 | Minor Collector |
| 7 | Local |

### `GET /roads/`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `functional_class` | int | no | F_SYSTEM code 1–7 |
| `county` | string | no | FIPS county code |
| `limit` | int | no | Max results (default 100, max 1000) |

### `GET /roads/{road_id}`

Returns a single road or 404.

`road_id` format: `{route_id}_{begin_point}_{end_point}`, for example `04010008500S_9.77_20.66`. This uniquely identifies a segment: which route it belongs to and where along that route it runs (in miles).

### `POST /roads/spatial_filter/`

```json
{ "bbox": [-80.05, 32.70, -79.85, 32.85] }
```

Returns all roads whose geometry intersects the bounding box `[min_lon, min_lat, max_lon, max_lat]`.

### `GET /roads/{road_id}/volume`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `day` | string | no | Filter by day name |
| `hour` | int | no | Filter by hour 0–23 |

Returns up to 168 volume points (24 hours × 7 days) or filtered subset.

### `GET /volume/`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `day` | string | yes | Day name e.g. `Monday` |
| `hour` | int | yes | Hour 0–23 |
| `functional_class` | int | no | Filter by F_SYSTEM code |
| `limit` | int | no | Max results (default 100) |

### `GET /patterns/high_volume/`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `threshold` | int | yes | AADT above this value |
| `functional_class` | int | no | Filter by F_SYSTEM code |
| `county` | string | no | Filter by county FIPS code |
| `limit` | int | no | Max results (default 100, max 1000) |

Returns roads ordered by AADT descending.

### `GET /patterns/peak_hours/`

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `functional_class` | int | no | Filter to one road class |

Returns the busiest hour of day per road class based on average estimated volume.

### `GET /pipeline/runs`

Returns pipeline run history ordered by most recent first.

---

## Tests

### Install test dependencies

```bash
pip install -r requirements.api.txt -r requirements.pipeline.txt -r requirements.test.txt
```

### Unit tests (no database required)

```bash
pytest tests/pipeline/ -v
```

### API integration tests (requires the stack)

Start the stack first, then point `TEST_DATABASE_URL` at a **separate test database** to avoid truncating pipeline-loaded data:

```bash
docker compose up --build
```

```bash
TEST_DATABASE_URL=postgresql://geotraffic:geotraffic@localhost:5432/traffic_test pytest tests/ -v
```

The integration tests create the schema automatically, seed their own data (3 roads, 504 volume estimates, 1 pipeline run), and truncate the target database at the start of each run. **Do not point `TEST_DATABASE_URL` at the main `traffic` database**; doing so will truncate all pipeline-loaded data. Without `TEST_DATABASE_URL` set, the API test modules are skipped automatically.

---

## Project Structure

```
geospatial-traffic-analytics/
│
├── docker-compose.yml          ← 4 services: db, prefect-server, prefect-worker, api
├── Dockerfile.api              ← FastAPI container
├── Dockerfile.worker           ← Prefect worker container
├── requirements.api.txt
├── requirements.pipeline.txt
├── requirements.test.txt
├── .env.example
│
├── data/                       ← Place input files here before running (gitignored)
│   ├── hpms.zip                ← HPMS GeoDatabase zip (downloaded manually)
│   └── overture_roads.parquet  ← Overture road segments (downloaded manually)
│
├── pipeline/                   ← Prefect pipeline
│   ├── flows/
│   │   └── ingest.py           ← Main flow, wires all tasks
│   ├── tasks/
│   │   ├── extract.py          ← locate_hpms, locate_overture, extract_tvt_factors
│   │   ├── validate.py         ← validate_hpms, validate_overture, validate_tvt_factors
│   │   ├── transform.py        ← transform_hpms, transform_overture, transform_tvt,
│   │   │                           enrich_roads, compute_volume_estimates
│   │   └── load.py             ← load_serving_layer, validate_load, log_pipeline_run
│   ├── config.py               ← TVT factor tables, PipelineSettings (HPMS_STATE, HPMS_SAMPLE)
│   └── db.py                   ← get_engine() helper used by transform and load tasks
│
├── app/                        ← FastAPI application
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models.py               ← ORM models for all 3 schema layers
│   ├── schemas.py              ← Pydantic response models
│   ├── constants.py            ← Functional class names, day-of-week mappings
│   └── routers/
│       ├── roads.py
│       ├── volume.py
│       ├── patterns.py
│       └── pipeline.py
│
├── tests/                      ← Test suite
│   ├── conftest.py             ← DB fixture, seed data, TestClient
│   ├── test_health.py
│   ├── test_roads.py
│   ├── test_volume.py
│   ├── test_patterns.py
│   ├── test_pipeline_runs.py
│   └── pipeline/               ← Unit tests (no DB)
│       ├── test_config.py
│       ├── test_validate.py
│       ├── test_extract.py
│       └── test_transform.py
```

---

## Pipeline Details

The pipeline runs automatically when the stack starts. Progress is visible in the Prefect UI at http://localhost:4200.

### Stages

**Stage 1: Locate** (`pipeline/tasks/extract.py`)

Finds the input files and loads the TVT constants. Runs three tasks in parallel:
- `locate_hpms`: checks `./data/hpms.zip`, extracts it to `./data/hpms/` if not already extracted, returns the path to `HPMS2024.gdb`
- `locate_overture`: checks that `./data/overture_roads.parquet` exists
- `extract_tvt_factors`: loads the FHWA hourly and day-of-week adjustment factors from embedded constants in `pipeline/config.py`

If either data file is missing the pipeline stops immediately with a clear error message.

---

**Stage 2: Validate** (`pipeline/tasks/validate.py`)

Validates each source against an explicit data contract before anything is written to the database. Runs three tasks in parallel:
- `validate_hpms`: reads the state layer from the GDB, checks row count ≥ 1,000, required columns (`f_system`, `aadt`, `geometry`) are present, and CRS is defined
- `validate_overture`: reads parquet metadata only (no rows loaded), checks row count ≥ 5,000 and required columns (`id`, `names`, `class`, `geometry`) are present
- `validate_tvt_factors`: checks all four road class groups are present, each has exactly 24 hourly factors, and all values are positive

A failure in any validation task stops the pipeline before anything is written to the database.

---

**Stage 3: Transform** (`pipeline/tasks/transform.py`)

Reads, cleans, and writes each source into the `raw` database schema. Runs three tasks in parallel:

- `transform_hpms`: chunked ingestion from the GDB in batches of 10,000 rows. Per batch: CRS normalization to EPSG:4326, column mapping to standard names, composite `road_id` key generation (`route_id + begin_point + end_point`), float-to-string cast for county FIPS codes, geometry coercion to MultiLineString, write to `raw.hpms_roads`. Honors `HPMS_SAMPLE` for partial loads.

- `transform_overture`: chunked ingestion from GeoParquet in batches of 10,000 rows with column projection (4 columns only). Per batch: WKB decoding to Shapely geometry objects, primary name extraction from the nested `names` struct, column renaming, write to `raw.overture_roads`.

- `transform_tvt`: expands the TVT constants into a flat table of 672 rows (4 factor groups × 24 hours × 7 days), writes to `raw.tvt_factors`.

---

**Stage 4: Enrich** (`pipeline/tasks/transform.py`, `enrich_roads`)

Performs a nearest-neighbor spatial join (GeoPandas `sjoin_nearest`) between `raw.hpms_roads` and `raw.overture_roads` to enrich each HPMS segment with the name of its closest Overture counterpart. Duplicate matches from equidistant candidates are deduplicated. Result is written to `staging.roads`.

---

**Stage 5: Compute** (`pipeline/tasks/transform.py`, `compute_volume_estimates`)

For each road in `staging.roads` that has a non-null AADT, generates 168 volume estimates (24 hours × 7 days):

```
estimated_volume = (aadt ÷ 24) × hourly_factor × day_of_week_factor
```

Factors come from `raw.tvt_factors` via the embedded constants. Roads are assigned to one of four factor groups based on their functional class: `interstate` (class 1–2), `arterial` (3–4), `collector` (5–6), `local` (7). Results are written to `staging.volume_estimates` in batches of 50,000 rows.

---

**Stage 6: Load** (`pipeline/tasks/load.py`)

Atomically promotes staging data to the public serving layer. The load is idempotent: existing data is always truncated before each run, so re-running produces a clean state with no duplicates.

1. Truncates `public.volume_estimates` and `public.roads` in one statement (required to satisfy the FK constraint)
2. Copies all rows from `staging.roads` → `public.roads`
3. Copies all rows from `staging.volume_estimates` → `public.volume_estimates`
4. Post-load validation: row counts must match staging, no null geometries, volume estimates must be non-zero

---

**Stage 7: Log** (`pipeline/tasks/load.py`, `log_pipeline_run`)

Writes a record to `public.pipeline_runs` with start time, end time, status (`success` or `failed`), total rows loaded, and error notes if the pipeline failed. This record is accessible via `GET /pipeline/runs`.
