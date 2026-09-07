"""
SROT data model.

Design rule: every displayed value must be traceable to a row here, and every
derived row records HOW it was derived (method + source evidence + confidence).
Nothing in the UI may exist without a backing record.
"""
from __future__ import annotations
import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON, Boolean, Index,
)
from sqlalchemy.orm import relationship
from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True)
    case_ref = Column(String, unique=True, index=True, nullable=False)   # CASE-2026-001
    title = Column(String, nullable=False)
    category = Column(String, default="Synthetic media")
    officer = Column(String, default="Investigating Officer")
    unit = Column(String, default="Cyber Crime Investigation Unit")
    summary = Column(Text, default="")
    status = Column(String, default="Open")
    created_at = Column(DateTime, default=utcnow)
    evidence = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True)
    evidence_ref = Column(String, unique=True, index=True, nullable=False)  # EV-CASE-2026-001-001
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    filename = Column(String, nullable=False)          # sanitised original filename
    stored_path = Column(String, nullable=False)       # immutable original on disk
    mime_type = Column(String)
    media_kind = Column(String)                        # image | video | other
    size_bytes = Column(Integer)
    sha256 = Column(String, index=True)
    hash_algorithm = Column(String, default="SHA-256")
    ingested_at = Column(DateTime, default=utcnow)
    # container / stream facts from ffprobe or PIL — measured, never assumed
    width = Column(Integer); height = Column(Integer)
    duration_s = Column(Float); fps = Column(Float)
    video_codec = Column(String); audio_codec = Column(String)
    container_format = Column(String); encoder_tag = Column(String)
    has_audio = Column(Boolean, default=False)
    probe_json = Column(JSON)                          # raw ffprobe / PIL info
    exif_json = Column(JSON)
    c2pa_present = Column(Boolean, default=False)
    c2pa_note = Column(String, default="")
    case = relationship("Case", back_populates="evidence")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True)
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime)
    status = Column(String, default="queued")          # queued|running|completed|failed
    stage = Column(String, default="")                 # current stage name
    stages_json = Column(JSON, default=dict)           # {stage: status}
    detector_backend = Column(String, default="")      # honest label of what actually ran
    assessment = Column(String)                        # Potentially Manipulated | Likely Authentic | Inconclusive
    confidence_band = Column(String)                   # HIGH|MEDIUM|LOW|INCONCLUSIVE
    aggregate_score = Column(Float)                    # 0..100, computed from signals
    aggregation_formula = Column(String, default="")   # printed in the report so it is checkable
    frames_sampled = Column(Integer, default=0)
    dissent = Column(Boolean, default=False)
    error = Column(Text)


class Signal(Base):
    """One measured forensic signal. `measurement` holds the raw numeric evidence."""
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    key = Column(String); name = Column(String)
    result = Column(String)          # human label
    strength = Column(String)        # Strong | Moderate | Weak | Unavailable | Counter-indicator
    score = Column(Float)            # normalised 0..100 contribution, or None
    weight = Column(Float, default=0.0)
    direction = Column(String, default="supports")   # supports | counter | neutral
    measurement = Column(JSON)       # the actual numbers measured
    method = Column(String)          # exactly how it was computed
    note = Column(Text)


class FrameAnalysis(Base):
    __tablename__ = "frame_analysis"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    frame_index = Column(Integer)      # index within the sampled set
    frame_number = Column(Integer)     # approximate source frame number
    timestamp_s = Column(Float)
    score = Column(Float)              # per-frame anomaly score, measured
    metrics_json = Column(JSON)
    path = Column(String)              # extracted frame file (working copy)


class Fingerprint(Base):
    __tablename__ = "fingerprints"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True, nullable=True)
    corpus_id = Column(Integer, ForeignKey("corpus_items.id"), index=True, nullable=True)
    hash_type = Column(String)        # phash | dhash | whash
    hash_hex = Column(String, index=True)
    frame_index = Column(Integer, default=0)
    bits = Column(Integer, default=64)


class CorpusItem(Base):
    """
    Reference corpus record. SYNTHETIC for the demo, and flagged as such, but the
    media files are real files on disk so every match is genuinely computed.
    """
    __tablename__ = "corpus_items"
    id = Column(Integer, primary_key=True)
    label = Column(String)              # forum_post_8841 / @chd_alerts_now
    source_kind = Column(String)        # forum | channel | aggregator | mirror
    filename = Column(String)
    stored_path = Column(String)
    observed_at = Column(DateTime)      # when this copy was observed (corpus record)
    sha256 = Column(String)
    is_synthetic = Column(Boolean, default=True)
    note = Column(String, default="")
    transform = Column(String, default="")   # how this copy differs from the seed


class OriginMatch(Base):
    __tablename__ = "origin_matches"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    corpus_id = Column(Integer, ForeignKey("corpus_items.id"))
    similarity = Column(Float)          # 0..100, computed from Hamming distance
    hamming = Column(Integer)
    hash_type = Column(String)
    normalisation = Column(String)      # which frame view produced the best match
    matched_frames = Column(Integer, default=1)
    total_frames = Column(Integer, default=1)
    is_earliest = Column(Boolean, default=False)


class ExtractedEntity(Base):
    __tablename__ = "extracted_entities"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    value = Column(String)
    entity_type = Column(String)        # PHONE|UPI|WALLET|URL|HANDLE|AMOUNT|DATE|TIME|TEXT
    raw_text = Column(Text)
    language = Column(String)
    frame_index = Column(Integer)
    frame_number = Column(Integer)
    timestamp_s = Column(Float)
    bbox_json = Column(JSON)            # [x, y, w, h] in frame pixels
    ocr_confidence = Column(Float)
    method = Column(String, default="tesseract-ocr")
    region = Column(String, default="full-frame")


class RecaptureResult(Base):
    __tablename__ = "recapture_results"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    likelihood = Column(String)         # HIGH|MEDIUM|LOW|INCONCLUSIVE
    score = Column(Float)
    letterbox_json = Column(JSON)
    static_band_json = Column(JSON)
    fft_json = Column(JSON)
    ui_regions_json = Column(JSON)
    recovered_handles_json = Column(JSON)
    note = Column(Text)


class StressTestRun(Base):
    __tablename__ = "stress_runs"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True)
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime)
    status = Column(String, default="queued")
    baseline_score = Column(Float)
    reliability_boundary = Column(String, default="")
    recommendation = Column(Text, default="")
    error = Column(Text)


class StressVariant(Base):
    __tablename__ = "stress_variants"
    id = Column(Integer, primary_key=True)
    stress_id = Column(Integer, ForeignKey("stress_runs.id"), index=True)
    name = Column(String); transform = Column(String); ffmpeg_args = Column(String)
    path = Column(String); sha256 = Column(String); size_bytes = Column(Integer)
    score = Column(Float); delta = Column(Float)
    phash_hex = Column(String); phash_hamming = Column(Integer); phash_similarity = Column(Float)
    # No default: an unassessed variant must stay NULL. Defaulting to True silently
    # reported variants as reliable that were never evaluated.
    reliable = Column(Boolean, nullable=True)
    processing_ms = Column(Integer)
    error = Column(String)


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True)
    node_key = Column(String, index=True)
    kind = Column(String)               # evidence|frame|extraction|identifier|copy|origin|case|signal
    label = Column(String); sublabel = Column(String)
    source_evidence_id = Column(Integer)
    frame_number = Column(Integer)
    extraction_method = Column(String)
    confidence = Column(Float)
    observed_at = Column(DateTime)
    is_synthetic = Column(Boolean, default=False)
    attrs_json = Column(JSON)


class GraphEdge(Base):
    __tablename__ = "graph_edges"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True)
    src_key = Column(String); dst_key = Column(String)
    relation = Column(String)
    reason = Column(Text)               # why this edge exists — shown in the UI
    evidence_ref = Column(String)
    observation = Column(String)        # DIRECTLY_OBSERVED | INFERRED
    confidence = Column(Float)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True)
    occurred_at = Column(DateTime, index=True)
    title = Column(String); detail = Column(Text)
    kind = Column(String)               # corpus|evidence|system|entity
    evidence_ref = Column(String)
    confidence = Column(Float)
    is_synthetic = Column(Boolean, default=False)


class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    rank = Column(Integer); priority = Column(String)
    title = Column(String); summary = Column(Text)
    reasons_json = Column(JSON)         # list of {text, evidence_ref, frame, value}
    limitation = Column(Text)
    status = Column(String, default="Potential investigative lead — human verification required.")


class CampaignMatch(Base):
    __tablename__ = "campaign_matches"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"))
    other_case_ref = Column(String)
    other_evidence_ref = Column(String)
    similarity = Column(Float)
    hamming = Column(Integer)
    hash_type = Column(String)
    normalisation = Column(String)
    seen_at = Column(DateTime)


class FingerprintLedger(Base):
    """Department-level ledger: every fingerprint ever ingested, across all cases."""
    __tablename__ = "fingerprint_ledger"
    id = Column(Integer, primary_key=True)
    perceptual_hash = Column(String, index=True)
    hash_type = Column(String)
    case_ref = Column(String, index=True)
    evidence_ref = Column(String, index=True)
    filename = Column(String)
    frame_index = Column(Integer, default=0)
    seen_at = Column(DateTime, default=utcnow)


Index("ix_ledger_hash_type", FingerprintLedger.perceptual_hash, FingerprintLedger.hash_type)


class AuditLog(Base):
    """Append-only, hash-linked. prev_hash → current_hash chain."""
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True)
    evidence_ref = Column(String)
    occurred_at = Column(DateTime, default=utcnow)
    action = Column(String)
    component = Column(String)
    actor = Column(String, default="system")
    payload_json = Column(JSON)
    evidence_hash = Column(String)
    prev_hash = Column(String)
    current_hash = Column(String)


class CourtPacket(Base):
    __tablename__ = "court_packets"
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"))
    created_at = Column(DateTime, default=utcnow)
    zip_path = Column(String)
    files_json = Column(JSON)           # {doc_key: path}
    packet_sha256 = Column(String)


class NeuralFrameResult(Base):
    """Real neural model inference result for a single frame.

    Every score here comes from actual model inference — never fabricated.
    """
    __tablename__ = "neural_frame_results"
    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), index=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), index=True)
    frame_index = Column(Integer)
    frame_number = Column(Integer)
    timestamp_s = Column(Float)
    model_name = Column(String)
    model_version = Column(String)
    model_input_size = Column(String, default="224x224")
    raw_output = Column(JSON)           # full model output
    normalized_score = Column(Float)    # 0..1, probability of AI-generated
    label = Column(String)             # "artificial" / "human"
    inference_time_ms = Column(Integer)
    preprocessing_version = Column(String)
    created_at = Column(DateTime, default=utcnow)
    error = Column(String)


class OfficerUser(Base):
    """Authenticated police officer / analyst account for SROT access gate."""
    __tablename__ = "officer_users"
    id = Column(Integer, primary_key=True)
    badge_id = Column(String, unique=True, index=True, nullable=False)  # e.g. "DEMO-OFFICER"
    name = Column(String, nullable=False)                               # e.g. "Insp. Vikramaditya (Cyber Ops)"
    role = Column(String, default="Senior Forensic Investigator")
    unit = Column(String, default="Cyber Crime Investigation Unit")
    password_hash = Column(String, nullable=False)                      # pbkdf2$sha256$100000$salt$hash
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    last_login_at = Column(DateTime, nullable=True)


class OfficerSession(Base):
    """Active officer session token storage."""
    __tablename__ = "officer_sessions"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String, unique=True, index=True, nullable=False)  # SHA-256 of session token
    officer_id = Column(Integer, ForeignKey("officer_users.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)

