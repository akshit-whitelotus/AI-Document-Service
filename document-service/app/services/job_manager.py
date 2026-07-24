from __future__ import annotations
import asyncio,logging,uuid
from collections import defaultdict
from app.schemas.job import JobProgress
from app.models.job import Job
from app.db.base import SessionLocal
from sqlalchemy import select

logger=logging.getLogger(__name__)

class JobManager:
    def __init__(self) -> None:
        self.jobs:dict[str,JobProgress] ={}
        self.subscribers:dict[str,set[asyncio.Queue[JobProgress]]]=defaultdict(set)
        self.background_tasks:set[asyncio.Task]=set()
    async def create_job(self,job_id:str,user_id:uuid.UUID,input_path:str) -> None:
        async with SessionLocal() as session :
            session.add(
                Job(
                    id=uuid.UUID(job_id),
                    user_id=user_id,
                    status="queued",
                    progress=0,
                    input_path=input_path
                )
            )
            await session.commit()
    async def set_output_path(self,job_id:str,output_path:str) -> None:
        async with SessionLocal() as session:
            job=await session.get(Job,uuid.UUID(job_id))
            if job is not None:
                job.output_path = output_path
                await session.commit()
    async def set_error(self,job_id:str,error_message:str)-> None:
        async with SessionLocal() as session:
            job=await session.get(Job,uuid.UUID(job_id))
            if job is not None:
                job.error_message = error_message
                await session.commit()
    async def get_job_record(self,job_id:str) -> Job |None:
        try:
            job_uuid=uuid.UUID(job_id)
        except ValueError:
            return None
        async with SessionLocal() as session:
            return await session.get(Job,job_uuid)

    async def get_job_owner(self,job_id:str) -> uuid.UUID | None:
        try:
            job_uuid=uuid.UUID(job_id)
        except ValueError:
            return None
        async with SessionLocal() as session:
            return await session.scalar(select(Job.user_id).where(Job.id==job_uuid))

    async def publish(self,update:JobProgress) -> None:
        self.jobs[update.job_id]=update
        logger.debug(
            "Publishing update for job %s to %d subscriber(s)",
            update.job_id,
            len(self.subscribers.get(update.job_id,set()))
        )
        async with SessionLocal() as session:
            job=await session.get(Job,uuid.UUID(update.job_id))
            if job is not None:
                job.status = update.status
                job.progress=update.progress
                await session.commit()
        for queue in self.subscribers.get(update.job_id,set()):
            await queue.put(update)
    async def subscribe(self,job_id:str) -> asyncio.Queue[JobProgress]:
        queue: asyncio.Queue[JobProgress]=asyncio.Queue()

        self.subscribers[job_id].add(queue)

        if job_id in self.jobs:
            await queue.put(self.jobs[job_id])
        return queue

    async def unsubscribe(self,job_id:str,queue:asyncio.Queue[JobProgress]) -> None:
        self.subscribers[job_id].discard(queue)

        if not self.subscribers[job_id]:
            del self.subscribers[job_id]

    def create_task(self,coroutine) -> None:
        task=asyncio.create_task(coroutine)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def shutdown(self) -> None:
        for task in self.background_tasks:
            task.cancel()
        await asyncio.gather(
            *self.background_tasks,
            return_exceptions=True,
        )
        