# SROT Phase 2 — Baseline Results

**Date**: 2026-09-01  
**Machine**: Apple M4, 16GB RAM, macOS Darwin 25.5.0 arm64  
**Python**: 3.13.9 | **Node**: v24.11.1 | **npm**: 11.6.2  

## System Dependencies
| Tool | Status | Version |
|------|--------|---------|
| ffmpeg | ✅ | 9.0.1 (homebrew-ffmpeg tap, with drawtext/freetype) |
| ffprobe | ✅ | 9.0.1 |
| tesseract | ✅ | 5.5.3 |
| OCR: eng, hin, pan | ✅ | All present |
| pango | ✅ | 1.58.2 (needs DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib) |

## Health Endpoint (Pre-Phase-2)
- neural_detector_loaded: false
- detector_backend: heuristic-forensic-ensemble-v1

## Test Results
- Calibration: PASS
- End-to-End: PASS (7 stages complete, score 19.84)
- Feature Tests: 23/24 (court packet pango path issue — pre-existing)
- Audit Chain: 10/10 PASS
- Data Integrity: 143/143 PASS
- Frontend TypeScript: 0 errors
- Frontend Build: 813ms
