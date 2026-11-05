"""Намира шрифт по име: YTF_FONT_DIRS, fonts/ до този файл, системните папки и кеша на CapCut."""
import os
import sys
from pathlib import Path

HOME = Path.home()


def font_dirs():
    dirs = [Path(p).expanduser() for p in os.environ.get("YTF_FONT_DIRS", "").split(":") if p]
    dirs += [Path(__file__).resolve().parent / "fonts", HOME / ".local/share/fonts", HOME / ".fonts",
             Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), HOME / "Library/Fonts",
             Path("/Library/Fonts"), Path("/System/Library/Fonts/Supplemental"), Path("C:/Windows/Fonts")]
    return [d for d in dirs if d.exists()]


def find_font(*names, required=True):
    for d in font_dirs():
        for n in names:
            if (d / n).exists():
                return str(d / n)
    for d in font_dirs():
        for n in names:
            hit = next(d.rglob(n), None)
            if hit:
                return str(hit)
    if required:
        sys.exit(f"Не намирам шрифт {' / '.join(names)} (пусни setup.sh или задай YTF_FONT_DIRS).")
    return None


def title_font():
    """Arial Black, ако го има; иначе Montserrat Black (също с кирилица)."""
    return find_font("Arial Black.ttf", "ariblk.ttf", required=False) or find_font("Montserrat-Black.ttf")
