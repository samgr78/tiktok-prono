"""Teste le déroulement complet, étape par étape, avec de vrais matchs.

    python test_pipeline.py              # test complet (génère 1 vidéo)
    python test_pipeline.py --no-render  # vérifie juste l'API, sans vidéo

Chaque étape affiche ✓ ou ✗ avec une piste pour corriger.
La vidéo de test est écrite dans output/test/ (n'écrase pas les vraies).
"""
import argparse
import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

OK, KO = "\033[92m✓\033[0m", "\033[91m✗\033[0m"
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def step(title):
    print(f"\n\033[1m— {title}\033[0m")


def fail(msg, hint=None):
    print(f"  {KO} {msg}")
    if hint:
        print(f"    → {hint}")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--days", type=int, default=7, help="jours à scanner pour trouver un match")
    args = ap.parse_args()

    # 1. Configuration --------------------------------------------------------
    step("1. Configuration")
    from main import load_dotenv
    load_dotenv()
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "")
    if not token:
        fail("FOOTBALL_DATA_TOKEN introuvable",
             "crée un fichier .env à la racine avec : FOOTBALL_DATA_TOKEN=ton_token")
    print(f"  {OK} token chargé ({token[:4]}…{token[-4:]})")

    if not args.no_render:
        if not shutil.which("ffmpeg"):
            fail("ffmpeg introuvable", "installe-le : brew install ffmpeg")
        print(f"  {OK} ffmpeg trouvé")

    try:
        import pygame, pymunk, requests  # noqa: F401
    except ImportError as exc:
        fail(f"module manquant : {exc.name}",
             "active le venv (source .venv/bin/activate) puis pip install -r requirements.txt")
    print(f"  {OK} modules Python installés")

    # 2. Connexion à l'API -----------------------------------------------------
    step("2. Connexion à football-data.org")
    from prono import fixtures as F
    try:
        data = F._get("competitions/FL1")
    except requests.exceptions.SSLError:
        fail("erreur de certificat SSL",
             "lance : pip install --upgrade certifi  (ou teste sur un autre réseau)")
    except requests.exceptions.ConnectionError:
        fail("impossible de joindre api.football-data.org",
             "vérifie ta connexion ; le Wi-Fi de l'école peut bloquer, essaie le partage 4G")
    except RuntimeError as exc:
        hint = "token invalide : vérifie-le dans .env (sans espaces ni guillemets)" \
            if " 400 " in str(exc) or " 403 " in str(exc) else None
        fail(str(exc), hint)
    season = data.get("currentSeason", {})
    print(f"  {OK} API joignable — {data.get('name')} saison "
          f"{season.get('startDate', '?')[:4]}, journée {season.get('currentMatchday', '?')}")

    # 3. Recherche d'un match à venir -----------------------------------------
    step(f"3. Recherche d'un match dans les {args.days} prochains jours")
    today = dt.date.today()
    resp = F._get("matches", {
        "competitions": ",".join(F.DEFAULT_LEAGUES),
        "dateFrom": today.isoformat(),
        "dateTo": (today + dt.timedelta(days=args.days)).isoformat(),
    })
    upcoming = [m for m in resp.get("matches", []) if m["status"] in ("SCHEDULED", "TIMED")]
    print(f"  {OK} {len(upcoming)} match(s) à venir trouvé(s)")
    if not upcoming:
        fail("aucun match à venir (trêve internationale ?)",
             f"relance avec --days 10, ou teste le rendu avec : python main.py --demo")
    first = min(upcoming, key=lambda m: m["utcDate"])
    match_date = dt.datetime.fromisoformat(first["utcDate"].replace("Z", "+00:00")) \
        .astimezone(F.PARIS).date()
    print(f"  {OK} premier jour avec match : {JOURS[match_date.weekday()]} {match_date:%d/%m}")

    # 4. Matchs du jour + probabilités (exactement ce que fait main.py) --------
    step(f"4. Matchs du {match_date:%d/%m} et probabilités")
    time.sleep(1)
    fixtures = F.fetch_fixtures(match_date, F.DEFAULT_LEAGUES, limit=5)
    if not fixtures:
        fail("fetch_fixtures n'a rien renvoyé pour ce jour")
    for fx in fixtures:
        print(f"  {OK} {fx.kickoff:%H:%M}  {fx.league:<20} {fx.home} vs {fx.away}"
              f"  → {fx.home_win_prob:.0%} domicile")
    if all(fx.home_win_prob == 0.55 for fx in fixtures):
        print("  ! toutes les probas sont à 55 % : classements non récupérés (voir messages ci-dessus)")

    if args.no_render:
        print(f"\n{OK} API OK. Relance sans --no-render pour tester la vidéo.")
        return

    # 5. Rendu d'une vidéo ----------------------------------------------------
    fx = fixtures[0]
    step(f"5. Génération de la vidéo : {fx.home} vs {fx.away}")
    from prono.games import GAMES
    from prono.palette import random_palette
    from prono.video import VideoWriter

    out_dir = Path("output/test")
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f"{fx.id}-{match_date}")
    game_name = rng.choice(list(GAMES))
    game = GAMES[game_name](fx, random_palette(rng), rng)
    path = out_dir / f"{fx.id}_{game_name}.mp4"
    t0 = time.time()
    writer = VideoWriter(str(path))
    try:
        winner = game.run(writer)
    finally:
        writer.close()
    print(f"  {OK} rendu en {time.time() - t0:.0f}s — prono : {(fx.home, fx.away)[winner]}")

    # 6. Vérification du fichier ----------------------------------------------
    step("6. Vérification du MP4")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height",
         "-of", "json", str(path)], capture_output=True, text=True)
    info = json.loads(probe.stdout or "{}")
    stream = (info.get("streams") or [{}])[0]
    duration = float(info.get("format", {}).get("duration", 0))
    if (stream.get("width"), stream.get("height")) != (1080, 1920) or duration < 5:
        fail(f"vidéo invalide : {stream} / {duration:.1f}s")
    size_mb = path.stat().st_size / 1e6
    print(f"  {OK} 1080x1920, {duration:.1f}s, {size_mb:.1f} Mo")

    from main import caption
    print(f"\n\033[1mTout fonctionne !\033[0m Vidéo : {path.resolve()}")
    print("Légende générée :\n" + caption(fx))
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)])  # ouvre la vidéo sur Mac


if __name__ == "__main__":
    main()
