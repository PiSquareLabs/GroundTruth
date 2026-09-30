# Demo video tooling

Regenerates `docs/demo/ground-truth-demo.mp4` and `.srt` by driving a local copy of the app with Playwright, recording
it through a Chrome DevTools screencast, and adding a synthesized voice-over from `narration.json`.

```bash
pip install -r requirements.txt playwright edge-tts imageio-ffmpeg
DEMO_MODE=true streamlit run app.py --server.port 8501 --client.toolbarMode minimal   # in another terminal
cd scripts/demo_video
python tts.py      # narration.json -> <scene>.wav + durations.json (needs network for the neural voice)
python record.py   # drives http://localhost:8501, writes frames/ + timeline.json; each scene lasts as long as its narration
python build.py    # frames + audio -> docs/demo/ground-truth-demo.mp4 and .srt
```

Optional environment variables for `record.py`: `CHROMIUM_PATH` (use a specific Chromium binary), `CHROMIUM_ARGS`
(extra launch flags), and `HTTPS_PROXY` (routed for everything except localhost). Set `GEMINI_API_KEY` before starting
the app to record semantic search instead of the keyword fallback, and adjust the "search" line in `narration.json`.
