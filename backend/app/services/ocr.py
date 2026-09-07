"""
Multilingual OCR + media-derived entity extraction.

Every entity carries the frame, bounding box, OCR confidence and language it was
read from. If OCR finds nothing we say so — we never synthesise an identifier.
"""
from __future__ import annotations
import re, shutil, subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract

def _find_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for candidate in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}"):
        if Path(candidate).is_file():
            return candidate
    return None


TESSERACT = _find_tool("tesseract")
if TESSERACT:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT


def available_languages() -> list[str]:
    tess_bin = TESSERACT or _find_tool("tesseract")
    if not tess_bin:
        return []
    try:
        out = subprocess.run([tess_bin, "--list-langs"], capture_output=True,
                             text=True, timeout=20).stdout
        return [l.strip() for l in out.splitlines()[1:] if l.strip() and l.strip() != "osd"]
    except Exception:  # noqa: BLE001
        return []


def lang_string() -> str:
    have = set(available_languages())
    wanted = [l for l in ("eng", "hin", "pan") if l in have]
    return "+".join(wanted) if wanted else "eng"


SCRIPT_OF = {"eng": "Latin", "hin": "Devanagari", "pan": "Gurmukhi"}

# ── entity patterns ──────────────────────────────────────────────────────────
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("UPI",     re.compile(r"\b[a-zA-Z0-9._-]{2,}@(?:upi|ybl|okaxis|oksbi|okhdfcbank|paytm|ibl|axl|apl)\b", re.I)),
    ("WALLET",  re.compile(r"\b(?:0x[a-fA-F0-9]{6,40}|bc1[a-z0-9]{8,42}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")),
    ("URL",     re.compile(r"\b(?:https?://)?(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?\b")),
    ("HANDLE",  re.compile(r"(?<![\w@])@[A-Za-z0-9_.]{3,30}\b")),
    ("PHONE",   re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}\b")),
    ("AMOUNT",  re.compile(r"(?:₹|Rs\.?|INR)\s?\d[\d,]{2,}(?:\.\d{1,2})?", re.I)),
    ("TIME",    re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?:\s?(?:AM|PM|am|pm))?\b")),
    ("DATE",    re.compile(r"\b\d{1,2}[/-][A-Za-z]{3,9}[/-]\d{2,4}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")),
]
_URL_NOISE = re.compile(r"^(?:\d+\.\d+|[a-z]\.[a-z])$", re.I)


MAX_OCR_SIDE = 1500          # keeps Tesseract fast enough for an interactive demo


def _scale_for(img: np.ndarray, want: float = 2.2) -> float:
    """Upscale small text, but never exceed MAX_OCR_SIDE on the longest edge."""
    longest = max(img.shape[:2])
    return max(1.0, min(want, MAX_OCR_SIDE / longest))


def _variants(img: np.ndarray, upscale: float = 2.2, deep: bool = False) -> list[tuple[str, np.ndarray]]:
    """Several preprocessing candidates — the best-scoring one is kept per language."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    up = cv2.resize(g, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    out = [("gray", up)]
    try:
        out.append(("otsu", cv2.threshold(up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]))
        if deep:
            out.append(("otsu_inv", cv2.threshold(up, 0, 255,
                                                  cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]))
    except cv2.error:                                    # pragma: no cover
        pass
    return out


def _pass(prep: np.ndarray, lang: str, psm: int, scale: float,
          ox: int, oy: int, region: str, min_conf: float) -> list[dict]:
    try:
        data = pytesseract.image_to_data(prep, lang=lang, output_type=pytesseract.Output.DICT,
                                         config=f"--oem 3 --psm {psm}")
    except Exception:                                    # noqa: BLE001
        return []
    words = []
    for i, txt in enumerate(data.get("text", [])):
        t = (txt or "").strip()
        if len(t) < 2:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, KeyError, IndexError):
            continue
        if conf < min_conf:
            continue
        words.append({
            "text": t, "conf": round(conf, 1), "lang": lang,
            "bbox": [int(data["left"][i] / scale) + ox, int(data["top"][i] / scale) + oy,
                     int(data["width"][i] / scale), int(data["height"][i] / scale)],
            "region": region,
        })
    return words


def _yield(words: list[dict]) -> float:
    """Ranking score for a pass: total confidence of reasonably long words."""
    return sum(w["conf"] * min(len(w["text"]), 12) for w in words)


def ocr_frame(path: str | Path, region: str = "full-frame",
              crop: tuple[int, int, int, int] | None = None,
              min_conf: float = 40.0, languages: list[str] | None = None,
              deep: bool = False) -> dict[str, Any]:
    """
    Run Tesseract over a frame (or a crop). Each language is run as its OWN pass —
    combining scripts in a single pass measurably corrupts Latin output — and the
    best-scoring preprocessing variant is kept per language.

    Bounding boxes are returned in ORIGINAL frame pixel coordinates.
    """
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "reason": "frame unreadable", "words": [], "text": ""}
    ox = oy = 0
    if crop:
        x, y, w, h = crop
        x, y = max(0, x), max(0, y)
        w = min(w, img.shape[1] - x); h = min(h, img.shape[0] - y)
        if w <= 4 or h <= 4:
            return {"ok": False, "reason": "crop empty", "words": [], "text": ""}
        img = img[y:y + h, x:x + w]
        ox, oy = x, y

    scale = _scale_for(img)
    preps = _variants(img, scale, deep=deep)
    have = set(available_languages())
    if languages is not None:
        langs = languages
    elif deep:
        langs = [l for l in ("eng", "hin", "pan") if l in have] or ["eng"]
    else:
        # Latin-only fast path. Indic models are ~8× slower, so they run only on the
        # frames the caller explicitly marks for a deep (multilingual) pass.
        langs = ["eng"]

    best_per_lang: dict[str, list[dict]] = {}
    for lang in langs:
        best: list[dict] = []
        for _, prep in preps:
            for psm in (11, 6):
                w = _pass(prep, lang, psm, scale, ox, oy, region, min_conf)
                if _yield(w) > _yield(best):
                    best = w
        if best:
            best_per_lang[lang] = best

    # Merge: Latin output is authoritative for ASCII; non-Latin passes contribute
    # only words that actually contain characters of their own script.
    merged: list[dict] = []
    seen: set[tuple[str, int, int]] = set()
    for lang in ("eng", "hin", "pan"):
        for w in best_per_lang.get(lang, []):
            if lang != "eng" and not _has_script(w["text"], lang):
                continue
            key = (w["text"].lower(), w["bbox"][0] // 12, w["bbox"][1] // 12)
            if key in seen:
                continue
            seen.add(key)
            merged.append(w)

    merged.sort(key=lambda w: (w["bbox"][1] // 18, w["bbox"][0]))
    return {"ok": True, "words": merged, "text": " ".join(w["text"] for w in merged),
            "languages_used": list(best_per_lang.keys()), "region": region,
            "passes": {k: len(v) for k, v in best_per_lang.items()}}


def _has_script(text: str, lang: str) -> bool:
    if lang == "hin":
        return any("\u0900" <= c <= "\u097F" for c in text)
    if lang == "pan":
        return any("\u0A00" <= c <= "\u0A7F" for c in text)
    return True


def detect_script(text: str) -> str:
    """Name the script actually present. Digits carry no script, and saying so is
    more useful than reporting 'unknown' for a phone number or an amount."""
    if not text:
        return "unknown"
    dev = sum(1 for c in text if "\u0900" <= c <= "\u097F")
    gur = sum(1 for c in text if "\u0A00" <= c <= "\u0A7F")
    lat = sum(1 for c in text if c.isascii() and c.isalpha())
    best = max((dev, "Devanagari (Hindi)"), (gur, "Gurmukhi (Punjabi)"), (lat, "Latin (English)"),
               key=lambda x: x[0])
    if best[0] > 0:
        return best[1]
    if any(c.isdigit() for c in text):
        return "Digits (no script)"
    return "unknown"


def extract_entities(words: list[dict], frame_index: int, frame_number: int | None,
                     timestamp_s: float | None) -> list[dict[str, Any]]:
    """
    Entities are matched against the OCR line text, then mapped back to the bounding
    box of the word that produced them, so every entity keeps a real coordinate.
    """
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # build a line-ish string but keep word offsets so we can map back
    joined_parts, index_map = [], []
    cursor = 0
    for w in words:
        joined_parts.append(w["text"])
        index_map.append((cursor, cursor + len(w["text"]), w))
        cursor += len(w["text"]) + 1
    joined = " ".join(joined_parts)

    for etype, rx in PATTERNS:
        for m in rx.finditer(joined):
            val = m.group(0).strip().rstrip(".,;:")
            if etype == "URL":
                if _URL_NOISE.match(val) or len(val) < 6:
                    continue
                # do not report the local part of a UPI/email token as a URL
                tail = joined[m.end():m.end() + 2]
                head = joined[max(0, m.start() - 1):m.start()]
                if tail.startswith("@") or head == "@":
                    continue
                if any(v.lower().startswith(val.lower() + "@") for (t, v) in seen if t == "UPI"):
                    continue
            if etype == "HANDLE" and len(val) < 4:
                continue
            key = (etype, val.lower())
            if key in seen:
                continue
            seen.add(key)
            owner = next((w for s, e, w in index_map if not (m.end() <= s or m.start() >= e)), None)
            out.append({
                "value": val, "entity_type": etype,
                "raw_text": owner["text"] if owner else val,
                "language": (owner.get("lang_label") if owner and owner.get("lang_label")
                             else detect_script(owner["text"] if owner else val)),
                "frame_index": frame_index, "frame_number": frame_number,
                "timestamp_s": timestamp_s,
                "bbox": owner["bbox"] if owner else None,
                "ocr_confidence": owner["conf"] if owner else None,
                "region": owner.get("region", "full-frame") if owner else "full-frame",
                "method": "tesseract-ocr + pattern match",
            })
    return out
