from __future__ import annotations
import uuid
from pathlib import Path
import aiofiles
from fastapi import APIRouter,Depends,Request,UploadFile,File,HTTPException
from fastapi.responses import StreamingResponse
from app.services.document_processor import DocumentProcessor
from app.core.config import settings
from app.core.auth import get_current_user_id

router=APIRouter(prefix='/documents',tags=["Documents"])
CHUNK_SIZE=1024*1024

@router.post("/upload",summary="Upload document",description=("Streams a large document upload""and starts asynchronous AI processing"))
async def upload_document(
    request:Request,
    file:UploadFile=File(...),
    user_id:uuid.UUID=Depends(get_current_user_id),
):
    job_id=str(uuid.uuid4())
    upload_dir=Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True,exist_ok=True)

    # Only use the base filename (strip any directory components) to
    # prevent path traversal via a crafted filename (e.g. "../../etc/passwd").
    safe_filename=Path(file.filename or "upload").name
    destination=(upload_dir/f"{job_id}_{safe_filename}")

    max_bytes=settings.MAX_UPLOAD_SIZE_MB*1024*1024
    bytes_written=0
    try:
        async with aiofiles.open(destination,"wb") as output :
            while True:
                chunk=await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                bytes_written+=len(chunk)
                if bytes_written>max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum upload size of {settings.MAX_UPLOAD_SIZE_MB}MB",
                    )
                await output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise

    job_manager = request.app.state.job_manager
    await job_manager.create_job(job_id, user_id, str(destination))

    processor=DocumentProcessor(job_manager,settings.OUTPUT_DIR)
    job_manager.create_task(processor.process(job_id,str(destination)))
    return {
        "job_id":job_id,
        "status":"queued"
    }

@router.get("/{job_id}/download")
async def download_document(
    job_id: str,
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    job_manager = request.app.state.job_manager
    owner_id = await job_manager.get_job_owner(job_id)

    # 404 (not 403) for both "doesn't exist" and "belongs to someone else"
    # — this avoids leaking whether a given job_id exists to a user who
    # doesn't own it.
    if owner_id is None or owner_id != user_id:
        raise HTTPException(status_code=404, detail="Processed file not found")

    output_dir = Path(settings.OUTPUT_DIR)

    candidates = [
        output_dir / f"{job_id}.txt",
        output_dir / f"{job_id}.pdf",
    ]

    path = next((p for p in candidates if p.exists()), None)

    if path is None:
        raise HTTPException(status_code=404, detail="Processed file not found")

    async def stream():
        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(1024 * 1024):
                yield chunk

    media_type = (
        "application/pdf"
        if path.suffix == ".pdf"
        else "text/plain"
    )

    return StreamingResponse(
        stream(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{path.name}"'
        },
    )
