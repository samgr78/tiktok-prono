"""Génère une palette de couleurs différente pour chaque vidéo."""
import colorsys
import random
from dataclasses import dataclass

RGB = tuple[int, int, int]


def _hls(h: float, l: float, s: float) -> RGB:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, l, s)
    return int(r * 255), int(g * 255), int(b * 255)


@dataclass
class Palette:
    background: RGB
    background_alt: RGB   # bandes / dégradé de fond
    obstacle: RGB
    text: RGB
    accent: RGB
    team_a: RGB
    team_b: RGB


def random_palette(rng: random.Random) -> Palette:
    base = rng.random()                       # teinte du fond
    dark = rng.random() < 0.75                # 75 % fonds sombres (meilleur rendu TikTok)

    if dark:
        bg = _hls(base, rng.uniform(0.07, 0.13), rng.uniform(0.35, 0.7))
        bg_alt = _hls(base, rng.uniform(0.15, 0.2), rng.uniform(0.35, 0.7))
        obstacle = _hls(base + 0.05, rng.uniform(0.7, 0.85), rng.uniform(0.3, 0.6))
        text = (245, 245, 245)
    else:
        bg = _hls(base, rng.uniform(0.86, 0.92), rng.uniform(0.4, 0.8))
        bg_alt = _hls(base, rng.uniform(0.78, 0.84), rng.uniform(0.4, 0.8))
        obstacle = _hls(base + 0.05, rng.uniform(0.25, 0.35), rng.uniform(0.3, 0.6))
        text = (25, 25, 30)

    # Les deux équipes : teintes éloignées du fond et entre elles
    hue_a = base + rng.uniform(0.25, 0.4)
    hue_b = hue_a + rng.uniform(0.35, 0.5)
    light = 0.55 if dark else 0.45
    team_a = _hls(hue_a, light, rng.uniform(0.75, 0.95))
    team_b = _hls(hue_b, light, rng.uniform(0.75, 0.95))
    accent = _hls(base + 0.5, 0.6, 0.9)

    return Palette(bg, bg_alt, obstacle, text, accent, team_a, team_b)