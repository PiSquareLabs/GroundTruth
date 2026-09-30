"""Synthesize the narration (narration.json) into per-scene WAV files and record their durations."""
import asyncio, json, edge_tts, subprocess, imageio_ffmpeg
F = imageio_ffmpeg.get_ffmpeg_exe()
N = json.load(open("narration.json"))
async def main():
    durs = {}
    for k, t in N.items():
        await edge_tts.Communicate(t, "en-US-AndrewMultilingualNeural", rate="+4%").save(f"{k}.mp3")
        subprocess.run([F, "-y", "-loglevel", "error", "-i", f"{k}.mp3", "-ar", "48000", "-ac", "2", f"{k}.wav"], check=True)
        import wave
        with wave.open(f"{k}.wav") as w: durs[k] = w.getnframes() / w.getframerate()
        print(k, round(durs[k], 1))
    json.dump(durs, open("durations.json", "w"))
    print("total", round(sum(durs.values()), 1))
asyncio.run(main())
