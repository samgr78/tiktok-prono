"""Jeu 1 : course de balles.

Deux balles (une par équipe) tombent dans un parcours de picots et de
barres tournantes. La première qui franchit la ligne d'arrivée gagne.
Le parcours change à chaque vidéo.
"""
import math
import random

import pygame
import pymunk

from ..video import FPS, HEIGHT, WIDTH, draw_text, fit_size, font, short_name
from .base import Game

# Zone « sûre » : TikTok recouvre ~130 px en haut, ~380 px en bas (légende)
# et ~120 px à droite (boutons). Tout ce qui compte reste dans ce cadre.
LEFT, RIGHT = 90, WIDTH - 90
TOP, FINISH, FLOOR = 340, 1490, 1560
BALL_R = 34
PEG_R = 13
SUBSTEPS = 4                     # pas physiques par image (120 Hz)
INTRO_S, COUNTDOWN_S, OUTRO_S = 2.0, 1.5, 3.0
MIN_RACE_S, MAX_RACE_S = 10.0, 20.0


def _lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


class BallRace(Game):
    name = "ball_race"

    def __init__(self, fixture, palette, rng):
        super().__init__(fixture, palette, rng)
        self._build_layout()

    # ---------- parcours (fixe pour une vidéo, différent d'une vidéo à l'autre)
    def _build_layout(self):
        rng = self.rng
        self.pegs: list[tuple[float, float]] = []
        self.spinners: list[dict] = []
        row_gap = rng.uniform(90, 105)
        col_gap = rng.uniform(105, 130)
        y = TOP + 160
        row = 0
        # rangées de barres tournantes, jamais adjacentes (sinon elles se touchent)
        spinner_rows = set(rng.sample(range(2, 9, 2), k=rng.randint(2, 3)))
        while y < FINISH - 70:
            if row in spinner_rows:
                # une rangée avec 2 barres tournantes au lieu des picots
                for cx in (LEFT + (RIGHT - LEFT) * 0.28, LEFT + (RIGHT - LEFT) * 0.72):
                    self.spinners.append({
                        "pos": (cx + rng.uniform(-30, 30), y),
                        "length": rng.uniform(170, 230),
                        "speed": rng.choice((-1, 1)) * rng.uniform(1.2, 2.2),
                        "phase": rng.uniform(0, math.pi),
                    })
            else:
                offset = (col_gap / 2) if row % 2 else 0
                x = LEFT + 45 + offset
                while x < RIGHT - 40:
                    self.pegs.append((x + rng.uniform(-6, 6), y))
                    x += col_gap
            y += row_gap
            row += 1

    # ---------- simulation physique (sans rendu)
    def _make_space(self, seed_rng: random.Random):
        space = pymunk.Space()
        space.gravity = (0, 300)
        space.damping = 0.995
        static = space.static_body
        shapes = [
            pymunk.Segment(static, (LEFT, 0), (LEFT, FLOOR), 6),
            pymunk.Segment(static, (RIGHT, 0), (RIGHT, FLOOR), 6),
            pymunk.Segment(static, (LEFT, FLOOR), (RIGHT, FLOOR), 6),
        ]
        shapes += [pymunk.Circle(static, PEG_R, p) for p in self.pegs]
        for s in shapes:
            s.elasticity, s.friction = 0.55, 0.4
        space.add(*shapes)

        spinner_bodies = []
        for sp in self.spinners:
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            body.position = sp["pos"]
            body.angle = sp["phase"] + seed_rng.uniform(0, math.pi)
            body.angular_velocity = sp["speed"]
            half = sp["length"] / 2
            seg = pymunk.Segment(body, (-half, 0), (half, 0), 9)
            seg.elasticity, seg.friction = 0.6, 0.5
            space.add(body, seg)
            spinner_bodies.append(body)

        balls = []
        cx = (LEFT + RIGHT) / 2
        for i, side in enumerate((-1, 1)):
            body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, BALL_R))
            body.position = (cx + side * seed_rng.uniform(70, 140), TOP + 40)
            body.velocity = (seed_rng.uniform(-120, 120), seed_rng.uniform(0, 60))
            shape = pymunk.Circle(body, BALL_R)
            shape.elasticity, shape.friction = 0.6, 0.3
            space.add(body, shape)
            balls.append(body)
        return space, balls, spinner_bodies

    def simulate(self, seed: int):
        rng = random.Random(seed)
        space, balls, spinners = self._make_space(rng)
        dt = 1 / (FPS * SUBSTEPS)
        frames = []          # par image : [(x, y) balle A, (x, y) balle B, angles barres]
        winner = None
        finish_frame = None
        max_frames = int(MAX_RACE_S * FPS)
        for f in range(max_frames + FPS):
            for _ in range(SUBSTEPS):
                space.step(dt)
            frames.append((
                [(b.position.x, b.position.y) for b in balls],
                [s.angle for s in spinners],
            ))
            if winner is None:
                done = [b.position.y + BALL_R >= FINISH for b in balls]
                if any(done):
                    if all(done):
                        return None, None    # arrivée simultanée : on rejette
                    winner = done.index(True)
                    finish_frame = f
            elif f - finish_frame >= int(0.8 * FPS):
                break                        # on laisse un peu vivre l'image après l'arrivée
        if winner is None or finish_frame < MIN_RACE_S * FPS:
            return None, None
        # Suspense : on garde les courses où le perdant n'est pas trop loin derrière
        loser_y = frames[finish_frame][0][1 - winner][1]
        if FINISH - loser_y > 550:
            return None, None
        return winner, {"frames": frames, "finish_frame": finish_frame}

    # ---------- rendu
    def _static_background(self):
        p = self.palette
        bg = pygame.Surface((WIDTH, HEIGHT))
        bg.fill(p.background)
        stripe = 120
        for i, x in enumerate(range(0, WIDTH, stripe)):
            if i % 2:
                pygame.draw.rect(bg, p.background_alt, (x, 0, stripe, HEIGHT))
        pygame.draw.rect(bg, p.background, (0, 0, WIDTH, TOP - 30))  # bandeau du haut uni
        for x in (LEFT, RIGHT):
            pygame.draw.line(bg, p.obstacle, (x, TOP - 30), (x, FLOOR), 10)
        pygame.draw.line(bg, p.obstacle, (LEFT, FLOOR), (RIGHT, FLOOR), 10)
        # ligne d'arrivée en damier
        sq = 24
        for i, x in enumerate(range(LEFT, RIGHT, sq)):
            for j in range(2):
                c = (240, 240, 240) if (i + j) % 2 else (20, 20, 20)
                pygame.draw.rect(bg, c, (x, FINISH + j * sq, sq, sq))
        for px, py in self.pegs:
            pygame.draw.circle(bg, p.obstacle, (int(px), int(py)), PEG_R)
        return bg

    def _draw_header(self, surf, leader=None):
        p, fx = self.palette, self.fixture
        draw_text(surf, f"{fx.league.upper()}  •  {fx.kickoff:%H:%M}", 42, p.text, (WIDTH // 2, 165))
        names = (fx.home, fx.away)
        colors = (p.team_a, p.team_b)
        for i, cx in enumerate((WIDTH // 4 + 10, 3 * WIDTH // 4 - 10)):
            label = names[i].upper()
            size = fit_size(label, WIDTH // 2 - 150, 72)
            draw_text(surf, label, size, colors[i], (cx, 250), outline=(0, 0, 0))
            if leader == i:  # soulignage de l'équipe en tête
                w = font(size).size(label)[0] + 20
                pygame.draw.rect(surf, colors[i], (cx - w // 2, 292, w, 10), border_radius=5)
        draw_text(surf, "VS", 56, p.accent, (WIDTH // 2, 250), outline=(0, 0, 0))

    def _draw_balls(self, surf, history, idx):
        p = self.palette
        colors = (p.team_a, p.team_b)
        labels = (short_name(self.fixture.home), short_name(self.fixture.away))
        for i in range(2):
            # traînée
            for k in range(8, 0, -1):
                j = max(0, idx - k * 2)
                x, y = history[j][0][i]
                c = _lerp(colors[i], p.background, k / 9)
                pygame.draw.circle(surf, c, (int(x), int(y)), int(BALL_R * (1 - k / 12)))
        for i in range(2):
            x, y = history[idx][0][i]
            pygame.draw.circle(surf, (255, 255, 255), (int(x), int(y)), BALL_R + 5)
            pygame.draw.circle(surf, colors[i], (int(x), int(y)), BALL_R)
            draw_text(surf, labels[i], 26, (255, 255, 255), (int(x), int(y)), outline=(0, 0, 0), outline_px=2)

    def _draw_dynamic(self, surf, history, idx):
        p = self.palette
        balls, angles = history[idx]
        # picots qui s'allument au contact
        for px, py in self.pegs:
            for i, (bx, by) in enumerate(balls):
                if (bx - px) ** 2 + (by - py) ** 2 < (BALL_R + PEG_R + 6) ** 2:
                    color = p.team_a if i == 0 else p.team_b
                    pygame.draw.circle(surf, color, (int(px), int(py)), PEG_R + 5)
        for sp, ang in zip(self.spinners, angles):
            half = sp["length"] / 2
            dx, dy = math.cos(ang) * half, math.sin(ang) * half
            x, y = sp["pos"]
            pygame.draw.line(surf, p.accent, (x - dx, y - dy), (x + dx, y + dy), 18)
            pygame.draw.circle(surf, p.text, (int(x), int(y)), 10)

    def render(self, data, winner, writer):
        p, fx = self.palette, self.fixture
        frames, finish = data["frames"], data["finish_frame"]
        bg = self._static_background()
        surf = pygame.Surface((WIDTH, HEIGHT))
        start = [frames[0]]  # position de départ figée pendant l'intro

        def base_frame(history, idx, leader=None):
            surf.blit(bg, (0, 0))
            self._draw_dynamic(surf, history, idx)
            self._draw_balls(surf, history, idx)
            self._draw_header(surf, leader)

        # 1) Intro
        for _ in range(int(INTRO_S * FPS)):
            base_frame(start, 0)
            draw_text(surf, "PRONO DU JOUR", 96, p.text, (WIDTH // 2, 780), outline=(0, 0, 0), outline_px=5)
            draw_text(surf, "Qui va gagner ?", 64, p.accent, (WIDTH // 2, 890), outline=(0, 0, 0))
            writer.write(surf)
        # 2) Compte à rebours
        n = int(COUNTDOWN_S * FPS)
        for f in range(n):
            base_frame(start, 0)
            num = 3 - int(f / n * 3)
            draw_text(surf, str(num), 260, p.text, (WIDTH // 2, 850), outline=(0, 0, 0), outline_px=8)
            writer.write(surf)
        # 3) Course
        for idx in range(len(frames)):
            ys = [frames[idx][0][i][1] for i in range(2)]
            leader = 0 if ys[0] > ys[1] else 1
            base_frame(frames, idx, leader if idx < finish else winner)
            writer.write(surf)
        # 4) Résultat
        name = (fx.home, fx.away)[winner]
        color = (p.team_a, p.team_b)[winner]
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 150))
        last = len(frames) - 1
        for f in range(int(OUTRO_S * FPS)):
            base_frame(frames, last, winner)
            surf.blit(veil, (0, 0))
            pop = min(1.0, f / 8)  # petite animation d'apparition
            draw_text(surf, "VICTOIRE", int(80 + 40 * pop), (255, 255, 255), (WIDTH // 2, 720), outline=(0, 0, 0))
            size = fit_size(name.upper(), WIDTH - 120, int(150 * pop) + 20)
            draw_text(surf, name.upper(), size, color, (WIDTH // 2, 880), outline=(255, 255, 255), outline_px=5)
            draw_text(surf, "Abonne-toi pour les pronos de demain", 46, (255, 255, 255), (WIDTH // 2, 1060))
            writer.write(surf)