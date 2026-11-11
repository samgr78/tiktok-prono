"""Habillage commun : tableau de score, intro, compte à rebours, bandeaux, résultat.

Zone « sûre » : TikTok recouvre ~130 px en haut, ~380 px en bas (légende)
et ~120 px à droite (boutons). Le jeu doit rester dans SAFE_*.
"""
import math
from functools import lru_cache

import pygame

from . import fx
from .video import HEIGHT, WIDTH, draw_text, fit_size, font, short_name

SAFE_LEFT, SAFE_RIGHT = 90, WIDTH - 90
SAFE_TOP, SAFE_BOTTOM = 340, 1490
BLACK, WHITE = (0, 0, 0), (255, 255, 255)
lerp = fx.lerp

BOARD_Y, BOARD_H = 186, 112


def team_labels(fx_):
    """Codes 3 lettres (PSG, OM…) fournis par l'API, sinon 3 premières lettres."""
    return (fx_.extra.get("home_tla") or short_name(fx_.home),
            fx_.extra.get("away_tla") or short_name(fx_.away))


@lru_cache(maxsize=64)
def _text_glow(text, size, color):
    img = font(size).render(text, True, color)
    pad = size // 2
    s = pygame.Surface((img.get_width() + 2 * pad, img.get_height() + 2 * pad))
    s.blit(img, (pad, pad))
    g = fx.blur(s, 6)
    g.blit(fx.blur(s, 3), (0, 0), special_flags=fx.ADD)
    return g


def glow_text(surf, text, size, color, center, outline=BLACK, outline_px=4):
    g = _text_glow(text, size, tuple(color))
    surf.blit(g, g.get_rect(center=center), special_flags=fx.ADD)
    draw_text(surf, text, size, WHITE if outline else color, center, outline=color if outline else None,
              outline_px=outline_px)


def _pill(surf, text, size, center, fill, border, text_color=WHITE, pad=(28, 10)):
    w, h = font(size).size(text)
    rect = (center[0] - w // 2 - pad[0], center[1] - h // 2 - pad[1], w + 2 * pad[0], h + 2 * pad[1])
    fx.panel(surf, rect, fill, 220, border, radius=(h + 2 * pad[1]) // 2)
    draw_text(surf, text, size, text_color, center)
    return rect


def header(surf, fx_, p, leader=None, t=0.0):
    """Tableau de score en haut de l'écran. t = temps (s) pour les animations."""
    _pill(surf, f"{fx_.league.upper()}  •  {fx_.kickoff:%H:%M}", 30, (WIDTH // 2, 152),
          (10, 10, 20), fx.scale(p.neon, 0.9))
    names = (fx_.home, fx_.away)
    labels = team_labels(fx_)
    colors = (p.team_a, p.team_b)
    card_w = 420
    for i in range(2):
        x = 60 if i == 0 else WIDTH - 60 - card_w
        rect = pygame.Rect(x, BOARD_Y, card_w, BOARD_H)
        lead = leader == i
        if lead:
            pulse = 0.75 + 0.25 * math.sin(t * 6)
            fx.blit_glow(surf, colors[i], rect.center, int(260 * pulse))
        fx.panel(surf, rect, fx.scale(colors[i], 0.42 if lead else 0.22), 235,
                 colors[i] if lead else fx.scale(colors[i], 0.7), radius=26, border_w=4 if lead else 3)
        # bande de couleur côté extérieur
        stripe = pygame.Rect(x + 10 if i == 0 else rect.right - 22, BOARD_Y + 14, 12, BOARD_H - 28)
        pygame.draw.rect(surf, colors[i], stripe, border_radius=6)
        badge_x = x + 92 if i == 0 else rect.right - 92
        fx.draw_ball(surf, colors[i], (badge_x, rect.centery), 40, labels[i], 26)
        name = names[i].upper()
        size = fit_size(name, card_w - 170, 52)
        img = font(size).render(name, True, WHITE)
        tx = badge_x + 58 if i == 0 else badge_x - 58 - img.get_width()
        ty = rect.centery - img.get_height() // 2
        shadow = font(size).render(name, True, BLACK)
        surf.blit(shadow, (tx + 3, ty + 3))
        surf.blit(img, (tx, ty))
        if lead:
            _pill(surf, "EN TÊTE", 20, (rect.centerx, rect.bottom), colors[i],
                  WHITE, BLACK, pad=(14, 4))
    # badge VS
    c = (WIDTH // 2, BOARD_Y + BOARD_H // 2)
    fx.blit_glow(surf, p.accent, c, 110)
    pygame.draw.circle(surf, (12, 12, 22), c, 50)
    pygame.draw.circle(surf, p.accent, c, 50, 5)
    draw_text(surf, "VS", 40, WHITE, c)


_veil_cache = {}


def veil(surf, alpha):
    if alpha not in _veil_cache:
        v = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        v.fill((0, 0, 0, alpha))
        _veil_cache[alpha] = v
    surf.blit(_veil_cache[alpha], (0, 0))


def intro(surf, p, subtitle, f, fx_=None):
    veil(surf, 150)
    k = min(1.0, f / 10)
    glow_text(surf, "PRONO", int(150 * (0.7 + 0.3 * k)), p.accent, (WIDTH // 2, 640))
    glow_text(surf, "DU JOUR", int(110 * (0.7 + 0.3 * k)), p.accent, (WIDTH // 2, 770))
    _pill(surf, subtitle.upper(), 40, (WIDTH // 2, 900), (10, 10, 20), p.neon)
    draw_text(surf, "Simulation basée sur la forme des équipes", 30, (210, 210, 220),
              (WIDTH // 2, 990))


def countdown(surf, p, number, phase):
    """phase : 0 → 1 pendant chaque seconde du décompte."""
    veil(surf, 90)
    c = (WIDTH // 2, 860)
    r = int(150 + 60 * phase)
    pygame.draw.circle(surf, fx.scale(p.accent, 1 - phase), c, r, 8)
    glow_text(surf, str(number), int(300 - 60 * phase), p.accent, c, outline_px=6)


def banner(surf, text, color, t, y=430):
    """Bandeau de tension (« DERNIER ANNEAU ! »). t = secondes depuis l'apparition."""
    if t < 0 or t > 1.8:
        return
    slide = min(1.0, t / 0.18)
    alpha = 1.0 if t < 1.5 else 1 - (t - 1.5) / 0.3
    x = int(-WIDTH + (WIDTH + WIDTH // 2) * slide) if slide < 1 else WIDTH // 2
    size = fit_size(text, WIDTH - 220, 58)
    w, h = font(size).size(text)
    rect = (x - w // 2 - 40, y - h // 2 - 16, w + 80, h + 32)
    fx.panel(surf, rect, fx.scale(color, 0.5), int(235 * alpha), color, radius=18, border_w=4)
    draw_text(surf, text, size, WHITE, (x, y), outline=BLACK, outline_px=3)


def outro(surf, fx_, p, winner, f):
    veil(surf, 170)
    name = (fx_.home, fx_.away)[winner]
    label = team_labels(fx_)[winner]
    color = (p.team_a, p.team_b)[winner]
    pop = min(1.0, f / 9)
    ease = 1 - (1 - pop) ** 3
    card = pygame.Rect(0, 0, 860, 640)
    card.center = (WIDTH // 2, 900 + int(80 * (1 - ease)))
    fx.blit_glow(surf, color, card.center, int(520 * ease) + 1)
    fx.panel(surf, card, fx.scale(color, 0.25), 240, color, radius=40, border_w=6)
    glow_text(surf, "VICTOIRE", 96, color, (WIDTH // 2, card.top + 90))
    fx.draw_ball(surf, color, (WIDTH // 2, card.top + 270), int(95 * ease) + 5, label, int(60 * ease) + 8)
    size = fit_size(name.upper(), card.width - 80, 96)
    draw_text(surf, name.upper(), size, WHITE, (WIDTH // 2, card.top + 440), outline=BLACK, outline_px=4)
    draw_text(surf, "Notre prono pour ce match", 34, (220, 220, 230), (WIDTH // 2, card.top + 520))
    if f > 12:
        _pill(surf, "Abonne-toi pour les pronos de demain", 34, (WIDTH // 2, card.bottom + 70),
              (10, 10, 20), p.accent)


def bar(surf, rect, share, ca, cb, label_a=None, label_b=None):
    """Barre partagée A | B (share = part de A entre 0 et 1)."""
    x, y, w, h = rect
    split = int(w * share)
    fx.panel(surf, rect, (10, 10, 20), 220, None, radius=h // 2)
    pygame.draw.rect(surf, ca, (x, y, split, h), border_top_left_radius=h // 2,
                     border_bottom_left_radius=h // 2)
    pygame.draw.rect(surf, cb, (x + split, y, w - split, h), border_top_right_radius=h // 2,
                     border_bottom_right_radius=h // 2)
    pygame.draw.rect(surf, fx.lerp(ca, WHITE, 0.6), (x, y + 4, split, 6), border_radius=3)
    pygame.draw.rect(surf, fx.lerp(cb, WHITE, 0.6), (x + split, y + 4, w - split, 6), border_radius=3)
    pygame.draw.line(surf, WHITE, (x + split, y - 6), (x + split, y + h + 6), 5)
    pygame.draw.rect(surf, WHITE, rect, 3, border_radius=h // 2)
    if label_a:
        draw_text(surf, label_a, int(h * 0.62), WHITE, (x + 70, y + h // 2), outline=BLACK, outline_px=3)
    if label_b:
        draw_text(surf, label_b, int(h * 0.62), WHITE, (x + w - 70, y + h // 2), outline=BLACK, outline_px=3)
