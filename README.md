# Any Transcript

Paste a video link (YouTube, Instagram, TikTok, X, Vimeo, and hundreds more sites
via `yt-dlp`) or upload a video/audio file, and get a formatted, timestamped
transcript back. Transcription runs on Whisper (`faster-whisper`), free and
with no API key.

## Run locally (Windows)

```
powershell -ExecutionPolicy Bypass -File run.ps1
```

Then open http://127.0.0.1:8000.

## Deploy for free so you can use it from any device

This repo's `Dockerfile` is set up to deploy as-is to [Render](https://render.com)'s
free Web Service tier: permanent public URL, works from your phone, no credit
card required to start.

1. Push this repo to a GitHub repository.
2. On Render, create a **New Web Service**, connect that GitHub repo. Render
   detects the `Dockerfile` automatically.
3. Choose the **Free** instance type, and deploy.
4. First build takes a few minutes (it pre-downloads the `tiny` and `base`
   Whisper models). After that, your transcript tool is live at
   `https://<your-service-name>.onrender.com`.

Render's free tier spins the service down after 15 minutes of no traffic and
takes about a minute to wake back up on the next request, that's normal, not
a bug. RAM is limited on the free tier, so stick to `tiny`/`base` models there
(`small`/`medium` risk running out of memory); the app also only runs one
transcription at a time so multiple requests don't compete for RAM.
