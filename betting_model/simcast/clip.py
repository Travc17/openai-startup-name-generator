"""90-second SizzleSims clip for X (1080x1920 MP4): the newest game played at the 90 s speed, then each team's final
box score held exactly 6 s (Travis, 2026-11-03).   python simcast/clip.py [out.mp4]
Gameplay is screen-recorded; the end cards are screenshots spliced in by ffmpeg, because the recorder drops frames
while the screen is still (a static card recorded directly did not stay up 6 s)."""
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent


def main(out: str) -> None:
    tmp = Path(tempfile.mkdtemp())
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    subprocess.run(["node", str(HERE / "record_clip.js"), str(HERE / "simcast.html"), str(tmp)], check=True, env=env)
    w = str(next(tmp.glob("*.webm")))
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", w],
                               capture_output=True, text=True).stdout)

    def frame(t):
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t}", "-i", w, "-frames:v", "1", "-vf",
                              "crop=1080:400:0:120,scale=108:40", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(40, 108, 3).astype(float) if len(raw) == 40 * 108 * 3 else None
    ref, t, cut = frame(dur - 0.3), max(0.0, dur - 25), None
    while t < dur:                                    # gameplay ends where the end-card layout first appears
        f = frame(t)
        if f is not None and np.abs(f - ref).mean() < 6:
            cut = t
            break
        t += 0.25
    cut = cut or dur
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", w, "-loop", "1", "-t", "6", "-i", str(tmp / "card_1.png"),
                    "-loop", "1", "-t", "6", "-i", str(tmp / "card_2.png"), "-filter_complex",
                    f"[0:v]trim=0:{cut:.2f},setpts=PTS-STARTPTS,fps=30,format=yuv420p[g];[1:v]fps=30,format=yuv420p[a];"
                    "[2:v]fps=30,format=yuv420p[b];[g][a][b]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-c:v", "libx264",
                    "-preset", "slow", "-crf", "19", "-movflags", "+faststart", out], check=True)
    print(f"{out}: gameplay {cut:.1f} s + 6 s + 6 s end cards")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "clip.mp4"))
