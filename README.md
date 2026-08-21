# Any Transcript

Paste a video link (YouTube, Instagram, TikTok, X, Vimeo, and hundreds more
sites via [`yt-dlp`](https://github.com/yt-dlp/yt-dlp)) or upload a video/audio
file, and get a formatted, timestamped transcript back. Transcription runs
locally on [Whisper](https://github.com/openai/whisper) via
[`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) — free, no API
key, no usage limits.

Runs on your own machine and your own internet connection, which matters:
YouTube and Instagram both rate-limit/block anonymous requests from cloud/
datacenter IPs, but not from a normal home connection, so running it locally
avoids that entirely with no extra setup (no cookies, no accounts).

This guide is for **Windows**. It hasn't been built or tested on Mac/Linux.

## Prerequisites

- **Windows 10/11** with [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) (built in on any reasonably recent Windows install — check with `winget --version`).
- **Git** (to clone this repo). Get it from [git-scm.com](https://git-scm.com/download/win) if you don't have it.
- A few GB of free disk space (Whisper models + Python packages).

You do **not** need a GPU — this runs fine on CPU. It'll automatically use a
GPU if one happens to be available, but it's not required.

## 1. Clone the repo

```powershell
git clone https://github.com/vanamthrishul/any-transcript.git
cd any-transcript
```

## 2. Install Python 3.12

The project needs Python 3.12 specifically, in its own virtual environment.
This is important even if you already have a different Python version
installed (e.g. a newer one): some of the ML packages this project depends
on (`ctranslate2`, used by `faster-whisper`) don't reliably have installable
builds for the very latest Python versions yet, and 3.12 is the safe, well
supported choice.

```powershell
winget install --id Python.Python.3.12 -e
```

## 3. Install ffmpeg

Used to extract audio from downloaded videos.

```powershell
winget install --id Gyan.FFmpeg -e
```

After installing, **close and reopen your terminal** so it picks up the
updated PATH (or just proceed — the app also locates ffmpeg itself at
startup as a fallback, so this step isn't strictly required, just tidier).

## 4. Create the virtual environment and install dependencies

From inside the `any-transcript` folder:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs FastAPI, `faster-whisper`, `yt-dlp`, and the rest — a few
hundred MB of packages, may take a few minutes.

## 5. Run it

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
```

(The `-ExecutionPolicy Bypass` is just for this one script run, it doesn't
change any system-wide setting. If you'd rather not use it, run
`.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
directly instead — same effect.)

Then open **http://127.0.0.1:8000** in your browser.

## Using it

1. Paste a video link (**Video link** tab) or choose a local file
   (**Upload file** tab).
2. Pick a **model size**:

   | Model | Speed | Accuracy | Notes |
   |---|---|---|---|
   | `tiny` | Fastest | Lowest | Good for quick drafts |
   | `base` | Fast | Good | **Default, recommended for most use** |
   | `small` | Slower | Better | Worth it for noisy/accented audio |
   | `medium` | Slowest | Best | Can be very slow on CPU-only machines |

3. Pick a language, or leave it on auto-detect.
4. Click **Transcribe** and watch the progress bar. When done, copy the
   text or download it as `.txt`/`.srt`.

The first time you use a given model size, it downloads the model weights
(one-time; cached afterward in `~/.cache/huggingface`).

## Troubleshooting

- **A video link fails to download / extractor errors.** `yt-dlp` needs to
  keep up with sites like YouTube constantly changing their internals; a
  `yt-dlp` version even a few months old can start failing. Update it:
  ```powershell
  .\venv\Scripts\python.exe -m pip install -U yt-dlp
  ```
- **"No speech was detected in this audio."** The file/video genuinely had
  no detectable speech (e.g. music-only, silent, or the wrong file).
- **Port 8000 already in use.** Something else is already running there, or
  a previous run didn't shut down. Close it, or edit `run.ps1` to use a
  different `--port`.
- **PowerShell won't run the script at all.** Make sure you're passing
  `-ExecutionPolicy Bypass -File run.ps1` exactly as shown above, from
  inside the `any-transcript` folder.
