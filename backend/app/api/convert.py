import io
import json
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import PlainTextResponse, StreamingResponse

from ..config import settings
from ..models import ConvertResponse, HealthResponse, KnowledgeBaseResponse
from ..pipeline.orchestrator import orchestrator, ConversionPipelineError

router = APIRouter(prefix="/api", tags=["Conversion"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    libreoffice_available = settings.find_libreoffice_bin() is not None
    tesseract_available = shutil.which(settings.resolve_tesseract_bin()) is not None or Path(settings.resolve_tesseract_bin()).exists()

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        libreoffice_available=libreoffice_available,
        tesseract_available=tesseract_available,
        density_threshold=settings.MIN_DENSITY_CHARS_PER_PAGE
    )

@router.post("/convert", response_model=ConvertResponse)
async def convert_file_endpoint(file: UploadFile = File(...)):
    filename = file.filename or "document.txt"
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    temp_path = Path(temp_file.name)

    try:
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        size = 0

        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
                )
            temp_file.write(chunk)
        temp_file.flush()
        temp_file.close()

        response = orchestrator.process_file(
            original_filename=filename,
            source_path=temp_path
        )
        return response

    except ConversionPipelineError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during document processing: {str(e)}"
        )
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)

@router.post("/convert-batch", response_model=List[ConvertResponse])
async def convert_batch_endpoint(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided in request."
        )

    results: List[ConvertResponse] = []
    for file in files:
        filename = file.filename or "document.txt"
        ext = Path(filename).suffix.lower()

        if ext not in settings.ALLOWED_EXTENSIONS:
            continue

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_path = Path(temp_file.name)

        try:
            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)
            temp_file.flush()
            temp_file.close()

            res = orchestrator.process_file(
                original_filename=filename,
                source_path=temp_path
            )
            results.append(res)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    return results

@router.post("/convert-batch/zip")
async def convert_batch_zip_endpoint(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided."
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file in files:
            filename = file.filename or "document.txt"
            ext = Path(filename).suffix.lower()

            if ext not in settings.ALLOWED_EXTENSIONS:
                continue

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_path = Path(temp_file.name)

            try:
                while chunk := await file.read(1024 * 1024):
                    temp_file.write(chunk)
                temp_file.flush()
                temp_file.close()

                res = orchestrator.process_file(
                    original_filename=filename,
                    source_path=temp_path
                )
                base_name = Path(filename).stem
                zip_file.writestr(f"{base_name}.md", res.markdown.encode("utf-8"))
            finally:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=converted_markdown_batch.zip"}
    )

@router.post("/convert-knowledge-base", response_model=KnowledgeBaseResponse)
async def convert_knowledge_base_endpoint(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided for Knowledge Base conversion."
        )

    saved_files: List[tuple[str, Path]] = []
    temp_files_to_clean: List[Path] = []

    try:
        for file in files:
            filename = file.filename or "document.txt"
            ext = Path(filename).suffix.lower()

            if ext not in settings.ALLOWED_EXTENSIONS:
                continue

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_path = Path(temp_file.name)
            temp_files_to_clean.append(temp_path)

            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)
            temp_file.flush()
            temp_file.close()

            saved_files.append((filename, temp_path))

        if not saved_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="None of the uploaded files have supported extensions."
            )

        kb_result = orchestrator.process_knowledge_base(saved_files)
        return kb_result

    finally:
        for p in temp_files_to_clean:
            if p.exists():
                p.unlink(missing_ok=True)

@router.post("/convert-knowledge-base/zip")
async def convert_knowledge_base_zip_endpoint(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided for ZIP generation."
        )

    saved_files: List[tuple[str, Path, bytes]] = []
    temp_files_to_clean: List[Path] = []

    try:
        for file in files:
            filename = file.filename or "document.txt"
            ext = Path(filename).suffix.lower()

            if ext not in settings.ALLOWED_EXTENSIONS:
                continue

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_path = Path(temp_file.name)
            temp_files_to_clean.append(temp_path)

            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            temp_file.close()

            saved_files.append((filename, temp_path, content))

        if not saved_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="None of the uploaded files have supported extensions."
            )

        files_data = [(fn, p) for fn, p, _ in saved_files]
        kb_result = orchestrator.process_knowledge_base(files_data)

        # Build ZIP matching the EXACT Knowledge Package specification
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. upload_to_ai/ folder (ONLY safe Markdown files for AI)
            if not kb_result.is_single_mode and kb_result.master_index_md:
                zf.writestr("upload_to_ai/00_Master_Index.md", kb_result.master_index_md.encode("utf-8"))

            for doc in kb_result.upload_to_ai_documents:
                base_name = Path(doc.filename).stem
                zf.writestr(f"upload_to_ai/{base_name}.md", doc.markdown.encode("utf-8"))

            # 2. technical/ folder (manifest, report, and failed/ if any)
            zf.writestr("technical/manifest.json", json.dumps(kb_result.manifest_json, ensure_ascii=False, indent=2).encode("utf-8"))
            zf.writestr("technical/conversion_report.md", kb_result.conversion_report_md.encode("utf-8"))

            for doc in kb_result.failed_documents:
                base_name = Path(doc.filename).stem
                zf.writestr(f"technical/failed/{base_name}.md", doc.markdown.encode("utf-8"))

            # 3. source/ folder
            for fn, _, content in saved_files:
                zf.writestr(f"source/{fn}", content)

            # 4. README.txt
            zf.writestr("README.txt", kb_result.readme_txt.encode("utf-8"))

        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=Knowledge_Package.zip"}
        )

    finally:
        for p in temp_files_to_clean:
            if p.exists():
                p.unlink(missing_ok=True)
