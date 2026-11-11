"""Base commune à tous les mini-jeux.

Principe : on tire d'abord le vainqueur selon la probabilité du match,
puis on cherche une graine (seed) de simulation qui produit naturellement
ce vainqueur. La physique reste 100 % réelle, seule la graine est choisie :
le « prono » colle donc aux stats du match.

Pour créer un jeu, il suffit d'implémenter :
  - simulate(seed) -> (winner, data) ou (None, None) si la partie est ratée
  - draw_frame(surf, data, idx)       dessine l'image n° idx de la partie
  - leader(data, idx)                 0 / 1 / None : qui mène à cette image
data contient "frames" (une entrée par image), "end_frame" (image où le
vainqueur est connu) et, en option, "banners" : [(image, texte, couleur)]
pour les moments de tension. L'habillage (intro, 3-2-1, ralenti final,
résultat) est géré ici, identique pour tous les jeux.
"""
import random
from abc import ABC, abstractmethod

import pygame

from .. import hud
from ..fixtures import Fixture
from ..palette import Palette
from ..video import FPS, HEIGHT, WIDTH

INTRO_S, COUNTDOWN_S, OUTRO_S = 2.5, 2.4, 3.5
SLOWMO_S = 1.2           # les dernières secondes avant la victoire passent au ralenti x0.5


class Game(ABC):
    name = "base"
    subtitle = "Qui va gagner ?"
    max_seed_tries = 300

    def __init__(self, fixture: Fixture, palette: Palette, rng: random.Random):
        self.fixture = fixture
        self.palette = palette
        self.rng = rng

    @abstractmethod
    def simulate(self, seed: int):
        ...

    @abstractmethod
    def draw_frame(self, surf, data, idx: int):
        ...

    def leader(self, data, idx: int):
        return None

    # ------------------------------------------------------------------
    def pick_winner(self) -> int:
        return 0 if self.rng.random() < self.fixture.home_win_prob else 1

    def run(self, writer) -> int:
        target = self.pick_winner()
        fallback = None
        for _ in range(self.max_seed_tries):
            winner, data = self.simulate(self.rng.randrange(1_000_000_000))
            if winner is None:
                continue
            if winner == target:
                self.render(data, winner, writer)
                return winner
            fallback = fallback or (winner, data)
        if fallback is None:
            raise RuntimeError(f"{self.name} : aucune simulation exploitable")
        # Très improbable : on garde une simulation valide même si le vainqueur diffère
        self.render(fallback[1], fallback[0], writer)
        return fallback[0]

    def render(self, data, winner, writer):
        fx_, p = self.fixture, self.palette
        surf = pygame.Surface((WIDTH, HEIGHT))
        end = data["end_frame"]
        last = len(data["frames"]) - 1
        banners = data.get("banners", [])
        clock = [0]

        def frame(idx, leader):
            self.draw_frame(surf, data, idx)
            for b_idx, text, color in banners:
                hud.banner(surf, text, color, (idx - b_idx) / FPS)
            hud.header(surf, fx_, p, leader, clock[0] / FPS)

        def out():
            writer.write(surf)
            clock[0] += 1

        for f in range(int(INTRO_S * FPS)):
            frame(0, None)
            hud.intro(surf, p, self.subtitle, f, fx_)
            out()
        n = int(COUNTDOWN_S * FPS)
        for f in range(n):
            frame(0, None)
            step = f / n * 3
            hud.countdown(surf, p, 3 - int(step), step - int(step))
            out()
        slow_from = end - int(SLOWMO_S * FPS)
        for idx in range(last + 1):
            frame(idx, self.leader(data, idx) if idx < end else winner)
            out()
            if slow_from <= idx <= end:      # ralenti : chaque image est montrée 2 fois
                out()
        for f in range(int(OUTRO_S * FPS)):
            frame(last, winner)
            hud.outro(surf, fx_, p, winner, f)
            out()
