import { Cpu, AlertTriangle, CheckCircle, HelpCircle, Info, ShieldAlert, Scale } from "lucide-react";
import {
  Async, Chip, EmptyState, Field, Meter, Notice, PageHead, Panel, Table, Row, Cell,
} from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { useSession } from "../state/session";
import { useApi, fmtNum } from "../lib/api";
import type { CaseComparisonPayload } from "../lib/api";

type FrameResult = {
  frame_index: number;
  frame_number: number | null;
  timestamp_s: number | null;
  score: number | null;
  label: string;
  raw_output: Record<string, number>;
  inference_time_ms: number;
  error: string | null;
};

type NeuralPayload = {
  evidence_ref: string;
  model_available: boolean;
  frames_analysed: number;
  frame_results: FrameResult[];
  aggregate: {
    median_score: number | null;
    mean_score: number | null;
    max_score: number | null;
    suspicious_frames: number;
    assessment: string;
    assessment_level?: string;
    assessment_text?: string;
    model_score_pct?: number | null;
  } | null;
  screenshot_caution?: boolean;
  caution_message?: string | null;
  disclaimer?: string;
  multi_signal_note?: string;
  empty_reason?: string;
  provenance: {
    model: string;
    model_id: string;
    version: string;
    revision?: string;
    architecture: string;
    source: string;
    license: string;
    license_note?: string;
    scope?: string;
    training_domain: string;
    limitations: string[];
    device: string;
    load_time_ms: number | null;
  };
};

const assessmentTone = (a?: string): "danger" | "amber" | "accent" | "muted" => {
  const level = (a || "").toLowerCase();
  if (level.includes("strong") || level === "high") return "danger";
  if (level.includes("moderate") || level === "medium") return "amber";
  if (level.includes("low")) return "accent";
  return "muted";
};

const assessmentIcon = (a?: string) => {
  const level = (a || "").toLowerCase();
  if (level.includes("strong") || level === "high" || level.includes("moderate") || level === "medium") {
    return <AlertTriangle size={18} />;
  }
  if (level.includes("low")) return <CheckCircle size={18} />;
  return <HelpCircle size={18} />;
};

const scoreTone = (s: number | null): "danger" | "amber" | "accent" | "ok" | "muted" => {
  if (s == null) return "muted";
  if (s >= 0.75) return "danger";
  if (s >= 0.5) return "amber";
  if (s >= 0.3) return "accent";
  return "ok";
};

export default function Neural() {
  return (
    <RequireEvidence>
      {(ev) => <NeuralBody key={ev.evidence_ref} evidenceRef={ev.evidence_ref} />}
    </RequireEvidence>
  );
}

function NeuralBody({ evidenceRef }: { evidenceRef: string }) {
  const data = useApi<NeuralPayload>(`/evidence/${evidenceRef}/neural-analysis`);
  const { caseRef } = useSession();
  const comparison = useApi<CaseComparisonPayload>(caseRef ? `/cases/${caseRef}/comparison` : null);

  const activeComp = comparison.data?.comparisons?.find(
    (c) => c.derivative_evidence_ref === evidenceRef
  );
  const isRef = comparison.data?.reference?.evidence_ref === evidenceRef;

  return (
    <>
      <PageHead
        eyebrow="Forensic Media Analysis"
        title="AI-SYNTHETIC IMAGE SIGNAL"
        sub="Frame-level synthetic-image signal from a local Vision Transformer (ViT). Decision-support signal only — not proof of manipulation or authenticity."
      />

      <Async state={data} rows={4}>
        {(d) => d.frames_analysed === 0 ? (
          <EmptyState
            title="AI-Synthetic Signal Unavailable"
            detail={d.empty_reason || "The neural model was not available when this evidence was analysed."}
          />
        ) : (
          <>
            {/* Authentic Reference Corroboration Panel */}
            {comparison.data?.has_reference && comparison.data.reference && (
              <div className="mb-4 rounded-xl border border-accent/25 bg-surface p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-lineSoft pb-2.5">
                  <div className="flex items-center gap-2">
                    <Scale size={15} className="text-accent" />
                    <span className="text-[12px] font-bold text-ink">
                      Comparative Ground Truth Corroboration
                    </span>
                    {isRef ? (
                      <Chip tone="ok" className="text-[10px]">CURRENT ITEM IS CAMERA REFERENCE</Chip>
                    ) : (
                      <Chip tone="amber" className="text-[10px]">EVALUATED AGAINST CASE REFERENCE</Chip>
                    )}
                  </div>
                  <div className="text-[11px] text-muted">
                    Reference: <span className="font-mono font-semibold text-accent">{comparison.data.reference.evidence_ref}</span> ({comparison.data.reference.filename})
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-[11.5px]">
                  <div className="rounded border border-line bg-s2/40 p-2.5">
                    <span className="block text-[10px] uppercase font-semibold text-muted">Authentic Reference Signal</span>
                    <div className="font-mono font-bold text-[15px] text-ink mt-0.5">
                      {activeComp?.ai_signal.reference_score != null ? `${activeComp.ai_signal.reference_score}%` : isRef ? `${((d.aggregate?.median_score ?? 0) * 100).toFixed(1)}%` : "Baseline intact"}
                    </div>
                    <span className="text-[10px] text-muted block mt-0.5">Physical camera sensor baseline</span>
                  </div>

                  <div className="rounded border border-line bg-s2/40 p-2.5">
                    <span className="block text-[10px] uppercase font-semibold text-muted">Current Item Signal</span>
                    <div className="font-mono font-bold text-[15px] text-amber mt-0.5">
                      {d.aggregate?.median_score != null ? `${(d.aggregate.median_score * 100).toFixed(1)}%` : "—"}
                    </div>
                    <span className="text-[10px] text-muted block mt-0.5">{isRef ? "Reference baseline" : "Derivative under examination"}</span>
                  </div>

                  <div className="rounded border border-line bg-s2/40 p-2.5">
                    <span className="block text-[10px] uppercase font-semibold text-muted">Pairwise Signal Delta</span>
                    <div className="font-mono font-bold text-[15px] text-accent mt-0.5">
                      {activeComp?.ai_signal.delta != null ? `${activeComp.ai_signal.delta > 0 ? "+" : ""}${fmtNum(activeComp.ai_signal.delta)}%` : isRef ? "0.0% (Baseline)" : "—"}
                    </div>
                    <span className="text-[10px] text-muted block mt-0.5">
                      {activeComp?.visual.ssim ? `Corroborated: SSIM ${activeComp.visual.ssim}` : "Decision-support delta"}
                    </span>
                  </div>
                </div>

                <div className="mt-2.5 text-[10.5px] text-muted italic">
                  MODEL SIGNAL BOUNDARY: Swin-ViT model scores indicate pattern resemblance to synthetic datasets, NOT legal certainty. SROT enforces multi-signal corroboration before establishing forensic findings.
                </div>
              </div>
            )}

            {/* Screenshot safety notice (when screenshot/recapture detected) */}
            {d.screenshot_caution && (
              <div className="mb-4">
                <Notice kind="warn">
                  <div className="flex items-start gap-2">
                    <ShieldAlert size={16} className="mt-0.5 shrink-0 text-amber" />
                    <div>
                      <strong className="text-amber">Forensic Safeguard — Screenshot Caution</strong>
                      <p className="mt-0.5 text-xs text-ink">
                        {d.caution_message || "Model result requires caution: screenshot/recaptured imagery may produce elevated synthetic-image scores."}
                      </p>
                    </div>
                  </div>
                </Notice>
              </div>
            )}

            {/* Headline Assessment & Provenance */}
            <div className="mb-4 grid gap-4 lg:grid-cols-[1.2fr_1fr]">
              <Panel title="Signal Assessment">
                <div className="flex items-center gap-3 mb-3">
                  {assessmentIcon(d.aggregate?.assessment_level || d.aggregate?.assessment || "")}
                  <span className="text-xl font-semibold">
                    {d.aggregate?.assessment_level
                      ? `${d.aggregate.assessment_level} model signal`
                      : (d.aggregate?.assessment || "N/A")}
                  </span>
                  <Chip tone={assessmentTone(d.aggregate?.assessment_level || d.aggregate?.assessment || "")}>
                    AI-Synthetic Signal
                  </Chip>
                </div>

                <div className="mb-3 rounded-lg border border-line bg-s2/60 p-3">
                  <div className="text-xs font-semibold text-muted uppercase tracking-wider">Model Headline Metric</div>
                  <div className="text-lg font-bold text-ink mt-0.5">
                    AI-synthetic model score:{" "}
                    <span className={scoreTone(d.aggregate?.median_score ?? null) === "danger" ? "text-danger" : scoreTone(d.aggregate?.median_score ?? null) === "amber" ? "text-amber" : "text-accent"}>
                      {d.aggregate?.median_score != null ? `${(d.aggregate.median_score * 100).toFixed(1)} / 100` : "—"}
                    </span>
                  </div>
                  <p className="text-xs text-muted mt-1">
                    Model score, not a calibrated probability. Assessment: {d.aggregate?.assessment_text || "Model indicates a decision-support synthetic-image signal."}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-3">
                  <Field label="Median score">
                    <Meter value={(d.aggregate?.median_score ?? 0) * 100}
                           tone={scoreTone(d.aggregate?.median_score ?? null)} />
                    <span className="text-sm text-zinc-400">
                      {d.aggregate?.median_score != null ? `${(d.aggregate.median_score * 100).toFixed(1)} / 100` : "—"}
                    </span>
                  </Field>
                  <Field label="Mean score">
                    <span className="text-sm">
                      {d.aggregate?.mean_score != null ? `${(d.aggregate.mean_score * 100).toFixed(1)} / 100` : "—"}
                    </span>
                  </Field>
                  <Field label="Max frame score">
                    <span className="text-sm">
                      {d.aggregate?.max_score != null ? `${(d.aggregate.max_score * 100).toFixed(1)} / 100` : "—"}
                    </span>
                  </Field>
                  <Field label="Suspicious frames (score ≥ 60 / 100)">
                    <span className="text-sm">
                      {d.aggregate?.suspicious_frames ?? 0} / {d.frames_analysed}
                    </span>
                  </Field>
                </div>
                <div className="text-xs text-zinc-500">
                  Frames analysed: {d.frames_analysed} (evenly sampled with start/middle/end anchors)
                </div>
              </Panel>

              <Panel title="Model provenance & scope">
                <div className="space-y-2 text-sm">
                  <Field label="Model">{d.provenance.model}</Field>
                  <Field label="Architecture">{d.provenance.architecture}</Field>
                  <Field label="Analysis type">Frame-level synthetic-image signal</Field>
                  <Field label="Source">
                    <a href={d.provenance.source} className="text-sky-400 hover:underline" target="_blank" rel="noopener">
                      {d.provenance.model_id}
                    </a>
                  </Field>
                  {d.provenance.revision && (
                    <Field label="Commit revision">
                      <span className="font-mono text-xs text-muted" title={d.provenance.revision}>
                        {d.provenance.revision.slice(0, 10)}…
                      </span>
                    </Field>
                  )}
                  <Field label="License">
                    <span className="font-semibold text-ink">{d.provenance.license}</span>
                  </Field>
                  <Field label="Device">
                    {d.provenance.device === "mps" ? "Apple MPS / Metal GPU" : d.provenance.device.toUpperCase()}
                  </Field>
                  {d.provenance.load_time_ms != null && (
                    <Field label="Load time">{d.provenance.load_time_ms} ms</Field>
                  )}
                  {d.provenance.license_note && (
                    <div className="mt-2 text-[11px] text-muted border-t border-line/60 pt-2 leading-relaxed">
                      <strong>License Notice:</strong> {d.provenance.license_note}
                    </div>
                  )}
                </div>
              </Panel>
            </div>

            {/* Frame-level results table */}
            <Panel title="Frame-level synthetic-image scores" hint="Each sampled frame is evaluated individually by the Vision Transformer without temporal smoothing.">
              <Table head={["Frame", "Timestamp", "Model score", "Verdict label", "Raw model outputs", "Inference time"]}>
                {d.frame_results.map((fr) => (
                  <Row key={fr.frame_index}>
                    <Cell>
                      #{fr.frame_index}
                      {fr.frame_number != null && ` (f${fr.frame_number})`}
                    </Cell>
                    <Cell>
                      {fr.timestamp_s != null ? `${fr.timestamp_s.toFixed(2)}s` : "—"}
                    </Cell>
                    <Cell>
                      {fr.score != null ? (
                        <span className="flex items-center gap-2">
                          <Meter value={fr.score * 100} tone={scoreTone(fr.score)} />
                          <span className="text-sm font-mono font-medium">{(fr.score * 100).toFixed(1)} / 100</span>
                        </span>
                      ) : fr.error ? (
                        <span className="text-red-400 text-xs">{fr.error}</span>
                      ) : "—"}
                    </Cell>
                    <Cell>
                      <Chip tone={scoreTone(fr.score)}>{fr.label || "—"}</Chip>
                    </Cell>
                    <Cell>
                      <span className="text-xs text-zinc-400 font-mono">
                        {Object.entries(fr.raw_output || {}).map(([k, v]) =>
                          `${k}: ${(v * 100).toFixed(1)} / 100`
                        ).join(", ")}
                      </span>
                    </Cell>
                    <Cell>{fr.inference_time_ms}ms</Cell>
                  </Row>
                ))}
              </Table>
            </Panel>

            {/* Mandatory Visible Scope & Limitations Notices */}
            <div className="mt-4">
              <Notice kind="warn">
                <div className="flex items-start gap-2">
                  <Info size={16} className="mt-0.5 shrink-0 text-amber" />
                  <div>
                    <strong>Model Scope &amp; Limitations Notice</strong>
                    <p className="mt-1 text-xs leading-relaxed text-ink">
                      This model is designed primarily for AI-generated artistic imagery and is not a standalone deepfake detector.
                      Results are one forensic decision-support signal and require expert review.
                    </p>
                    <ul className="list-disc ml-4 mt-2 text-xs space-y-0.5 text-ink2">
                      {d.provenance.limitations.map((l, i) => (
                        <li key={i}>{l}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </Notice>
            </div>

            {/* Multi-Signal Verification Notice */}
            <div className="mt-3">
              <Notice kind="info">
                <div className="flex items-start gap-2">
                  <Cpu size={16} className="mt-0.5 shrink-0 text-accent" />
                  <div className="text-xs leading-relaxed text-ink2">
                    <strong>Multi-Signal Independent Review Principle:</strong> Multiple independent forensic signals (Metadata, C2PA, Encoder, Frame artifacts, Recapture, Origin Trace, OCR, Campaign linking) should be reviewed together. No single signal establishes authenticity or manipulation.
                  </div>
                </div>
              </Notice>
            </div>
          </>
        )}
      </Async>
    </>
  );
}
