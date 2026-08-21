import os
import re
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .transcriber import (
    JobNotFound,
    TranscriptionError,
    create_job,
    get_job,
    run_file_job,
    run_url_job,
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Any Transcript")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class UrlRequest(BaseModel):
    url: str
    model_size: Optional[str] = "base"
    language: Optional[str] = None


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/transcribe/url")
def transcribe_url(req: UrlRequest):
    url = req.url.strip()
    if not url or not re.match(r"^https?://", url, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Please provide a valid http(s) URL.")

    job_id = create_job()
    thread = threading.Thread(
        target=run_url_job,
        args=(job_id, url, req.model_size, req.language),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}


@app.post("/api/transcribe/file")
async def transcribe_file(
    file: UploadFile = File(...),
    model_size: str = Form("base"),
    language: Optional[str] = Form(None),
):
    job_id = create_job()

    suffix = Path(file.filename or "upload").suffix or ".bin"
    tmp_path = DOWNLOADS_DIR / f"{job_id}{suffix}"
    with open(tmp_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    thread = threading.Thread(
        target=run_file_job,
        args=(job_id, str(tmp_path), model_size, language),
        daemon=True,
    )
    thread.start()
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def status(job_id: str):
    try:
        job = get_job(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    return job.to_dict()


@app.get("/api/download/{job_id}")
def download(job_id: str, fmt: str = "txt"):
    try:
        job = get_job(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Unknown job id.")
    if job.status != "done":
        raise HTTPException(status_code=409, detail="Job is not finished yet.")

    if fmt == "srt":
        return PlainTextResponse(job.srt, media_type="text/plain", headers={
            "Content-Disposition": f'attachment; filename="transcript-{job_id}.srt"'
        })
    return PlainTextResponse(job.text, media_type="text/plain", headers={
        "Content-Disposition": f'attachment; filename="transcript-{job_id}.txt"'
    })


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
