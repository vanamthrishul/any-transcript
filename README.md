# Any Transcript

Paste a video link (YouTube, Instagram, TikTok, X, Vimeo, and hundreds more sites
via `yt-dlp`) or upload a video/audio file, and get a formatted, timestamped
transcript back. Transcription runs on Whisper (`faster-whisper`), free and
with no API key.

Runs locally on your own machine and your own internet connection, which
matters: YouTube and Instagram both rate-limit/block anonymous requests from
cloud/datacenter IPs, but not from a normal home connection, so running it
here avoids that entirely with no extra setup (no cookies, no accounts).

## Setup (Windows)

Requires a dedicated Python 3.12 virtual environment (`venv/`) and ffmpeg,
both already set up in this project. If setting up fresh on another machine:

```
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

ffmpeg must also be installed and on PATH (e.g. `winget install Gyan.FFmpeg`).

## Run it

```
powershell -ExecutionPolicy Bypass -File run.ps1
```

Then open http://127.0.0.1:8000, paste a link or upload a file, pick a model
size, and transcribe.
