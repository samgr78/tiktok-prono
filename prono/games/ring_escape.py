"""Jeu 2 : évasion des anneaux (« Will the ball escape? »).

Les deux balles partent du centre de 9 anneaux qui tournent, chacun percé
d'une ouverture. Quand une balle franchit un anneau en premier, il se brise :
le chemin s'ouvre aussi pour l'adversaire, d'où des retours fréquents.
La première balle qui sort du dernier anneau gagne.
"""
import math
import random

import pygame
import pymunk

from .. import fx
from ..hud import SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT, SAFE_TOP, team_labels
from ..video import FPS, WIDTH, draw_text
from .base import Game

CX = WIDTH // 2
CY = (SAFE_TOP + SAFE_BOTTOM) // 2 + 50
N_RINGS = 9
BALL_R = 19
RING_W = 8
SUBSTEPS = 4
MIN_S, MAX_S = 36.0, 50.0
MIN_SPEED, MAX_SPEED = 430, 900


def _clamp_speed(body, gravity, damping, dt):
    pymunk.Body.update_velocity(body, gravity, damping, dt)
    v = body.velocity.length
    if v > MAX_SPEED:
        body.velocity = body.velocity * (MAX_SPEED / v)
    elif 0 < v < MIN_SPEED:
        body.velocity = body.velocity * (MIN_SPEED / v)


class RingEscape(Game):
    name = "ring_escape"
    subtitle = "Qui s'échappe en premier ?"

    def __init__(self, fixture, palette, rng):
        super().__init__(fixture, palette, rng)
        # ouverture plus ou moins large selon la calibration (durée visée ~42 s)
        self._layout_seed = rng.random()
        best = None
        for gap_px in (185, 170, 200, 155, 215):
            self._layout(gap_px)
            median = sorted(self.simulate(s, raw=True) for s in range(3))[1]
            if best is None or abs(median - 42) < abs(best[0] - 42):
                best = (median, gap_px)
            if 38 <= median <= 47:
                break
        self._layout(best[1])
        self._bg = None

    def _layout(self, gap_px):
        rng = random.Random(self._layout_seed)
        r_min, r_max = 95, (SAFE_RIGHT - SAFE_LEFT) // 2 - 12
        self.rings = []
        for i in range(N_RINGS):
            r = r_min + (r_max - r_min) * i / (N_RINGS - 1)
            self.rings.append({
                "r": r,
                "gap": gap_px * rng.uniform(0.9, 1.1) / r,
                "speed": (1 if i % 2 else -1) * rng.uniform(0.8, 1.6),
                "phase": rng.uniform(0, 2 * math.pi),
            })

    def _make_space(self, rng):
        space = pymunk.Space()
        space.gravity = (0, 420)
        ring_parts = []
        for ring in self.rings:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = (CX, CY)
            body.angle = ring["phase"] + rng.uniform(-0.4, 0.4)
            body.angular_velocity = ring["speed"]
            r, gap = ring["r"], ring["gap"]
            steps = max(18, int(r / 14))
            arc = 2 * math.pi - gap
            pts = [(r * math.cos(gap / 2 + arc * k / steps), r * math.sin(gap / 2 + arc * k / steps))
                   for k in range(steps + 1)]
            segs = [pymunk.Segment(body, a, b, RING_W / 2) for a, b in zip(pts, pts[1:])]
            for s in segs:
                s.elasticity, s.friction = 1.0, 0.0
            space.add(body, *segs)
            ring_parts.append((body, segs))
        balls = []
        for side in (-1, 1):
            body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, BALL_R))
            body.position = (CX + side * 30, CY - 15)
            body.velocity = (rng.uniform(-400, 400), rng.uniform(-300, 0))
            body.velocity_func = _clamp_speed
            shape = pymunk.Circle(body, BALL_R)
            shape.elasticity, shape.friction = 1.0, 0.0
            space.add(body, shape)
            balls.append(body)
        return space, balls, ring_parts

    def simulate(self, seed, raw=False):
        """raw=True : renvoie juste la durée de la partie (pour calibrer)."""
        rng = random.Random(seed)
        space, balls, rings = self._make_space(rng)
        dt = 1 / (FPS * SUBSTEPS)
        radii = [r["r"] for r in self.rings]
        level = [0, 0]                    # anneaux franchis par chaque balle
        broken = [None] * N_RINGS          # (image, équipe) quand l'anneau se brise
        frames, winner, end = [], None, None
        lead, changes, last_change, banners = None, [], -999, []
        labels = team_labels(self.fixture)
        colors = (self.palette.team_a, self.palette.team_b)
        for f in range(int(MAX_S * FPS) + FPS):
            for _ in range(SUBSTEPS):
                space.step(dt)
            for i, b in enumerate(balls):
                d = math.hypot(b.position.x - CX, b.position.y - CY)
                while level[i] < N_RINGS and d > radii[level[i]] + BALL_R:
                    k = level[i]
                    if broken[k] is None:      # premier passage : l'anneau se brise
                        broken[k] = (f, i)
                        space.remove(rings[k][0], *rings[k][1])
                        if k == N_RINGS - 2 and not raw:
                            banners.append((f, "DERNIER ANNEAU !", self.palette.accent))
                    level[i] += 1
            frames.append(([(b.position.x, b.position.y) for b in balls],
                           [body.angle for body, _ in rings], tuple(level)))
            if winner is None:
                now = 0 if level[0] > level[1] else 1 if level[1] > level[0] else lead
                if now is not None and lead is not None and now != lead and f - last_change > 3 * FPS:
                    changes.append((f, now))
                    last_change = f
                lead = now
                if max(level) == N_RINGS:
                    if level[0] == level[1]:
                        return (999.0 if raw else (None, None))
                    winner, end = (0 if level[0] > level[1] else 1), f
                    if raw:
                        return f / FPS
                    for b in balls:
                        b.velocity = (0, 0)
                    space.gravity = (0, 0)
            elif f - end >= int(1.0 * FPS):
                break
        if raw:
            return 999.0
        if winner is None or end < MIN_S * FPS or len(changes) < 2:
            return None, None
        if level[1 - winner] < N_RINGS - 3:          # le perdant n'est pas largué
            return None, None
        banners += [(f, f"{labels[t]} PASSE DEVANT !", colors[t]) for f, t in changes
                    if all(abs(f - b[0]) > 2 * FPS for b in banners) and end - f > 2 * FPS]
        return winner, {"frames": frames, "end_frame": end, "broken": broken, "banners": banners}

    def leader(self, data, idx):
        balls, _, level = data["frames"][idx]
        if level[0] != level[1]:
            return 0 if level[0] > level[1] else 1
        d = [math.hypot(x - CX, y - CY) for x, y in balls]
        return 0 if d[0] > d[1] else 1

    # ================================================================ rendu
    def draw_frame(self, surf, data, idx):
        p = self.palette
        if self._bg is None:
            self._bg = fx.background(p, random.Random(3), pattern="dots")
            self._glow = fx.GlowLayer()
            plate = pygame.Surface((WIDTH, WIDTH), pygame.SRCALPHA)
            pygame.draw.circle(plate, (0, 0, 0, 120), (WIDTH // 2, WIDTH // 2), int(self.rings[-1]["r"]) + 30)
            self._bg.blit(plate, (CX - WIDTH // 2, CY - WIDTH // 2))
        colors = (p.team_a, p.team_b)
        frames, broken = data["frames"], data["broken"]
        balls, angles, level = frames[idx]
        surf.blit(self._bg, (0, 0))
        g = self._glow
        g.clear()
        for k, (ring, ang) in enumerate(zip(self.rings, angles)):
            r, gap = ring["r"], ring["gap"]
            if broken[k] is not None and broken[k][0] <= idx:
                fx.shards(surf, (CX, CY), r, colors[broken[k][1]], (idx - broken[k][0]) / FPS, k * 97 + 5)
                continue
            col = fx.lerp(p.neon, p.accent, k / (N_RINGS - 1))
            start, stop = -(ang + 2 * math.pi - gap / 2), -(ang + gap / 2)
            g.arc((CX, CY), r, start, stop, col, RING_W + 14)
            rect = pygame.Rect(0, 0, 2 * r, 2 * r)
            rect.center = (CX, CY)
            pygame.draw.arc(surf, col, rect, start, stop, RING_W + 2)
            pygame.draw.arc(surf, fx.lerp(col, (255, 255, 255), 0.6), rect.inflate(-4, -4), start, stop, 3)
        for i in range(2):
            pts = [frames[max(0, idx - k)][0][i] for k in range(0, 12, 2)]
            for k in range(len(pts) - 1):
                g.line(pts[k], pts[k + 1], fx.scale(colors[i], 1 - k / len(pts)), 24 - 3 * k)
        g.apply(surf)
        labels = team_labels(self.fixture)
        for i, (x, y) in enumerate(balls):
            fx.draw_ball(surf, colors[i], (int(x), int(y)), BALL_R, labels[i], 15)
        self._draw_levels(surf, level, colors, labels)

    def _draw_levels(self, surf, level, colors, labels):
        """Sous le tableau de score : anneaux franchis par chaque équipe."""
        w, h, y = 430, 64, 330
        for i in range(2):
            x = 60 if i == 0 else WIDTH - 60 - w
            fx.panel(surf, (x, y, w, h), fx.scale(colors[i], 0.22), 230, fx.scale(colors[i], 0.8), radius=20)
            draw_text(surf, f"{level[i]}/{N_RINGS}", 34, (255, 255, 255), (x + 62, y + h // 2))
            for k in range(N_RINGS):
                cx = x + 130 + k * 32
                on = k < level[i]
                if on:
                    fx.blit_glow(surf, colors[i], (cx, y + h // 2), 22)
                pygame.draw.circle(surf, colors[i] if on else (40, 40, 55), (cx, y + h // 2), 11)
                pygame.draw.circle(surf, (255, 255, 255), (cx, y + h // 2), 11, 2)
