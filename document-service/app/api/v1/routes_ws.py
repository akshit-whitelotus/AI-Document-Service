from __future__ import annotations

import logging,uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect,Depends
from app.core.auth import get_current_user_id_ws
from app.services.job_manager import JobManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_progress(
    websocket: WebSocket,
    job_id: str,
    user_id:uuid.UUID=Depends(get_current_user_id_ws)
):
    

    job_manager: JobManager = websocket.app.state.job_manager
    owner_id=await job_manager.get_job_owner(job_id)
    if owner_id is None or owner_id != user_id:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    queue = await job_manager.subscribe(job_id)

    try:
        while True:
            update = await queue.get()

            await websocket.send_json(
                update.model_dump(mode="json")
            )

    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected for job %s",
            job_id,
        )

    except Exception:
        logger.exception(
            "Unexpected websocket error"
        )

        try:
            await websocket.close()
        except Exception:
            pass

    finally:
        await job_manager.unsubscribe(
            job_id,
            queue,
        )