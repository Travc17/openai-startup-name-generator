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
    print(f"{len(games)} game(s) -> {out} ({out.stat().st_size // 1024} KB)")
    return out


if __name__ == "__main__":
    build()
