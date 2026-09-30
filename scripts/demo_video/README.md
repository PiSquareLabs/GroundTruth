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

## Voice-over

The published video uses ElevenLabs clips (voice "Rahul Bharadwaj", model Eleven Multilingual v2) stored in `voice/`,
one MP3 per key in `narration.json`, generated from the website. To use them instead of `tts.py`, convert each to a
trimmed WAV next to the scripts and write `durations.json`:

```bash
for f in voice/*.mp3; do k=$(basename "$f" .mp3); ffmpeg -y -i "$f" -af "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.15,areverse" -ar 48000 -ac 2 "$k.wav"; done
python -c "import json,wave;json.dump({k:(lambda w:w.getnframes()/w.getframerate())(wave.open(k+'.wav')) for k in json.load(open('narration.json'))},open('durations.json','w'))"
```

Then run `record.py` and `build.py` as above; each scene is timed to its clip.
