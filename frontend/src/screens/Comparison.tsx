import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, CheckCircle2, AlertTriangle,
  Scale, QrCode, RefreshCw
} from "lucide-react";
import {
  Async, Chip, EmptyState, Meter, Notice, PageHead, Panel, Table, Row, Cell, Stat,
} from "../components/ui";
import { useSession } from "../state/session";
import { useApi, fmtBytes, fmtDate, fmtNum, authenticatedUrl, api } from "../lib/api";
import type { CaseComparisonPayload, ForensicComparison } from "../lib/api";

export default function Comparison() {
  const { caseRef, detail, setEvidenceRef } = useSession();
  const comparisonApi = useApi<CaseComparisonPayload>(caseRef ? `/cases/${caseRef}/comparison` : null);
  const [selectedDerivativeRef, setSelectedDerivativeRef] = useState<string | null>(null);
  const [settingRef, setSettingRef] = useState(false);

  const handleSetReference = async (evRef: string) => {
    if (!caseRef) return;
    if (!confirm(`Designate ${evRef} as the Authentic Camera Reference baseline for case ${caseRef}?`)) return;
    setSettingRef(true);
    try {
      await api.post(`/cases/${caseRef}/set-reference`, { evidence_ref: evRef });
      comparisonApi.reload();
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setSettingRef(false);
    }
  };

  return (
    <>
      <PageHead
        eyebrow="Comparative Forensics · Authentic Reference Baseline"
        title="AUTHENTIC REFERENCE VS DERIVATIVE COMPARISON"
        sub="Rigorous pairwise evaluation between authenticated camera reference and manipulated derivatives. All signals, deltas, and difference heatmaps are computed deterministically from raw file bytes."
        right={
          <div className="flex items-center gap-2">
            <button onClick={() => comparisonApi.reload()} className="btn btn-ghost text-[12px] flex items-center gap-1.5">
              <RefreshCw size={13} />
              <span>Refresh Metrics</span>
            </button>
            <Link to="/packet" className="btn btn-primary text-[12px] flex items-center gap-1.5">
              <span>Court Packet</span>
              <ArrowRight size={13} />
            </Link>
          </div>
        }
      />

      <Async state={comparisonApi} rows={8}>
        {(data) => {
          if (!data.has_reference || !data.reference) {
            return (
              <EmptyState
                title="No authentic reference established for this case."
                detail="An authentic reference baseline provides an authenticated benchmark against which derivative files are compared. Upload or designate an authentic camera capture."
                action={
                  detail?.evidence && detail.evidence.length > 0 ? (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {detail.evidence.map((ev) => (
                        <button
                          key={ev.evidence_ref}
                          onClick={() => handleSetReference(ev.evidence_ref)}
                          disabled={settingRef}
                          className="btn btn-ghost text-xs py-1 px-2.5"
                        >
                          Designate {ev.evidence_ref} as Reference
                        </button>
                      ))}
                    </div>
                  ) : (
                    <Link to="/upload" className="btn btn-primary text-xs mt-2">
                      Upload Evidence
                    </Link>
                  )
                }
              />
            );
          }

          const ref = data.reference;
          const comparisons = data.comparisons || [];
          const activeComparison: ForensicComparison | undefined =
            comparisons.find((c) => c.derivative_evidence_ref === selectedDerivativeRef) ||
            comparisons[0];

          return (
            <div className="space-y-6">
              {/* Scientific comparison boundaries notice */}
              <Notice kind="info">
                {data.scientific_boundaries ||
                  "SCIENTIFIC COMPARISON BOUNDARIES: SROT compares submitted items strictly within the available case corpus. No claim of universal internet-wide origin discovery is made. Visual delta indices and model signals represent technical decision-support metrics, not definitive human attribution."}
              </Notice>

              {/* Top Overview Cards: Authentic Reference Baseline */}
              <div className="rounded-xl border border-accent/30 bg-accent/[0.03] p-5 shadow-panel">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10.5px] font-bold uppercase tracking-wider text-accent">
                        Authentic Reference Baseline
                      </span>
                      <Chip tone="ok">AUTHENTIC CAMERA REFERENCE</Chip>
                      <Chip tone="muted">{ref.evidence_ref}</Chip>
                    </div>
                    <h2 className="mt-1.5 text-[19px] font-bold text-ink">
                      {ref.filename}
                    </h2>
                    <p className="mt-1 text-[12px] text-ink2 max-w-[85ch]">
                      {ref.classification_basis ||
                        "Authentic camera reference baseline in case custody. Serves as authenticated reference baseline used for comparative analysis of scene geometry, sensor noise, and text elements."}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <Stat label="Resolution" value={ref.width && ref.height ? `${ref.width}×${ref.height}` : "Original"} tone="accent" />
                    <Stat label="File Size" value={fmtBytes(ref.size_bytes)} tone="ink" />
                    <Stat label="EXIF Metadata" value={ref.exif_fields > 0 ? `${ref.exif_fields} Tags` : "Stripped"} tone={ref.exif_fields > 0 ? "ok" : "amber"} />
                    <Stat label="C2PA Manifest" value={ref.c2pa_present ? "Present" : "None"} tone="ink" />
                  </div>
                </div>

                <div className="mt-4 pt-3.5 border-t border-lineSoft flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono text-muted">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-ink2">SHA-256 Digest:</span>
                    <span className="text-ink">{ref.sha256}</span>
                  </div>
                  <div>
                    <span>Ingested: {fmtDate(ref.ingested_at)}</span>
                  </div>
                </div>
              </div>

              {/* Derivative Selection Bar */}
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <div className="lbl text-[11px] font-bold text-ink flex items-center gap-1.5">
                    <Scale size={14} className="text-accent" />
                    <span>Select Case Derivative to Compare ({comparisons.length} Evaluated)</span>
                  </div>
                  <span className="text-[11px] text-muted">
                    Click a derivative to examine pairwise deltas against reference
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {comparisons.map((c) => {
                    const isSelected = activeComparison?.derivative_evidence_ref === c.derivative_evidence_ref;
                    const roleLabel =
                      c.identity.derivative.forensic_role === "AI_GENERATED"
                        ? "AI-Generated"
                        : c.identity.derivative.forensic_role === "AI_MODIFIED"
                        ? "AI-Modified"
                        : c.identity.derivative.forensic_role === "RECAPTURED_COPY"
                        ? "Recaptured"
                        : "Derivative";

                    return (
                      <button
                        key={c.derivative_evidence_ref}
                        onClick={() => setSelectedDerivativeRef(c.derivative_evidence_ref)}
                        className={`text-left rounded-lg border p-3 transition-all ${
                          isSelected
                            ? "border-accent bg-accent/[0.08] shadow-md ring-1 ring-accent"
                            : "border-line bg-surface hover:bg-s2/60"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1.5">
                          <span className="font-mono text-[11px] font-bold text-accent">
                            {c.derivative_evidence_ref}
                          </span>
                          <Chip tone={roleLabel.includes("AI") ? "danger" : "amber"} className="text-[9.5px]">
                            {roleLabel}
                          </Chip>
                        </div>
                        <div className="mt-1 text-[11.5px] font-medium text-ink truncate">
                          {c.identity.derivative.filename}
                        </div>
                        <div className="mt-2 grid grid-cols-2 gap-1 text-[10px] text-muted">
                          <div>Similarity: <span className="font-bold text-ink">{fmtNum(c.visual.best_view_similarity)}%</span></div>
                          <div>SSIM: <span className="font-bold text-ink">{c.visual.ssim}</span></div>
                          <div>Model Signal: <span className="font-bold text-amber">{c.ai_signal.derivative_score ?? "—"}%</span></div>
                          <div>Added IDs: <span className="font-bold text-ink">{c.identifiers.added_count}</span></div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Active Pairwise Comparison Dossier */}
              {activeComparison && (
                <div className="space-y-6 pt-2">
                  {/* Pairwise Header / Summary Badge */}
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface p-4">
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-wider text-muted">
                        Active Pairwise Evaluation
                      </div>
                      <div className="text-[16px] font-bold text-ink mt-0.5">
                        {ref.evidence_ref} (Authentic Reference) ⟷ {activeComparison.derivative_evidence_ref} ({activeComparison.identity.derivative.filename})
                      </div>
                      <div className="text-[12px] text-accent font-medium mt-1">
                        Assessment: {activeComparison.assessment}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Link
                        to="/analysis"
                        onClick={() => setEvidenceRef(activeComparison.derivative_evidence_ref)}
                        className="btn btn-ghost text-xs flex items-center gap-1"
                      >
                        <span>Single-File Analysis</span>
                        <ArrowRight size={12} />
                      </Link>
                    </div>
                  </div>

                  {/* 3-Card Visual Comparison: Reference vs Derivative vs Heatmap */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Card 1: Authentic Reference */}
                    <Panel
                      title="1. Authentic Camera Reference"
                      hint="Physical camera baseline capture in police custody."
                      pad={false}
                    >
                      <div className="relative aspect-[4/3] bg-black/40 overflow-hidden flex items-center justify-center border-b border-lineSoft">
                        <img
                          src={authenticatedUrl(`/api/evidence/${ref.evidence_ref}/media`)}
                          alt={ref.filename}
                          className="max-h-full max-w-full object-contain"
                        />
                        <div className="absolute top-2 left-2">
                          <Chip tone="ok">REFERENCE BASELINE</Chip>
                        </div>
                      </div>
                      <div className="p-3.5 space-y-2 text-[11.5px]">
                        <div className="flex justify-between">
                          <span className="text-muted">Filename:</span>
                          <span className="font-mono text-ink truncate max-w-[180px]">{ref.filename}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Dimensions:</span>
                          <span className="font-mono text-ink">{ref.width}×{ref.height} px</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">EXIF Metadata:</span>
                          <span className="text-ok font-semibold">{ref.exif_fields} fields intact</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Model Signal:</span>
                          <span className="font-mono text-ink">{activeComparison.ai_signal.reference_score ?? "—"}%</span>
                        </div>
                      </div>
                    </Panel>

                    {/* Card 2: Selected Derivative */}
                    <Panel
                      title="2. Manipulated Derivative"
                      hint="Submitted/intercepted derivative media item."
                      pad={false}
                    >
                      <div className="relative aspect-[4/3] bg-black/40 overflow-hidden flex items-center justify-center border-b border-lineSoft">
                        <img
                          src={authenticatedUrl(`/api/evidence/${activeComparison.derivative_evidence_ref}/media`)}
                          alt={activeComparison.identity.derivative.filename}
                          className="max-h-full max-w-full object-contain"
                        />
                        <div className="absolute top-2 left-2">
                          <Chip tone="danger">DERIVATIVE COPY</Chip>
                        </div>
                      </div>
                      <div className="p-3.5 space-y-2 text-[11.5px]">
                        <div className="flex justify-between">
                          <span className="text-muted">Filename:</span>
                          <span className="font-mono text-ink truncate max-w-[180px]">{activeComparison.identity.derivative.filename}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Dimensions:</span>
                          <span className="font-mono text-ink">{activeComparison.identity.derivative.width}×{activeComparison.identity.derivative.height} px</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">EXIF Metadata:</span>
                          <span className={activeComparison.identity.derivative.exif_fields > 0 ? "text-ink" : "text-amber"}>
                            {activeComparison.identity.derivative.exif_fields > 0 ? `${activeComparison.identity.derivative.exif_fields} fields` : "Stripped"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Model Signal:</span>
                          <span className="font-mono font-bold text-amber">{activeComparison.ai_signal.derivative_score ?? "—"}%</span>
                        </div>
                      </div>
                    </Panel>

                    {/* Card 3: Difference Heatmap */}
                    <Panel
                      title="3. Spatial Difference Heatmap"
                      hint="Pixel & gradient delta: 35% derivative + 65% Magma colormap."
                      pad={false}
                    >
                      <div className="relative aspect-[4/3] bg-black/40 overflow-hidden flex items-center justify-center border-b border-lineSoft">
                        <img
                          src={authenticatedUrl(`/api/evidence/${activeComparison.derivative_evidence_ref}/traces/difference?ref_ref=${ref.evidence_ref}`)}
                          alt="Difference Heatmap"
                          className="max-h-full max-w-full object-contain"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = "none";
                          }}
                        />
                        <div className="absolute top-2 left-2">
                          <Chip tone="violet">MAGMA DELTA TRACE</Chip>
                        </div>
                      </div>
                      <div className="p-3.5 space-y-2 text-[11.5px]">
                        <div className="flex justify-between">
                          <span className="text-muted">Structural SSIM:</span>
                          <span className="font-mono font-bold text-ink">{activeComparison.visual.ssim}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Mean Pixel Shift:</span>
                          <span className="font-mono text-ink">{activeComparison.visual.mean_pixel_delta} Luma</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Edge Gradient Delta:</span>
                          <span className="font-mono text-ink">{activeComparison.visual.edge_delta}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted">Color Correlation:</span>
                          <span className="font-mono text-ink">{activeComparison.visual.color_histogram_correlation}</span>
                        </div>
                      </div>
                    </Panel>
                  </div>

                  <div className="text-[11px] text-muted italic px-1">
                    Heatmap note: Highlights localized manipulation, added donation banners, pasted QR codes, or altered portrait regions against the authentic baseline.
                  </div>

                  {/* Forensic Comparison Metrics Table */}
                  <Panel
                    title="Forensic Signals & Pairwise Differencing Matrix"
                    hint="Calculated across multi-view perceptual hashing, SSIM, sensor residual, quantization error, and offline Swin-ViT model signal."
                  >
                    <Table head={["Forensic Metric", "Authentic Reference", "Derivative Media", "Computed Delta", "Forensic Interpretation"]}>
                      <Row>
                        <Cell className="font-semibold text-ink">Perceptual Similarity</Cell>
                        <Cell mono>100% (Baseline)</Cell>
                        <Cell mono className="font-bold text-accent">{fmtNum(activeComparison.visual.best_view_similarity)}%</Cell>
                        <Cell mono>Hamming: {activeComparison.visual.best_view_distance}/64</Cell>
                        <Cell className="text-[11px]">
                          {activeComparison.visual.best_view_similarity > 80
                            ? "Substantial visual alignment; shared scene geometry and composition."
                            : "Partial visual match; heavy cropping, reformatting or severe re-synthesis."}
                        </Cell>
                      </Row>

                      <Row>
                        <Cell className="font-semibold text-ink">Structural SSIM</Cell>
                        <Cell mono>1.0000 (Identity)</Cell>
                        <Cell mono className="font-bold text-ink">{activeComparison.visual.ssim}</Cell>
                        <Cell mono>Δ = {fmtNum((1.0 - activeComparison.visual.ssim) * 100)}%</Cell>
                        <Cell className="text-[11px]">
                          True Gaussian-filtered Structural Similarity Index on aligned resolutions.
                        </Cell>
                      </Row>

                      <Row>
                        <Cell className="font-semibold text-ink">Color Histogram Corr</Cell>
                        <Cell mono>1.0000 (Identity)</Cell>
                        <Cell mono>{activeComparison.visual.color_histogram_correlation}</Cell>
                        <Cell mono>Δ = {fmtNum((1.0 - activeComparison.visual.color_histogram_correlation) * 100)}%</Cell>
                        <Cell className="text-[11px]">
                          2D HSV chromatic correlation; detects color grading, re-rendering, or synthetic palette shift.
                        </Cell>
                      </Row>

                      <Row>
                        <Cell className="font-semibold text-ink">Model Signal (AI/Synth)</Cell>
                        <Cell mono>{activeComparison.ai_signal.reference_score ?? "—"}%</Cell>
                        <Cell mono className="font-bold text-amber">{activeComparison.ai_signal.derivative_score ?? "—"}%</Cell>
                        <Cell mono className={activeComparison.ai_signal.delta && activeComparison.ai_signal.delta > 0 ? "text-danger" : "text-ok"}>
                          {activeComparison.ai_signal.delta != null ? `${activeComparison.ai_signal.delta > 0 ? "+" : ""}${fmtNum(activeComparison.ai_signal.delta)}%` : "—"}
                        </Cell>
                        <Cell className="text-[11px]">
                          <span className="font-semibold text-amber">MODEL SIGNAL: </span>
                          {activeComparison.ai_signal.interpretation}
                        </Cell>
                      </Row>

                      <Row>
                        <Cell className="font-semibold text-ink">Sensor Noise Residual</Cell>
                        <Cell mono>{activeComparison.traces.reference.noise_uniformity}</Cell>
                        <Cell mono>{activeComparison.traces.derivative.noise_uniformity}</Cell>
                        <Cell mono>Δ = {activeComparison.traces.noise_uniformity_delta}</Cell>
                        <Cell className="text-[11px]">
                          Sensor noise floor uniformity. Natural photos show uniform camera PRNU; synthetic derivatives show localized smoothing.
                        </Cell>
                      </Row>

                      <Row>
                        <Cell className="font-semibold text-ink">Error Level Analysis (ELA)</Cell>
                        <Cell mono>{activeComparison.traces.reference.ela_mean_error}</Cell>
                        <Cell mono>{activeComparison.traces.derivative.ela_mean_error}</Cell>
                        <Cell mono>Δ = {activeComparison.traces.ela_error_delta}</Cell>
                        <Cell className="text-[11px]">
                          Quantization error difference. Spliced banners or modified text exhibit disparate compression error rates.
                        </Cell>
                      </Row>

                      <Row>
                        <Cell className="font-semibold text-ink">Recapture Indication</Cell>
                        <Cell>{activeComparison.recapture.reference.likelihood}</Cell>
                        <Cell>{activeComparison.recapture.derivative.likelihood}</Cell>
                        <Cell mono>Score: {activeComparison.recapture.derivative.score ?? "—"}</Cell>
                        <Cell className="text-[11px]">
                          {activeComparison.recapture.interpretation}
                        </Cell>
                      </Row>
                    </Table>
                  </Panel>

                  {/* Normalized Comparison Index Bar Chart */}
                  <Panel
                    title="Normalized Comparison Index (Relative Scale 0–100)"
                    hint="Visualization showing magnitude of divergence between authentic reference and derivative across each forensic dimension."
                  >
                    <div className="space-y-4">
                      {activeComparison.chart_metrics.map((m, idx) => {
                        const barVal = Math.min(Math.max(m.delta, 2), 100);
                        const isHigh = m.delta >= 50;
                        const isMedium = m.delta >= 25 && m.delta < 50;

                        return (
                          <div key={idx} className="space-y-1.5">
                            <div className="flex items-center justify-between text-[11.5px]">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold text-ink">{m.signal}</span>
                                <span className="text-[10px] text-muted">({m.evidence_basis})</span>
                              </div>
                              <div className="flex items-center gap-3 font-mono">
                                <span className="text-muted text-[10.5px]">Ref: {m.reference}</span>
                                <span className="text-ink text-[10.5px]">Deriv: {m.derivative}</span>
                                <span className={`font-bold text-[11.5px] ${isHigh ? "text-danger" : isMedium ? "text-amber" : "text-ok"}`}>
                                  Δ {m.delta}
                                </span>
                              </div>
                            </div>
                            <Meter value={barVal} tone={isHigh ? "danger" : isMedium ? "amber" : "accent"} />
                          </div>
                        );
                      })}
                    </div>

                    <div className="mt-4 pt-3 border-t border-lineSoft flex items-center justify-between">
                      <span className="text-[10.5px] font-semibold text-amber bg-amber/10 px-2 py-1 rounded border border-amber/30">
                        {activeComparison.chart_disclaimer || "Normalized comparison index — visualization only; not a mathematical confidence score."}
                      </span>
                    </div>
                  </Panel>

                  {/* OCR & Entity Differencing + QR Extraction */}
                  <Panel
                    title="Text & Identifier Differencing (OCR & QR Analysis)"
                    hint="Diff of text, handles, URLs, and payment identifiers observed directly in media."
                  >
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* Added Identifiers */}
                      <div className="rounded-lg border border-danger/30 bg-danger/[0.04] p-3.5">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[11px] font-bold text-danger uppercase tracking-wider">
                            Added in Derivative (+{activeComparison.identifiers.added_count})
                          </span>
                          <Chip tone="danger">{activeComparison.identifiers.added_count}</Chip>
                        </div>
                        {activeComparison.identifiers.added.length === 0 ? (
                          <div className="text-[11.5px] text-muted py-2">No new text elements introduced.</div>
                        ) : (
                          <ul className="space-y-2">
                            {activeComparison.identifiers.added.map((it, idx) => (
                              <li key={idx} className="rounded border border-line bg-surface p-2 text-[11.5px]">
                                <div className="flex items-center gap-1.5">
                                  <Chip tone="danger" className="text-[9px] py-0 px-1">{it.entity_type}</Chip>
                                  <span className="font-mono font-semibold text-ink break-all">{it.value}</span>
                                </div>
                                <div className="text-[10px] text-muted mt-1">{it.observation}</div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      {/* Removed Identifiers */}
                      <div className="rounded-lg border border-line bg-s2/40 p-3.5">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[11px] font-bold text-muted uppercase tracking-wider">
                            Removed from Reference (-{activeComparison.identifiers.removed_count})
                          </span>
                          <Chip tone="muted">{activeComparison.identifiers.removed_count}</Chip>
                        </div>
                        {activeComparison.identifiers.removed.length === 0 ? (
                          <div className="text-[11.5px] text-muted py-2">No reference text was erased.</div>
                        ) : (
                          <ul className="space-y-2">
                            {activeComparison.identifiers.removed.map((it, idx) => (
                              <li key={idx} className="rounded border border-line bg-surface p-2 text-[11.5px]">
                                <div className="flex items-center gap-1.5">
                                  <Chip tone="muted" className="text-[9px] py-0 px-1">{it.entity_type}</Chip>
                                  <span className="font-mono text-muted line-through break-all">{it.value}</span>
                                </div>
                                <div className="text-[10px] text-muted mt-1">{it.observation}</div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      {/* QR Code & Payment Detection Card */}
                      <div className="rounded-lg border border-accent/30 bg-accent/[0.04] p-3.5">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[11px] font-bold text-accent uppercase tracking-wider flex items-center gap-1">
                            <QrCode size={13} />
                            <span>QR Code &amp; UPI Forensics</span>
                          </span>
                          <Chip tone={activeComparison.identifiers.qr?.detected ? "amber" : "muted"}>
                            {activeComparison.identifiers.qr?.detected ? "DETECTED" : "NONE"}
                          </Chip>
                        </div>

                        {activeComparison.identifiers.qr?.detected ? (
                          <div className="space-y-2 text-[11.5px]">
                            <div className="rounded border border-line bg-surface p-2">
                              <span className="block text-[10px] uppercase font-semibold text-muted">QR Status</span>
                              <span className="font-semibold text-ink">{activeComparison.identifiers.qr.status}</span>
                            </div>
                            {activeComparison.identifiers.qr.coordinates && (
                              <div className="rounded border border-line bg-surface p-2">
                                <span className="block text-[10px] uppercase font-semibold text-muted">Bounding Box Coordinates</span>
                                <span className="font-mono text-[11px] text-accent">
                                  [x={activeComparison.identifiers.qr.coordinates[0]}, y={activeComparison.identifiers.qr.coordinates[1]}, w={activeComparison.identifiers.qr.coordinates[2]}, h={activeComparison.identifiers.qr.coordinates[3]}]
                                </span>
                              </div>
                            )}
                            <div className="text-[10.5px] text-muted leading-relaxed mt-2">
                              Label: <span className="font-semibold text-ink2">{activeComparison.identifiers.evidence_label}</span> (does not establish identity of recipient or perpetrator).
                            </div>
                          </div>
                        ) : (
                          <div className="text-[11.5px] text-muted py-2">
                            No QR barcode matrix detected in this derivative.
                          </div>
                        )}
                      </div>
                    </div>
                  </Panel>

                  {/* Why SROT Reached This Result & What SROT Cannot Establish */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Why SROT reached this result */}
                    <Panel
                      title="Why SROT Reached This Result"
                      hint="Technical justification synthesized from raw measurements."
                    >
                      <ul className="space-y-2">
                        {activeComparison.why_srot_reached_result.map((reason, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-[11.5px] leading-relaxed text-ink2">
                            <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-ok" />
                            <span>{reason}</span>
                          </li>
                        ))}
                      </ul>
                    </Panel>

                    {/* What SROT cannot establish */}
                    <Panel
                      title="What SROT Cannot Establish"
                      hint="Strict legal, scientific, and investigative boundaries."
                    >
                      <ul className="space-y-2">
                        {activeComparison.what_srot_cannot_establish.map((boundary, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-[11.5px] leading-relaxed text-ink2">
                            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber" />
                            <span>{boundary}</span>
                          </li>
                        ))}
                      </ul>
                    </Panel>
                  </div>
                </div>
              )}
            </div>
          );
        }}
      </Async>
    </>
  );
}
