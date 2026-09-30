"""Stitch the recorded frames and narration into docs/demo/ground-truth-demo.mp4 (+ .srt captions)."""
import json, subprocess, imageio_ffmpeg
from pathlib import Path
OUT = Path(__file__).resolve().parents[2] / "docs" / "demo"
F = imageio_ffmpeg.get_ffmpeg_exe()
T = json.load(open("timeline.json"))
t0, end = T["t0"], T["end"]
fr = [(max(ts - t0, 0), n) for ts, n in sorted(T["frames"])]
lines = ["ffconcat version 1.0"]
for i, (ts, n) in enumerate(fr):
    nxt = fr[i + 1][0] if i + 1 < len(fr) else end - t0
    d = max(nxt - (0 if i == 0 else ts), 0.001)
    lines += [f"file frames/{n}", f"duration {d:.4f}"]
lines.append(f"file frames/{fr[-1][1]}")
open("frames.txt", "w").write("\n".join(lines) + "\n")
dur = end - t0
ins, filt = [], []
for i, (k, off) in enumerate(T["scenes"]):
    ins += ["-i", f"{k}.wav"]
    ms = int(off * 1000)
    filt.append(f"[{i+1}:a]adelay={ms}|{ms}[a{i}]")
n = len(T["scenes"])
filt.append("".join(f"[a{i}]" for i in range(n)) +
            f"amix=inputs={n}:normalize=0,apad,atrim=0:{dur:.3f},afade=t=out:st={dur-1:.3f}:d=1,"
            "loudnorm=I=-16:TP=-1.5,aresample=48000[aout]")
filt.append(f"[0:v]scale=1920:1080:flags=lanczos,fps=30,format=yuv420p,fade=t=in:st=0:d=0.6,"
            f"fade=t=out:st={dur-1:.3f}:d=1[vout]")
cmd = [F, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "frames.txt", *ins,
       "-filter_complex", ";".join(filt), "-map", "[vout]", "-map", "[aout]",
       "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
       "-movflags", "+faststart", "-t", f"{dur:.3f}", str(OUT / "ground-truth-demo.mp4")]
subprocess.run(cmd, check=True)


def ts(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


open(OUT / "ground-truth-demo.srt", "w").write(
    "\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{c}\n" for i, (a, b, c) in enumerate(T["cues"], 1)))
print("scenes", [(k, round(o, 1)) for k, o in T["scenes"]])
