from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Literal
from pathlib import Path

from jobs import create_job, get_status, get_results, export_job, cancel_job

BASE_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = BASE_DIR / "exports"

app = FastAPI(title="SearchMaps API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    city: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    state: str | None = Field(default=None)
    limit: int | None = Field(default=20, ge=1, le=50)


class ExportRequest(BaseModel):
    jobId: str = Field(..., min_length=1)
    format: Literal["csv", "xlsx"]


@app.post("/api/search")
def start_search(payload: SearchRequest):
    state = payload.state.strip() if payload.state else None
    job_id = create_job(payload.city.strip(), payload.query.strip(), state, payload.limit)
    return {"jobId": job_id}


@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    status = get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return status


@app.get("/api/results/{job_id}")
def get_job_results(job_id: str):
    results = get_results(job_id)
    if not results:
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return results


@app.post("/api/export")
def export_results(payload: ExportRequest):
    try:
        exported = export_job(payload.jobId, payload.format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not exported:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    filename = exported["filename"]
    return {
        "filename": filename,
        "downloadUrl": f"/api/download/{filename}",
    }


@app.get("/api/download/{filename}")
def download_file(filename: str):
    file_path = EXPORT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(file_path, filename=filename)


@app.post("/api/cancel/{job_id}")
def cancel_job_endpoint(job_id: str):
    if not cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job não encontrado.")
    return {"status": "canceled"}
