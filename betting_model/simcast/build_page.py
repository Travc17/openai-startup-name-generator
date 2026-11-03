"""Bundle every exported game (simcast/games/*.json) into one self-contained page: simcast/simcast.html."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(out: Path = HERE / "simcast.html") -> Path:
    games = [json.loads(p.read_text()) for p in sorted((HERE / "games").glob("*.json"))]
    games.sort(key=lambda g: (g["key"], g["away"]))
    blob = json.dumps(games, separators=(",", ":")).replace("</", "<\\/")
    html = (HERE / "viewer.html").read_text().replace("/*__GAMES__*/[]", blob, 1)
    out.write_text(html)
    # bake the newest game's final into the file for apps that open HTML without running scripts
    import os, subprocess
    env = dict(os.environ, NODE_PATH=subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
    r = subprocess.run(["node", str(HERE / "snapshot.js"), str(out)], capture_output=True, text=True, env=env)
    print(r.stdout.strip() or f"WARNING: no pre-rendered fallback (scripts-off previews will be blank): {r.stderr.strip()[:200]}")
    print(f"{len(games)} game(s) -> {out} ({out.stat().st_size // 1024} KB)")
    return out


if __name__ == "__main__":
    build()
