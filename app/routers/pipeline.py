from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PipelineRun
from app.schemas import PipelineRunResponse

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/runs", response_model=list[PipelineRunResponse])
def get_pipeline_runs(db: Session = Depends(get_db)):
    rows = db.execute(
        select(PipelineRun).order_by(PipelineRun.started_at.desc())
    ).scalars().all()
    return rows
