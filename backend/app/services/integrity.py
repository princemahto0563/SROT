"""Evidence integrity: hashing, safe filenames, file typing. Nothing here guesses."""
from __future__ import annotations
import hashlib, mimetypes, re, unicodedata
from pathlib import Path

MAX_UPLOAD_BYTES = 300 * 1024 * 1024      # 300 MB ceiling
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
ALLOWED_EXT = IMAGE_EXT | VIDEO_EXT | AUDIO_EXT


def sanitize_filename(name: str) -> str:
    """Strip path components and unsafe characters — prevents traversal."""
    name = unicodedata.normalize("NFKD", name or "")
    name = Path(name).name                      # drop any directory part
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "evidence"
    return name[:120]


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def media_kind_for(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    return "other"


def guess_mime(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def is_allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT
