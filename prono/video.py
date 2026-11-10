"""Écriture MP4 via ffmpeg + petits outils de dessin communs à tous les jeux."""
import os
import subprocess

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # pas de fenêtre : rendu hors écran
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

WIDTH, HEIGHT, FPS = 1080, 1920, 30


class VideoWriter:
    """Envoie les images pygame directement dans ffmpeg (pas de fichiers PNG)."""

    def __init__(self, path: str, width=WIDTH, height=HEIGHT, fps=FPS):
        self.proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
             "-r", str(fps), "-i", "-",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", path],
            stdin=subprocess.PIPE,
        )

    def write(self, surface: pygame.Surface):
        self.proc.stdin.write(pygame.image.tobytes(surface, "RGB"))

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError("ffmpeg a échoué")


_fonts: dict[int, pygame.font.Font] = {}


def font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        if not pygame.font.get_init():
            pygame.font.init()
        path = os.environ.get("FONT_PATH")  # ex. une police .ttf grasse dans assets/
        _fonts[size] = pygame.font.Font(path, size)
    return _fonts[size]


def draw_text(surf, text, size, color, center, outline=None, outline_px=4):
    """Texte centré, avec contour optionnel pour rester lisible sur tous les fonds."""
    f = font(size)
    if outline:
        shadow = f.render(text, True, outline)
        for dx in (-outline_px, 0, outline_px):
            for dy in (-outline_px, 0, outline_px):
                if dx or dy:
                    surf.blit(shadow, shadow.get_rect(center=(center[0] + dx, center[1] + dy)))
    img = f.render(text, True, color)
    surf.blit(img, img.get_rect(center=center))


def fit_size(text: str, max_width: int, size: int) -> int:
    """Réduit la taille de police jusqu'à ce que le texte tienne en largeur."""
    while size > 20 and font(size).size(text)[0] > max_width:
        size -= 4
    return size


def short_name(name: str) -> str:
    """'Paris SG' -> 'PAR' (affiché dans la balle)."""
    letters = [c for c in name.upper() if c.isalpha()]
    return "".join(letters[:3])