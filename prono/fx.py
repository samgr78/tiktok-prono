"""Effets visuels partagés : fonds, lueurs néon, balles en relief, particules."""
import math
import random
from functools import lru_cache

import pygame

from .video import HEIGHT, WIDTH

ADD = pygame.BLEND_RGB_ADD
BLACK, WHITE = (0, 0, 0), (255, 255, 255)


def lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def scale(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


# ---------------------------------------------------------------- fonds
def gradient(size, top, bottom):
    w, h = size
    surf = pygame.Surface((1, h))
    for y in range(h):
        surf.set_at((0, y), lerp(top, bottom, y / max(1, h - 1)))
    return pygame.transform.scale(surf, (w, h))


def background(p, rng: random.Random, size=(WIDTH, HEIGHT), pattern="dots"):
    """Dégradé + motif discret + étoiles + vignette. À calculer une fois par vidéo."""
    w, h = size
    bg = gradient(size, p.bg_top, p.bg_bottom)
    deco = scale(p.neon, 0.16)
    if pattern == "dots":
        for y in range(0, h, 48):
            for x in range(24 if (y // 48) % 2 else 0, w, 48):
                pygame.draw.circle(bg, deco, (x, y), 2)
    elif pattern == "grid":
        for x in range(0, w, 60):
            pygame.draw.line(bg, deco, (x, 0), (x, h), 1)
        for y in range(0, h, 60):
            pygame.draw.line(bg, deco, (0, y), (w, y), 1)
    for _ in range(w * h // 9000):  # petites étoiles
        c = scale(p.neon, rng.uniform(0.2, 0.6))
        pygame.draw.circle(bg, c, (rng.randrange(w), rng.randrange(h)), rng.choice((1, 1, 2)))
    # halo lumineux doux au centre
    halo = pygame.Surface((w // 8, h // 8))
    cx, cy = w // 16, h // 16
    for r in range(max(cx, cy), 0, -2):
        pygame.draw.circle(halo, scale(p.neon, 0.10 * (1 - r / max(cx, cy))), (cx, cy), r)
    bg.blit(pygame.transform.smoothscale(halo, (w, h)), (0, 0), special_flags=ADD)
    # vignette (bords assombris)
    vig = pygame.Surface((w // 8, h // 8), pygame.SRCALPHA)
    vw, vh = vig.get_size()
    for i in range(12):
        a = int(150 * (1 - i / 12) ** 2)
        pygame.draw.rect(vig, (0, 0, 0, a), (i, i, vw - 2 * i, vh - 2 * i), 1)
    bg.blit(pygame.transform.smoothscale(vig, (w, h)), (0, 0))
    return bg


# ---------------------------------------------------------------- lueurs
def blur(surf, factor=8):
    """Flou rapide : réduction puis agrandissement lissés."""
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (max(1, w // factor), max(1, h // factor)))
    return pygame.transform.smoothscale(small, (w, h))


class GlowLayer:
    """Calque de lueur : on y dessine les éléments néon, puis on l'ajoute flouté.

    Le calque est dessiné en quart de résolution (rapide) puis flouté.
    """
    K = 4

    def __init__(self, size=(WIDTH, HEIGHT)):
        self.size = size
        self.small = pygame.Surface((size[0] // self.K, size[1] // self.K))

    def clear(self):
        self.small.fill(BLACK)

    def _p(self, pt):
        return (pt[0] / self.K, pt[1] / self.K)

    def line(self, a, b, color, width):
        pygame.draw.line(self.small, color, self._p(a), self._p(b), max(1, int(width / self.K)))

    def circle(self, c, r, color, width=0):
        pygame.draw.circle(self.small, color, self._p(c), max(1, r / self.K),
                           max(1, int(width / self.K)) if width else 0)

    def polygon(self, pts, color):
        pygame.draw.polygon(self.small, color, [self._p(q) for q in pts])

    def arc(self, center, r, start, stop, color, width):
        rect = pygame.Rect(0, 0, 2 * r / self.K, 2 * r / self.K)
        rect.center = self._p(center)
        pygame.draw.arc(self.small, color, rect, start, stop, max(1, int(width / self.K)))

    def apply(self, target, strength=1.0, offset=(0, 0)):
        w, h = self.small.get_size()
        tiny = pygame.transform.smoothscale(self.small, (max(1, w // 3), max(1, h // 3)))
        glow = pygame.transform.smoothscale(tiny, self.size)
        if strength != 1.0:
            glow.fill(scale(WHITE, strength), special_flags=pygame.BLEND_RGB_MULT)
        target.blit(glow, offset, special_flags=ADD)
        # deuxième passe plus nette pour un coeur lumineux
        sharp = pygame.transform.smoothscale(self.small, self.size)
        sharp.fill(scale(WHITE, 0.5 * strength), special_flags=pygame.BLEND_RGB_MULT)
        target.blit(sharp, offset, special_flags=ADD)


def bake_glow(neon_surface, strength=1.0):
    """Lueur d'un décor statique (calculée une seule fois)."""
    glow = blur(neon_surface, 10)
    glow2 = blur(neon_surface, 4)
    out = neon_surface.copy()
    out.fill(BLACK)
    for g, k in ((glow, 1.4 * strength), (glow2, 0.8 * strength)):
        g.fill(scale(WHITE, min(1.0, k)), special_flags=pygame.BLEND_RGB_MULT)
        out.blit(g, (0, 0), special_flags=ADD)
        if k > 1:
            out.blit(g, (0, 0), special_flags=ADD)
    return out


@lru_cache(maxsize=64)
def glow_sprite(color, radius):
    """Halo radial (à ajouter en mode ADD)."""
    size = radius * 2
    s = pygame.Surface((size, size))
    for r in range(radius, 0, -1):
        t = 1 - r / radius
        pygame.draw.circle(s, scale(color, 0.55 * t * t), (radius, radius), r)
    return s


def blit_glow(surf, color, center, radius):
    g = glow_sprite(tuple(color), int(radius))
    surf.blit(g, (center[0] - radius, center[1] - radius), special_flags=ADD)


@lru_cache(maxsize=64)
def ball_sprite(color, r):
    """Balle en relief : bord sombre, dégradé, reflet, liseré blanc."""
    pad = 6
    size = 2 * (r + pad)
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = (r + pad, r + pad)
    pygame.draw.circle(s, WHITE, c, r + 4)
    pygame.draw.circle(s, scale(color, 0.45), c, r)
    steps = 14
    for i in range(steps):
        t = i / steps
        rr = int(r * (1 - t * 0.85))
        off = int(r * 0.28 * t)
        pygame.draw.circle(s, lerp(scale(color, 0.7), lerp(color, WHITE, 0.25), t),
                           (c[0] - off, c[1] - off), rr)
    # reflet
    hl = pygame.Surface((r, r // 2), pygame.SRCALPHA)
    pygame.draw.ellipse(hl, (255, 255, 255, 120), hl.get_rect())
    s.blit(hl, (c[0] - int(r * 0.75), c[1] - int(r * 0.8)))
    return s


def draw_ball(surf, color, center, r, label=None, label_size=None, flash=0.0):
    from .video import draw_text
    sprite = ball_sprite(tuple(color), int(r))
    blit_glow(surf, color, center, int(r * 2.2))
    surf.blit(sprite, (center[0] - sprite.get_width() // 2, center[1] - sprite.get_height() // 2))
    if flash > 0:
        f = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
        pygame.draw.circle(f, (255, 255, 255, int(220 * flash)), (r, r), r)
        surf.blit(f, (center[0] - r, center[1] - r))
    if label:
        draw_text(surf, label, label_size or int(r * 0.7), WHITE, center, outline=BLACK, outline_px=2)


# ---------------------------------------------------------------- particules
def burst(surf, origin, color, t, seed, n=14, speed=380, life=0.6, size=6, gravity=500):
    """Explosion de particules déterministe. t = secondes écoulées depuis l'impact."""
    if t < 0 or t > life:
        return
    rng = random.Random(seed)
    k = 1 - t / life
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        v = rng.uniform(0.35, 1.0) * speed
        x = origin[0] + math.cos(a) * v * t
        y = origin[1] + math.sin(a) * v * t + 0.5 * gravity * t * t
        r = max(1, int(size * k * rng.uniform(0.6, 1.2)))
        pygame.draw.circle(surf, lerp(WHITE, color, 1 - k), (int(x), int(y)), r)


def shards(surf, center, radius, color, t, seed, n=18, life=0.9):
    """Morceaux d'anneau qui volent (anneau brisé)."""
    if t < 0 or t > life:
        return
    rng = random.Random(seed)
    k = 1 - t / life
    for _ in range(n):
        a = rng.uniform(0, 2 * math.pi)
        v = rng.uniform(150, 420)
        x = center[0] + math.cos(a) * (radius + v * t)
        y = center[1] + math.sin(a) * (radius + v * t) + 350 * t * t
        ln = 18 * k + 4
        rot = a + rng.uniform(-1, 1) + t * rng.uniform(-8, 8)
        dx, dy = math.cos(rot) * ln, math.sin(rot) * ln
        pygame.draw.line(surf, lerp(WHITE, color, 0.4 + 0.6 * (1 - k)), (x - dx, y - dy), (x + dx, y + dy),
                         max(2, int(6 * k)))


# ---------------------------------------------------------------- panneaux
def panel(surf, rect, fill, alpha=200, border=None, radius=24, border_w=3):
    x, y, w, h = rect
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*fill, alpha), (0, 0, w, h), border_radius=radius)
    surf.blit(s, (x, y))
    if border:
        pygame.draw.rect(surf, border, rect, border_w, border_radius=radius)
