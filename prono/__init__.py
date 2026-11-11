import os

# Doit être réglé avant tout import de pygame (rendu sans fenêtre, sans message d'accueil)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
