import { useState } from "react";
import {
  CheckCircle2, AlertTriangle,
} from "lucide-react";
import {
  Async, Chip, Notice, PageHead, Panel, Table, Row, Cell, Stat,
} from "../components/ui";
import { useApi } from "../lib/api";

type BenchmarkSample = {
  index: number;
  id: string;
  category: string;
  ground_truth: string;
  description: string;
  sha256: string;
  dimensions: string;
  quality_grade: string;
  reliability_status: string;
  quality_score_pct: number;
  sensor_noise_score: number;
  dct_benford_score: number;
  blockiness_score: number;
  recompression_score: number;
  recapture_likelihood: string;
  recapture_score: number;
  neural_score_pct?: number | null;
  evidence_state?: string;
  signal_consistency?: string;
  synthesis_headline?: string;
  trace_metrics?: {
    noise_uniformity?: number;
    ela_mean_diff?: number;
    grad_p95?: number;
  };
  latency_ms: number;
};

type BenchmarkData = {
  timestamp_utc: string;
  total_samples: number;
  total_duration_seconds: number;
  mean_latency_ms: number;
  confusion_matrix: {
    true_positives: number;
    false_positives: number;
    true_negatives: number;
    false_negatives: number;
  };
  metrics: {
    tpr_recall: number;
    tnr_specificity: number;
    fpr: number;
    fnr: number;
    precision: number;
    f1_score: number;
    signal_disagreement_rate: number;
    authentic_post_processing_survival_rate: number;
    synthetic_post_processing_survival_rate: number;
  };
  results: BenchmarkSample[];
};

function gtTone(gt?: string): "muted" | "danger" | "violet" | "amber" {
  const g = (gt || "").toUpperCase();
  if (g === "AUTHENTIC") return "muted";
  if (g === "SYNTHETIC" || g === "MANIPULATED") return "danger";
  if (g === "RECAPTURED") return "violet";
  if (g === "LAUNDERED") return "amber";
  return "muted";
}

function stateTone(st?: string): "ok" | "accent" | "danger" | "muted" {
  const s = (st || "").toUpperCase();
  if (s === "CONSISTENT") return "ok";
  if (s === "PARTIALLY_CORROBORATED") return "accent";
  if (s === "CONFLICTING") return "danger";
  return "muted";
}

function formatConsistency(s?: string | null): string {
  if (!s) return "—";
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
}

export default function Benchmark() {
  const b = useApi<BenchmarkData>("/benchmark/adversarial-summary", []);
  const [activeTab, setActiveTab] = useState<string>("ALL");

  return (
    <>
      <PageHead
        eyebrow="Verification & Validation · Multi-Signal Adversarial Test Bench"
        title="Internal Adversarial Validation Benchmark"
        sub="Tests cover authentic media, AI-generated media, manipulated media, and common post-processing attacks across 27 reference samples."
      />

      <div className="mb-4">
        <Notice kind="info">
          <b>Internal validation results on the current benchmark. These metrics are not universal real-world accuracy.</b> This dataset is a curated technical test bench designed to measure signal behavior, failure boundaries, and cross-signal safeguards. It is not a statistical field population and does not claim uniform general-population accuracy.
        </Notice>
      </div>

      <Async state={b}>
        {(data) => {
          const categories = [
            "ALL",
            "Authentic Original",
            "Synthetic / AI Generated",
            "Face Swap / Spliced",
            "Display Recapture",
            "Laundering & Compression",
          ];

          const filtered = activeTab === "ALL"
            ? data.results || []
            : (data.results || []).filter((r) => {
                const cat = (r.category || "").toLowerCase();
                if (activeTab === "Authentic Original") return cat.includes("authentic");
                if (activeTab === "Synthetic / AI Generated") return cat.includes("synthetic") || cat.includes("ai");
                if (activeTab === "Face Swap / Spliced") return cat.includes("spliced") || cat.includes("face") || cat.includes("manipulated");
                if (activeTab === "Display Recapture") return cat.includes("recapture") || cat.includes("screenshot");
                if (activeTab === "Laundering & Compression") return cat.includes("laundering") || cat.includes("compression");
                return true;
              });

          return (
            <div className="space-y-4">
              {/* Stat Summary Grid */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                <Stat
                  label="Total Test Bench"
                  value={String(data.total_samples || 0)}
                  sub="27 reference samples"
                />
                <Stat
                  label="Mean Latency"
                  value={`${(data.mean_latency_ms || 0).toFixed(0)} ms`}
                  sub="Apple MPS / CPU"
                />
                <Stat
                  label="Recall (TPR)"
                  value={`${((data.metrics?.tpr_recall ?? 0) * 100).toFixed(1)}%`}
                  sub="Of target-class samples, how many were detected."
                />
                <Stat
                  label="Specificity (TNR)"
                  value={`${((data.metrics?.tnr_specificity ?? 0) * 100).toFixed(1)}%`}
                  sub="Of authentic samples, how many were correctly unflagged."
                />
                <Stat
                  label="Precision"
                  value={`${((data.metrics?.precision ?? 0) * 100).toFixed(1)}%`}
                  sub="Of flagged samples, how many were actually target class."
                />
                <Stat
                  label="F1-Score"
                  value={`${((data.metrics?.f1_score ?? 0) * 100).toFixed(1)}%`}
                  sub="Combined measure of precision and recall."
                />
              </div>

              {/* Confusion Matrix & Safeguards Panel */}
              <div className="grid gap-4 lg:grid-cols-2">
                <Panel title={`Confusion matrix — n = ${(data.confusion_matrix?.true_positives ?? 0) + (data.confusion_matrix?.false_positives ?? 0) + (data.confusion_matrix?.false_negatives ?? 0) + (data.confusion_matrix?.true_negatives ?? 0)} binary-classified samples`}>
                  <div className="grid grid-cols-2 gap-2 text-center text-xs">
                    <div className="rounded-lg border border-ok/30 bg-ok/5 p-3">
                      <div className="text-[10.5px] font-semibold text-muted uppercase">True Positives</div>
                      <div className="text-xl font-bold text-ok">{data.confusion_matrix?.true_positives ?? 0}</div>
                      <div className="text-[10px] text-ink2 mt-0.5">Synthetic correctly flagged</div>
                    </div>
                    <div className="rounded-lg border border-danger/30 bg-danger/5 p-3">
                      <div className="text-[10.5px] font-semibold text-muted uppercase">False Positives</div>
                      <div className="text-xl font-bold text-danger">{data.confusion_matrix?.false_positives ?? 0}</div>
                      <div className="text-[10px] text-ink2 mt-0.5">Authentic flagged as synthetic</div>
                    </div>
                    <div className="rounded-lg border border-danger/30 bg-danger/5 p-3">
                      <div className="text-[10.5px] font-semibold text-muted uppercase">False Negatives</div>
                      <div className="text-xl font-bold text-danger">{data.confusion_matrix?.false_negatives ?? 0}</div>
                      <div className="text-[10px] text-ink2 mt-0.5">Synthetic categorized inconclusive</div>
                    </div>
                    <div className="rounded-lg border border-ok/30 bg-ok/5 p-3">
                      <div className="text-[10.5px] font-semibold text-muted uppercase">True Negatives</div>
                      <div className="text-xl font-bold text-ok">{data.confusion_matrix?.true_negatives ?? 0}</div>
                      <div className="text-[10px] text-ink2 mt-0.5">Authentic correctly preserved</div>
                    </div>
                  </div>
                  <div className="mt-3 text-[11px] text-muted leading-relaxed">
                    False positive rate: <b>{((data.metrics?.fpr ?? 0) * 100).toFixed(2)}%</b> · False negative rate: <b>{((data.metrics?.fnr ?? 0) * 100).toFixed(2)}%</b>.
                    SROT deliberately opts for higher specificity on compressed and recaptured images to prevent wrongful accusations.
                  </div>
                  <div className="mt-2.5 rounded-lg border border-lineSoft bg-s2/50 p-2.5 text-[11px] text-muted leading-relaxed">
                    Remaining benchmark samples (4 samples: Face Swap / Spliced [3] and Display Recapture [1]) were evaluated separately because they belong to categories outside the binary confusion-matrix classification.
                  </div>
                </Panel>

                <Panel title="Safeguard & Post-Processing Survival">
                  <div className="space-y-2.5 text-xs">
                    <div className="flex items-center justify-between rounded-lg border border-line bg-s2 p-2.5">
                      <div>
                        <div className="font-semibold text-ink">Signal Disagreement Rate</div>
                        <div className="text-[10.5px] text-muted">Conflict between classical physics &amp; neural ViT</div>
                      </div>
                      <div className="font-mono font-bold text-accent">
                        {((data.metrics?.signal_disagreement_rate ?? 0) * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-line bg-s2 p-2.5">
                      <div>
                        <div className="font-semibold text-ink">Authentic Post-Processing Survival</div>
                        <div className="text-[10.5px] text-muted">Resilience under social-media recompression</div>
                      </div>
                      <div className="font-mono font-bold text-ok">
                        {((data.metrics?.authentic_post_processing_survival_rate ?? 0) * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-line bg-s2 p-2.5">
                      <div>
                        <div className="font-semibold text-ink">Synthetic Post-Processing Survival</div>
                        <div className="text-[10.5px] text-muted">Detection retention under crop &amp; resample</div>
                      </div>
                      <div className="font-mono font-bold text-ok">
                        {((data.metrics?.synthetic_post_processing_survival_rate ?? 0) * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                </Panel>
              </div>

              {/* Sample Table with Filter Tabs */}
              <Panel
                title="Adversarial Validation Benchmark Samples"
                right={
                  <div className="flex items-center gap-1 overflow-x-auto">
                    {categories.map((c) => (
                      <button
                        key={c}
                        onClick={() => setActiveTab(c)}
                        className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                          activeTab === c
                            ? "bg-accent text-white"
                            : "bg-s2 text-ink2 hover:bg-s3 hover:text-ink"
                        }`}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                }
              >
                <Table
                  head={[
                    "#",
                    "Sample ID",
                    "Category",
                    "Ground Truth",
                    "Evidence State",
                    "Signal Consistency",
                    "Neural Score",
                    "Recapture Indication",
                    "Quality",
                    "Latency",
                  ]}
                >
                  {filtered.map((r) => {
                    const isConsistent = (r.signal_consistency || "").includes("STRONG") || (r.evidence_state || "").includes("CONSISTENT");

                    return (
                      <Row key={r.id}>
                        <Cell><span className="font-mono text-muted">{r.index}</span></Cell>
                        <Cell>
                          <div className="font-mono text-[11px] font-semibold text-ink">{r.id}</div>
                          <div className="text-[9.5px] text-muted truncate max-w-[150px]">{r.description || r.synthesis_headline || "—"}</div>
                        </Cell>
                        <Cell><span className="text-[11px] text-ink2">{r.category}</span></Cell>
                        <Cell>
                          <Chip tone={gtTone(r.ground_truth)}>{r.ground_truth || "—"}</Chip>
                        </Cell>
                        <Cell>
                          <div className="flex items-center gap-1.5">
                            {isConsistent ? (
                              <CheckCircle2 size={12} className="text-ok shrink-0" />
                            ) : (
                              <AlertTriangle size={12} className="text-amber shrink-0" />
                            )}
                            <Chip tone={stateTone(r.evidence_state)}>{r.evidence_state || "—"}</Chip>
                          </div>
                        </Cell>
                        <Cell>
                          <span className="text-[11px] text-ink2">
                            {formatConsistency(r.signal_consistency)}
                          </span>
                        </Cell>
                        <Cell>
                          <span className="font-mono text-[11px]">
                            {r.neural_score_pct != null ? `${r.neural_score_pct.toFixed(1)} / 100` : "—"}
                          </span>
                        </Cell>
                        <Cell>
                          <Chip tone={(r.recapture_likelihood || "").toUpperCase() === "HIGH" ? "amber" : "muted"}>
                            {r.recapture_likelihood || "—"}
                          </Chip>
                        </Cell>
                        <Cell>
                          <span className="text-[10.5px] font-mono text-ink2">{r.quality_grade || "—"}</span>
                        </Cell>
                        <Cell>
                          <span className="font-mono text-[10.5px] text-muted">{(r.latency_ms || 0).toFixed(0)} ms</span>
                        </Cell>
                      </Row>
                    );
                  })}
                </Table>
              </Panel>
            </div>
          );
        }}
      </Async>
    </>
  );
}
