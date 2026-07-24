from __future__ import annotations
import asyncio,logging
from datetime import datetime,timezone
from pathlib import Path
from app.schemas.job import JobProgress
from app.services.job_manager import JobManager

logger=logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self,job_manager:JobManager,output_dir:str) -> None :
        self.job_manager=job_manager
        self.output_dir=Path(output_dir)
        self.output_dir.mkdir(parents=True,exist_ok=True)
    async def process(self,job_id:str,file_path:str) -> None:
        stages=[
            ("queued",5),
            ("extracting",30),
            ("analyzing",60),
            ("summarizing",80),
            ("done",100)
        ]
        try:
            extracted_text:str | None = None
            for status,progress in stages :
                if status == "extracting":
                    extracted_text = await asyncio.to_thread(self._extract_text,Path(file_path))
                await self.job_manager.publish(
                    JobProgress(
                        job_id=job_id,
                        status=status,
                        progress=progress,
                        timestamp=datetime.now(timezone.utc)
                    )
                )
                if status != "done":
                    await asyncio.sleep(1)
            output_path = await self._generate_output(job_id, extracted_text or "")
            await self.job_manager.set_output_path(job_id, str(output_path))
        except Exception:
            logger.exception("Document Processing failed",extra={"job_id":job_id})
            await self.job_manager.set_error(job_id, "Processing failed. See server logs for details.")
            await self.job_manager.publish(
                JobProgress(
                    job_id=job_id,
                    status="failed",
                    progress=0,
                    timestamp=datetime.now(timezone.utc)
                )
            )
    def _extract_text(self,input_path:Path) -> str:
        suffix=input_path.suffix.lower()

        if suffix == ".pdf":
            text=self._extract_pdf_text(input_path)
            if text.strip():
                return text
            return self._ocr_pdf(input_path)

        try:
            return input_path.read_text(encoding="utf-8",errors="replace")
        except OSError as exc :
            logger.warning("COuld not read %s as text: %s",input_path,exc)
            return ""

    @staticmethod
    def _extract_pdf_text(input_path:Path) -> str :
        try:
            from pypdf import PdfReader
        except ImportError:
            logger.warning("pypdf is not installed; cannot extrat PDF text")
            return ""
        try:
            reader=PdfReader(str(input_path))
        except Exception:
            logger.exception("Failed to open PDF %s",input_path)
            return ""

        pages=[] 
        for i , page in enumerate(reader.pages,start=1):
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                logger.exception("Failed to extract text from page %d of %s", i , input_path)
        return "\n/n".join(pages)
    @staticmethod
    def _ocr_pdf(input_path:Path)-> str:
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError:
            logger.info(
                "No extractable text layer in %s and OCR liraries"
                "(pytesseract/pdf2image) aren't installed; skipped OCR.",
                input_path
            )
            return ""
        try:
            images=convert_from_path(str(input_path))
        except Exception:
            logger.exception(
                "OCR fallback failed to render %s to images"
                "(is poppler-utils installed?)",input_path
            )
            return ""

        pages=[]
        for i ,image in enumerate(images,start=1):
            try:
                pages.append(pytesseract.image_to_string(image))
            except Exception:
                logger.exception("OCR failed on page %d of %s",i,input_path)
        return "\n\n".join(pages)
    async def _generate_output(self,job_id:str,extracted_text:str) -> None:
        import aiofiles
        output_file=(
            self.output_dir/f"{job_id}.txt"
        )
        if extracted_text.strip():
            body=extracted_text
        else:
            body=(
                 "No text could be extracted from this document.\n"
                 "It may be a scanned/image-only PDF and OCR dependencies "
                 "(tesseract-ocr, poppler-utils) are not installed on this "
                 "server, or the file contains no readable text."
            )
        async with aiofiles.open(output_file,"w",encoding="utf-8") as file:
            await file.write(
                "AI generated document summary\n"
                f"JOb ID:{job_id}\n\n"
                "--- Extracted content ---\n"
                f"{body}\n"
            )
            