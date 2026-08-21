import glob
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from faster_whisper import WhisperModel

CPU_THREADS = max(1, os.cpu_count() or 4)
PARAGRAPH_GAP_SECONDS = 1.2
PARAGRAPH_MAX_CHARS = 400

BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)


class JobNotFound(Exception):
    pass


class TranscriptionError(Exception):
    pass


@dataclass
class Job:
    id: str
    status: str = "queued"  # queued -> downloading -> transcribing -> done | error
    message: str = ""
    progress: int = 0
    text: str = ""
    srt: str = ""
    language: str = ""
    error: str = ""

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "progress": self.progress,
            "text": self.text if self.status == "done" else "",
            "language": self.language,
            "error": self.error,
        }


_jobs: Dict[str, Job] = {}
_jobs_lock = threading.Lock()

_models: Dict[str, WhisperModel] = {}
_models_lock = threading.Lock()

# Free-tier hosting has very limited RAM, so only one transcription (download +
# model inference) runs at a time; anything else waits in a queue.
_processing_lock = threading.Lock()


def create_job() -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = Job(id=job_id)
    return job_id


def get_job(job_id: str) -> Job:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise JobNotFound(job_id)
    return job


def _set(job_id: str, **kwargs):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        for k, v in kwargs.items():
            setattr(job, k, v)


def _find_ffmpeg_dir() -> Optional[str]:
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)
    candidates = glob.glob(
        str(
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Microsoft"
            / "WinGet"
            / "Packages"
            / "Gyan.FFmpeg*"
            / "ffmpeg-*"
            / "bin"
        )
    )
    return candidates[0] if candidates else None


_FFMPEG_DIR = _find_ffmpeg_dir()
if _FFMPEG_DIR and _FFMPEG_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")


def _detect_device_and_compute_type():
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "int8_float16"
    except Exception:
        pass
    return "cpu", "int8"


def _get_model(model_size: str) -> WhisperModel:
    with _models_lock:
        model = _models.get(model_size)
        if model is None:
            device, compute_type = _detect_device_and_compute_type()
            model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                cpu_threads=CPU_THREADS,
            )
            _models[model_size] = model
        return model


def _format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_clock(seconds: float) -> str:
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _build_paragraphs(segments: List[dict]) -> str:
    if not segments:
        return ""

    paragraphs: List[str] = []
    current_texts: List[str] = []
    current_start = segments[0]["start"]
    prev_end = segments[0]["start"]

    for seg in segments:
        gap = seg["start"] - prev_end
        current_len = sum(len(t) for t in current_texts)
        if current_texts and (gap > PARAGRAPH_GAP_SECONDS or current_len > PARAGRAPH_MAX_CHARS):
            paragraphs.append(f"[{_format_clock(current_start)}] " + " ".join(current_texts))
            current_texts = []
            current_start = seg["start"]

        current_texts.append(seg["text"])
        prev_end = seg["end"]

    if current_texts:
        paragraphs.append(f"[{_format_clock(current_start)}] " + " ".join(current_texts))

    return "\n\n".join(paragraphs)


def _transcribe(job_id: str, audio_path: str, model_size: str, language: Optional[str]):
    _set(job_id, status="transcribing", message="Loading model...", progress=0)
    model = _get_model(model_size)

    _set(job_id, message="Transcribing...", progress=5)
    segments_iter, info = model.transcribe(
        audio_path,
        language=language or None,
        vad_filter=True,
        beam_size=1,
        best_of=1,
        condition_on_previous_text=False,
    )

    total_duration = max(info.duration, 0.01)
    segments: List[dict] = []
    srt_parts: List[str] = []

    for i, seg in enumerate(segments_iter, start=1):
        clean = seg.text.strip()
        if not clean:
            continue
        segments.append({"start": seg.start, "end": seg.end, "text": clean})
        srt_parts.append(
            f"{i}\n{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}\n{clean}\n"
        )
        progress = min(99, int((seg.end / total_duration) * 100))
        _set(job_id, progress=progress, message=f"Transcribing... {progress}%")

    full_text = _build_paragraphs(segments)
    full_srt = "\n".join(srt_parts)

    if not full_text:
        raise TranscriptionError("No speech was detected in this audio.")

    _set(
        job_id,
        status="done",
        message="Done.",
        progress=100,
        text=full_text,
        srt=full_srt,
        language=info.language,
    )


def run_file_job(job_id: str, file_path: str, model_size: str, language: Optional[str]):
    _set(job_id, status="queued", message="Waiting for another transcription to finish...", progress=0)
    try:
        with _processing_lock:
            _transcribe(job_id, file_path, model_size, language)
    except Exception as e:
        _set(job_id, status="error", error=str(e), message="Failed.")
    finally:
        try:
            os.remove(file_path)
        except OSError:
            pass


def run_url_job(job_id: str, url: str, model_size: str, language: Optional[str]):
    import yt_dlp

    audio_path = str(DOWNLOADS_DIR / f"{job_id}.wav")
    _set(job_id, status="queued", message="Waiting for another transcription to finish...", progress=0)

    def hook(d):
        if d.get("status") == "downloading":
            pct = d.get("_percent_str", "").strip().replace("%", "")
            try:
                pct_val = int(float(pct))
            except ValueError:
                pct_val = 0
            _set(job_id, progress=min(99, pct_val), message="Downloading...")
        elif d.get("status") == "finished":
            _set(job_id, message="Converting audio...", progress=99)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(DOWNLOADS_DIR / f"{job_id}.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "socket_timeout": 30,
    }
    if _FFMPEG_DIR:
        ydl_opts["ffmpeg_location"] = _FFMPEG_DIR

    try:
        with _processing_lock:
            _set(job_id, status="downloading", message="Fetching video...", progress=0)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            if not os.path.exists(audio_path):
                matches = glob.glob(str(DOWNLOADS_DIR / f"{job_id}.*"))
                if matches:
                    audio_path = matches[0]
                else:
                    raise TranscriptionError("Could not download audio from that link.")

            _transcribe(job_id, audio_path, model_size, language)
    except Exception as e:
        _set(job_id, status="error", error=str(e), message="Failed.")
    finally:
        for f in glob.glob(str(DOWNLOADS_DIR / f"{job_id}.*")):
            try:
                os.remove(f)
            except OSError:
                pass
