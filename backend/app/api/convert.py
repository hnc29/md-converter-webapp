import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import PlainTextResponse
from ..config import settings
from ..models import ConvertResponse, HealthResponse
from ..pipeline.orchestrator import orchestrator, ConversionPipelineError

router = APIRouter(prefix="/api", tags=["Conversion"])

@router.get("/health", response_model=HealthResponse)
async def health_check():
    libreoffice_available = shutil.which(settings.resolve_libreoffice_bin()) is not None or Path(settings.resolve_libreoffice_bin()).exists()
    tesseract_available = shutil.which(settings.resolve_tesseract_bin()) is not None or Path(settings.resolve_tesseract_bin()).exists()

    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        libreoffice_available=libreoffice_available,
        tesseract_available=tesseract_available,
        density_threshold=settings.MIN_DENSITY_CHARS_PER_PAGE
    )

from typing import List
import zipfile
import io
from fastapi.responses import PlainTextResponse, StreamingResponse

@router.post("/convert", response_model=ConvertResponse)
async def convert_file_endpoint(file: UploadFile = File(...)):
    filename = file.filename or "document.txt"
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # Save uploaded file to temporary path
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    temp_path = Path(temp_file.name)

    try:
        # Check file size limit while writing
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

        # Run conversion through the orchestrator
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
            # Skip or record error response
            results.append(
                ConvertResponse(
                    filename=filename,
                    converted_via_legacy=False,
                    markdown=f"<!-- Error: Định dạng {ext} không được hỗ trợ -->",
                    pages_total=0,
                    pages_ocr=[],
                    warnings=[f"Định dạng {ext} không nằm trong danh sách hỗ trợ."],
                    duration_ms=0,
                    word_count=0,
                    character_count=0
                )
            )
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
        except Exception as err:
            results.append(
                ConvertResponse(
                    filename=filename,
                    converted_via_legacy=False,
                    markdown=f"<!-- Lỗi khi xử lý file: {str(err)} -->",
                    pages_total=0,
                    pages_ocr=[],
                    warnings=[f"Lỗi: {str(err)}"],
                    duration_ms=0,
                    word_count=0,
                    character_count=0
                )
            )
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
                md_filename = f"{base_name}.md"
                zip_file.writestr(md_filename, res.markdown.encode("utf-8"))
            except Exception as err:
                base_name = Path(filename).stem
                zip_file.writestr(f"{base_name}_error.txt", f"Lỗi: {str(err)}")
            finally:
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=converted_markdown_batch.zip"}
    )
