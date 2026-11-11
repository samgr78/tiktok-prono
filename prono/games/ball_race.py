"""Jeu 1 : course de billes sur un long parcours qui défile.

Deux billes (une par équipe) dévalent un parcours néon de plusieurs écrans
de haut, assemblé au hasard à partir de sections (picots, rampes en zigzag,
entonnoir, barres tournantes, bumpers). La caméra suit la bille en tête ;
la ligne d'arrivée n'est visible qu'à la fin.
"""
import bisect
import math
import random

import pygame
import pymunk

from .. import fx
from ..hud import SAFE_LEFT, SAFE_RIGHT, team_labels
from ..video import FPS, HEIGHT, WIDTH, draw_text
from .base import Game

LEFT, RIGHT = SAFE_LEFT, SAFE_RIGHT
VIEW_TOP = 330                    # le parcours s'affiche de y=330 jusqu'en bas de l'écran
VIEW_H = HEIGHT - VIEW_TOP
BALL_R = 34
PEG_R = 12
SUBSTEPS = 4
MIN_RACE_S, MAX_RACE_S = 36.0, 50.0
CALIBRATION = (38.0, 46.0)        # durée médiane visée pour un parcours
TARGET_HEIGHT = (4300, 5000)      # hauteur du parcours en pixels (~4 écrans)
PX_PER_M = 100                    # pour afficher les écarts en mètres


class BallRace(Game):
    name = "ball_race"
    subtitle = "Qui franchira la ligne en premier ?"

    def __init__(self, fixture, palette, rng):
        super().__init__(fixture, palette, rng)
        # On génère des parcours jusqu'à en trouver un dont la durée typique
        # tombe dans la bonne fenêtre (3 courses d'essai, ~20 ms chacune).
        for _ in range(12):
            self._build_course()
            times = sorted(self.simulate(s, raw=True) for s in range(3))
            if CALIBRATION[0] <= times[1] <= CALIBRATION[1]:
                break
        self._course = None

    # ================================================================ parcours
    def _build_course(self):
        rng = self.rng
        self.segs = []       # (a, b, rayon, élasticité)
        self.pegs = []       # (x, y, rayon, élasticité, type)  type: "peg" | "bumper"
        self.spinners = []
        y = 260
        self.segs.append(((LEFT, 200), (LEFT + 330, 260), 6, 0.4))    # toboggan de départ
        self.segs.append(((RIGHT, 200), (RIGHT - 330, 260), 6, 0.4))
        builders = [self._pegs, self._zigzag, self._spinners, self._bumpers, self._funnel]
        last = None
        target = rng.uniform(*TARGET_HEIGHT)
        while y < target:
            choices = [b for b in builders if b is not last] if last else [self._pegs]
            build = rng.choice(choices)
            y = build(y + 60) + 40
            last = build
        y = self._pegs(y + 40, rows=4)
        self.finish_y = y + 140
        self.floor_y = self.finish_y + 180
        self.world_h = self.floor_y + 40
        self.segs += [((LEFT, 0), (LEFT, self.floor_y), 8, 0.5),
                      ((RIGHT, 0), (RIGHT, self.floor_y), 8, 0.5),
                      ((LEFT, self.floor_y), (RIGHT, self.floor_y), 8, 0.2)]
        self.pegs.sort(key=lambda p: p[1])
        self._peg_ys = [p[1] for p in self.pegs]

    def _pegs(self, y, rows=None):
        rng = self.rng
        rows = rows or rng.randint(6, 8)
        gap_y, gap_x = rng.uniform(88, 100), rng.uniform(105, 125)
        for r in range(rows):
            x = LEFT + 45 + (gap_x / 2 if r % 2 else 0)
            while x < RIGHT - 40:
                self.pegs.append((x + rng.uniform(-6, 6), y, PEG_R, 0.5, "peg"))
                x += gap_x
            y += gap_y
        return y

    def _zigzag(self, y):
        rng = self.rng
        n = rng.randint(3, 4)
        length = RIGHT - LEFT - rng.uniform(200, 240)
        drop = rng.uniform(120, 150)
        for i in range(n):
            if i % 2 == 0:
                a, b = (LEFT, y), (LEFT + length, y + drop)
            else:
                a, b = (RIGHT, y), (RIGHT - length, y + drop)
            self.segs.append((a, b, 7, 0.3))
            y += drop + 150
        return y

    def _spinners(self, y):
        rng = self.rng
        for row in range(2):
            for cx in (LEFT + (RIGHT - LEFT) * 0.27, LEFT + (RIGHT - LEFT) * 0.73):
                self.spinners.append({
                    "pos": (cx + rng.uniform(-25, 25), y),
                    "length": rng.uniform(200, 250),
                    "speed": rng.choice((-1, 1)) * rng.uniform(1.4, 2.4),
                    "phase": rng.uniform(0, math.pi),
                })
            self.pegs.append(((LEFT + RIGHT) / 2, y + 130, PEG_R + 4, 0.5, "peg"))
            y += 300
        return y

    def _bumpers(self, y):
        rng = self.rng
        placed = []
        h = rng.uniform(560, 680)
        for _ in range(60):
            if len(placed) >= 7:
                break
            r = rng.uniform(42, 58)
            p = (rng.uniform(LEFT + r + 40, RIGHT - r - 40), rng.uniform(y + r, y + h - r))
            if all(math.dist(p, q) > r + qr + 2.4 * BALL_R for q, qr in placed):
                placed.append((p, r))
                self.pegs.append((p[0], p[1], r, 1.05, "bumper"))
        return y + h

    def _funnel(self, y):
        rng = self.rng
        gap = BALL_R * 2 + rng.uniform(70, 90)
        cx = (LEFT + RIGHT) / 2 + rng.uniform(-80, 80)
        depth = rng.uniform(300, 360)
        self.segs.append(((LEFT, y), (cx - gap / 2, y + depth), 7, 0.3))
        self.segs.append(((RIGHT, y), (cx + gap / 2, y + depth), 7, 0.3))
        return y + depth + 80

    # ================================================================ physique
    def _make_space(self, rng):
        space = pymunk.Space()
        space.gravity = (0, 320)
        space.damping = 0.995
        st = space.static_body
        shapes = []
        for a, b, r, e in self.segs:
            s = pymunk.Segment(st, a, b, r)
            s.elasticity, s.friction = e, 0.35
            shapes.append(s)
        for x, y, r, e, _ in self.pegs:
            s = pymunk.Circle(st, r, (x, y))
            s.elasticity, s.friction = e, 0.3
            shapes.append(s)
        space.add(*shapes)
        spinners = []
        for sp in self.spinners:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = sp["pos"]
            body.angle = sp["phase"] + rng.uniform(0, math.pi)
            body.angular_velocity = sp["speed"]
            half = sp["length"] / 2
            seg = pymunk.Segment(body, (-half, 0), (half, 0), 10)
            seg.elasticity, seg.friction = 0.6, 0.5
            space.add(body, seg)
            spinners.append(body)
        balls = []
        cx = (LEFT + RIGHT) / 2
        for side in (-1, 1):
            body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, BALL_R))
            body.position = (cx + side * rng.uniform(60, 130), 120)
            body.velocity = (rng.uniform(-100, 100), 0)
            shape = pymunk.Circle(body, BALL_R)
            shape.elasticity, shape.friction = 0.55, 0.3
            space.add(body, shape)
            balls.append(body)
        return space, balls, spinners

    def simulate(self, seed, raw=False):
        """raw=True : renvoie juste la durée de course (pour calibrer le parcours)."""
        rng = random.Random(seed)
        space, balls, spinners = self._make_space(rng)
        dt = 1 / (FPS * SUBSTEPS)
        frames = []
        winner = finish = None
        leader, changes, last_change = None, [], -999
        stuck = [0, 0]
        for f in range(int(MAX_RACE_S * FPS) + FPS):
            for _ in range(SUBSTEPS):
                space.step(dt)
            # anti-blocage : une bille immobile plus d'1 s reçoit une pichenette
            for i, b in enumerate(balls):
                stuck[i] = stuck[i] + 1 if b.velocity.length < 25 else 0
                if stuck[i] > FPS and winner is None:
                    b.velocity = (rng.uniform(-260, 260), rng.uniform(-320, -180))
                    stuck[i] = 0
            ys = [b.position.y for b in balls]
            frames.append(([(b.position.x, b.position.y) for b in balls], [s.angle for s in spinners]))
            if winner is None:
                # changement de leader avec hystérésis (40 px) pour éviter le clignotement
                if leader is None:
                    leader = 0 if ys[0] >= ys[1] else 1
                elif ys[1 - leader] > ys[leader] + 40:
                    leader = 1 - leader
                    if f - last_change > 3 * FPS:
                        changes.append((f, leader))
                        last_change = f
                done = [y + BALL_R >= self.finish_y for y in ys]
                if any(done):
                    if all(done):
                        return None, None
                    winner, finish = done.index(True), f
                    if raw:
                        return f / FPS
            elif f - finish >= int(1.0 * FPS):
                break
        if raw:
            return 999.0
        if winner is None or finish < MIN_RACE_S * FPS:
            return None, None
        if len(changes) < 2:                                   # il faut du suspense
            return None, None
        if self.finish_y - frames[finish][0][1 - winner][1] > 700:
            return None, None
        labels = team_labels(self.fixture)
        colors = (self.palette.team_a, self.palette.team_b)
        banners = [(f, f"{labels[t]} PASSE DEVANT !", colors[t]) for f, t in changes
                   if f > 4 * FPS and finish - f > 3 * FPS]
        for f, (pos, _) in enumerate(frames):                  # dernière ligne droite
            if max(p[1] for p in pos) > self.finish_y - 900:
                if all(abs(f - b[0]) > 2 * FPS for b in banners):
                    banners.append((f, "DERNIÈRE LIGNE DROITE", self.palette.accent))
                break
        return winner, {"frames": frames, "end_frame": finish, "banners": banners}

    def leader(self, data, idx):
        (a, b), _ = data["frames"][idx]
        return 0 if a[1] > b[1] else 1

    # ================================================================ rendu
    def _prepare(self, data):
        p = self.palette
        self._bg = fx.background(p, random.Random(1), pattern="dots")
        # décor statique du parcours, dessiné une fois sur une grande image
        neon = pygame.Surface((WIDTH, self.world_h))
        for a, b, r, e in self.segs:
            pygame.draw.line(neon, p.neon, a, b, int(2 * r))
            for q in (a, b):
                pygame.draw.circle(neon, p.neon, q, r)
        for x, y, r, e, kind in self.pegs:
            if kind == "bumper":
                pygame.draw.circle(neon, fx.scale(p.accent, 0.35), (x, y), r)
                pygame.draw.circle(neon, p.accent, (x, y), r, 6)
                pygame.draw.circle(neon, p.accent, (x, y), r * 0.45, 4)
            else:
                pygame.draw.circle(neon, fx.lerp(p.neon, (255, 255, 255), 0.3), (x, y), r)
        # ligne d'arrivée en damier
        sq = 30
        for i, x in enumerate(range(LEFT, RIGHT, sq)):
            for j in range(2):
                c = (235, 235, 235) if (i + j) % 2 else (25, 25, 25)
                pygame.draw.rect(neon, c, (x, self.finish_y + j * sq, sq, sq))
        draw_text(neon, "ARRIVÉE", 64, (255, 255, 255), ((LEFT + RIGHT) // 2, self.finish_y + 120))
        # marqueurs de distance tous les 10 m
        for wy in range(1000, int(self.finish_y) - 300, 1000):
            left = (self.finish_y - wy) / PX_PER_M
            draw_text(neon, f"{left:.0f} m", 28, fx.scale(p.neon, 0.8), (LEFT + 60, wy))
            pygame.draw.line(neon, fx.scale(p.neon, 0.35), (LEFT + 110, wy), (RIGHT - 20, wy), 2)
        self._course = neon
        self._course.blit(fx.bake_glow(neon, 0.9), (0, 0), special_flags=fx.ADD)
        # caméra lissée qui suit la bille en tête
        cams, cam = [], 0.0
        cam_max = self.finish_y - (1380 - VIEW_TOP)
        for pos, _ in data["frames"]:
            lead_y = max(q[1] for q in pos)
            target = min(cam_max, max(0.0, lead_y - 640))
            cam += (target - cam) * 0.08
            cams.append(cam)
        self._cams = cams
        self._glow = fx.GlowLayer()

    def draw_frame(self, surf, data, idx):
        if self._course is None:
            self._prepare(data)
        p = self.palette
        colors = (p.team_a, p.team_b)
        frames = data["frames"]
        balls, angles = frames[idx]
        cam = self._cams[idx]
        to_screen = lambda x, y: (int(x), int(VIEW_TOP + y - cam))

        surf.blit(self._bg, (0, 0))
        surf.blit(self._course, (0, VIEW_TOP), area=pygame.Rect(0, int(cam), WIDTH, VIEW_H),
                  special_flags=fx.ADD)
        g = self._glow
        g.clear()
        # picots / bumpers qui s'allument au passage des billes
        for i, (bx, by) in enumerate(balls):
            lo = bisect.bisect_left(self._peg_ys, by - 90)
            hi = bisect.bisect_right(self._peg_ys, by + 90)
            for x, y, r, e, kind in self.pegs[lo:hi]:
                if math.hypot(bx - x, by - y) < BALL_R + r + 8:
                    c = to_screen(x, y)
                    pygame.draw.circle(surf, colors[i], c, int(r) + 4)
                    g.circle(c, r + 18, colors[i])
        for sp, ang in zip(self.spinners, angles):
            half = sp["length"] / 2
            dx, dy = math.cos(ang) * half, math.sin(ang) * half
            a = to_screen(sp["pos"][0] - dx, sp["pos"][1] - dy)
            b = to_screen(sp["pos"][0] + dx, sp["pos"][1] + dy)
            g.line(a, b, p.accent, 34)
            pygame.draw.line(surf, p.accent, a, b, 20)
            pygame.draw.line(surf, (255, 255, 255), a, b, 6)
            pygame.draw.circle(surf, (255, 255, 255), to_screen(*sp["pos"]), 12)
        # traînées lumineuses
        for i in range(2):
            pts = [to_screen(*frames[max(0, idx - k)][0][i]) for k in range(0, 14, 2)]
            for k in range(len(pts) - 1):
                g.line(pts[k], pts[k + 1], fx.scale(colors[i], 1 - k / len(pts)), 30 - 3 * k)
        g.apply(surf)
        labels = team_labels(self.fixture)
        for i, (x, y) in enumerate(balls):
            fx.draw_ball(surf, colors[i], to_screen(x, y), BALL_R, labels[i], 22)
        self._draw_progress(surf, balls, labels, colors, cam)

    def _draw_progress(self, surf, balls, labels, colors, cam):
        """Barre de progression verticale à gauche + flèche pour la bille hors champ."""
        x, top, bottom = 45, 380, 1440
        pygame.draw.line(surf, (25, 25, 40), (x, top), (x, bottom), 14)
        pygame.draw.line(surf, self.palette.neon, (x, top), (x, bottom), 4)
        for j in range(4):  # petit drapeau à damier
            for k in range(2):
                c = (240, 240, 240) if (j + k) % 2 else (20, 20, 20)
                pygame.draw.rect(surf, c, (x - 16 + j * 8, bottom + 8 + k * 8, 8, 8))
        for i, (bx, by) in enumerate(balls):
            t = max(0.0, min(1.0, by / self.finish_y))
            cy = int(top + (bottom - top) * t)
            fx.blit_glow(surf, colors[i], (x, cy), 30)
            pygame.draw.circle(surf, (255, 255, 255), (x, cy), 14)
            pygame.draw.circle(surf, colors[i], (x, cy), 10)
        # bille hors champ (au-dessus de l'écran) : flèche + écart en mètres
        lead = 0 if balls[0][1] > balls[1][1] else 1
        for i, (bx, by) in enumerate(balls):
            if VIEW_TOP + by - cam < VIEW_TOP + 20:
                gap = (balls[lead][1] - by) / PX_PER_M
                cx = int(max(LEFT + 90, min(RIGHT - 90, bx)))
                cy = VIEW_TOP + 40
                fx.panel(surf, (cx - 90, cy - 26, 180, 52), fx.scale(colors[i], 0.4), 230, colors[i],
                         radius=26)
                pygame.draw.polygon(surf, (255, 255, 255),
                                    [(cx - 68, cy + 8), (cx - 56, cy - 10), (cx - 44, cy + 8)])
                draw_text(surf, f"{labels[i]} -{gap:.0f} m", 26, (255, 255, 255), (cx + 14, cy))
