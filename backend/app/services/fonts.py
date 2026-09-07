"""
Cross-platform font resolution for FFmpeg's drawtext filter.

The demonstration media is rendered locally with FFmpeg, which needs an absolute
path to a TrueType file. That path differs on every platform, so it is discovered
at run time rather than hardcoded — a Linux DejaVu path silently breaks the whole
seed step on macOS.
"""
from __future__ import annotations
import glob
import shutil
import subprocess
from pathlib import Path

# Ordered best-first. Bold faces first: the demonstration overlays must stay legible
# to OCR after the clip is downscaled and re-encoded.
CANDIDATES = [
    # Linux (Debian/Ubuntu, Fedora, Arch)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Supplemental/Tahoma Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Homebrew font casks
    "/opt/homebrew/share/fonts/DejaVuSans-Bold.ttf",
    "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
]

GLOB_FALLBACKS = [
    "/usr/share/fonts/**/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/**/*Sans*Bold.ttf",
    "/System/Library/Fonts/Supplemental/*Bold.ttf",
    "/System/Library/Fonts/*.ttf",
    "/Library/Fonts/*.ttf",
    str(Path.home() / "Library/Fonts/*.ttf"),
]


class FontNotFound(RuntimeError):
    """Raised with actionable installation guidance rather than a bare failure."""


def _fc_match() -> str | None:
    """Ask fontconfig, when it is installed, for a concrete file path."""
    fc = shutil.which("fc-match")
    if not fc:
        return None
    try:
        out = subprocess.run([fc, "-f", "%{file}", "sans-serif:bold"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        return None
    return out if out and Path(out).is_file() else None


def find_font() -> str:
    """
    Absolute path to a usable TrueType file.

    Raises FontNotFound with an install command rather than letting FFmpeg fail
    with an opaque filter error halfway through generating the demo corpus.
    """
    for c in CANDIDATES:
        if Path(c).is_file():
            return c
    hit = _fc_match()
    if hit:
        return hit
    for pattern in GLOB_FALLBACKS:
        for m in sorted(glob.glob(pattern, recursive=True)):
            if Path(m).is_file():
                return m
    raise FontNotFound(
        "No TrueType font found for rendering the demonstration media.\n"
        "  macOS:         the system fonts in /System/Library/Fonts/Supplemental are\n"
        "                 normally present; if not, install one with\n"
        "                     brew install --cask font-dejavu\n"
        "  Debian/Ubuntu: sudo apt-get install -y fonts-dejavu-core\n"
        "  Fedora:        sudo dnf install -y dejavu-sans-fonts\n"
        "Or set SROT_FONT=/absolute/path/to/font.ttf"
    )


def escape_for_filter(path: str) -> str:
    """
    Escape a font path for use inside an FFmpeg filtergraph.

    macOS paths contain spaces ('Arial Bold.ttf'); Windows-style paths and any path
    containing ':' or '\\' would otherwise terminate the option early.
    """
    return path.replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")
