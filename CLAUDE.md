# Any Transcript

A local-first, free, unlimited video/audio transcriber. Paste a link (YouTube,
Instagram, TikTok, X, Vimeo, etc. via `yt-dlp`) or upload a file, and get a
formatted, timestamped transcript. Transcription runs on `faster-whisper`
(open-source Whisper) — no API keys, no per-use cost, no rate limits.

## Architecture

- **Backend**: FastAPI (`backend/main.py`) + a background-thread job system
  (`backend/transcriber.py`). Jobs are in-memory (`_jobs` dict keyed by a
  short uuid), polled by the frontend via `GET /api/status/{job_id}`.
- **Frontend**: single static page (`static/index.html`), no build step —
  plain HTML/CSS/JS, polls job status every 1.2s and renders progress/result.
- **Transcription engine**: `faster-whisper` (CTranslate2-based Whisper).
  Model size selectable per job (`tiny`/`base`/`small`/`medium`); models are
  cached in-process after first load (`_models` dict in transcriber.py).
- **Video/audio fetch**: `yt-dlp` downloads best audio and extracts to WAV
  via ffmpeg for URL jobs; uploaded files are transcribed directly (PyAV
  inside faster-whisper handles most containers).
- **Env**: runs in a dedicated `venv/` on Python 3.12 (NOT the system Python,
  which is 3.14 — ctranslate2/faster-whisper wheels aren't reliably available
  for 3.14 yet). ffmpeg is installed via winget (Gyan.FFmpeg build); its bin
  dir is located at runtime in `transcriber.py::_find_ffmpeg_dir()` and
  injected into `PATH` for the process, since a fresh shell may not have
  picked up the PATH change from the winget install yet.

## Hardware constraint (important context for future speed work)

This dev machine has **no GPU and only 4 CPU cores**. That's the ceiling for
local transcription speed here — see `_detect_device_and_compute_type()` in
transcriber.py, which auto-uses CUDA if it's ever available but otherwise
runs `int8` on CPU with `cpu_threads` set to the core count. Any future
"make it faster" work either means accepting CPU limits, or offloading to
a cloud GPU/API (not yet done — see Open Items).

## Deployment (for "usable from anywhere, free")

**Hugging Face Spaces was the original plan but is dead**: as of this
session, HF changed policy so Docker/Gradio Spaces (anything that runs a
backend) require a paid PRO plan — only Static (no backend) Spaces are free.
Confirmed by fetching HF's own docs (`spaces-overview`) live, not from
training memory, since this is exactly the kind of thing that changes.
Don't re-suggest HF Docker Spaces as a free option without re-checking.

**Current plan: Render.com free Web Service tier.** No credit card required
to start, reuses the same `Dockerfile`, 750 free instance-hours/month.
- `Dockerfile`: installs ffmpeg, installs deps, **pre-bakes `tiny` and `base`
  Whisper models into the image** at build time (avoids a cold-start
  download on first request), binds to `$PORT` (Render injects this;
  defaults to 8000 for local `docker run`).
- Render deploys via **GitHub integration**, not a direct git push like HF
  Spaces did — the repo needs to live on GitHub first, then Render connects
  to it and auto-deploys on push. **Blocked on**: confirming the user has
  a GitHub account, then pushing this repo there (with confirmation, since
  it's a push to a third-party service).
- Added a global `_processing_lock` (transcriber.py) so only one
  transcription runs at a time app-wide — Render's free tier RAM (~512MB)
  is tight for concurrent Whisper inference.
- Free tier sleeps after 15 min idle, ~1 min cold-start on next request.
  Stick to `tiny`/`base` models there; `small`/`medium` risk OOM.

Fallback options if Render turns out to not work well in practice: Oracle
Cloud Always Free VM (real always-on, more setup, wants a card for identity
verification) or a Cloudflare Tunnel back to this PC (zero new accounts,
but only reachable while this machine is on). User was offered these and
picked Render first.

## Key files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI routes: `/`, `/api/transcribe/url`, `/api/transcribe/file`, `/api/status/{id}`, `/api/download/{id}` |
| `backend/transcriber.py` | Job state, model loading/caching, yt-dlp download, whisper transcription, paragraph/SRT formatting |
| `static/index.html` | Entire frontend (link/upload tabs, progress bar, transcript view, copy/download) |
| `requirements.txt` | Pinned deps (yt-dlp pinned loosely as `>=` since YouTube breaks old pins often — see below) |
| `run.ps1` | Local launcher: `venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000` |
| `Dockerfile`, `.dockerignore`, `README.md` | Render.com deployment |

## Known gotchas / lessons learned

- **`yt-dlp` goes stale fast.** YouTube changes its extraction/anti-bot
  behavior often; a `yt-dlp` version even a few months old can start
  failing with errors like `"The page needs to be reloaded"`. Keep it
  updated (`pip install -U yt-dlp`) if URL transcription starts failing.
- System Python here is 3.14; the project venv pins **3.12** specifically
  for ML-package wheel compatibility. Always use `venv\Scripts\python.exe`,
  not bare `python`.
- ffmpeg is not on system PATH in existing shells after winget install
  until the shell restarts — `transcriber.py` locates and injects it itself
  so the app doesn't depend on that.

## Progress log

- **2026-08-21**: Initial build. FastAPI + faster-whisper + yt-dlp app,
  web UI with link/upload tabs, progress polling, txt/srt download.
  Installed Python 3.12 + ffmpeg via winget (system Python 3.14 too new for
  ctranslate2 wheels). Verified end-to-end (YouTube URL, file upload, error
  handling, downloads).
- **2026-08-21 (follow-up)**: Fixed 3 issues raised by user:
  1. *Speed* — switched to `beam_size=1`/`best_of=1` greedy decoding,
     forced `int8` compute type, set `cpu_threads` explicitly, default
     model changed from `small` to `base`.
  2. *Formatting* — transcript is now built as timestamped paragraphs
     (`[mm:ss] ...`, new paragraph on a >1.2s pause or >400 chars) instead
     of one dumped paragraph (`_build_paragraphs()` in transcriber.py).
  3. *Anywhere access* — user chose "free cloud hosting" (Hugging Face
     Spaces) over tunneling or a paid-API hybrid. Deployment files prepared
     (Dockerfile, README frontmatter) but **not yet pushed** — waiting on
     user to create the HF Space.
  - Also removed em dashes from UI copy per user preference.

## Cookies (needed for YouTube AND Instagram, likely others too)

Not just a YouTube problem: Instagram also rate-limits/redirects anonymous
cloud-IP requests to its login page (`"You have exceeded the rate-limit for
accessing posts anonymously"`), same root cause as YouTube's bot check, same
fix. The cookie mechanism in transcriber.py (`_find_cookies_file()`) is
already generic, it applies whatever cookies.txt it finds to every
extraction, not just YouTube-flagged ones, since a single Netscape cookies
file can carry cookies for multiple domains at once (yt-dlp filters by
domain internally). Looks for, in order: `YTDLP_COOKIES_FILE` env var,
`/etc/secrets/cookies.txt`, then `/etc/secrets/youtube_cookies.txt` (back-compat
with the original YouTube-only setup). User should export cookies while
logged into *both* youtube.com and instagram.com (most export extensions
support exporting the whole cookie jar at once) and upload as one Render
Secret File named `cookies.txt`. Untested so far: TikTok, X/Twitter - likely
same story given both have tightened anonymous access recently, but don't
claim this without testing when it comes up.

## Progress log (continued)

- **2026-08-21 (pivot)**: User hit a paywall — HF now requires PRO for
  Docker/Gradio Spaces. Verified via live fetch of HF docs. Switched plan to
  Render.com free Web Service. Code changes: Dockerfile CMD now binds
  `${PORT:-8000}` instead of hardcoded 7860; added `_processing_lock` in
  transcriber.py to serialize transcriptions (RAM safety on free tier);
  rewrote README.md deployment section for Render + GitHub flow instead of
  HF Spaces git-push flow. Repo is still not yet a git repository.

## Open items / next session should pick up here

- [ ] Confirm user has (or creates) a GitHub account — needed because
      Render deploys via GitHub integration, not direct git push.
- [ ] `git init` this repo, create a GitHub repo, push (confirm with user
      first — visible third-party action).
- [ ] Walk user through Render dashboard: New Web Service → connect the
      GitHub repo → Free instance type → deploy.
- [ ] Once deployed, verify the Render service actually builds and serves
      correctly; watch for OOM on the free tier's ~512MB RAM.
- [ ] Consider whether in-memory job storage (`_jobs` dict) is a problem if
      the container restarts/sleeps mid-job — currently fine for
      single-user personal use, would need a real store (file/DB) for
      anything more durable.
