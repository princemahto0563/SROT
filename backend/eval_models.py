"""
SROT Phase 2 — Neural model evaluation harness.

Tests three candidate models against a fixed set of evaluation inputs.
Every score is from REAL inference — nothing fabricated.
"""
import sys, time, json, io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

# ── evaluation image generators (NOT from the demo corpus) ──────────────────

def make_authentic_photo():
    """Simulate a natural photograph: noisy gradient with realistic texture."""
    rng = np.random.RandomState(42)
    h, w = 512, 512
    y_grad = np.linspace(0, 1, h).reshape(-1, 1)
    x_grad = np.linspace(0, 1, w).reshape(1, -1)
    r = 80 + 120 * y_grad + rng.normal(0, 15, (h, w))
    g = 100 + 80 * x_grad + rng.normal(0, 12, (h, w))
    b = 60 + 140 * (x_grad + y_grad) / 2 + rng.normal(0, 18, (h, w))
    base = np.stack([r, g, b], axis=-1)
    base = np.clip(base, 0, 255).astype(np.uint8)
    return Image.fromarray(base)


def make_ai_art_style():
    """Create a clean, smooth AI-art-like image (no sensor noise, smooth gradients)."""
    h, w = 512, 512
    x = np.arange(w).reshape(1, -1)
    y = np.arange(h).reshape(-1, 1)
    r = (128 + 127 * np.sin(x / 30)).astype(np.uint8)
    g = (128 + 127 * np.cos(y / 25)).astype(np.uint8)
    b = (128 + 127 * np.sin((x + y) / 40)).astype(np.uint8)
    arr = np.stack([np.broadcast_to(r, (h, w)),
                    np.broadcast_to(g, (h, w)),
                    np.broadcast_to(b, (h, w))], axis=-1).astype(np.uint8)
    img = Image.fromarray(arr)
    # Apply slight Gaussian blur (typical of diffusion outputs)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    return img


def make_screenshot():
    """Simulate a screenshot: flat background, sharp text, UI elements."""
    img = Image.new("RGB", (512, 512), (30, 30, 40))
    draw = ImageDraw.Draw(img)
    # Status bar
    draw.rectangle([0, 0, 512, 28], fill=(50, 50, 60))
    draw.text((10, 5), "9:41 AM", fill=(200, 200, 200))
    # Content area
    draw.rectangle([20, 50, 492, 120], fill=(45, 45, 55))
    draw.text((30, 65), "WhatsApp Message", fill=(255, 255, 255))
    draw.text((30, 90), "Check this investment opportunity!", fill=(180, 180, 180))
    # Button
    draw.rounded_rectangle([150, 350, 362, 390], radius=8, fill=(0, 128, 255))
    draw.text((200, 360), "Click Here", fill=(255, 255, 255))
    return img


def make_solid_black():
    """Minimal image — should NOT be classified confidently either way."""
    return Image.new("RGB", (224, 224), (0, 0, 0))


def make_solid_noise():
    """Pure random noise."""
    rng = np.random.RandomState(99)
    return Image.fromarray(rng.randint(0, 256, (512, 512, 3), dtype=np.uint8))


def jpeg_compress(img, quality=30):
    """Return a heavily JPEG-compressed version."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).copy()


def resize_small(img, size=128):
    """Downscale to small resolution."""
    return img.resize((size, size), Image.LANCZOS)


def crop_centre(img, fraction=0.5):
    """Centre crop to fraction of original size."""
    w, h = img.size
    nw, nh = int(w * fraction), int(h * fraction)
    left, top = (w - nw) // 2, (h - nh) // 2
    return img.crop((left, top, left + nw, top + nh))


# ── evaluation inputs ───────────────────────────────────────────────────────

def build_eval_set():
    """Build evaluation inputs. Returns list of (name, category, image)."""
    authentic = make_authentic_photo()
    ai_art = make_ai_art_style()
    screenshot = make_screenshot()
    noise = make_solid_noise()

    inputs = [
        # A. Known "authentic-style" images
        ("authentic_photo", "authentic", authentic),
        ("authentic_photo_jpeg30", "authentic+transform", jpeg_compress(authentic, 30)),
        ("authentic_photo_small", "authentic+transform", resize_small(authentic, 128)),
        ("authentic_photo_crop50", "authentic+transform", crop_centre(authentic, 0.5)),

        # B. Known "AI-art-style" images
        ("ai_art_synthetic", "ai-generated", ai_art),
        ("ai_art_jpeg30", "ai-generated+transform", jpeg_compress(ai_art, 30)),
        ("ai_art_small", "ai-generated+transform", resize_small(ai_art, 128)),
        ("ai_art_crop50", "ai-generated+transform", crop_centre(ai_art, 0.5)),

        # D. Screenshots
        ("screenshot_ui", "screenshot", screenshot),
        ("screenshot_jpeg30", "screenshot+transform", jpeg_compress(screenshot, 30)),

        # E. Synthetic demo frames (from SROT corpus if available)
        # Will be added below from actual extracted frames

        # Noise / edge cases
        ("pure_noise", "edge-case", noise),
        ("solid_black", "edge-case", make_solid_black()),
    ]

    # E. Extracted SROT demo frames (if available)
    work = Path("data/work")
    if work.exists():
        frame_dirs = sorted(work.glob("*/frames"))
        for fd in frame_dirs[:1]:  # first evidence only
            frame_files = sorted(fd.glob("*.jpg"))[:3]
            for i, fp in enumerate(frame_files):
                img = Image.open(fp).convert("RGB")
                inputs.append((f"srot_demo_frame_{i}", "synthetic-demo", img))
                if i == 0:
                    inputs.append((f"srot_demo_frame_0_jpeg30", "synthetic-demo+transform",
                                   jpeg_compress(img, 30)))
                    inputs.append((f"srot_demo_frame_0_small", "synthetic-demo+transform",
                                   resize_small(img, 128)))

    return inputs


# ── model evaluation ────────────────────────────────────────────────────────

def eval_model(model_id, eval_inputs, label_map=None):
    """Evaluate a model against all inputs. Returns list of result dicts."""
    from transformers import pipeline as hf_pipeline
    print(f"\n{'='*70}")
    print(f"  EVALUATING: {model_id}")
    print(f"{'='*70}")

    t0 = time.time()
    try:
        pipe = hf_pipeline("image-classification", model=model_id, device="mps")
    except Exception:
        try:
            pipe = hf_pipeline("image-classification", model=model_id, device="cpu")
        except Exception as e:
            print(f"  FAILED TO LOAD: {e}")
            return None
    load_ms = round((time.time() - t0) * 1000)
    print(f"  Loaded in {load_ms}ms")

    results = []
    for name, category, img in eval_inputs:
        t1 = time.time()
        try:
            out = pipe(img)
            inf_ms = round((time.time() - t1) * 1000)
            # Normalise: find the "artificial/fake/ai" score
            scores = {r["label"].lower(): r["score"] for r in out}
            ai_score = None
            for key in ("artificial", "fake", "ai", "ai-generated", "deepfake",
                        "ai_generated", "Fake"):
                if key in scores:
                    ai_score = scores[key]
                    break
            if ai_score is None:
                # Try to find by exclusion — the non-"real"/"human" one
                for key in ("human", "real", "authentic", "Real"):
                    if key in scores:
                        ai_score = 1.0 - scores[key]
                        break
            results.append({
                "name": name, "category": category,
                "ai_score": round(ai_score, 4) if ai_score is not None else None,
                "raw": {r["label"]: round(r["score"], 4) for r in out},
                "inference_ms": inf_ms, "error": None,
            })
        except Exception as e:
            results.append({
                "name": name, "category": category,
                "ai_score": None, "raw": {}, "inference_ms": 0,
                "error": str(e)[:100],
            })

    # Print results table
    print(f"\n  {'Input':<35} {'Category':<25} {'AI Score':>10} {'ms':>6}  Raw")
    print(f"  {'-'*35} {'-'*25} {'-'*10} {'-'*6}  {'-'*30}")
    for r in results:
        ai_s = f"{r['ai_score']:.4f}" if r['ai_score'] is not None else "ERROR"
        raw_str = ", ".join(f"{k}:{v:.3f}" for k, v in r['raw'].items())
        print(f"  {r['name']:<35} {r['category']:<25} {ai_s:>10} {r['inference_ms']:>6}  {raw_str}")

    return {"model_id": model_id, "load_ms": load_ms, "results": results}


# ── main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building evaluation inputs...")
    eval_inputs = build_eval_set()
    print(f"  {len(eval_inputs)} evaluation images prepared\n")

    CANDIDATES = [
        "umm-maybe/AI-image-detector",        # Current model
        "Organika/sdxl-detector",              # SDXL-focused
        "prithivMLmods/Deepfake-Detect-Siglip2",  # Modern SigLIP2-based
    ]

    all_results = {}
    for model_id in CANDIDATES:
        result = eval_model(model_id, eval_inputs)
        if result:
            all_results[model_id] = result

    # Summary comparison
    print(f"\n\n{'='*80}")
    print("COMPARATIVE SUMMARY")
    print(f"{'='*80}")
    print(f"\n{'Input':<35}", end="")
    for mid in all_results:
        short = mid.split("/")[-1][:18]
        print(f"  {short:>18}", end="")
    print()
    print("-" * (35 + 20 * len(all_results)))

    for i, (name, category, _) in enumerate(eval_inputs):
        print(f"{name:<35}", end="")
        for mid in all_results:
            r = all_results[mid]["results"][i]
            s = f"{r['ai_score']:.3f}" if r['ai_score'] is not None else "ERR"
            print(f"  {s:>18}", end="")
        print(f"  [{category}]")

    # Save JSON results
    out_path = Path("MODEL-EVAL-RESULTS.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nRaw results saved to {out_path}")
