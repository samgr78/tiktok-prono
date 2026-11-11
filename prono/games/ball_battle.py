"""Jeu 4 : combat de balles armées (style « weapon balls »).

Chaque équipe reçoit une arme au hasard, avec ses propres règles :
  ÉPÉE    équilibrée, +1 dégât à chaque coup porté
  DAGUE   courte et rapide, tourne de plus en plus vite
  LANCE   très longue, s'allonge à chaque coup
  MARTEAU lent et lourd, gros recul, ne peut pas être paré
  FAUX    vole une partie des dégâts infligés (soin)
Deux armes qui se croisent font un « clash » : elles repartent en sens inverse.
"""
import math
import random

import pygame
import pymunk

from .. import fx
from ..hud import team_labels
from ..video import FPS, HEIGHT, WIDTH, draw_text, font
from .base import Game

ARENA = pygame.Rect(130, 500, 820, 820)
BALL_R = 50
HP_MAX = 100
SUBSTEPS = 4
MIN_S, MAX_S = 36.0, 50.0
MIN_SPEED, MAX_SPEED = 380, 760
HIT_COOLDOWN = 0.4
CLASH_COOLDOWN = 0.25
ATTRACT = 160          # px/s² : attirance d'une balle vers l'autre
THICK = 1.5            # épaisseur des armes à l'affichage

WEAPONS = {
    "sword":  dict(name="ÉPÉE", reach=180, dmg=11, spin=3.8, perk="+1 DÉGÂT / COUP"),
    "dagger": dict(name="DAGUE", reach=120, dmg=9, spin=6.5, perk="+ VITESSE / COUP"),
    "spear":  dict(name="LANCE", reach=215, dmg=10, spin=3.0, perk="+ PORTÉE / COUP"),
    "hammer": dict(name="MARTEAU", reach=170, dmg=18, spin=2.4, perk="IMPARABLE"),
    "scythe": dict(name="FAUX", reach=185, dmg=12, spin=3.4, perk="VOL DE VIE"),
}

METAL, METAL_HI, OUTLINE, WOOD = (205, 212, 225), (250, 252, 255), (25, 25, 35), (150, 95, 50)


def _speed_func(body, gravity, damping, dt):
    pymunk.Body.update_velocity(body, gravity, damping, dt)
    v = body.velocity.length
    if v > MAX_SPEED:
        body.velocity = body.velocity * (MAX_SPEED / v)
    elif 0 < v < MIN_SPEED:
        body.velocity = body.velocity * (MIN_SPEED / v)


def _seg_point_dist(a, b, p):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(a[0] + t * dx - p[0], a[1] + t * dy - p[1])


def _segments_cross(p1, p2, p3, p4):
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (orient(p1, p2, p3) * orient(p1, p2, p4) < 0
            and orient(p3, p4, p1) * orient(p3, p4, p2) < 0)


def weapon_parts(kind, reach, r):
    """Formes de l'arme en coordonnées locales (u = le long de l'arme, v = travers).
    Renvoie [(points, rôle)] avec rôle parmi metal / hi / grip / team / wood."""
    def rect(u0, u1, v0, v1):
        return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    if kind in ("sword", "dagger"):
        w = 11 if kind == "sword" else 9
        g = 26 if kind == "sword" else 18
        hilt = r + (30 if kind == "sword" else 22)
        return [
            (rect(r, hilt, -6, 6), "grip"),
            (rect(hilt, hilt + 10, -g, g), "team"),
            ([(hilt + 10, -w), (reach - 28, -w), (reach, 0), (reach - 28, w), (hilt + 10, w)], "metal"),
            (rect(hilt + 18, reach - 36, -2.5, 2.5), "hi"),
        ]
    if kind == "spear":
        return [
            (rect(r, reach - 48, -5, 5), "wood"),
            (rect(reach - 56, reach - 46, -8, 8), "team"),
            ([(reach - 48, 0), (reach - 34, -15), (reach, 0), (reach - 34, 15)], "metal"),
            ([(reach - 40, 0), (reach - 30, -5), (reach - 6, 0), (reach - 30, 5)], "hi"),
        ]
    if kind == "hammer":
        return [
            (rect(r, reach - 40, -6, 6), "wood"),
            (rect(reach - 48, reach, -36, 36), "metal"),
            (rect(reach - 34, reach - 22, -36, 36), "team"),
            (rect(reach - 46, reach - 40, -32, 32), "hi"),
        ]
    if kind == "scythe":
        outer = [(reach + 2 - 80 * t ** 1.3, -6 + 110 * t) for t in [i / 10 for i in range(11)]]
        inner = [(reach - 20 - 55 * t, 10 + 86 * t) for t in [i / 10 for i in range(11)]]
        return [
            (rect(r, reach, -5, 5), "wood"),
            (outer + inner[::-1], "metal"),
            (rect(reach - 14, reach + 4, -9, 9), "team"),
        ]
    raise ValueError(kind)


class BallBattle(Game):
    name = "ball_battle"
    subtitle = "Qui survivra au combat ?"

    def __init__(self, fixture, palette, rng):
        super().__init__(fixture, palette, rng)
        # paire d'armes au hasard, gardée si un combat type dure 38-50 s
        best = None
        for _ in range(10):
            self.weapons = rng.sample(list(WEAPONS), 2)
            median = sorted(self.simulate(s, raw=True) for s in range(3))[1]
            if best is None or abs(median - 44) < abs(best[0] - 44):
                best = (median, self.weapons)
            if 38 <= median <= 50:
                break
        self.weapons = best[1]
        self._bg = None

    # ================================================================ simulation
    def _blade(self, pos, angle, reach):
        c, s = math.cos(angle), math.sin(angle)
        return ((pos[0] + c * (BALL_R + 4), pos[1] + s * (BALL_R + 4)),
                (pos[0] + c * reach, pos[1] + s * reach))

    def simulate(self, seed, raw=False):
        """raw=True : renvoie juste la durée du combat (pour calibrer)."""
        rng = random.Random(seed)
        space = pymunk.Space()
        x0, y0, x1, y1 = ARENA.left, ARENA.top, ARENA.right, ARENA.bottom
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            wall = pymunk.Segment(space.static_body, a, b, 8)
            wall.elasticity, wall.friction = 1.0, 0.0
            space.add(wall)
        balls = []
        for team in (0, 1):
            body = pymunk.Body(1, pymunk.moment_for_circle(1, 0, BALL_R))
            body.position = (x0 + ARENA.width * (0.27 if team == 0 else 0.73),
                             rng.uniform(y0 + 160, y1 - 160))
            a = rng.uniform(0, 2 * math.pi)
            body.velocity = (math.cos(a) * 500, math.sin(a) * 500)
            body.velocity_func = _speed_func
            shape = pymunk.Circle(body, BALL_R)
            shape.elasticity, shape.friction = 1.0, 0.0
            space.add(body, shape)
            balls.append(body)

        st = [dict(WEAPONS[k], kind=k) for k in self.weapons]
        for w in st:
            w["spin"] *= rng.choice((-1, 1))
        angle = [rng.uniform(0, 2 * math.pi) for _ in range(2)]
        hp = [HP_MAX, HP_MAX]
        cooldown = [0.0, 0.0]
        clash_cd = 0.0
        dt = 1 / (FPS * SUBSTEPS)
        frames = []
        winner = end = None
        hp_leader, lead_changes, danger = None, 0, [False, False]
        banners = []
        labels = team_labels(self.fixture)
        colors = (self.palette.team_a, self.palette.team_b)
        for f in range(int(MAX_S * FPS) + FPS):
            events = []
            for _ in range(SUBSTEPS):
                space.step(dt)
                if winner is not None:
                    continue
                # légère attirance : les balles se cherchent (évite les parties qui tournent en rond)
                dx = balls[1].position.x - balls[0].position.x
                dy = balls[1].position.y - balls[0].position.y
                d = math.hypot(dx, dy) or 1
                pull = ATTRACT * dt / d
                balls[0].velocity += (dx * pull, dy * pull)
                balls[1].velocity -= (dx * pull, dy * pull)
                for i in range(2):
                    angle[i] += st[i]["spin"] * dt
                    cooldown[i] = max(0.0, cooldown[i] - dt)
                clash_cd = max(0.0, clash_cd - dt)
                pos = [(b.position.x, b.position.y) for b in balls]
                blades = [self._blade(pos[i], angle[i], st[i]["reach"]) for i in range(2)]
                if clash_cd == 0 and _segments_cross(*blades[0], *blades[1]):
                    for i in range(2):          # le marteau ne se laisse pas renvoyer
                        if st[i]["kind"] != "hammer" or st[1 - i]["kind"] == "hammer":
                            st[i]["spin"] = -st[i]["spin"]
                    clash_cd = CLASH_COOLDOWN
                    mx = (blades[0][1][0] + blades[1][1][0]) / 2
                    my = (blades[0][1][1] + blades[1][1][1]) / 2
                    events.append(("clash", mx, my, rng.random()))
                    continue
                for i in range(2):
                    j = 1 - i
                    if cooldown[i] == 0 and _seg_point_dist(*blades[i], pos[j]) < BALL_R:
                        w = st[i]
                        dmg = w["dmg"] + rng.randint(0, 2)
                        hp[j] = max(0, hp[j] - dmg)
                        cooldown[i] = HIT_COOLDOWN
                        w["spin"] = -w["spin"]                       # la lame rebondit
                        kind = w["kind"]
                        if kind == "sword":
                            w["dmg"] += 1
                        elif kind == "dagger":
                            w["spin"] = math.copysign(min(14.0, abs(w["spin"]) * 1.1), w["spin"])
                        elif kind == "spear":
                            w["reach"] = min(300, w["reach"] + 7)
                        elif kind == "scythe":
                            hp[i] = min(HP_MAX, hp[i] + dmg // 3)
                        knock = MAX_SPEED * (1.6 if kind == "hammer" else 1.0)
                        dx, dy = pos[j][0] - pos[i][0], pos[j][1] - pos[i][1]
                        d = math.hypot(dx, dy) or 1
                        balls[j].velocity = (dx / d * knock, dy / d * knock)
                        events.append(("hit", pos[j][0], pos[j][1], dmg, j, rng.random()))
                        if hp[j] == 0:
                            winner, end = i, f
                            if raw:
                                return f / FPS
            frames.append(([(b.position.x, b.position.y) for b in balls], tuple(angle), tuple(hp),
                           events, tuple(w["reach"] for w in st), tuple(w["dmg"] for w in st)))
            if winner is None:
                lead = None if hp[0] == hp[1] else (0 if hp[0] > hp[1] else 1)
                if lead is not None and hp_leader is not None and lead != hp_leader:
                    lead_changes += 1
                hp_leader = lead if lead is not None else hp_leader
                for i in range(2):
                    if hp[i] <= 30 and not danger[i]:
                        danger[i] = True
                        banners.append((f, f"{labels[i]} EN DANGER !", colors[i]))
            else:
                for b in balls:
                    b.velocity = (0, 0)
                if f - end >= int(1.0 * FPS):
                    break
        if raw:
            return 999.0
        if winner is None or end < MIN_S * FPS:
            return None, None
        if hp[winner] > 50 or lead_changes < 1:      # suspense
            return None, None
        return winner, {"frames": frames, "end_frame": end, "banners": banners}

    def leader(self, data, idx):
        a, b = data["frames"][idx][2]
        return None if a == b else (0 if a > b else 1)

    # ================================================================ rendu
    def _prepare(self):
        p = self.palette
        bg = fx.background(p, random.Random(2), pattern="grid")
        neon = pygame.Surface((WIDTH, HEIGHT))
        pygame.draw.rect(neon, p.neon, ARENA.inflate(16, 16), 8, border_radius=18)
        pygame.draw.circle(neon, fx.scale(p.neon, 0.5), ARENA.center, 150, 4)
        pygame.draw.line(neon, fx.scale(p.neon, 0.5), (ARENA.left, ARENA.centery),
                         (ARENA.right, ARENA.centery), 4)
        for cx, cy in ((ARENA.left, ARENA.top), (ARENA.right, ARENA.top),
                       (ARENA.left, ARENA.bottom), (ARENA.right, ARENA.bottom)):
            pygame.draw.circle(neon, p.neon, (cx, cy), 16)
        floor = pygame.Surface(ARENA.size, pygame.SRCALPHA)
        floor.fill((0, 0, 0, 110))
        bg.blit(floor, ARENA.topleft)
        bg.blit(neon, (0, 0), special_flags=fx.ADD)
        bg.blit(fx.bake_glow(neon, 0.8), (0, 0), special_flags=fx.ADD)
        self._bg = bg
        self._glow = fx.GlowLayer()

    def _draw_weapon(self, surf, center, angle, team, kind, reach):
        c, s = math.cos(angle), math.sin(angle)
        tc = (self.palette.team_a, self.palette.team_b)[team]
        role_color = {"metal": METAL, "hi": METAL_HI, "grip": fx.scale(tc, 0.55), "team": tc, "wood": WOOD}
        for pts, role in weapon_parts(kind, reach, BALL_R):
            world = [(center[0] + u * c - v * THICK * s, center[1] + u * s + v * THICK * c) for u, v in pts]
            pygame.draw.polygon(surf, role_color[role], world)
            if role != "hi":
                pygame.draw.polygon(surf, OUTLINE, world, 3)

    def draw_frame(self, surf, data, idx):
        if self._bg is None:
            self._prepare()
        p = self.palette
        colors = (p.team_a, p.team_b)
        frames = data["frames"]
        balls, angles, hp, _, reaches, dmgs = frames[idx]
        surf.blit(self._bg, (0, 0))
        g = self._glow
        g.clear()
        dead = [h == 0 for h in hp]

        # traînées lumineuses des armes (arc parcouru par la pointe)
        for i in range(2):
            if dead[i]:
                continue
            pts = []
            for k in range(0, 6):
                j = max(0, idx - k)
                (bx, by), a = frames[j][0][i], frames[j][1][i]
                pts.append((bx + math.cos(a) * reaches[i], by + math.sin(a) * reaches[i]))
            for k in range(len(pts) - 1):
                g.line(pts[k], pts[k + 1], fx.scale(colors[i], 1 - k / 6), 34 - 5 * k)
        for i, (pos, ang) in enumerate(zip(balls, angles)):
            if not dead[i]:
                self._draw_weapon(surf, pos, ang, i, self.weapons[i], reaches[i])

        # dernier coup reçu (pour le flash blanc) + effets
        flash = [0.0, 0.0]
        shake = 0.0
        texts = []
        labels = team_labels(self.fixture)
        for back in range(int(0.7 * FPS)):
            j = idx - back
            if j < 0:
                break
            t = back / FPS
            for ev in frames[j][3]:
                if ev[0] == "clash":
                    _, x, y, sd = ev
                    fx.burst(surf, (x, y), (255, 230, 120), t, int(sd * 1e6), n=16, speed=520,
                             life=0.35, size=5, gravity=0)
                    if t < 0.15:
                        g.circle((x, y), 70, (255, 220, 120))
                else:
                    _, x, y, dmg, victim, sd = ev
                    fx.burst(surf, (x, y), colors[victim], t, int(sd * 1e6), n=22, speed=480, life=0.5)
                    if t < 0.15:
                        flash[victim] = max(flash[victim], 1 - t / 0.15)
                    if dmg >= 9 and t < 0.2:
                        shake = max(shake, (1 - t / 0.2) * 14)
                    rise = min(1.0, t / 0.6)
                    texts.append((f"-{dmg}", int(70 * (1.2 - 0.4 * rise)),
                                  (int(x), int(y - BALL_R - 40 - 90 * rise))))
        for i, (x, y) in enumerate(balls):
            c = fx.lerp(colors[i], (70, 70, 70), 0.75) if dead[i] else colors[i]
            fx.draw_ball(surf, c, (int(x), int(y)), BALL_R, labels[i], 32, flash=flash[i])
        g.apply(surf)
        for text, size, pos in texts:            # dégâts au premier plan
            draw_text(surf, text, size, (255, 70, 70), pos, outline=(0, 0, 0), outline_px=4)
        if shake:
            rng = random.Random(idx)
            surf.scroll(int(rng.uniform(-shake, shake)), int(rng.uniform(-shake, shake)))
        self._draw_hp(surf, frames, idx, hp, dmgs, reaches, colors)

    def _draw_hp(self, surf, frames, idx, hp, dmgs, reaches, colors):
        w, h, y = 430, 46, 330
        for i in range(2):
            x = 60 if i == 0 else WIDTH - 60 - w
            # « trace » blanche : PV d'il y a ~0,5 s, qui fond vers la valeur actuelle
            prev = frames[max(0, idx - FPS // 2)][2][i]
            fx.panel(surf, (x, y, w, h), (12, 12, 20), 230, None, radius=h // 2)
            for val, col in ((prev, (255, 255, 255)), (hp[i], colors[i])):
                fill = int((w - 8) * val / HP_MAX)
                if fill > 0:
                    rx = x + 4 if i == 0 else x + w - 4 - fill
                    pygame.draw.rect(surf, col, (rx, y + 4, fill, h - 8), border_radius=(h - 8) // 2)
            if hp[i] <= 30 and (idx // 6) % 2:      # clignote quand la vie est basse
                pygame.draw.rect(surf, (255, 50, 50), (x, y, w, h), 4, border_radius=h // 2)
            else:
                pygame.draw.rect(surf, (255, 255, 255), (x, y, w, h), 3, border_radius=h // 2)
            draw_text(surf, f"{hp[i]} PV", 30, (255, 255, 255), (x + w // 2, y + h // 2),
                      outline=(0, 0, 0), outline_px=3)
            wpn = WEAPONS[self.weapons[i]]
            stat = {"sword": f"DÉGÂTS {dmgs[i] + 1}", "dagger": "ULTRA RAPIDE",
                    "spear": f"PORTÉE {reaches[i]}", "hammer": "IMPARABLE",
                    "scythe": "VOL DE VIE"}[self.weapons[i]]
            text = f"{wpn['name']}  •  {stat}"
            tw = font(24).size(text)[0]
            cx = x + w // 2
            fx.panel(surf, (cx - tw // 2 - 20, y + h + 10, tw + 40, 40), fx.scale(colors[i], 0.3), 230,
                     colors[i], radius=20)
            draw_text(surf, text, 24, (255, 255, 255), (cx, y + h + 30))
