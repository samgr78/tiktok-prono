"""Registre des mini-jeux : ajouter un jeu = ajouter une ligne ici."""
from .ball_battle import BallBattle
from .ball_race import BallRace
from .color_war import ColorWar
from .ring_escape import RingEscape

GAMES = {
    BallRace.name: BallRace,
    RingEscape.name: RingEscape,
    ColorWar.name: ColorWar,
    BallBattle.name: BallBattle,
}
