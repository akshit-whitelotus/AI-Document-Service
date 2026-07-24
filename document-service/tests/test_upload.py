"""
Tests document upload and streaming download.
"""

import asyncio
import uuid
from pathlib import Path

import pytest

from app.main import app
from app.services.job_manager import JobManager
from app.services.document_processor import DocumentProcessor


@pytest.mark.asyncio
async def test_document_upload_requires_auth(client):
    response = await client.post(
        "/documents/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_document_upload(client, auth_headers):
    response = await client.post(
        "/documents/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert "job_id" in data
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_download_requires_auth(client):
    response = await client.get(f"/documents/{uuid.uuid4()}/download")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_unknown_job_returns_404(client, auth_headers):
    response = await client.get(f"/documents/{uuid.uuid4()}/download", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_stream_download_as_owner(client, auth_headers, test_user_id):
    output_dir = Path("storage/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())
    file = output_dir / f"{job_id}.txt"
    file.write_text("processed content")

    job_manager = app.state.job_manager
    await job_manager.create_job(job_id, test_user_id, "storage/uploads/does-not-matter.txt")

    response = await client.get(f"/documents/{job_id}/download", headers=auth_headers)

    assert response.status_code == 200
    assert response.text == "processed content"

    file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_download_rejects_non_owner(client, auth_headers, test_user_id):
    output_dir = Path("storage/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())
    file = output_dir / f"{job_id}.txt"
    file.write_text("someone else's content")

    job_manager = app.state.job_manager
    # Job belongs to a DIFFERENT user than the one in auth_headers.
    await job_manager.create_job(job_id, uuid.uuid4(), "storage/uploads/does-not-matter.txt")

    response = await client.get(f"/documents/{job_id}/download", headers=auth_headers)

    assert response.status_code == 404

    file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_document_processor_runs_end_to_end(tmp_path, test_user_id):
    """
    Regression test: exercises DocumentProcessor.process() for real (not by
    hand-constructing JobProgress with the correct field names), so a typo
    like publishing 'progess' instead of 'progress' would be caught here.
    """
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()

    input_file = upload_dir / "input.txt"
    input_file.write_text("hello world")

    job_manager = JobManager()
    processor = DocumentProcessor(job_manager, str(output_dir))

    job_id = str(uuid.uuid4())
    await job_manager.create_job(job_id, test_user_id, str(input_file))
    await processor.process(job_id, str(input_file))

    # The job must have reached "done", not silently died partway through
    # (e.g. from a validation error inside JobProgress).
    assert job_manager.jobs[job_id].status == "done"
    assert job_manager.jobs[job_id].progress == 100

    output_file = output_dir / f"{job_id}.txt"
    assert output_file.exists()

    record = await job_manager.get_job_record(job_id)
    assert record.output_path == str(output_file)

    await job_manager.shutdown()


@pytest.mark.asyncio
async def test_document_processor_extracts_real_pdf_text(tmp_path, test_user_id):
    """
    Regression test for real PDF text extraction: builds an actual PDF
    (not a fake .txt renamed to .pdf), runs it through the real processor,
    and checks the *actual PDF content* comes back in the output file.
    """
    fpdf = pytest.importorskip("fpdf", reason="fpdf2 is only needed to build a test PDF")
    from fpdf import FPDF

    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    marker_text = "The quarterly revenue grew by twelve percent."
    pdf.cell(text=marker_text)
    input_file = upload_dir / "report.pdf"
    pdf.output(str(input_file))

    job_manager = JobManager()
    processor = DocumentProcessor(job_manager, str(output_dir))

    job_id = str(uuid.uuid4())
    await job_manager.create_job(job_id, test_user_id, str(input_file))
    await processor.process(job_id, str(input_file))

    assert job_manager.jobs[job_id].status == "done"

    output_file = output_dir / f"{job_id}.txt"
    contents = output_file.read_text(encoding="utf-8")

    # The real PDF content must appear in the output, not a generic stub.
    assert marker_text in contents
    assert "No text could be extracted" not in contents

    await job_manager.shutdown()
