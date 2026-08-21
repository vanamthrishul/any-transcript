# Any Transcript

A local-only, free, unlimited video/audio transcriber. Paste a link (YouTube,
Instagram, TikTok, X, Vimeo, etc. via `yt-dlp`) or upload a file, and get a
formatted, timestamped transcript. Transcription runs on `faster-whisper`
(open-source Whisper), no API keys, no per-use cost, no rate limits.

**Runs locally only, by deliberate decision** (see "Why local-only" below) —
not deployed anywhere. GitHub repo (vanamthrishul/any-transcript) is kept as
a backup/version history only, not connected to any live hosting.

## Architecture

- **Backend**: FastAPI (`backend/main.py`) + a background-thread job system
  (`backend/transcriber.py`). Jobs are in-memory (`_jobs` dict keyed by a
  short uuid), polled by the frontend via `GET /api/status/{job_id}`.
- **Frontend**: single static page (`static/index.html`), no build step —
  plain HTML/CSS/JS, polls job status every 1.2s and renders progress/result.
- **Transcription engine**: `faster-whisper` (CTranslate2-based Whisper).
  Model size selectable per job (`tiny`/`base`/`small`/`medium`); models are
  cached in-process after first load (`_models` dict in transcriber.py).
  Greedy decoding (`beam_size=1`, `best_of=1`) and forced `int8` compute for
  speed on CPU; auto-switches to CUDA if a GPU is ever present
  (`_detect_device_and_compute_type()`).
- **Video/audio fetch**: `yt-dlp` downloads best audio and extracts to WAV
  via ffmpeg for URL jobs; uploaded files are transcribed directly (PyAV
  inside faster-whisper handles most containers).
- **Concurrency**: a global `_processing_lock` in transcriber.py serializes
  transcriptions so only one runs at a time (originally added for a cloud
  RAM constraint, but harmless and still reasonable locally on a 4-core CPU).
- **Env**: runs in a dedicated `venv/` on Python 3.12 (NOT the system Python,
  which is 3.14 — ctranslate2/faster-whisper wheels aren't reliably available
  for 3.14 yet). ffmpeg is installed via winget (Gyan.FFmpeg build); its bin
  dir is located at runtime in `transcriber.py::_find_ffmpeg_dir()` and
  injected into `PATH` for the process, since a fresh shell may not have
  picked up the PATH change from the winget install yet.

## Hardware constraint

This dev machine has **no GPU and only 4 CPU cores** — the ceiling for local
transcription speed. Not a problem worth chasing further locally; `tiny`/
`base` models are fast enough for personal use.

## Why local-only (history of the cloud-hosting attempt)

The user originally wanted this usable from any device, not just this PC.
That path was tried and abandoned for good reasons, worth remembering so it
isn't re-attempted blindly:

1. **Hugging Face Spaces** (first choice): as of this session, HF requires a
   paid PRO plan for anything that runs a backend (Docker/Gradio SDKs) — only
   Static (no backend) Spaces are free. Confirmed via a live fetch of HF's
   own docs, not assumed from training memory. Dead end for a free backend.
2. **Render.com free tier** (second choice): this actually got fully
   deployed and working (GitHub repo pushed, Dockerfile built, ffmpeg +
   Whisper pipeline confirmed functional end-to-end on Render). But then hit
   a different wall: **YouTube and Instagram both block/rate-limit anonymous
   requests from cloud/datacenter IPs** (confirmed live against the deployed
   URL — YouTube: "Sign in to confirm you're not a bot"; Instagram: "You have
   exceeded the rate-limit for accessing posts anonymously"). Direct file
   links and less-guarded sites worked fine; it's specifically the big
   platforms with anti-bot systems that reject datacenter IPs.
   - The real fix (cookies from a real browser session, passed to `yt-dlp`
     via a Render Secret File) was implemented and would have worked, but
     added real ongoing maintenance (cookies expire and need re-export) and
     a real tradeoff (tying a personal account session to a server).
3. **Decision**: given the maintenance burden and account-security tradeoff,
   the user chose to abandon cloud hosting and use the app locally only.
   Residential IPs (a home connection) are not subject to the same anti-bot
   blocking, so locally none of this is a problem at all — confirmed by the
   very first successful test in this project, before any of this cloud
   investigation started.

**If cloud hosting ever comes up again**: don't re-suggest HF Docker Spaces
without re-checking current pricing (it changes), and know upfront that
YouTube/Instagram will need a cookies-file mechanism on any cloud host - it
isn't a one-off bug, it's inherent to hosting this kind of tool on a
datacenter IP. The removed code (see git history around commits
`8e73add`/`3e7fea0`) is a reasonable starting point if revisited.

**Cleanup status**: Render service deletion requires the user's dashboard
access (no Render CLI/API token available in this environment) — guided
instructions given, not verified done from this session. GitHub repo kept
intentionally as a backup, not deleted.

## Key files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI routes: `/`, `/api/transcribe/url`, `/api/transcribe/file`, `/api/status/{id}`, `/api/download/{id}` |
| `backend/transcriber.py` | Job state, model loading/caching, yt-dlp download, whisper transcription, paragraph/SRT formatting |
| `static/index.html` | Entire frontend (link/upload tabs, progress bar, transcript view, copy/download) |
| `requirements.txt` | Pinned deps (`yt-dlp` pinned loosely as `>=` since YouTube breaks old pins often, see below) |
| `run.ps1` | Local launcher: `venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000` |

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
- Platform pricing/policy pages (Hugging Face, Render, etc.) are worth
  re-fetching live rather than trusting memory — they changed mid-project.

## Progress log

- **2026-08-21**: Initial build. FastAPI + faster-whisper + yt-dlp app,
  web UI with link/upload tabs, progress polling, txt/srt download.
  Installed Python 3.12 + ffmpeg via winget (system Python 3.14 too new for
  ctranslate2 wheels). Verified end-to-end (YouTube URL, file upload, error
  handling, downloads).
- **2026-08-21 (speed/format fixes)**: Switched to greedy decoding + `int8`
  compute + explicit `cpu_threads`, default model `small` → `base`.
  Transcript output changed from one dumped paragraph to timestamped
  paragraphs (`_build_paragraphs()`). Removed em dashes from UI copy per
  user preference.
- **2026-08-21 (cloud attempt, later reverted)**: Tried HF Spaces (blocked
  by pricing change), then deployed to Render.com successfully (GitHub repo
  created, Dockerfile built, pipeline verified working on Render). Hit
  YouTube + Instagram anti-bot blocking on the cloud IP; added then later
  removed a cookies-file mechanism. See "Why local-only" above for the full
  story and reasoning.
- **2026-08-21 (final: local-only)**: User decided to drop cloud hosting
  entirely. Removed `Dockerfile`, `.dockerignore`, and the cookies-file
  lookup code from transcriber.py. Rewrote README.md and this file for a
  local-only tool. GitHub repo kept as a backup. Cleanup pushed to GitHub
  (commit `e4a654e`). User confirmed the Render service itself was deleted
  from the dashboard. Cloud-hosting chapter fully closed out.

## Open items / next session should pick up here

None outstanding. Project is local-only, working, and documented. If
"usable from anywhere" comes up again in a future session, read the "Why
local-only" section above first before re-proposing cloud hosting.
