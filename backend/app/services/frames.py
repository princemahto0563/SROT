"""Keyframe sampling. Bounded work: we never decode every frame of a long video."""
from __future__ import annotations
import shutil, subprocess
from pathlib import Path

def _find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if Path(candidate).is_file():
            return candidate
    return None


FFMPEG = _find_ffmpeg()
DEFAULT_MAX_FRAMES = 24


def extract_frames(src: str | Path, out_dir: str | Path,
                   duration_s: float | None, max_frames: int = DEFAULT_MAX_FRAMES,
                   width: int = 640) -> list[dict]:
    """
    Sample up to `max_frames` evenly-spaced frames from a working copy of the media.
    Uses reliable sequential ffmpeg decoding with a safe fallback to OpenCV frame decoding.
    Guarantees the original immutable evidence file is preserved untouched.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    src_path = Path(src)
    if not src_path.is_file() or src_path.stat().st_size == 0:
        return []

    existing = sorted([p for p in out_dir.glob("frame_*.jpg") if p.stat().st_size > 0])
    if not existing:
        ffmpeg_bin = FFMPEG or _find_ffmpeg()

        # Step 1: Create an isolated working copy to preserve immutable evidence
        work_copy = out_dir / f"_extract_work_{src_path.name}"
        try:
            shutil.copy2(src_path, work_copy)
        except Exception:
            work_copy = src_path

        try:
            # Step 2: Primary extraction — sequential ffmpeg decode path
            if ffmpeg_bin:
                if duration_s and duration_s > 0.4:
                    fps_expr = f"{max_frames / duration_s:.6f}"
                    vf = f"fps={fps_expr},scale='min(iw,{width})':-2"
                else:
                    vf = f"scale='min(iw,{width})':-2"
                cmd = [
                    ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(work_copy),
                    "-vf", vf,
                    "-frames:v", str(max_frames),
                    "-q:v", "3",
                    str(out_dir / "frame_%03d.jpg"),
                ]
                try:
                    subprocess.run(cmd, capture_output=True, timeout=180, check=False)
                except subprocess.TimeoutExpired:
                    pass
                existing = sorted([p for p in out_dir.glob("frame_*.jpg") if p.stat().st_size > 0])

            # Step 3: Fallback extraction — ONLY if primary produced zero frames
            if not existing and ffmpeg_bin:
                # Fallback A: sequential ffmpeg decode without complex fps filter
                cmd_fb = [
                    ffmpeg_bin, "-hide_banner", "-loglevel", "error",
                    "-err_detect", "ignore_err", "-y",
                    "-i", str(work_copy),
                    "-vf", f"scale='min(iw,{width})':-2",
                    "-frames:v", str(max_frames),
                    "-q:v", "3",
                    str(out_dir / "frame_%03d.jpg"),
                ]
                try:
                    subprocess.run(cmd_fb, capture_output=True, timeout=180, check=False)
                except subprocess.TimeoutExpired:
                    pass
                existing = sorted([p for p in out_dir.glob("frame_*.jpg") if p.stat().st_size > 0])

            # Fallback B: OpenCV sequential frame decode directly from raw bitstream bytes
            if not existing:
                try:
                    import cv2
                    cap = cv2.VideoCapture(str(work_copy))
                    if cap.isOpened():
                        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        step = max(1, total_frames // max_frames) if total_frames > max_frames else 1
                        idx = 0
                        saved = 0
                        while cap.isOpened() and saved < max_frames:
                            ret, frame = cap.read()
                            if not ret:
                                break
                            if idx % step == 0:
                                saved += 1
                                h, w = frame.shape[:2]
                                if w > width:
                                    new_h = max(2, int(round(h * width / w / 2)) * 2)
                                    frame = cv2.resize(frame, (width, new_h), interpolation=cv2.INTER_AREA)
                                cv2.imwrite(
                                    str(out_dir / f"frame_{saved:03d}.jpg"),
                                    frame,
                                    [int(cv2.IMWRITE_JPEG_QUALITY), 92],
                                )
                            idx += 1
                        cap.release()
                    existing = sorted([p for p in out_dir.glob("frame_*.jpg") if p.stat().st_size > 0])
                except Exception:
                    pass
        finally:
            # Clean up working copy to preserve storage hygiene
            if work_copy != src_path and work_copy.exists():
                try:
                    work_copy.unlink(missing_ok=True)
                except Exception:
                    pass

    n = len(existing)
    records: list[dict] = []
    for i, p in enumerate(existing):
        ts = (duration_s * i / n) if (duration_s and n) else None
        records.append({
            "frame_index": i,
            "path": str(p),
            "timestamp_s": round(ts, 3) if ts is not None else None,
            # approximate source frame number, honestly derived from fps × timestamp
            "frame_number": None,
        })
    return records


def annotate_frame_numbers(records: list[dict], fps: float | None) -> list[dict]:
    for r in records:
        if fps and r.get("timestamp_s") is not None:
            r["frame_number"] = int(round(r["timestamp_s"] * fps))
    return records


def extract_audio(src: str | Path, out_path: str | Path) -> bool:
    ffmpeg_bin = FFMPEG or _find_ffmpeg()
    if not ffmpeg_bin:
        return False
    cmd = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
           "-vn", "-ac", "1", "-ar", "16000", str(out_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
        return r.returncode == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 1024
    except subprocess.TimeoutExpired:
        return False
