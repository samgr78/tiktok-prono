"""Palettes néon : un fond sombre « ambiance » + deux couleurs d'équipe vives.

Les couleurs sont choisies dans des listes faites à la main (et non plus
tirées au hasard) pour éviter les tons pastel et garantir le contraste.
"""
import colorsys
import random
from dataclasses import dataclass

RGB = tuple[int, int, int]

# Fonds : (haut du dégradé, bas du dégradé, couleur des décors néon)
THEMES = [
    ((10, 8, 36), (38, 10, 64), (120, 90, 255)),      # violet nuit
    ((4, 16, 38), (6, 42, 74), (0, 200, 255)),        # bleu abysse
    ((18, 4, 20), (64, 8, 40), (255, 60, 170)),       # magenta sombre
    ((4, 24, 22), (6, 58, 50), (0, 255, 190)),        # émeraude
    ((26, 10, 4), (70, 22, 6), (255, 140, 30)),       # braise
    ((8, 8, 12), (28, 28, 40), (220, 220, 255)),      # carbone
]

# Couleurs d'équipe néon (saturées, lumineuses)
TEAM_COLORS = [
    (0, 229, 255),    # cyan
    (255, 46, 136),   # rose
    (255, 214, 0),    # jaune
    (57, 255, 20),    # vert fluo
    (255, 106, 0),    # orange
    (176, 82, 255),   # violet
    (255, 48, 48),    # rouge
    (40, 120, 255),   # bleu roi
]


@dataclass
class Palette:
    bg_top: RGB
    bg_bottom: RGB
    neon: RGB            # décors (murs, obstacles) avec lueur
    team_a: RGB
    team_b: RGB
    accent: RGB          # badge VS, détails
    text: RGB = (255, 255, 255)

    # compatibilité avec l'ancien code
    @property
    def background(self):
        return self.bg_top

    @property
    def background_alt(self):
        return self.bg_bottom

    @property
    def obstacle(self):
        return self.neon


def _hue(c: RGB) -> float:
    return colorsys.rgb_to_hsv(*(v / 255 for v in c))[0]


def _hue_dist(a: RGB, b: RGB) -> float:
    if a == (255, 255, 255) or b == (255, 255, 255):
        return 0.5
    d = abs(_hue(a) - _hue(b))
    return min(d, 1 - d)


def random_palette(rng: random.Random) -> Palette:
    top, bottom, neon = rng.choice(THEMES)
    # deux couleurs d'équipe bien distinctes entre elles et du décor
    for _ in range(100):
        a, b = rng.sample(TEAM_COLORS, 2)
        if _hue_dist(a, b) > 0.22 and _hue_dist(a, neon) > 0.08 and _hue_dist(b, neon) > 0.08:
            break
    accent = rng.choice([c for c in TEAM_COLORS if c not in (a, b)])
    return Palette(top, bottom, neon, a, b, accent)
