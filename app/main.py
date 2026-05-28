from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routers import patterns, pipeline, roads, volume


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Geospatial Traffic Analytics",
    description="Road network volume analysis API powered by FHWA HPMS, Overture Maps, and FHWA TVT factors.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(roads.router)
app.include_router(volume.router)
app.include_router(patterns.router)
app.include_router(pipeline.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
