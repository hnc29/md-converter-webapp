import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import settings
from .api.convert import router as convert_router
from .api.ingestion import router as ingestion_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Webapp for converting PDF, DOC/DOCX, XLS/XLSX to Markdown using MarkItDown and Local OCR."
)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(convert_router)
app.include_router(ingestion_router)

# Mount Frontend static files and assets with no-cache headers
frontend_dir = settings.PROJECT_ROOT.parent / "frontend"
if frontend_dir.exists():
    @app.get("/")
    async def serve_index():
        response = FileResponse(frontend_dir / "index.html")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
