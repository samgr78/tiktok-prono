"""Jeu 3 : guerre de territoire (« Pong Wars »).

Le terrain est coupé en deux couleurs. Chaque équipe a 3 balles qui se
déplacent dans leur camp et capturent les cases adverses qu'elles touchent
(en rebondissant, ou parfois en perçant plus loin). À la fin du chrono,
l'équipe qui possède le plus de cases gagne.
"""
import math
import random

import pygame

from .. import fx, hud
from ..hud import SAFE_LEFT, SAFE_RIGHT, team_labels
from ..video import FPS, WIDTH, draw_text, font
from .base import Game

CELL = 45
COLS = (SAFE_RIGHT - SAFE_LEFT) // CELL           # 20
ROWS = 23
X0, Y0 = SAFE_LEFT, 405
GRID = pygame.Rect(X0, Y0, COLS * CELL, ROWS * CELL)
BALL_R = 14
SPEED = 1000                                      # px/s
BALLS_PER_TEAM = 3
PIERCE = 0.6                                      # chance de traverser une case au lieu de rebondir
SUBSTEPS = 6
DURATION_S = 42.0
FINAL_S = 10                                      # compte à rebours final


class ColorWar(Game):
    name = "color_war"
    subtitle = "Qui prendra le plus de terrain ?"

    def __init__(self, fixture, palette, rng):
        super().__init__(fixture, palette, rng)
        self._grid_surf = None
        self._drawn_idx = -1

    def simulate(self, seed):
        rng = random.Random(seed)
        grid = [[0 if c < COLS // 2 else 1 for c in range(COLS)] for _ in range(ROWS)]
        w, h = COLS * CELL, ROWS * CELL
        balls, teams = [], []
        for team in (0, 1):
            for _ in range(BALLS_PER_TEAM):
                x = rng.uniform(w * 0.1, w * 0.4) + (w / 2 if team else 0)
                a = rng.uniform(0, 2 * math.pi)
                balls.append([x, rng.uniform(h * 0.1, h * 0.9), math.cos(a) * SPEED, math.sin(a) * SPEED])
                teams.append(team)
        dt = 1 / (FPS * SUBSTEPS)
        count = [sum(row.count(0) for row in grid), sum(row.count(1) for row in grid)]
        frames = []
        changes, last_leader, last_change = [], None, -999
        for f in range(int(DURATION_S * FPS)):
            flips = []
            for _ in range(SUBSTEPS):
                for team, b in zip(teams, balls):
                    for k in range(8):            # 8 points autour de la balle
                        ang = k * math.pi / 4
                        px = b[0] + math.cos(ang) * BALL_R
                        py = b[1] + math.sin(ang) * BALL_R
                        c, r = int(px // CELL), int(py // CELL)
                        if 0 <= c < COLS and 0 <= r < ROWS and grid[r][c] != team:
                            grid[r][c] = team
                            count[team] += 1
                            count[1 - team] -= 1
                            flips.append((r, c, team))
                            if rng.random() < PIERCE:
                                continue          # la balle perce et s'enfonce chez l'adversaire
                            if abs(math.cos(ang)) > abs(math.sin(ang)):
                                b[2] = -b[2]
                            else:
                                b[3] = -b[3]
                            rot = rng.uniform(-0.08, 0.08)   # évite les boucles infinies
                            vx, vy = b[2], b[3]
                            b[2] = vx * math.cos(rot) - vy * math.sin(rot)
                            b[3] = vx * math.sin(rot) + vy * math.cos(rot)
                    if not BALL_R <= b[0] + b[2] * dt <= w - BALL_R:
                        b[2] = -b[2]
                    if not BALL_R <= b[1] + b[3] * dt <= h - BALL_R:
                        b[3] = -b[3]
                    b[0] += b[2] * dt
                    b[1] += b[3] * dt
            leader = 0 if count[0] > count[1] else 1 if count[1] > count[0] else last_leader
            if leader != last_leader and last_leader is not None and f - last_change > 2 * FPS:
                changes.append((f, leader))
                last_change = f
            last_leader = leader
            frames.append(([(X0 + b[0], Y0 + b[1], t) for b, t in zip(balls, teams)], tuple(count), flips))
        if count[0] == count[1]:
            return None, None
        winner = 0 if count[0] > count[1] else 1
        total = COLS * ROWS
        late = [c for c in changes if c[0] > (DURATION_S - 15) * FPS]
        # suspense : écart final serré, plusieurs retournements dont un dans les 15 dernières secondes
        if abs(count[0] - count[1]) > total * 0.2 or len(changes) < 3 or not late:
            return None, None
        labels = team_labels(self.fixture)
        colors = (self.palette.team_a, self.palette.team_b)
        final = int((DURATION_S - FINAL_S) * FPS)
        banners = [(final, f"{FINAL_S} SECONDES !", self.palette.accent)]
        banners += [(f, f"{labels[t]} REPREND LA TÊTE !", colors[t]) for f, t in changes
                    if f > 3 * FPS and all(abs(f - b[0]) > 2 * FPS for b in banners)]
        return winner, {"frames": frames, "end_frame": len(frames) - 1, "banners": banners}

    def leader(self, data, idx):
        a, b = data["frames"][idx][1]
        return None if a == b else (0 if a > b else 1)

    # ================================================================ rendu
    def _cell(self, surf, r, c, color):
        x, y = c * CELL, r * CELL
        pygame.draw.rect(surf, fx.scale(color, 0.55), (x, y, CELL, CELL))
        pygame.draw.rect(surf, fx.scale(color, 0.85), (x + 3, y + 3, CELL - 6, CELL - 6), border_radius=6)
        pygame.draw.rect(surf, fx.lerp(color, (255, 255, 255), 0.35), (x + 6, y + 6, CELL - 12, 6), border_radius=3)

    def draw_frame(self, surf, data, idx):
        p = self.palette
        colors = (p.team_a, p.team_b)
        frames = data["frames"]
        if self._grid_surf is None or idx < self._drawn_idx:
            bg = fx.background(p, random.Random(4), pattern="dots")
            neon = pygame.Surface(surf.get_size())
            pygame.draw.rect(neon, p.neon, GRID.inflate(20, 20), 6, border_radius=14)
            bg.blit(neon, (0, 0), special_flags=fx.ADD)
            bg.blit(fx.bake_glow(neon), (0, 0), special_flags=fx.ADD)
            self._bg = bg
            self._grid_surf = pygame.Surface(GRID.size)
            for r in range(ROWS):
                for c in range(COLS):
                    self._cell(self._grid_surf, r, c, colors[0 if c < COLS // 2 else 1])
            self._last_flip = {}
            self._drawn_idx = -1
            self._glow = fx.GlowLayer()
        for j in range(self._drawn_idx + 1, idx + 1):
            for r, c, team in frames[j][2]:
                self._cell(self._grid_surf, r, c, colors[team])
                self._last_flip[(r, c)] = (j, team)
        self._drawn_idx = idx

        surf.blit(self._bg, (0, 0))
        surf.blit(self._grid_surf, GRID.topleft)
        # cases fraîchement capturées : flash blanc qui s'estompe
        for (r, c), (j, team) in list(self._last_flip.items()):
            age = idx - j
            if age > 10:
                del self._last_flip[(r, c)]
                continue
            k = 1 - age / 10
            pygame.draw.rect(surf, fx.lerp(colors[team], (255, 255, 255), 0.8 * k),
                             (X0 + c * CELL + 3, Y0 + r * CELL + 3, CELL - 6, CELL - 6), border_radius=6)
        balls, count, _ = frames[idx]
        g = self._glow
        g.clear()
        for x, y, team in balls:
            g.circle((x, y), 40, colors[team])
        g.apply(surf)
        for x, y, team in balls:
            pygame.draw.circle(surf, (10, 10, 18), (int(x), int(y)), BALL_R + 8)
            fx.draw_ball(surf, colors[team], (int(x), int(y)), BALL_R)

        # compte à rebours final : gros chiffre translucide au centre
        remaining = max(0.0, DURATION_S - idx / FPS)
        if remaining <= FINAL_S and idx < data["end_frame"]:
            sec = math.ceil(remaining)
            phase = sec - remaining
            size = int(420 - 120 * phase)
            img = font(size).render(str(sec), True, (255, 255, 255))
            img.set_alpha(int(170 * (1 - phase * 0.6)))
            surf.blit(img, img.get_rect(center=GRID.center))
        # barre de domination + chrono
        total = COLS * ROWS
        share = count[0] / total
        hud.bar(surf, (60, 330, WIDTH - 120, 52), share, colors[0], colors[1],
                f"{share:.0%}", f"{1 - share:.0%}")
        urgent = remaining <= FINAL_S
        tc = (255, 70, 70) if urgent and (idx // 8) % 2 else (255, 255, 255)
        label = f"{remaining:0.1f}s"
        tw = font(44).size(label)[0]
        fx.panel(surf, (WIDTH // 2 - tw // 2 - 30, GRID.bottom + 22, tw + 60, 62), (10, 10, 20), 230,
                 (255, 70, 70) if urgent else p.neon, radius=31)
        draw_text(surf, label, 44, tc, (WIDTH // 2, GRID.bottom + 53))
