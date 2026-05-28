from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path(__file__).parent.parent / "data"

# South Carolina bounding box (min_lon, min_lat, max_lon, max_lat)
SC_BBOX = (-83.35, 32.03, -78.54, 35.22)

# Maps HPMS F_SYSTEM code to the TVT factor group used for volume estimation
FUNCTIONAL_CLASS_TO_FACTOR_GROUP = {
    1: "interstate",
    2: "interstate",
    3: "arterial",
    4: "arterial",
    5: "collector",
    6: "collector",
    7: "local",
}

# Hourly adjustment factors by road class (index = hour 0–23).
# Multiply (AADT / 24) by this value to estimate volume for that hour.
# A value of 1.0 means exactly the daily average; 2.0 means twice the average.
#
# Source: FHWA Traffic Monitoring Guide, 2016 Edition, Appendix A
# https://www.fhwa.dot.gov/policyinformation/tmguide/
# Update manually when a new TMG edition is published.
HOURLY_FACTORS: dict[str, list[float]] = {
    "interstate": [
        0.31, 0.20, 0.15, 0.14, 0.20, 0.51,   # 00–05
        1.12, 1.68, 1.71, 1.35, 1.18, 1.15,   # 06–11
        1.18, 1.21, 1.29, 1.54, 1.85, 1.74,   # 12–17
        1.44, 1.21, 0.98, 0.75, 0.56, 0.40,   # 18–23
    ],
    "arterial": [
        0.27, 0.17, 0.12, 0.11, 0.17, 0.47,
        1.05, 1.58, 1.49, 1.28, 1.22, 1.21,
        1.25, 1.28, 1.35, 1.62, 1.89, 1.74,
        1.42, 1.17, 0.93, 0.71, 0.52, 0.37,
    ],
    "collector": [
        0.33, 0.22, 0.17, 0.16, 0.21, 0.41,
        0.82, 1.18, 1.28, 1.22, 1.18, 1.19,
        1.24, 1.26, 1.31, 1.42, 1.55, 1.58,
        1.48, 1.31, 1.12, 0.89, 0.68, 0.48,
    ],
    "local": [
        0.24, 0.15, 0.11, 0.10, 0.14, 0.38,
        0.79, 1.12, 1.18, 1.15, 1.14, 1.16,
        1.21, 1.24, 1.28, 1.38, 1.48, 1.52,
        1.44, 1.28, 1.05, 0.82, 0.60, 0.41,
    ],
}

# Day-of-week adjustment factors (1=Sunday … 7=Saturday).
# Source: FHWA Traffic Monitoring Guide, 2016 Edition, Appendix A
# https://www.fhwa.dot.gov/policyinformation/tmguide/
# Update manually when a new TMG edition is published.
DOW_FACTORS: dict[str, dict[int, float]] = {
    "interstate": {1: 0.82, 2: 1.06, 3: 1.08, 4: 1.07, 5: 1.09, 6: 1.01, 7: 0.87},
    "arterial":   {1: 0.79, 2: 1.07, 3: 1.08, 4: 1.08, 5: 1.10, 6: 1.02, 7: 0.86},
    "collector":  {1: 0.89, 2: 1.04, 3: 1.05, 4: 1.05, 5: 1.06, 6: 1.05, 7: 0.92},
    "local":      {1: 0.92, 2: 1.03, 3: 1.04, 4: 1.04, 5: 1.05, 6: 1.04, 7: 0.94},
}


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://geotraffic:geotraffic@localhost:5432/traffic"
    hpms_state: str = "SC"  # 2-letter state abbreviation, e.g. SC, TX, CA
    hpms_sample: Optional[int] = None  # if set, load only this many rows (e.g. 5000)


pipeline_settings = PipelineSettings()
