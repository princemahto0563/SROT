"""
Container / metadata / provenance inspection.

Every field returned here is READ from the file. If something is absent we return
None and the caller renders "Not available" — we never substitute a plausible value.
"""
from __future__ import annotations
import json, subprocess, shutil
from pathlib import Path
from typing import Any

from PIL import Image, ExifTags

def _find_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}"):
        if Path(candidate).is_file():
            return candidate
    return None


FFPROBE = _find_tool("ffprobe")
FFMPEG = _find_tool("ffmpeg")


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def probe_video(path: str | Path) -> dict[str, Any]:
    """ffprobe -> normalised dict. Returns {'available': False} if ffprobe is missing."""
    ffprobe_bin = FFPROBE or _find_tool("ffprobe")
    if not ffprobe_bin:
        return {"available": False, "reason": "ffprobe not installed"}
    rc, out, err = _run([ffprobe_bin, "-v", "error", "-print_format", "json",
                         "-show_format", "-show_streams", str(path)])
    if rc != 0:
        return {"available": False, "reason": (err or "ffprobe failed").strip()[:300]}
    try:
        raw = json.loads(out)
    except json.JSONDecodeError:
        return {"available": False, "reason": "ffprobe returned unparseable output"}

    fmt = raw.get("format", {}) or {}
    streams = raw.get("streams", []) or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)

    fps = None
    if v and v.get("avg_frame_rate") and "/" in str(v["avg_frame_rate"]):
        num, den = str(v["avg_frame_rate"]).split("/")
        try:
            fps = round(float(num) / float(den), 3) if float(den) else None
        except (ValueError, ZeroDivisionError):
            fps = None

    tags = {**(fmt.get("tags") or {}), **((v or {}).get("tags") or {})}
    encoder = tags.get("encoder") or tags.get("Encoder") or tags.get("handler_name")

    return {
        "available": True,
        "raw": raw,
        "width": int(v["width"]) if v and v.get("width") else None,
        "height": int(v["height"]) if v and v.get("height") else None,
        "duration_s": float(fmt["duration"]) if fmt.get("duration") else None,
        "fps": fps,
        "video_codec": (v or {}).get("codec_name"),
        "audio_codec": (a or {}).get("codec_name"),
        "container_format": fmt.get("format_name"),
        "encoder_tag": encoder,
        "has_audio": a is not None,
        "nb_frames": int(v["nb_frames"]) if v and str(v.get("nb_frames", "")).isdigit() else None,
        "bit_rate": int(fmt["bit_rate"]) if str(fmt.get("bit_rate", "")).isdigit() else None,
        "tags": tags,
    }


def probe_image(path: str | Path) -> dict[str, Any]:
    try:
        with Image.open(path) as im:
            info = {
                "available": True,
                "width": im.width, "height": im.height,
                "format": im.format, "mode": im.mode,
                "duration_s": None, "fps": None,
                "video_codec": None, "audio_codec": None,
                "container_format": (im.format or "").lower() or None,
                "encoder_tag": None, "has_audio": False,
            }
            # JPEG quantisation tables are a genuine forensic artefact
            qt = getattr(im, "quantization", None)
            if qt:
                info["quant_tables"] = {str(k): list(v)[:16] for k, v in qt.items()}
            return info
    except Exception as e:                                   # noqa: BLE001
        return {"available": False, "reason": f"{type(e).__name__}: {e}"[:300]}


def read_exif(path: str | Path) -> dict[str, Any]:
    """Returns {} when the file carries no EXIF — which is common and NOT suspicious."""
    try:
        with Image.open(path) as im:
            raw = im.getexif()
            if not raw:
                return {}
            out: dict[str, Any] = {}
            for tag_id, value in raw.items():
                tag = ExifTags.TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    value = value.decode("utf-8", "replace")[:200]
                out[tag] = str(value)[:200]
            return out
    except Exception:                                        # noqa: BLE001
        return {}


# ── C2PA / Content Credentials ───────────────────────────────────────────────
# Real byte-level check for a JUMBF box carrying a c2pa manifest. This detects
# presence, not validity — and we say exactly that in the UI.
_C2PA_MARKERS = (
    b"c2pa", b"jumb", b"jumd", b"c2ma", b"c2pa.assertions",
    b"c2pa.actions", b"c2pa.claim", b"c2pa.hash.data", b"urn:uuid:"
)


def detect_c2pa(path: str | Path, scan_bytes: int = 4 * 1024 * 1024) -> dict[str, Any]:
    try:
        from app.services.c2pa_trust import validate_c2pa
        trust_res = validate_c2pa(path)
        is_present = bool(trust_res.get("manifest_detected"))
        
        return {
            "present": is_present,
            "status": trust_res.get("status"),
            "markers": trust_res.get("markers_found", []),
            "manifest_type": "JUMBF C2PA Container" if is_present else None,
            "signature_valid": trust_res.get("signature_valid"),
            "trust_anchor_verified": trust_res.get("trust_anchor_verified"),
            "signer_info": trust_res.get("signer_info"),
            "trust_store_info": trust_res.get("trust_store_info"),
            "note": trust_res.get("trust_status_summary", "No C2PA manifest found."),
            "limitations": trust_res.get("forensic_boundary", "Provenance metadata presence does not prove physical scene reality."),
        }
    except Exception as e:                                   # noqa: BLE001
        return {"present": False, "markers": [], "status": "TRUST_VALIDATION_UNAVAILABLE",
                "note": f"Provenance scan unavailable: {type(e).__name__}"}


def has_audio_stream(path: str | Path) -> bool:
    info = probe_video(path)
    return bool(info.get("available") and info.get("has_audio"))
