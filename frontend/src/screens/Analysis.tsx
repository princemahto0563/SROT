import { useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronDown, ShieldCheck, ShieldAlert,
  Sparkles, RefreshCw, FileCheck, Scale
} from "lucide-react";
import {
  Async, Button, Chip, EmptyState, Field, Meter, Notice, PageHead, Panel, Table, Row, Cell,
} from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { useApi, api, fmtNum, authenticatedUrl } from "../lib/api";
import type { Signal, CrossSignalAssessment, QualityGate, ReplayResult, Evidence } from "../lib/api";

type AnalysisPayload = {
  evidence_ref: string; assessment: string; confidence_band: string;
  aggregate_score: number | null; detector_backend: string; aggregation_formula: string;
  neural_detector_loaded: boolean; frames_sampled: number; dissent: boolean;
  finished_at: string | null; signals: Signal[];
  quality_gate?: QualityGate;
  container: Record<string, unknown>;
  provenance: { c2pa_present: boolean; note: string; exif_fields: number };
  supporting: string[]; counter: string[]; unmeasured: string[]; limitations: string[];
};

type ProvenanceStage = {
  stage: string;
  name: string;
  source: "NEW_FILE" | "REFERENCE_CORPUS" | "CASE_CONTEXT" | "NOT_AVAILABLE" | "NOT_APPLICABLE";
  status: string;
  value: string;
  details: Record<string, unknown>;
};

type ProvenanceTrace = {
  evidence_ref: string;
  case_ref: string;
  filename: string;
  sha256: string;
  media_kind: string;
  stages: ProvenanceStage[];
  all_stages_isolated: boolean;
};

type FramesPayload = {
  frames: { frame_index: number; frame_number: number | null; timestamp_s: number | null;
            score: number | null; metrics: Record<string, unknown>; image_url: string }[];
  peak: { frame_index: number; score: number } | null;
};

const bandTone = (b: string) =>
  b === "HIGH" ? "danger" : b === "MEDIUM" ? "amber" : b === "LOW" ? "accent" : "muted";

const dirTone = (s: Signal) => {
  if (s.score == null) return "muted";
  if (s.score >= 45) return "danger";
  if (s.score >= 20) return "amber";
  return "ok";
};

const statusTone = (status: string) => {
  switch (status) {
    case "VERIFIED":
    case "CONSISTENT":
      return "ok";
    case "ANOMALOUS":
    case "INDICATIVE":
      return "danger";
    case "REDUCED_RELIABILITY":
    case "LIMITED":
      return "amber";
    default:
      return "muted";
  }
};

export const formatConsistency = (s?: string | null): string => {
  if (!s) return "Not enough evidence for a reliable conclusion";
  switch (s.toUpperCase()) {
    case "STRONG_CONSISTENCY":
      return "Multiple checks support the same finding";
    case "MODERATE_CONSISTENCY":
      return "Most checks support the same finding";
    case "MIXED":
      return "Checks show mixed results";
    case "CONFLICTING":
      return "Important checks disagree";
    case "INSUFFICIENT":
      return "Not enough evidence for a reliable conclusion";
    default:
      return s.replace(/_/g, " ");
  }
};

const METRIC_LABELS: Record<string, string> = {
  blockiness: "Compression artifacts",
  blockiness_ratio: "Compression blockiness",
  sensor_noise_residual: "Sensor noise",
  high_freq_energy: "High-frequency detail",
  dct_std: "Compression-domain variation",
  temporal_continuity: "Frame-to-frame consistency",
  noise_residual: "Noise residual",
  compression_blockiness: "Compression blockiness",
  sharpness_laplacian: "Edge sharpness (Laplacian)",
  dynamic_range: "Dynamic range",
  noise_variance: "Sensor noise floor variance",
  ela_mean_diff: "Error Level Analysis delta",
};

export default function AnalysisScreen() {
  return (
    <RequireEvidence>
      {(ev) => <AnalysisBody evidenceRef={ev.evidence_ref} evidence={ev} />}
    </RequireEvidence>
  );
}

function AnalysisBody({ evidenceRef, evidence }: { evidenceRef: string; evidence?: Evidence }) {
  const a = useApi<AnalysisPayload>(`/evidence/${evidenceRef}/analysis`);
  const frames = useApi<FramesPayload>(`/evidence/${evidenceRef}/frames`);
  const cross = useApi<CrossSignalAssessment>(`/evidence/${evidenceRef}/cross-signal-assessment`);
  const prov = useApi<ProvenanceTrace>(`/evidence/${evidenceRef}/provenance-trace`);
  const [activeTrace, setActiveTrace] = useState<string>("noise_residual");
  const [viewMode, setViewMode] = useState<"side_by_side" | "trace_only" | "original_only">("side_by_side");
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayData, setReplayData] = useState<ReplayResult | null>(null);
  const [replayError, setReplayError] = useState<string | null>(null);

  const runReplay = async () => {
    setReplayLoading(true);
    setReplayError(null);
    try {
      const res = await api.post<ReplayResult>(`/evidence/${evidenceRef}/replay`);
      setReplayData(res);
    } catch (err) {
      setReplayError((err as Error).message || "Failed to execute case replay.");
    } finally {
      setReplayLoading(false);
    }
  };

  return (
    <>
      <PageHead
        eyebrow="Step 2 · Forensic analysis & evidence matrix"
        title="Multi-Signal Forensic Assessment"
        sub="Synthesizes cryptographic integrity, physical sensor noise, compression physics, display recapture, and AI-synthetic neural signals into a transparent, defensible forensic assessment."
        right={
          <Button onClick={runReplay} disabled={replayLoading} tone="ghost">
            <RefreshCw size={13} className={replayLoading ? "animate-spin" : ""} />
            {replayLoading ? "Replaying case…" : "Verify case reproducibility"}
          </Button>
        }
      />

      {/* Investigation Pipeline Workflow Stepper */}
      <div className="mb-5 overflow-x-auto rounded-xl border border-line bg-surface/80 p-3">
        <div className="flex min-w-[760px] items-center justify-between gap-1 text-[11px]">
          {[
            { label: "1. Intake", status: "complete", path: "/upload" },
            { label: "2. Hash & Verify", status: "complete", path: "/analysis" },
            { label: "3. Classical Signals", status: "complete", path: "/analysis" },
            { label: "4. Neural ViT", status: a.data?.neural_detector_loaded ? "complete" : "warning", path: "/neural" },
            { label: "5. Recapture", status: "complete", path: "/recapture" },
            { label: "6. Visual Traces", status: "complete", path: "#visual-traces" },
            { label: "7. Stress Validation", status: "complete", path: "/stress" },
            { label: "8. Origin Graph", status: "complete", path: "/graph" },
            { label: "9. Court Packet", status: "complete", path: "/packet" },
          ].map((st, i, arr) => (
            <div key={i} className="flex items-center gap-1">
              <span className={`inline-flex items-center gap-1 rounded-md px-2 py-1 font-semibold ${
                st.status === "complete" ? "bg-ok/10 text-ok border border-ok/25" :
                st.status === "warning" ? "bg-amber/10 text-amber border border-amber/25" :
                "bg-s2 text-muted border border-line"
              }`}>
                {st.status === "complete" && <CheckCircle2 size={11} />}
                {st.status === "warning" && <AlertTriangle size={11} />}
                {st.label}
              </span>
              {i < arr.length - 1 && <span className="text-muted/40 font-mono">→</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Replay Results Card (when active) */}
      {replayData && (
        <div className="mb-5 rounded-xl border border-accent/40 bg-accent/[0.04] p-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-accent/20 pb-3">
            <div className="flex items-center gap-2">
              <FileCheck size={18} className="text-accent" />
              <span className="text-[14px] font-bold text-ink">Deterministic Forensic Replay Verification</span>
              <Chip tone={replayData.ok ? "ok" : "danger"}>
                {replayData.ok ? "DETERMINISTICALLY REPRODUCED" : "DIVERGENCE DETECTED"}
              </Chip>
            </div>
            <div className="flex items-center gap-2 text-[11px] font-mono text-muted">
              <span>Device: {replayData.device}</span>
              <span>•</span>
              <span>Replay Time: {replayData.replay_time_ms} ms</span>
            </div>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-3 text-[11.5px]">
            <div className="rounded-lg border border-line bg-surface p-2.5">
              <span className="text-muted">Stored SHA-256:</span>
              <div className="font-mono text-xs text-ink truncate mt-0.5">{replayData.stored_sha256}</div>
            </div>
            <div className="rounded-lg border border-line bg-surface p-2.5">
              <span className="text-muted">Replayed SHA-256:</span>
              <div className="font-mono text-xs text-ink truncate mt-0.5">{replayData.recomputed_sha256}</div>
            </div>
            <div className="rounded-lg border border-line bg-surface p-2.5">
              <span className="text-muted">Cryptographic Match:</span>
              <div className="font-semibold text-ok mt-0.5">
                {replayData.hash_immutable ? "Exact Byte Match (Immutable)" : "MISMATCH (Altered)"}
              </div>
            </div>
          </div>

          <div className="mt-3.5">
            <Table head={["Measured Stream", "Stored Value", "Replayed Value", "Delta (Δ)", "Status"]}>
              {replayData.comparisons.map((c, idx) => (
                <Row key={idx}>
                  <Cell className="font-medium text-ink">{c.field}</Cell>
                  <Cell mono>{String(c.stored)}</Cell>
                  <Cell mono>{String(c.replayed)}</Cell>
                  <Cell mono className={c.delta && Math.abs(c.delta) > 0.5 ? "text-amber" : "text-ink2"}>
                    {c.delta != null ? `${c.delta > 0 ? "+" : ""}${c.delta.toFixed(2)}` : "—"}
                  </Cell>
                  <Cell>
                    <Chip tone={c.match ? "ok" : "danger"} dot={false}>
                      {c.match ? "PASS" : "FAIL"}
                    </Chip>
                  </Cell>
                </Row>
              ))}
            </Table>
          </div>
        </div>
      )}

      {replayError && (
        <div className="mb-4 rounded-lg border border-danger/35 bg-danger/[0.07] px-3.5 py-2.5 text-[11.5px] text-danger">
          {replayError}
        </div>
      )}

      {/* Forensic Decision & Evidence Explanation Card */}
      {a.data && (
        <ForensicDecisionCard analysis={a.data} cross={cross.data} />
      )}

      {/* Executive Forensic Decision Transparency Card */}
      {cross.data && (
        <div className="mb-5">
          <Panel
            title="Forensic Decision Transparency & Assessment"
            hint="Structured answers to the 7 essential judicial forensic inquiries."
          >
            {/* Header badges */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3.5">
              <div className="flex items-center gap-2.5">
                <Sparkles size={18} className="text-accent" />
                <span className="text-[16px] font-bold text-ink">{cross.data.synthesis_headline}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={cross.data.evidence_state === "CONSISTENT" ? "ok" : cross.data.evidence_state === "PARTIALLY_CORROBORATED" ? "amber" : cross.data.evidence_state === "CONFLICTING" ? "danger" : "muted"}>
                  Evidence State: {cross.data.evidence_state}
                </Chip>
                <Chip
                  tone={cross.data.signal_consistency === "STRONG_CONSISTENCY" ? "ok" : cross.data.signal_consistency === "MODERATE_CONSISTENCY" ? "accent" : cross.data.signal_consistency === "MIXED" ? "amber" : "danger"}
                  title="Shows whether independent checks point in the same direction."
                >
                  Signal Agreement: {formatConsistency(cross.data.signal_consistency)}
                </Chip>
                <Chip tone={cross.data.quality_status === "RELIABLE" ? "ok" : "amber"}>
                  Quality Gate: {cross.data.quality_status}
                </Chip>
              </div>
            </div>

            {/* Evidence State Rationale */}
            <div className="mt-3.5 rounded-lg border border-line bg-s2/40 px-4 py-3">
              <div className="text-[11px] font-bold text-ink uppercase tracking-wider">
                Why SROT Assigned This Evidence State:
              </div>
              <p className="mt-1 text-[12px] leading-relaxed text-ink2">
                {cross.data.evidence_state_rationale}
              </p>
            </div>

            {/* 7 Core Forensic Answers Grid */}
            <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {/* Q1: What was analyzed? */}
              <div className="rounded-lg border border-line bg-surface p-3">
                <div className="text-[11px] font-semibold text-accent uppercase tracking-wider mb-1">
                  1. Target of Analysis
                </div>
                <p className="text-[11.5px] text-ink2 leading-relaxed">
                  Evidence <span className="font-mono text-ink">{evidenceRef}</span> ({String(a.data?.container?.format_name ?? "Media Container")} · {a.data?.frames_sampled ?? 8} sampled keyframes).
                </p>
              </div>

              {/* Q2: Primary Finding */}
              <div className="rounded-lg border border-line bg-surface p-3">
                <div className="text-[11px] font-semibold text-accent uppercase tracking-wider mb-1">
                  2. Primary Observed Finding
                </div>
                <p className="text-[11.5px] text-ink2 leading-relaxed">
                  {cross.data.synthesis_narrative}
                </p>
              </div>

              {/* Q3: Neural Score Semantics */}
              <div className="rounded-lg border border-line bg-surface p-3">
                <div className="text-[11px] font-semibold text-accent uppercase tracking-wider mb-1">
                  3. Neural Signal Semantics
                </div>
                <p className="text-[11.5px] text-ink2 leading-relaxed">
                  <span className="font-semibold text-ink">{cross.data.score_semantics}</span>: {cross.data.score_semantics_note}
                </p>
              </div>

              {/* Q4: Agreeing Signals */}
              <div className="rounded-lg border border-ok/30 bg-ok/[0.03] p-3">
                <div className="text-[11px] font-semibold text-ok uppercase tracking-wider mb-1">
                  4. Corroborating Signals ({cross.data.corroborating_factors.length})
                </div>
                <ul className="space-y-1 text-[11px] text-ink2">
                  {cross.data.corroborating_factors.map((cf, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-ok font-bold">•</span>
                      <span>{cf}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Q5: Disagreeing / Caveats */}
              <div className="rounded-lg border border-amber/35 bg-amber/[0.04] p-3">
                <div className="text-[11px] font-semibold text-amber uppercase tracking-wider mb-1">
                  5. Disagreements & Safeguards
                </div>
                <ul className="space-y-1 text-[11px] text-ink2">
                  {cross.data.dissenting_or_neutral_factors.map((df, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-amber font-bold">•</span>
                      <span>{df}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Q6: Recommended Next Step */}
              <div className="rounded-lg border border-accent/30 bg-accent/[0.03] p-3">
                <div className="text-[11px] font-semibold text-accent uppercase tracking-wider mb-1">
                  6. Next Investigative Step
                </div>
                <ul className="space-y-1 text-[11px] text-ink2">
                  {cross.data.investigative_recommendations.slice(0, 2).map((rec, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="font-mono text-accent">[{idx + 1}]</span>
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Panel>
        </div>
      )}

      <Async state={a} rows={6}>
        {(d) => (
          <>
            {/* Primary Ensemble & Quality Gate */}
            <div className="mb-5 grid gap-4 lg:grid-cols-[1.1fr_1fr]">
              <Panel title="Assessment & Forensic Signal Ensemble Summary" hint="Combined assessment from multiple independent forensic checks.">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="text-[26px] font-bold leading-none text-ink">{d.assessment}</div>
                  <Chip tone={bandTone(d.confidence_band)}>{d.confidence_band} confidence</Chip>
                </div>
                <div className="mt-4">
                  <div className="mb-1.5 flex items-center justify-between text-[11.5px]">
                    <span className="text-muted">Aggregate indicator score</span>
                    <span className="font-mono tabular-nums text-ink">
                      {fmtNum(d.aggregate_score)} / 100
                    </span>
                  </div>
                  <Meter value={d.aggregate_score ?? 0} tone={bandTone(d.confidence_band)} />
                </div>
                <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3.5">
                  <Field label="Detector backend"><span className="font-mono text-[11px]">{d.detector_backend}</span></Field>
                  <Field label="Frames sampled">{d.frames_sampled}</Field>
                  <div className="col-span-2">
                    <Field label="Aggregation formula">
                      <span className="font-mono text-[10.5px] leading-relaxed">{d.aggregation_formula}</span>
                    </Field>
                  </div>
                </div>
                <div className="mt-4">
                  <Notice kind="warn">
                    {d.neural_detector_loaded ? (
                      <>
                        Assessment is produced by a weighted ensemble of classical forensic measurements augmented by an AI-synthetic image signal (<span className="font-mono">neural_detector_loaded = true</span>). This is a forensic decision-support signal, not a definitive determination of authenticity or manipulation.
                      </>
                    ) : (
                      <>
                        No trained neural model is active in this run (<span className="font-mono">neural_detector_loaded = false</span>). The assessment is an ensemble of classical forensic measurements and must not be read as a definitive determination of authenticity or manipulation.
                      </>
                    )}
                  </Notice>
                </div>
              </Panel>

              {/* Image Quality Gate */}
              {d.quality_gate ? (
                <Panel title="Image Quality & Forensic Gating" hint="Pre-analysis quality assessment determining signal reliability.">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {d.quality_gate.reliability_status === "RELIABLE" ? (
                        <ShieldCheck size={20} className="text-ok" />
                      ) : (
                        <ShieldAlert size={20} className="text-amber" />
                      )}
                      <div>
                        <div className="text-[13px] font-semibold text-ink">
                          Grade: {d.quality_gate.quality_grade}
                        </div>
                        <div className="text-[10.5px] text-muted">
                          Reliability: {d.quality_gate.reliability_status}
                        </div>
                      </div>
                    </div>
                    <Chip tone={d.quality_gate.reliability_status === "RELIABLE" ? "ok" : "amber"}>
                      Quality Score: {d.quality_gate.quality_score_pct}%
                    </Chip>
                  </div>

                  <div className="mt-3.5 grid grid-cols-2 gap-x-3 gap-y-2 text-[11px]">
                    {(evidence?.width || typeof d.container?.width === "number") && (evidence?.height || typeof d.container?.height === "number") && (
                      <div className="flex justify-between border-b border-lineSoft py-1">
                        <span className="text-muted" title="Original dimensions of the uploaded media file.">Source resolution</span>
                        <span className="font-mono text-ink2">{String(evidence?.width || d.container?.width)}×{String(evidence?.height || d.container?.height)}</span>
                      </div>
                    )}
                    <div className="flex justify-between border-b border-lineSoft py-1">
                      <span className="text-muted" title="Frame actually passed through the analysis preprocessing pipeline.">Analysis frame resolution (post-preprocessing)</span>
                      <span className="font-mono text-ink2">{d.quality_gate.metrics.width}×{d.quality_gate.metrics.height} ({d.quality_gate.metrics.megapixels} MP)</span>
                    </div>
                    <div className="flex justify-between border-b border-lineSoft py-1">
                      <span className="text-muted">Sharpness (Laplacian)</span>
                      <span className="font-mono text-ink2">{d.quality_gate.metrics.sharpness_laplacian}</span>
                    </div>
                    <div className="flex justify-between border-b border-lineSoft py-1">
                      <span className="text-muted">Dynamic Range</span>
                      <span className="font-mono text-ink2">{d.quality_gate.metrics.dynamic_range} / 255</span>
                    </div>
                    <div className="flex justify-between border-b border-lineSoft py-1">
                      <span className="text-muted">Compression artifacts (Blockiness ratio)</span>
                      <span className="font-mono text-ink2">{d.quality_gate.metrics.blockiness_ratio}</span>
                    </div>
                  </div>

                  <div className="mt-2 text-[10px] text-muted italic">
                    Source resolution is the original media dimensions. Analysis frame resolution is the frame actually passed through the analysis preprocessing pipeline.
                  </div>

                  <div className="mt-3 rounded bg-s2/40 p-2.5 text-[10.5px] text-ink2">
                    <p className="font-medium text-ink">{d.quality_gate.impact_summary}</p>
                    {d.quality_gate.gating_factors.length > 0 && (
                      <ul className="mt-1.5 space-y-0.5 text-muted">
                        {d.quality_gate.gating_factors.map((gf, i) => (
                          <li key={i}>• {gf}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </Panel>
              ) : (
                <Panel title="Signal agreement">
                  <div className="space-y-3">
                    <AgreeGroup label="Signals indicating manipulation" tone="danger" items={d.supporting} />
                    <AgreeGroup label="Signals not indicating manipulation" tone="ok" items={d.counter} />
                    <AgreeGroup label="Could not be measured" tone="muted" items={d.unmeasured} />
                  </div>
                </Panel>
              )}
            </div>

            {/* Explicit Evidence Matrix Table */}
            {cross.data?.evidence_matrix && (
              <div className="mb-5">
                <Panel
                  title="Explicit Evidence Matrix"
                  hint="Forensic evidence source-by-source mapping with observations, strength, and scientific boundaries."
                >
                  <Table head={["Evidence Source", "Observation & Measurement", "Strength", "Status", "Operational Limitation"]}>
                    {cross.data.evidence_matrix.map((em, idx) => (
                      <Row key={idx}>
                        <Cell className="font-semibold text-ink whitespace-nowrap">{em.source}</Cell>
                        <Cell className="text-ink2 leading-relaxed">{em.observation}</Cell>
                        <Cell><Chip tone={em.strength === "STRONG" ? "ok" : em.strength === "MODERATE" ? "accent" : "muted"}>{em.strength}</Chip></Cell>
                        <Cell><Chip tone={statusTone(em.status)} dot={false}>{em.status}</Chip></Cell>
                        <Cell className="text-[10.5px] text-muted leading-relaxed max-w-[280px]">{em.limitation}</Cell>
                      </Row>
                    ))}
                  </Table>
                </Panel>
              </div>
            )}

            {/* Interactive Side-by-Side Visual Forensic Trace Inspector */}
            <div id="visual-traces" className="mb-5">
              <Panel
                title="Spatial Forensic Trace & Side-by-Side Localization Inspector"
                hint="Compare reference frames against false-color high-pass noise residuals, ELA compression deltas, and edge gradients."
              >
                {/* Controls */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[11.5px] font-semibold text-ink">Trace Mode:</span>
                    <div className="flex gap-1.5">
                      <Button
                        tone={activeTrace === "noise_residual" ? "primary" : "ghost"}
                        className="text-xs py-1 px-2.5"
                        onClick={() => setActiveTrace("noise_residual")}
                      >
                        Sensor Noise Residual
                      </Button>
                      <Button
                        tone={activeTrace === "ela_residual" ? "primary" : "ghost"}
                        className="text-xs py-1 px-2.5"
                        onClick={() => setActiveTrace("ela_residual")}
                      >
                        Error Level Analysis (ELA)
                      </Button>
                      <Button
                        tone={activeTrace === "gradient_inconsistency" ? "primary" : "ghost"}
                        className="text-xs py-1 px-2.5"
                        onClick={() => setActiveTrace("gradient_inconsistency")}
                      >
                        High-Frequency Gradient
                      </Button>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-[11.5px] font-semibold text-ink">View:</span>
                    <Button
                      tone={viewMode === "side_by_side" ? "primary" : "ghost"}
                      className="text-xs py-1 px-2"
                      onClick={() => setViewMode("side_by_side")}
                    >
                      Side-by-Side (2-Up)
                    </Button>
                    <Button
                      tone={viewMode === "trace_only" ? "primary" : "ghost"}
                      className="text-xs py-1 px-2"
                      onClick={() => setViewMode("trace_only")}
                    >
                      Trace Only
                    </Button>
                    <Button
                      tone={viewMode === "original_only" ? "primary" : "ghost"}
                      className="text-xs py-1 px-2"
                      onClick={() => setViewMode("original_only")}
                    >
                      Original Frame
                    </Button>
                  </div>
                </div>

                {/* Side-by-Side Images */}
                <div className={`mt-4 grid gap-4 ${viewMode === "side_by_side" ? "md:grid-cols-2" : "grid-cols-1 max-w-[560px] mx-auto"}`}>
                  {(viewMode === "side_by_side" || viewMode === "original_only") && (
                    <div className="flex flex-col items-center">
                      <div className="mb-2 text-[11.5px] font-semibold text-ink">Original Reference Frame</div>
                      <div className="overflow-hidden rounded-lg border border-line bg-black w-full flex justify-center">
                        <img
                          src={authenticatedUrl(`/api/evidence/${evidenceRef}/frames/0/image`)}
                          alt="Original evidence frame"
                          className="block max-h-[340px] w-auto object-contain"
                          loading="lazy"
                        />
                      </div>
                    </div>
                  )}

                  {(viewMode === "side_by_side" || viewMode === "trace_only") && (
                    <div className="flex flex-col items-center">
                      <div className="mb-2 text-[11.5px] font-semibold text-accent">
                        {activeTrace === "noise_residual" && "Sensor Noise Residual (Viridis Heatmap)"}
                        {activeTrace === "ela_residual" && "Error Level Analysis (Inferno Heatmap)"}
                        {activeTrace === "gradient_inconsistency" && "Sobel Gradient Magnitude (Turbo Heatmap)"}
                      </div>
                      <div className="overflow-hidden rounded-lg border border-line bg-black w-full flex justify-center">
                        <img
                          src={authenticatedUrl(`/api/evidence/${evidenceRef}/traces/${activeTrace}`)}
                          alt={`Forensic trace ${activeTrace}`}
                          className="block max-h-[340px] w-auto object-contain"
                          loading="lazy"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Legend & Scientific Boundaries */}
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div className="rounded-lg border border-line bg-s2/30 p-3.5">
                    <div className="text-[12px] font-bold text-ink mb-1">
                      What This Visualization Can Reveal
                    </div>
                    <p className="text-[11px] leading-relaxed text-ink2">
                      {activeTrace === "noise_residual" &&
                        "Isolates sensor noise floor. Natural camera lenses distribute stochastic photon noise evenly; AI synthetic rendering or pasted patches appear as flat, smooth, or discontinuous noise variance."}
                      {activeTrace === "ela_residual" &&
                        "Displays quantization error differentials against a Q=90 baseline. Regions saved under differing compression algorithms or spliced from another source appear noticeably brighter."}
                      {activeTrace === "gradient_inconsistency" &&
                        "Highlights spatial gradient spikes. Digital text, mobile UI overlays, and vector graphics generate razor-sharp edges compared to optical camera lens roll-off."}
                    </p>
                  </div>

                  <div className="rounded-lg border border-line bg-s2/30 p-3.5">
                    <div className="text-[12px] font-bold text-amber mb-1">
                      What This Visualization Cannot Prove
                    </div>
                    <p className="text-[11px] leading-relaxed text-ink2">
                      {activeTrace === "noise_residual" &&
                        "Heavy JPEG compression or aggressive downscaling attenuates high-frequency noise floor naturally, which can mimic synthetic smoothness without malicious manipulation."}
                      {activeTrace === "ela_residual" &&
                        "High-contrast natural edges (e.g. tree branches against sky) inherently produce higher error differentials without constituting digital splicing."}
                      {activeTrace === "gradient_inconsistency" &&
                        "Native camera UI graphics (e.g., date stamps) are genuine physical overlays and must not be misinterpreted as malicious content modification."}
                    </p>
                  </div>
                </div>
              </Panel>
            </div>

            {/* Forensic Debug & Data-Provenance Mode */}
            <div className="mb-5">
              <Panel
                title="Forensic Data-Provenance & Pipeline Audit Trace"
                hint="Audit proof: displays the isolated origin of each finding (NEW_FILE vs REFERENCE_CORPUS) to verify no results were inherited."
                right={
                  prov.data?.all_stages_isolated ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-ok/10 px-2.5 py-0.5 text-[11px] font-semibold text-ok border border-ok/30">
                      <ShieldCheck size={12} /> Verified Isolated Pipeline
                    </span>
                  ) : undefined
                }
              >
                <Async state={prov} rows={4}>
                  {(pt) => (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px] rounded-lg border border-line bg-surface/40 p-2.5">
                        <div><span className="text-muted">Evidence Ref:</span> <span className="font-mono text-accent font-semibold">{pt.evidence_ref}</span></div>
                        <div><span className="text-muted">Case Container:</span> <span className="font-mono text-ink font-semibold">{pt.case_ref}</span></div>
                        <div><span className="text-muted">Filename:</span> <span className="text-ink font-medium">{pt.filename}</span></div>
                        <div><span className="text-muted">Media Kind:</span> <span className="text-ink uppercase font-semibold">{pt.media_kind}</span></div>
                      </div>

                      <div className="overflow-x-auto rounded-lg border border-line">
                        <table className="w-full text-left text-[11px]">
                          <thead className="border-b border-line bg-surface/80 text-muted font-semibold">
                            <tr>
                              <th className="p-2.5">#</th>
                              <th className="p-2.5">Pipeline Stage</th>
                              <th className="p-2.5">Source Attribution</th>
                              <th className="p-2.5">Observed Value / Finding</th>
                              <th className="p-2.5">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-line/40">
                            {pt.stages.map((st, idx) => (
                              <tr key={st.stage} className="hover:bg-s2/30">
                                <td className="p-2.5 text-muted font-mono">{idx + 1}</td>
                                <td className="p-2.5 font-medium text-ink">{st.name}</td>
                                <td className="p-2.5">
                                  <span className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold font-mono ${
                                    st.source === "NEW_FILE" ? "bg-ok/15 text-ok border border-ok/30" :
                                    st.source === "REFERENCE_CORPUS" ? "bg-accent/15 text-accent border border-accent/30" :
                                    st.source === "CASE_CONTEXT" ? "bg-amber/15 text-amber border border-amber/30" :
                                    "bg-muted/15 text-muted border border-line"
                                  }`}>
                                    {st.source}
                                  </span>
                                </td>
                                <td className="p-2.5 text-ink2 max-w-[360px] truncate" title={st.value}>
                                  {st.value}
                                </td>
                                <td className="p-2.5">
                                  <span className={`text-[10px] font-semibold ${st.status === "COMPLETED" ? "text-ok" : "text-muted"}`}>
                                    {st.status}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </Async>
              </Panel>
            </div>

            {/* Classical Signal Breakdown */}
            <div className="mb-5">
              <Panel title="Classical Signal Breakdown" hint="Expand a row to see the raw measurement and the method that produced it.">
                <Table head={["Signal", "Result", "Score", "Weight", "Strength", ""]}>
                  {d.signals.map((s) => <SignalRow key={s.key} s={s} />)}
                </Table>
              </Panel>
            </div>

            {/* Frame-level suspicion */}
            <div className="mb-5">
              <Panel title="Frame-level suspicion"
                     hint="Per-frame scores from the same measurements. Frames are sampled across the
                           whole clip, and the peak frame is where an examiner should look first.">
                <Async state={frames} rows={3}
                       empty={<EmptyState title="No frame analysis recorded." />}>
                  {(f) => f.frames.length === 0 ? (
                    <EmptyState title="No frames were analysed."
                                detail="This happens for still images, or where no frame could be extracted." />
                  ) : (
                    <FrameStrip frames={f.frames} peak={f.peak} />
                  )}
                </Async>
              </Panel>
            </div>

            {/* Stated Limitations */}
            <Panel title="Stated limitations"
                   hint="Derived from what actually happened in this run — an absent finding is stated as absent.">
              <ul className="space-y-1.5">
                {d.limitations.map((l, i) => (
                  <li key={i} className="flex gap-2.5 text-[11.5px] leading-relaxed text-ink2">
                    <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-muted" />{l}
                  </li>
                ))}
              </ul>
            </Panel>
          </>
        )}
      </Async>
    </>
  );
}

function AgreeGroup({ label, tone, items }:
  { label: string; tone: "danger" | "ok" | "muted"; items: string[] }) {
  return (
    <div>
      <div className="lbl mb-1.5">{label}</div>
      {items.length === 0 ? (
        <span className="text-[11.5px] text-muted">None</span>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {items.map((n) => <Chip key={n} tone={tone}>{n}</Chip>)}
        </div>
      )}
    </div>
  );
}

function SignalRow({ s }: { s: Signal }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Row>
        <Cell className="font-medium text-ink">{s.name}</Cell>
        <Cell>{s.result}</Cell>
        <Cell className="w-[130px]">
          {s.score == null ? <span className="text-muted">Not measured</span> : (
            <div className="flex items-center gap-2">
              <span className="w-[38px] shrink-0 font-mono tabular-nums">{fmtNum(s.score, 1)}</span>
              <Meter value={s.score} tone={dirTone(s)} />
            </div>
          )}
        </Cell>
        <Cell mono>{s.weight.toFixed(1)}</Cell>
        <Cell><Chip tone={dirTone(s)} dot={false}>{s.strength}</Chip></Cell>
        <Cell className="w-[34px]">
          <button onClick={() => setOpen((o) => !o)} aria-expanded={open}
                  aria-label={`${open ? "Hide" : "Show"} measurement for ${s.name}`}
                  className="rounded p-1 text-muted hover:bg-s2 hover:text-ink">
            <ChevronDown size={14} className={`transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
        </Cell>
      </Row>
      {open && (
        <Row tone="bg-s2/40">
          <td colSpan={6} className="px-2.5 py-3">
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="Method">{s.method}</Field>
              <Field label="Note">{s.note}</Field>
              <div className="md:col-span-2">
                <div className="lbl mb-1.5">Raw measurement</div>
                <pre className="max-h-56 overflow-auto rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-[10.5px] leading-relaxed text-ink2">
{JSON.stringify(s.measurement, null, 2)}
                </pre>
              </div>
            </div>
          </td>
        </Row>
      )}
    </>
  );
}

function FrameStrip({ frames, peak }: {
  frames: FramesPayload["frames"]; peak: FramesPayload["peak"];
}) {
  const [sel, setSel] = useState(peak?.frame_index ?? frames[0].frame_index);
  const chosen = frames.find((f) => f.frame_index === sel) ?? frames[0];
  const max = Math.max(...frames.map((f) => f.score ?? 0), 1);

  return (
    <>
      <div className="flex items-end gap-[3px]" role="group" aria-label="Frame suspicion scores">
        {frames.map((f) => {
          const h = Math.max(((f.score ?? 0) / max) * 76, 4);
          const isPeak = peak?.frame_index === f.frame_index;
          return (
            <button
              key={f.frame_index}
              onClick={() => setSel(f.frame_index)}
              title={`Frame ${f.frame_number ?? f.frame_index} · score ${fmtNum(f.score, 1)}`}
              aria-label={`Frame ${f.frame_index}, score ${fmtNum(f.score, 1)}`}
              className={`flex-1 rounded-t transition-opacity hover:opacity-100 ${
                sel === f.frame_index ? "opacity-100 ring-1 ring-accent" : "opacity-75"
              } ${isPeak ? "bg-amber" : "bg-accent"}`}
              style={{ height: h }}
            />
          );
        })}
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-muted">
        <span>frame {frames[0].frame_index}</span>
        <span>{frames.length} sampled frames · amber = peak</span>
        <span>frame {frames[frames.length - 1].frame_index}</span>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,240px)_1fr]">
        <div className="mx-auto w-fit overflow-hidden rounded-lg border border-line bg-black">
          <img src={authenticatedUrl(chosen.image_url)} alt={`Sampled frame ${chosen.frame_index}`}
               className="block max-h-[360px] w-auto" loading="lazy" />
        </div>
        <div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            <Field label="Frame index">{chosen.frame_index}</Field>
            <Field label="Frame number">{chosen.frame_number ?? "—"}</Field>
            <Field label="Timestamp">
              {chosen.timestamp_s != null ? `${chosen.timestamp_s.toFixed(2)} s` : "—"}
            </Field>
            <Field label="Frame score">{fmtNum(chosen.score, 1)}</Field>
          </div>
          <div className="mt-3">
            <div className="lbl mb-1.5">Measured metrics for this frame</div>
            <MetricTree value={chosen.metrics ?? {}} />
          </div>
        </div>
      </div>
    </>
  );
}

function MetricTree({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value == null) return <span className="text-muted">—</span>;
  if (Array.isArray(value)) {
    return (
      <span className="font-mono text-[10.5px] text-ink2">
        [{value.map((v) => (typeof v === "number" ? v.toFixed(4) : String(v))).join(", ")}]
      </span>
    );
  }
  if (typeof value === "object") {
    return (
      <div className={depth === 0 ? "space-y-2" : "mt-1 space-y-0.5 border-l border-lineSoft pl-2.5"}>
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => {
          const nested = v !== null && typeof v === "object" && !Array.isArray(v);
          return (
            <div key={k} className={nested ? "" : "flex justify-between gap-3 border-b border-lineSoft py-1 last:border-0"}>
              <span className={`text-[11px] ${nested ? "font-semibold text-ink2" : "text-muted"}`} title={k}>
                {METRIC_LABELS[k] ?? k}
              </span>
              {nested ? <MetricTree value={v} depth={depth + 1} />
                      : <span className="shrink-0 text-right"><MetricTree value={v} depth={depth + 1} /></span>}
            </div>
          );
        })}
      </div>
    );
  }
  return (
    <span className="font-mono text-[11px] tabular-nums text-ink2">
      {typeof value === "number"
        ? (Number.isInteger(value) ? value.toString() : value.toFixed(4))
        : String(value)}
    </span>
  );
}

function ForensicDecisionCard({
  analysis,
  cross,
}: {
  analysis: AnalysisPayload;
  cross?: CrossSignalAssessment | null;
}) {
  const assessment = analysis.assessment || "Inconclusive";
  const confidenceBand = analysis.confidence_band || "LOW";
  const isInc = assessment.toLowerCase().includes("inconclusive");
  const isManipulated = assessment.toLowerCase().includes("manipulated");

  // Deterministic explanation of why SROT reached this result
  const deterministicRationale = (() => {
    if (isInc) {
      const qGate = analysis.quality_gate;
      const isQualityRestricted =
        qGate &&
        (qGate.reliability_status === "INSUFFICIENT_EVIDENCE" ||
          qGate.reliability_status === "REDUCED_RELIABILITY");
      const hasConflictingSignals =
        (analysis.counter &&
          analysis.counter.length > 0 &&
          analysis.supporting &&
          analysis.supporting.length > 0) ||
        (cross &&
          (cross.signal_consistency === "CONFLICTING" ||
            cross.signal_consistency === "MIXED"));
      const isRecaptured = cross?.evidence_matrix?.some(
        (m) =>
          m.source.toLowerCase().includes("recapture") &&
          (m.status === "INDICATIVE" || m.status === "ANOMALOUS")
      );

      if (isQualityRestricted) {
        return `Multiple forensic signals were evaluated independently. Due to quality constraints (${qGate?.reliability_status}, Grade: ${qGate?.quality_grade}), the available signals do not provide sufficient corroboration for a definitive manipulation conclusion, so the result remains inconclusive.`;
      }
      if (isRecaptured && hasConflictingSignals) {
        return `Multiple forensic signals were evaluated independently. While screen-recording indicators and elevated neural scores are present, dissenting classical compression and sensor-noise signals prevent mutual corroboration for a definitive manipulation conclusion, so the result remains inconclusive.`;
      }
      if (hasConflictingSignals) {
        return `Multiple forensic signals were evaluated independently. Dissenting and counter-balancing signals (${analysis.supporting.length} indicating, ${analysis.counter.length} counter) do not provide sufficient corroboration for a definitive manipulation conclusion, so the result remains inconclusive.`;
      }
      return "Multiple forensic signals were evaluated independently. The available signals do not provide sufficient corroboration for a definitive manipulation conclusion, so the result remains inconclusive.";
    }

    if (cross?.evidence_state_rationale) {
      return cross.evidence_state_rationale;
    }

    if (isManipulated) {
      return `Multiple forensic signals were evaluated independently. Corroborating physical, compression, and neural indicators (${analysis.supporting.length} indicating manipulation) exceed the decision threshold, supporting an assessment of potential manipulation.`;
    }

    return "Multiple forensic signals were evaluated independently. All physical, compression, and neural measurements fall within baseline parameters, consistent with standard authentic media.";
  })();

  // 1. Neural Signal finding
  const neuralFinding = (() => {
    const matItem = cross?.evidence_matrix?.find(
      (m) =>
        m.source.toLowerCase().includes("synthetic") ||
        m.source.toLowerCase().includes("neural")
    );
    if (matItem?.observation) return matItem.observation;

    const sig = analysis.signals.find(
      (s) =>
        s.key === "neural_detector" ||
        s.name.toLowerCase().includes("synthetic")
    );
    if (sig) {
      if (sig.score != null) {
        return `AI-synthetic model score: ${fmtNum(sig.score, 1)} / 100 (${sig.result}). Model score, not a calibrated probability.`;
      }
      return "Neural detector signal unavailable for this container.";
    }
    if (!analysis.neural_detector_loaded) {
      return "No trained neural model active in this run; unmeasured.";
    }
    return "Neural signal evaluated within baseline limits.";
  })();

  // 2. Forensic Ensemble finding
  const ensembleFinding = (() => {
    const agg =
      analysis.aggregate_score != null
        ? `${fmtNum(analysis.aggregate_score, 1)} / 100`
        : "Unmeasured";
    const suppCount = analysis.supporting?.length || 0;
    const countCount = analysis.counter?.length || 0;
    return `Combined assessment: ${agg} across ${analysis.frames_sampled} sampled keyframes (${suppCount} indicating manipulation, ${countCount} counter-indicator(s)).`;
  })();

  // 3. Recapture result finding
  const recaptureFinding = (() => {
    const matItem = cross?.evidence_matrix?.find((m) =>
      m.source.toLowerCase().includes("recapture")
    );
    if (matItem?.observation) return matItem.observation;
    return "No secondary screen-recapture or static interface borders detected.";
  })();

  // 4. Provenance / Origin result finding
  const provenanceFinding = (() => {
    const parts: string[] = [];
    if (analysis.provenance.c2pa_present) {
      parts.push("Signed content provenance information (C2PA Manifest) detected.");
    } else {
      parts.push("No C2PA credentials found in this file. This does not by itself indicate manipulation.");
    }

    const originItem = cross?.evidence_matrix?.find(
      (m) =>
        m.source.toLowerCase().includes("origin") ||
        m.source.toLowerCase().includes("propagation")
    );
    if (originItem?.observation) {
      parts.push(originItem.observation);
    } else if (analysis.provenance.exif_fields === 0) {
      parts.push("Metadata: EXIF tags removed during transmission.");
    } else {
      parts.push(`${analysis.provenance.exif_fields} EXIF tags preserved.`);
    }
    return parts.join(" ");
  })();

  // 5. Cross-Signal Assessment finding
  const crossSignalFinding = (() => {
    if (cross) {
      return `${cross.evidence_state} (${formatConsistency(cross.signal_consistency)}) — ${cross.synthesis_headline}.`;
    }
    return `${analysis.assessment} (${analysis.confidence_band} confidence band).`;
  })();

  // Evidence supporting the assessment
  const supportingEvidence = (() => {
    const items: string[] = [];
    if (cross?.corroborating_factors && cross.corroborating_factors.length > 0) {
      items.push(...cross.corroborating_factors);
    } else if (analysis.supporting && analysis.supporting.length > 0) {
      for (const name of analysis.supporting) {
        const s = analysis.signals.find((sig) => sig.name === name);
        if (s && s.score != null) {
          items.push(`${s.name}: score ${fmtNum(s.score, 1)}/100 (${s.result}) indicates elevated anomaly.`);
        } else {
          items.push(`${name} indicates elevated anomaly.`);
        }
      }
    }
    if (items.length === 0) {
      items.push("No individual forensic signal independently exceeded the manipulation threshold.");
    }
    return items;
  })();

  // Evidence limiting confidence
  const limitingEvidence = (() => {
    const items: string[] = [];
    if (cross?.dissenting_or_neutral_factors && cross.dissenting_or_neutral_factors.length > 0) {
      items.push(...cross.dissenting_or_neutral_factors);
    }
    if (analysis.counter && analysis.counter.length > 0) {
      items.push(`Counter-indicators conforming to baseline: ${analysis.counter.join(", ")}.`);
    }
    if (analysis.unmeasured && analysis.unmeasured.length > 0) {
      items.push(`Unmeasured or unavailable streams: ${analysis.unmeasured.join(", ")}.`);
    }
    if (analysis.quality_gate && analysis.quality_gate.reliability_status !== "RELIABLE") {
      items.push(
        `Image Quality Gate is ${analysis.quality_gate.reliability_status} (${analysis.quality_gate.quality_grade}): high-frequency signal sensitivity is attenuated.`
      );
    }
    if (items.length === 0) {
      items.push("Absence of hardware-level cryptographic key or immutable camera trust anchor.");
    }
    return items;
  })();

  // What the examiner should review next
  const nextSteps = (() => {
    const steps: string[] = [];
    if (cross?.investigative_recommendations && cross.investigative_recommendations.length > 0) {
      steps.push(...cross.investigative_recommendations);
    }
    if (analysis.frames_sampled > 0) {
      steps.push("Inspect the peak suspicious keyframe in the Spatial Visual Trace Inspector for localized noise/compression discontinuities.");
    }
    if (analysis.provenance.c2pa_present) {
      steps.push("Verify the C2PA cryptographic signature chain against the department trust store.");
    } else {
      steps.push("Query the searched reference corpus to trace earliest known copies and identify any prior syndication.");
    }
    return steps.slice(0, 3);
  })();

  return (
    <div className="mb-5 rounded-xl border border-line bg-surface/90 p-4 shadow-panel">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <Scale size={16} className="text-accent" />
          <span className="text-[12px] font-bold uppercase tracking-wider text-ink">
            FORENSIC DECISION &amp; EVIDENCE EXPLANATION
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone={isInc ? "amber" : isManipulated ? "danger" : "ok"}>
            {assessment.toUpperCase()}
          </Chip>
          <Chip tone={bandTone(confidenceBand)}>
            {confidenceBand.toUpperCase()} CONFIDENCE
          </Chip>
        </div>
      </div>

      {/* Why SROT reached this result */}
      <div className="mt-3 rounded-lg border border-line bg-s2/40 px-3.5 py-2.5">
        <div className="text-[11px] font-bold uppercase tracking-wider text-ink">
          Why SROT reached this result
        </div>
        <p className="mt-1 text-[11.5px] leading-relaxed text-ink2">
          {deterministicRationale}
        </p>
      </div>

      {/* Why this result? — 5 Signal streams */}
      <div className="mt-3.5">
        <div className="text-[11px] font-bold uppercase tracking-wider text-ink mb-1.5">
          Why this result?
        </div>
        <ul className="space-y-1.5 text-[11.5px] text-ink2">
          <li className="flex items-start gap-1.5">
            <span className="text-accent font-bold leading-none mt-0.5">•</span>
            <span>
              <strong className="text-ink">Existing neural signal:</strong> {neuralFinding}
            </span>
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-accent font-bold leading-none mt-0.5">•</span>
            <span>
              <strong className="text-ink">Existing forensic signal ensemble:</strong> {ensembleFinding}
            </span>
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-accent font-bold leading-none mt-0.5">•</span>
            <span>
              <strong className="text-ink">Existing recapture result:</strong> {recaptureFinding}
            </span>
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-accent font-bold leading-none mt-0.5">•</span>
            <span>
              <strong className="text-ink">Existing provenance/origin result:</strong> {provenanceFinding}
            </span>
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-accent font-bold leading-none mt-0.5">•</span>
            <span>
              <strong className="text-ink">Existing cross-signal assessment:</strong> {crossSignalFinding}
            </span>
          </li>
        </ul>
      </div>

      {/* Supporting vs Limiting Evidence Grid */}
      <div className="mt-3.5 grid gap-3 md:grid-cols-2 pt-2 border-t border-line/60">
        <div className="rounded-lg border border-ok/25 bg-ok/[0.02] p-2.5">
          <div className="text-[10.5px] font-bold uppercase tracking-wider text-ok mb-1.5">
            Evidence supporting the assessment
          </div>
          <ul className="space-y-1 text-[11px] text-ink2">
            {supportingEvidence.map((item, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="text-ok font-bold leading-none mt-0.5">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-amber/25 bg-amber/[0.02] p-2.5">
          <div className="text-[10.5px] font-bold uppercase tracking-wider text-amber mb-1.5">
            Evidence limiting confidence
          </div>
          <ul className="space-y-1 text-[11px] text-ink2">
            {limitingEvidence.map((item, idx) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="text-amber font-bold leading-none mt-0.5">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Recommended Examiner Next Steps */}
      <div className="mt-3.5 pt-2.5 border-t border-line/60">
        <div className="text-[10.5px] font-bold uppercase tracking-wider text-accent mb-1.5">
          What the examiner should review next
        </div>
        <ul className="space-y-1 text-[11px] text-ink2">
          {nextSteps.map((step, idx) => (
            <li key={idx} className="flex items-start gap-1.5">
              <span className="font-mono text-accent font-bold">[{idx + 1}]</span>
              <span>{step}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Footer / Safeguard notice */}
      <div className="mt-3 flex items-center gap-1.5 pt-2 text-[10.5px] text-muted border-t border-line/40">
        <AlertTriangle size={12} className="text-amber shrink-0" />
        <span className="font-semibold text-amber">Requires examiner review</span>
        <span>
          — Forensic decision-support signal only; does not independently establish authenticity or manipulation.
        </span>
      </div>
    </div>
  );
}
