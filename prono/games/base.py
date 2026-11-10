"""Base commune à tous les mini-jeux.

Principe : on tire d'abord le vainqueur selon la probabilité du match,
puis on cherche une graine (seed) de simulation physique qui produit
naturellement ce vainqueur. La physique reste 100 % réelle, seule la
graine est choisie : le « prono » colle donc aux stats du match.
"""
import random
from abc import ABC, abstractmethod

from ..fixtures import Fixture
from ..palette import Palette


class Game(ABC):
    name = "base"
    max_seed_tries = 200

    def __init__(self, fixture: Fixture, palette: Palette, rng: random.Random):
        self.fixture = fixture
        self.palette = palette
        self.rng = rng

    @abstractmethod
    def simulate(self, seed: int):
        """Simule sans rendu. Retourne (winner, data) avec winner = 0 (domicile) ou 1,
        ou (None, data) si la simulation n'est pas exploitable (trop longue, bloquée)."""

    @abstractmethod
    def render(self, data, winner: int, writer):
        """Dessine toutes les images de la vidéo dans writer."""

    def pick_winner(self) -> int:
        return 0 if self.rng.random() < self.fixture.home_win_prob else 1

    def run(self, writer) -> int:
        target = self.pick_winner()
        fallback = None
        for _ in range(self.max_seed_tries):
            seed = self.rng.randrange(1_000_000_000)
            winner, data = self.simulate(seed)
            if winner is None:
                continue
            if winner == target:
                self.render(data, winner, writer)
                return winner
            fallback = fallback or (winner, data)
        if fallback is None:
            raise RuntimeError("Aucune simulation exploitable")
        # Très improbable : on garde une simulation valide même si le vainqueur diffère
        self.render(fallback[1], fallback[0], writer)
        return fallback[0]