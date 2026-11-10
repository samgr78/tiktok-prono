"""Récupère les matchs du jour via API-Football (api-sports.io)."""
import datetime as dt
import os
from dataclasses import dataclass, field

import requests

API_URL = "https://v3.football.api-sports.io"

# IDs API-Football des compétitions suivies (modifiable via la variable LEAGUES)
DEFAULT_LEAGUES = {
    61: "Ligue 1",
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    2: "Ligue des champions",
}


@dataclass
class Fixture:
    id: int
    league: str
    kickoff: dt.datetime
    home: str
    away: str
    # probabilité (0-1) que l'équipe à domicile gagne, hors match nul
    home_win_prob: float = 0.5
    extra: dict = field(default_factory=dict)


def _get(path: str, params: dict) -> dict:
    key = os.environ["API_FOOTBALL_KEY"]
    r = requests.get(f"{API_URL}/{path}", params=params,
                     headers={"x-apisports-key": key}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(f"API-Football: {data['errors']}")
    return data


def _prediction(fixture_id: int) -> float:
    """Probabilité domicile vs extérieur d'après /predictions (1 requête)."""
    try:
        resp = _get("predictions", {"fixture": fixture_id})["response"]
        pct = resp[0]["predictions"]["percent"]
        home = float(pct["home"].rstrip("%"))
        away = float(pct["away"].rstrip("%"))
        if home + away > 0:
            return home / (home + away)
    except Exception as exc:  # pas bloquant : on reste à 50/50
        print(f"  ! prédiction indisponible pour {fixture_id}: {exc}")
    return 0.5


def fetch_fixtures(date: dt.date, leagues: dict[int, str], limit: int,
                   with_predictions: bool = True) -> list[Fixture]:
    # Un seul appel pour tous les matchs du jour, filtrés ensuite par compétition
    data = _get("fixtures", {"date": date.isoformat(), "timezone": "Europe/Paris"})
    fixtures = []
    for item in data["response"]:
        league_id = item["league"]["id"]
        if league_id not in leagues:
            continue
        if item["fixture"]["status"]["short"] not in ("NS", "TBD"):
            continue  # match déjà commencé ou reporté
        fixtures.append(Fixture(
            id=item["fixture"]["id"],
            league=leagues[league_id],
            kickoff=dt.datetime.fromisoformat(item["fixture"]["date"]),
            home=item["teams"]["home"]["name"],
            away=item["teams"]["away"]["name"],
        ))
    # Ordre des compétitions = ordre de priorité
    order = list(leagues)
    fixtures.sort(key=lambda f: (order.index(_league_id(f, leagues)), f.kickoff))
    fixtures = fixtures[:limit]
    if with_predictions:
        for f in fixtures:
            f.home_win_prob = _prediction(f.id)
    return fixtures


def _league_id(f: Fixture, leagues: dict[int, str]) -> int:
    return next(k for k, v in leagues.items() if v == f.league)


def demo_fixtures(date: dt.date) -> list[Fixture]:
    """Matchs fictifs pour tester sans clé API."""
    tz = dt.timezone(dt.timedelta(hours=1))
    at = lambda h, m: dt.datetime.combine(date, dt.time(h, m), tz)
    return [
        Fixture(900001, "Ligue 1", at(21, 0), "Paris SG", "Marseille", 0.68),
        Fixture(900002, "Premier League", at(17, 30), "Arsenal", "Chelsea", 0.57),
        Fixture(900003, "La Liga", at(18, 30), "Real Madrid", "Atlético Madrid", 0.6),
    ]