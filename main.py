"""Génère les vidéos « prono du jour » pour les matchs d'aujourd'hui.

Exemples :
    python main.py --demo                 # sans clé API, matchs fictifs
    python main.py                        # matchs réels (FOOTBALL_DATA_TOKEN requis)
    python main.py --date 2026-11-12 --limit 3
"""
import argparse
import datetime as dt
import json
import os
import random
import time
from pathlib import Path

from prono.fixtures import DEFAULT_LEAGUES, demo_fixtures, fetch_fixtures
from prono.games import GAMES
from prono.palette import random_palette
from prono.video import VideoWriter

HASHTAGS = {
    "Ligue 1": "#ligue1", "Premier League": "#premierleague", "La Liga": "#laliga",
    "Serie A": "#seriea", "Bundesliga": "#bundesliga", "Ligue des champions": "#ucl",
}


def load_dotenv(path=".env"):
    """Mini lecteur de .env (évite une dépendance de plus)."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def caption(fx) -> str:
    tag = HASHTAGS.get(fx.league, "")
    return (f"🔮 {fx.home} vs {fx.away} : qui gagne ce soir ? Réponse à la fin 👀\n"
            f"{fx.league} • {fx.kickoff:%H:%M}\n"
            f"#prono #pronostic #football #foot {tag}").strip()


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--limit", type=int, default=int(os.environ.get("MAX_VIDEOS", 5)))
    ap.add_argument("--game", choices=list(GAMES) + ["random"], default="random")
    ap.add_argument("--demo", action="store_true", help="matchs fictifs, sans API")
    ap.add_argument("--out", default="output")
    args = ap.parse_args()

    if args.demo or not os.environ.get("FOOTBALL_DATA_TOKEN"):
        if not args.demo:
            print("FOOTBALL_DATA_TOKEN absent : passage en mode démo")
        fixtures = demo_fixtures(args.date)[: args.limit]
    else:
        fixtures = fetch_fixtures(args.date, DEFAULT_LEAGUES, args.limit)

    if not fixtures:
        print("Aucun match à venir aujourd'hui dans les compétitions suivies.")
        return

    out_dir = Path(args.out) / args.date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []

    for fx in fixtures:
        # Graine propre à chaque match : couleurs + parcours différents à chaque vidéo,
        # mais reproductibles si on relance le script pour le même match.
        rng = random.Random(f"{fx.id}-{args.date}")
        game_name = rng.choice(list(GAMES)) if args.game == "random" else args.game
        game = GAMES[game_name](fx, random_palette(rng), rng)

        stem = f"{fx.id}_{game_name}"
        video_path = out_dir / f"{stem}.mp4"
        print(f"▶ {fx.home} vs {fx.away} ({fx.league}) – {game_name}, "
              f"proba domicile {fx.home_win_prob:.0%}")
        t0 = time.time()
        writer = VideoWriter(str(video_path))
        try:
            winner = game.run(writer)
        finally:
            writer.close()
        winner_name = (fx.home, fx.away)[winner]
        print(f"  ✓ {video_path} ({time.time() - t0:.0f}s) – prono : {winner_name}")

        text = caption(fx)
        (out_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
        manifest.append({
            "fixture_id": fx.id, "league": fx.league, "kickoff": fx.kickoff.isoformat(),
            "home": fx.home, "away": fx.away, "home_win_prob": fx.home_win_prob,
            "game": game_name, "prediction": winner_name,
            "video": video_path.name, "caption": text,
        })

    # Le manifest servira à la publication auto et au bilan « prono vs résultat réel »
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(manifest)} vidéo(s) dans {out_dir}/")


if __name__ == "__main__":
    main()
