/**
 * Live API client. Every screen reads from the running backend — there is no
 * bundled fixture data, so anything the interface shows was actually computed.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const envApi = (import.meta.env.VITE_API_URL || "").trim().replace(/\/+$/, "");

// Normalize API base so that it ends with '/api' if pointing to backend root, or stays '/api' locally
export const API = (() => {
  if (!envApi) return "/api";
  if (envApi.endsWith("/api")) return envApi;
  return `${envApi}/api`;
})();

const TOKEN_KEY = "srot_officer_token";

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {}
}

export function authenticatedUrl(path?: string | null): string {
  if (!path) return "";
  let fullUrl = path;
  if (API.startsWith("http")) {
    const baseOrigin = API.replace(/\/api$/, "");
    if (path.startsWith("/api")) {
      fullUrl = `${baseOrigin}${path}`;
    } else if (path.startsWith("http")) {
      fullUrl = path;
    } else {
      fullUrl = `${API}${path.startsWith("/") ? "" : "/"}${path}`;
    }
  }
  const token = getAuthToken();
  if (!token) return fullUrl;
  const sep = fullUrl.includes("?") ? "&" : "?";
  return `${fullUrl}${sep}token=${encodeURIComponent(token)}`;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const reqInit = { ...init };
  const headers = new Headers(reqInit.headers);
  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  reqInit.headers = headers;

  try {
    const cleanPath = path.startsWith("/api/") ? path.slice(4) : (path === "/api" ? "/" : path);
    const targetPath = cleanPath.startsWith("/") ? cleanPath : `/${cleanPath}`;
    res = await fetch(`${API}${targetPath}`, reqInit);
  } catch {
    throw new ApiError(
      "Cannot reach the SROT backend. Start it with: uvicorn app.main:app --port 8077",
      0,
    );
  }
  if (!res.ok) {
    if (res.status === 401 && path !== "/auth/login") {
      window.dispatchEvent(new CustomEvent("srot:unauthorized"));
    }
    let detail = `Request failed (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch { /* non-JSON error body */ }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(p: string) => request<T>(p),
  post: <T,>(p: string, body?: unknown) =>
    request<T>(p, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    }),
  del: <T,>(p: string) => request<T>(p, { method: "DELETE" }),
  upload: <T,>(p: string, form: FormData) =>
    request<T>(p, { method: "POST", body: form }),
};

/* ── types (mirrors of the API payloads actually returned) ─────────────────── */
export type Health = {
  status: string; detector_backend: string; neural_detector_loaded: boolean;
  tools: Record<string, boolean>; ocr_languages: string[];
  corpus_items: number; cases: number; ledger_entries: number; offline: boolean;
};

export type RunSummary = {
  id: number; status: string; stage: string | null;
  stages: Record<string, string>; assessment: string | null;
  aggregate_score: number | null; confidence_band: string | null;
  dissent: boolean; frames_sampled: number | null; error?: string | null;
};

export type Evidence = {
  id: number; evidence_ref: string; filename: string; media_kind: string;
  mime_type: string; size_bytes: number; sha256: string; hash_algorithm: string;
  ingested_at: string; width: number | null; height: number | null;
  duration_s: number | null; fps: number | null; video_codec: string | null;
  audio_codec: string | null; container_format: string | null;
  encoder_tag: string | null; has_audio: boolean; exif_fields: number;
  exif: Record<string, unknown>; c2pa_present: boolean; c2pa_note: string;
  latest_run: RunSummary | null;
};

export type CaseSummary = {
  id: number; case_ref: string; title: string; category: string;
  officer: string; summary: string; opened_at: string;
  counts?: Record<string, number>;
};

export type CaseDetail = CaseSummary & {
  evidence: Evidence[];
  audit_chain: { verified: boolean; entries: number; message: string; broken_at_id: number | null };
};

export type Signal = {
  key: string; name: string; result: string; strength: string;
  score: number | null; weight: number; direction: string;
  measurement: Record<string, unknown>; method: string; note: string;
};

export type Analysis = {
  evidence_ref: string; status: string; detector_backend: string;
  neural_detector_available: boolean; aggregation_formula: string;
  aggregate_score: number | null; assessment: string; confidence_band: string;
  dissent: boolean; frames_sampled: number; signals: Signal[];
  supporting?: string[]; counter?: string[];
  limitations: string[]; started_at: string | null; finished_at: string | null;
};

export type OriginMatch = {
  corpus_id: number; label: string; source_kind: string; observed_at: string | null;
  similarity: number; hamming: number; hash_type: string; normalisation: string | null;
  matched_frames: number; total_frames: number; is_earliest: boolean;
  transform: string; is_synthetic: boolean; sha256: string; note: string;
};

export type Origin = {
  evidence_ref: string; corpus_size: number; matches: OriginMatch[];
  match_count: number; earliest: OriginMatch | null;
  propagation_span_days: number | null; max_similarity: number | null;
  method: string; threshold: string;
  threshold_calibration: Record<string, unknown>;
  established: boolean; empty_reason: string | null; disclaimer: string;
  attribution_ceiling: Ceiling;
};

export type CeilingStep = {
  step: number; what: string; actor: string; mode: string;
  established: boolean; detail: string;
};
export type Ceiling = CeilingStep[];

export type Entity = {
  value: string; entity_type: string; raw_text: string; language: string;
  frame_index: number; frame_number: number | null; timestamp_s: number | null;
  bbox: number[] | null; ocr_confidence: number | null; method: string; region: string;
};

export type Entities = {
  evidence_ref: string; count: number; entities: Entity[];
  ocr_languages_available: string[]; scripts_detected: string[];
  empty_reason: string | null; disclaimer: string;
};

export type Recapture = {
  evidence_ref: string; likelihood: string; score: number | null;
  letterbox: Record<string, unknown> | null; static_bands: Record<string, unknown> | null;
  moire: Record<string, unknown> | null;
  recovered_handles: { handle: string; frame_index: number; region: string;
                       bbox: number[]; confidence: number; method: string }[];
  metadata_note: string; note: string; method: string; indicators: string[];
};

export type FrameRow = {
  frame_index: number; frame_number: number | null; timestamp_s: number | null;
  score: number | null; metrics: Record<string, number>; image_url: string;
};

export type GraphPayload = {
  nodes: { id: string; key: string; label: string; kind: string; layer: number;
           x: number; y: number; confidence: number | null; detail: string;
           source_evidence: string | null; method: string | null }[];
  edges: { id: string; source: string; target: string; label: string;
           relation: string; inferred: boolean; confidence: number | null;
           method: string | null }[];
  stats: { nodes: number; edges: number; directly_observed: number; inferred: number };
  legend?: Record<string, string>;
  empty_reason?: string | null;
};

export type LeadReason = { text: string; value: string | number | null };
export type Lead = {
  rank: number; priority: string; title: string; summary: string;
  reasons: LeadReason[]; limitation: string; status: string;
};

export type TimelineRow = {
  occurred_at: string; title: string; detail: string; kind: string;
  evidence_ref: string | null; confidence: number | null; is_synthetic: boolean;
};

export type AuditRow = {
  id: number; occurred_at: string; action: string; component: string; actor: string;
  evidence_ref: string | null; evidence_hash: string | null;
  prev_hash: string; current_hash: string; payload: Record<string, unknown>;
};

export type AuditPayload = {
  chain: { verified: boolean; entries: number; broken_at_id: number | null;
           reason: string | null; message: string };
  entries: AuditRow[];
  disclaimer: string;
};

export type QualityGate = {
  quality_grade: string;
  reliability_status: string;
  quality_score_pct: number;
  gating_factors: string[];
  impact_summary: string;
  metrics: {
    width: number;
    height: number;
    megapixels: number;
    sharpness_laplacian: number;
    mean_luminance: number;
    contrast_std: number;
    dynamic_range: number;
    underexposed_pct: number;
    overexposed_pct: number;
    blockiness_ratio: number;
    noise_floor: number;
    frames_evaluated: number;
  };
};

export type EvidenceMatrixItem = {
  source: string;
  measurement: string;
  observation: string;
  strength: "STRONG" | "MODERATE" | "LIMITED" | "BASELINE" | "INCONCLUSIVE";
  status: "VERIFIED" | "ANOMALOUS" | "CONSISTENT" | "INCONSISTENT" | "INDICATIVE" | "NOT_DETECTED" | "INSUFFICIENT" | "REDUCED_RELIABILITY" | "BASELINE";
  corroboration: string;
  limitation: string;
};

export type CrossSignalAssessment = {
  synthesis_headline: string;
  synthesis_narrative: string;
  evidence_state: "CONSISTENT" | "PARTIALLY_CORROBORATED" | "CONFLICTING" | "INSUFFICIENT";
  evidence_state_rationale: string;
  signal_consistency: "STRONG_CONSISTENCY" | "MODERATE_CONSISTENCY" | "MIXED" | "CONFLICTING" | "INSUFFICIENT";
  score_semantics: string;
  score_semantics_note: string;
  evidence_matrix: EvidenceMatrixItem[];
  corroborating_factors: string[];
  dissenting_or_neutral_factors: string[];
  investigative_recommendations: string[];
  quality_status: string;
  total_signals_evaluated: number;
};

export type DirectionalStability = {
  grade: string;
  mean_delta: number | null;
  max_delta: number | null;
  summary: string;
  surviving_count: number;
  total_count: number;
};

export type StressVariant = {
  name: string; transform: string; ffmpeg_args: string; score: number | null;
  delta: number | null; sha256: string | null; size_bytes: number | null;
  phash_similarity: number | null; phash_hamming: number | null;
  reliable: boolean | null; processing_ms: number | null; error: string | null;
};

export type ReplayComparison = {
  field: string;
  stored: string | number;
  replayed: string | number;
  delta?: number;
  match: boolean;
};

export type ReplayResult = {
  ok: boolean;
  evidence_ref: string;
  filename: string;
  hash_immutable: boolean;
  stored_sha256: string;
  recomputed_sha256: string;
  replay_time_ms: number;
  quality_grade?: string;
  reliability_status?: string;
  comparisons: ReplayComparison[];
  evidence_state: string;
  signal_consistency: string;
  synthesis_headline: string;
  device?: string;
  model_version?: string;
  model_provenance?: Record<string, unknown>;
  pipeline_version?: string;
  error?: string;
};

export type Stress = {
  stress_id?: number; status: string; baseline_score?: number | null;
  reliability_boundary?: string | null; recommendation?: string | null;
  error?: string | null; finished_at?: string | null;
  directional_stability?: DirectionalStability;
  variants: StressVariant[]; empty_reason?: string;
};

export type CampaignPayload = {
  matches: { other_case_ref: string; other_evidence_ref: string; similarity: number;
             hamming: number; hash_type: string; normalisation?: string | null;
             seen_at: string | null }[];
  count: number; wording: string; empty_reason?: string | null; disclaimer?: string;
};

export type Packet = {
  packet_id: number; created_at: string; packet_sha256: string; zip_url: string;
  documents: { key: string; name: string; url: string }[];
  status?: string; empty_reason?: string;
};

export type Consistency = {
  all_consistent: boolean;
  checks: { field: string; database: unknown; api: unknown; report: unknown; match: boolean }[];
  note: string;
};

/* ── hooks ────────────────────────────────────────────────────────────────── */
export type AsyncState<T> = {
  data: T | null; error: string | null; loading: boolean; reload: () => void;
};

export function useApi<T>(path: string | null, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [tick, setTick] = useState(0);
  const alive = useRef(true);

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => {
    if (!path) { setData(null); setLoading(false); return; }
    setLoading(true);
    api.get<T>(path)
      .then((d) => { if (alive.current) { setData(d); setError(null); } })
      .catch((e: Error) => { if (alive.current) { setError(e.message); setData(null); } })
      .finally(() => { if (alive.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}

/** Poll while `shouldContinue` holds — used for background analysis jobs. */
export function usePolling<T>(
  path: string | null,
  shouldContinue: (d: T) => boolean,
  intervalMs = 1500,
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [tick, setTick] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    let alive = true;
    if (!path) { setLoading(false); return; }
    const stop = () => { if (timer.current) { clearTimeout(timer.current); timer.current = null; } };

    const run = async () => {
      try {
        const d = await api.get<T>(path);
        if (!alive) return;
        setData(d); setError(null); setLoading(false);
        if (shouldContinue(d)) timer.current = window.setTimeout(run, intervalMs);
      } catch (e) {
        if (!alive) return;
        setError((e as Error).message); setLoading(false);
      }
    };
    setLoading(true); run();
    return () => { alive = false; stop(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, intervalMs]);

  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}

/* ── formatting helpers ───────────────────────────────────────────────────── */
export const fmtBytes = (n?: number | null) =>
  n == null ? "—"
    : n < 1024 ? `${n} B`
    : n < 1048576 ? `${(n / 1024).toFixed(1)} KB`
    : `${(n / 1048576).toFixed(2)} MB`;

export const fmtDate = (s?: string | null) => {
  if (!s) return "—";
  const d = new Date(s.endsWith("Z") || s.includes("+") ? s : `${s}Z`);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZone: "UTC",
  }) + " UTC";
};

export const fmtNum = (n?: number | null, dp = 2) =>
  n == null ? "—" : n.toFixed(dp);

export const shortHash = (h?: string | null, n = 12) =>
  !h ? "—" : `${h.slice(0, n)}…${h.slice(-4)}`;
