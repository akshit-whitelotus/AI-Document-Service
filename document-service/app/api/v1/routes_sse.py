from __future__ import annotations

import asyncio,logging,uuid

from fastapi import APIRouter, Request,Depends,HTTPException
from sse_starlette.sse import EventSourceResponse
from app.core.auth import get_current_user_id_sse

logger=logging.getLogger(__name__)
router = APIRouter(tags=["SSE"])


@router.get("/sse/jobs/{job_id}")
async def job_stream(job_id: str, request: Request,user_id:uuid.UUID=Depends(get_current_user_id_sse)):
    job_manager = request.app.state.job_manager
    owner_id=await job_manager.get_job_owner(job_id)
    if owner_id is None or owner_id != user_id:
        raise HTTPException(status_code=404,detail="Job not found")
    
    async def event_generator():
        queue = await job_manager.subscribe(job_id)
        logger.debug("SSE client subscribed to job %s",job_id)
        try:
            while True:
                update = await queue.get()

                yield {
                    "event": "progress",
                    "data": update.model_dump_json(),
                }

        except asyncio.CancelledError:
            pass

        finally:
            await job_manager.unsubscribe(job_id, queue)

    return EventSourceResponse(event_generator())