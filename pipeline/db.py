from sqlalchemy import create_engine

from pipeline.config import pipeline_settings


def get_engine():
    return create_engine(pipeline_settings.database_url)
