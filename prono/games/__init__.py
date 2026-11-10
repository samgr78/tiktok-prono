"""Registre des mini-jeux : ajouter un jeu = ajouter une ligne ici."""
from .ball_race import BallRace

GAMES = {
    BallRace.name: BallRace,
}