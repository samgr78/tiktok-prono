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
_font_path: str | None = None

# Polices grasses essayées dans l'ordre si FONT_PATH n'est pas défini
# et qu'il n'y a pas de .ttf dans assets/fonts/
_SYSTEM_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Black.ttf",   # macOS
    "/Library/Fonts/Arial Black.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux / GitHub Actions
]


def _usable(path: str) -> bool:
    try:
        pygame.font.Font(path, 20).render("Aé", True, (255, 255, 255))
        return True
    except Exception:
        return False


def _resolve_font() -> str | None:
    candidates = [os.environ.get("FONT_PATH", "")]
    assets = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
    if os.path.isdir(assets):
        candidates += [os.path.join(assets, n) for n in sorted(os.listdir(assets))
                       if n.lower().endswith((".ttf", ".otf"))]
    candidates += _SYSTEM_FONTS
    return next((p for p in candidates if p and os.path.exists(p) and _usable(p)), None)


_resolved = False


def font(size: int) -> pygame.font.Font:
    global _font_path, _resolved
    if size not in _fonts:
        if not pygame.font.get_init():
            pygame.font.init()
        if not _resolved:
            _font_path, _resolved = _resolve_font(), True
        _fonts[size] = pygame.font.Font(_font_path, size)
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
