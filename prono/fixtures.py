"""Récupère les matchs du jour via football-data.org (plan gratuit)."""
import datetime as dt
import math
import os
import time
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import requests

API_URL = "https://api.football-data.org/v4"
PARIS = ZoneInfo("Europe/Paris")

# Codes football-data.org des compétitions suivies, par ordre de priorité
DEFAULT_LEAGUES = {
    "FL1": "Ligue 1",
    "CL": "Ligue des champions",
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
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


def _get(path: str, params: dict | None = None) -> dict:
    token = os.environ["FOOTBALL_DATA_TOKEN"]
    for attempt in range(3):
        r = requests.get(f"{API_URL}/{path}", params=params,
                         headers={"X-Auth-Token": token}, timeout=20)
        if r.status_code == 429:          # limite de 10 appels/minute atteinte
            time.sleep(15)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"football-data.org {r.status_code} sur /{path} : {r.text[:200]}")
        return r.json()
    raise RuntimeError("football-data.org : trop de requêtes, réessaie plus tard")


def _standings(code: str) -> dict[int, float]:
    """Points par match de chaque équipe (1 requête par compétition)."""
    try:
        data = _get(f"competitions/{code}/standings")
    except Exception as exc:
        print(f"  ! classement indisponible pour {code}: {exc}")
        return {}
    ppg = {}
    for group in data.get("standings", []):
        if group.get("type") != "TOTAL":
            continue
        for row in group["table"]:
            played = row.get("playedGames") or 0
            if played:
                ppg[row["team"]["id"]] = row["points"] / played
    return ppg


def _home_win_prob(home_ppg: float | None, away_ppg: float | None) -> float:
    """Modèle simple : écart de points par match + avantage du terrain."""
    if home_ppg is None or away_ppg is None:
        return 0.55                     # pas de classement : léger avantage domicile
    diff = home_ppg - away_ppg + 0.25   # 0.25 pt/match ~ avantage du terrain
    p = 1 / (1 + math.exp(-1.2 * diff))
    return min(0.8, max(0.2, p))        # on garde toujours une part de suspense


def fetch_fixtures(date: dt.date, leagues: dict[str, str], limit: int,
                   with_predictions: bool = True) -> list[Fixture]:
    # Un seul appel pour tous les matchs (dates en UTC, on filtre ensuite en heure de Paris)
    data = _get("matches", {
        "competitions": ",".join(leagues),
        "dateFrom": date.isoformat(),
        "dateTo": (date + dt.timedelta(days=1)).isoformat(),
    })
    fixtures, team_ids = [], {}
    for m in data.get("matches", []):
        if m["status"] not in ("SCHEDULED", "TIMED"):
            continue                    # match commencé, terminé ou reporté
        kickoff = dt.datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).astimezone(PARIS)
        if kickoff.date() != date:
            continue
        code = m["competition"]["code"]
        home, away = m["homeTeam"], m["awayTeam"]
        fixtures.append(Fixture(
            id=m["id"],
            league=leagues.get(code, m["competition"]["name"]),
            kickoff=kickoff,
            home=home.get("shortName") or home["name"],
            away=away.get("shortName") or away["name"],
            extra={"code": code, "home_tla": home.get("tla"), "away_tla": away.get("tla")},
        ))
        team_ids[m["id"]] = (home["id"], away["id"])

    order = list(leagues)
    fixtures.sort(key=lambda f: (order.index(f.extra["code"]) if f.extra["code"] in order else 99,
                                 f.kickoff))
    fixtures = fixtures[:limit]

    if with_predictions:
        tables = {code: _standings(code) for code in {f.extra["code"] for f in fixtures}}
        for f in fixtures:
            h, a = team_ids[f.id]
            table = tables[f.extra["code"]]
            f.home_win_prob = _home_win_prob(table.get(h), table.get(a))
    return fixtures


def demo_fixtures(date: dt.date) -> list[Fixture]:
    """Matchs fictifs pour tester sans clé API."""
    at = lambda h, m: dt.datetime.combine(date, dt.time(h, m), PARIS)
    return [
        Fixture(900001, "Ligue 1", at(21, 0), "PSG", "Marseille", 0.68),
        Fixture(900002, "Premier League", at(17, 30), "Arsenal", "Chelsea", 0.57),
        Fixture(900003, "La Liga", at(18, 30), "Real Madrid", "Atleti", 0.6),
    ]
