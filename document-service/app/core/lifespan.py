import asyncio
import logging
from contextlib import asynccontextmanager
from app.db.base import engine
from fastapi import FastAPI
from app.services.job_manager import JobManager

logger=logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app:FastAPI):
    logger.info("Application started")
    app.state.job_manager=JobManager()
    yield
    logger.info("Application shutdown")
    job_manager:JobManager=app.state.job_manager
    await job_manager.shutdown()
    await engine.dispose()

    await asyncio.sleep(0)
    
