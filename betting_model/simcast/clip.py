"""SizzleSims clip for X. Default: LANDSCAPE 1920x1080 broadcast (Travis, 2026-11-04: like a TV broadcast, live box
score per team on its side, no buttons, nothing cut off), then the full final box score for both teams held 10 s.
--portrait: the older 1080x1920 clip (each team's final box 6 s).      python simcast/clip.py out.mp4 [--portrait]
Gameplay is screen-recorded; end cards are screenshots spliced in by ffmpeg (the recorder drops frames on static
screens, so a recorded end card does not hold its full time)."""
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent


def main(out: str, portrait: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp())
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    script = "record_clip.js" if portrait else "record_broadcast.js"
    subprocess.run(["node", str(HERE / script), str(HERE / "simcast.html"), str(tmp)], check=True, env=env)
    w = str(next(tmp.glob("*.webm")))
    W, H = (1080, 1920) if portrait else (1920, 1080)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", w],
                               capture_output=True, text=True).stdout)
    crop = "crop=1080:400:0:120,scale=108:40" if portrait else "crop=1920:360:0:0,scale=192:36"
    size = 108 * 40 * 3 if portrait else 192 * 36 * 3
    def frame(t):
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t}", "-i", w, "-frames:v", "1", "-vf", crop,
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        return np.frombuffer(raw, np.uint8).astype(float) if len(raw) == size else None
    ref, t, cut = frame(dur - 0.3), max(0.0, dur - 25), None
    while t < dur:                                    # gameplay ends where the end-card layout first appears
        f = frame(t)
        if f is not None and np.abs(f - ref).mean() < 6:
            cut = t
            break
        t += 0.25
    cut = cut or dur
    cards = [("card_1.png", 6), ("card_2.png", 6)] if portrait else [("card.png", 10)]
    args = ["ffmpeg", "-y", "-loglevel", "error", "-i", w]
    for name, secs in cards:
        args += ["-loop", "1", "-t", str(secs), "-i", str(tmp / name)]
    parts = [f"[0:v]trim=0:{cut:.2f},setpts=PTS-STARTPTS,scale={W}:{H},fps=30,format=yuv420p[g]"]
    parts += [f"[{k + 1}:v]scale={W}:{H},fps=30,format=yuv420p[c{k}]" for k in range(len(cards))]
    parts.append("[g]" + "".join(f"[c{k}]" for k in range(len(cards))) + f"concat=n={len(cards) + 1}:v=1:a=0[v]")
    silent = str(tmp / "silent.mp4")
    subprocess.run(args + ["-filter_complex", ";".join(parts), "-map", "[v]", "-c:v", "libx264", "-preset", "slow",
                           "-crf", "19", "-movflags", "+faststart", silent], check=True)
    cues = tmp / "cues.json"
    if cues.exists():   # original soundtrack (simcast/sound.py), cue times calibrated so the end card lines up exactly
        import json
        final_t = next(c["t"] for c in json.loads(cues.read_text()) if c["kind"] == "final")
        offset = cut - (final_t + 3.0)                    # the end card appears 3.0 s after the final whistle
        total = cut + sum(sec for _, sec in cards)
        wav = str(tmp / "sound.wav")
        subprocess.run([sys.executable, str(HERE / "sound.py"), str(cues), f"{offset:.3f}", f"{total:.3f}",
                        str(sum(sec for _, sec in cards)), wav], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                        "-shortest", "-movflags", "+faststart", out], check=True)       # -16 LUFS: phone-loud, no clipping
    else:
        import shutil
        shutil.copy(silent, out)
    print(f"{out}: {W}x{H}, gameplay {cut:.1f} s + " + " + ".join(f"{s} s" for _, s in cards) + " end card(s)")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0] if a else str(HERE / "clip.mp4"), portrait="--portrait" in sys.argv)
