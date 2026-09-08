import { useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Loader2, Play } from "lucide-react";
import {
  Async, Button, Chip, EmptyState, Field, Notice, PageHead, Panel, Table, Row, Cell,
} from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { api, usePolling, fmtBytes, fmtNum, shortHash } from "../lib/api";
import type { Stress as StressPayload } from "../lib/api";

export default function Stress() {
  return <RequireEvidence>{(ev) => <Body evidenceRef={ev.evidence_ref} />}</RequireEvidence>;
}

function Body({ evidenceRef }: { evidenceRef: string }) {
  const [starting, setStarting] = useState(false);
  const [startErr, setStartErr] = useState<string | null>(null);

  const s = usePolling<StressPayload>(
    `/evidence/${evidenceRef}/stress-test`,
    (d) => d.status === "queued" || d.status === "running",
    3000,
  );

  const start = async () => {
    setStarting(true); setStartErr(null);
    try {
      await api.post(`/evidence/${evidenceRef}/stress-test`);
      s.reload();
    } catch (e) {
      setStartErr((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  const running = s.data?.status === "queued" || s.data?.status === "running";

  return (
    <>
      <PageHead
        eyebrow="Step 8 · Laundering stress test"
        title="When should this result be treated with caution?"
        sub="Checks whether the assessment remains stable after common media transformations such as resizing, compression, cropping, screenshots, and re-encoding. Media laundering: processing or re-encoding media in ways that can weaken or alter forensic traces."
        right={
          <Button onClick={start} disabled={starting || running}>
            {starting || running
              ? <><Loader2 size={14} className="animate-spin" /> Running…</>
              : <><Play size={14} /> {s.data?.variants?.length ? "Run again" : "Run stress test"}</>}
          </Button>
        }
      />

      {startErr && (
        <div className="mb-4 rounded-lg border border-danger/35 bg-danger/[0.07] px-3.5 py-2.5 text-[11.5px] text-danger">
          {startErr}
        </div>
      )}

      <Async state={s} rows={4}>
        {(d) => {
          const vs = d.variants ?? [];
          if (d.status === "none" || (!vs.length && !running)) {
            return (
              <EmptyState
                title="No stress test has been executed for this evidence."
                detail={d.empty_reason ??
                  "Run the stress test to measure whether the assessment remains stable after common media transformations such as resizing, compression, cropping, and re-encoding."}
                action={<Button onClick={start} disabled={starting}>Run stress test</Button>}
              />
            );
          }

          const scored = vs.filter((v) => v.score != null);
          const chart = scored.map((v) => ({
            name: v.name.replace(/^(Re-encode|Downscale|Crop) /, ""),
            full: v.name,
            score: v.score as number,
            similarity: v.phash_similarity,
          }));

          return (
            <>
              <div className="mb-4 grid gap-4 lg:grid-cols-[1fr_1.4fr]">
                <Panel title="Result">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3.5">
                    <Field label="Status">
                      <Chip tone={d.status === "completed" ? "ok" : d.status === "failed" ? "danger" : "amber"}>
                        {d.status}
                      </Chip>
                    </Field>
                    <Field label="Baseline score">{fmtNum(d.baseline_score, 2)}</Field>
                    <Field label="Variants generated">{vs.length}</Field>
                    <Field label="Variants re-scored">{scored.length}</Field>
                    {d.directional_stability && (
                      <>
                        <Field label="Directional stability">
                          <Chip tone={d.directional_stability.grade === "HIGHLY_STABLE" ? "ok" : d.directional_stability.grade === "DIRECTIONALLY_CONSISTENT" ? "amber" : "danger"}>
                            {d.directional_stability.grade}
                          </Chip>
                        </Field>
                        <Field label="Mean shift (Δ)">
                          {d.directional_stability.mean_delta != null ? `±${d.directional_stability.mean_delta}%` : "—"}
                        </Field>
                      </>
                    )}
                    <div className="col-span-2">
                      <Field label="Observed reliability boundary">{d.reliability_boundary}</Field>
                    </div>
                  </div>
                  {d.directional_stability?.summary && (
                    <div className="mt-3 rounded-lg border border-line bg-s2/40 px-3.5 py-2.5 text-[11px] text-ink2">
                      <span className="font-semibold text-ink">Robustness assessment: </span>
                      {d.directional_stability.summary}
                    </div>
                  )}
                  {d.error && (
                    <div className="mt-3 rounded-lg border border-danger/35 bg-danger/[0.07] px-3.5 py-2.5 text-[11.5px] text-danger">
                      {d.error}
                    </div>
                  )}
                  {d.recommendation && (
                    <div className="mt-3.5"><Notice kind="warn">{d.recommendation}</Notice></div>
                  )}
                </Panel>

                <Panel title="Score under transformation"
                       hint="Each point is a real re-encoded file scored by the same ensemble. The dashed
                             line is the score of the untouched evidence.">
                  {chart.length === 0 ? (
                    <EmptyState title="No variant has been scored yet."
                                detail="Scores appear as each generated file completes analysis." />
                  ) : (
                    <div style={{ height: 250 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chart} margin={{ top: 8, right: 12, bottom: 32, left: -14 }}>
                          <CartesianGrid stroke="#202330" vertical={false} />
                          <XAxis dataKey="name" tick={{ fontSize: 9.5, fill: "#686E7D" }}
                                 angle={-32} textAnchor="end" interval={0} height={54}
                                 stroke="#292D3A" />
                          <YAxis tick={{ fontSize: 10, fill: "#686E7D" }} stroke="#292D3A"
                                 domain={[0, 100]} />
                          <Tooltip
                            contentStyle={{ background: "#10121A", border: "1px solid #292D3A",
                                            borderRadius: 8, fontSize: 11.5 }}
                            labelStyle={{ color: "#F1F2F6" }}
                            formatter={(v, n) =>
                              [typeof v === "number" ? v.toFixed(2) : String(v ?? "—"),
                               n === "score" ? "Indicator score" : "pHash similarity %"] as [string, string]}
                          />
                          {d.baseline_score != null && (
                            <ReferenceLine y={d.baseline_score} stroke="#9B7BFF" strokeDasharray="5 4"
                                           label={{ value: "baseline", fill: "#9B7BFF", fontSize: 10,
                                                    position: "insideTopLeft" }} />
                          )}
                          <Line type="monotone" dataKey="score" stroke="#E5B85C" strokeWidth={2}
                                dot={{ r: 2.5, fill: "#E5B85C" }} />
                          <Line type="monotone" dataKey="similarity" stroke="#55C98A" strokeWidth={1.4}
                                strokeDasharray="4 3" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </Panel>
              </div>

              <Panel title="Generated variants"
                     hint="Each variant is a real file on disk with its own SHA-256 — not a simulated number.">
                <Table head={["Variant", "Transformation", "Score", "Δ baseline", "pHash similarity",
                              "Size", "SHA-256", "Time"]}>
                  {vs.map((v) => (
                    <Row key={v.name} tone={v.error ? "bg-danger/[0.05]" : ""}>
                      <Cell className="font-medium text-ink">{v.name}</Cell>
                      <Cell className="max-w-[210px]">{v.transform}</Cell>
                      <Cell mono>{v.error ? "—" : fmtNum(v.score, 2)}</Cell>
                      <Cell mono className={
                        v.delta == null ? "" : v.delta > 8 ? "text-amber" : v.delta < -8 ? "text-accent" : ""
                      }>
                        {v.delta == null ? "—" : `${v.delta > 0 ? "+" : ""}${v.delta.toFixed(2)}`}
                      </Cell>
                      <Cell mono>{v.phash_similarity == null ? "—" : `${fmtNum(v.phash_similarity)}%`}</Cell>
                      <Cell>{fmtBytes(v.size_bytes)}</Cell>
                      <Cell mono>{shortHash(v.sha256, 8)}</Cell>
                      <Cell mono>{v.processing_ms != null ? `${(v.processing_ms / 1000).toFixed(1)}s` : "—"}</Cell>
                    </Row>
                  ))}
                </Table>
                {vs.some((v) => v.error) && (
                  <p className="mt-3 text-[11px] text-danger">
                    Some variants could not be generated or scored; their rows show the recorded error
                    rather than a substituted value.
                  </p>
                )}
              </Panel>

              <div className="mt-4">
                <Notice kind="info">
                  A boundary observed here applies to these transformations on this file. It is not a
                  general robustness claim, and it does not imply the assessment is correct within the
                  boundary — only that it did not change.
                </Notice>
              </div>
            </>
          );
        }}
      </Async>
    </>
  );
}
