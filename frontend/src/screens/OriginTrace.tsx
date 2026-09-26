import { CheckCircle2, CircleDashed, Clock3 } from "lucide-react";
import {
  Async, Chip, EmptyState, Field, Meter, Notice, PageHead, Panel, Table, Row, Cell,
} from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { useApi, fmtDate, fmtNum, shortHash } from "../lib/api";
import type { Origin } from "../lib/api";

export default function OriginTrace() {
  return (
    <RequireEvidence>
      {(ev) => <Body key={ev.evidence_ref} evidenceRef={ev.evidence_ref} />}
    </RequireEvidence>
  );
}

function Body({ evidenceRef }: { evidenceRef: string }) {
  const o = useApi<Origin>(`/evidence/${evidenceRef}/origin`);

  return (
    <>
      <PageHead
        eyebrow="Step 3 · Origin trace"
        title="EARLIEST OBSERVED MATCH WITHIN SEARCHED CORPUS"
        sub="Perceptual fingerprints compare visual structure against available reference copies. SROT explicitly isolates source platform observation, evidence collection, and SROT ingestion timestamps."
      />

      <Async state={o} rows={6}>
        {(d) => (
          <>
            {!d.established ? (
              <div className="mb-4">
                <EmptyState
                  title="Origin cannot be established from the available reference corpus."
                  detail={d.empty_reason ?? "No qualifying matching copy was observed within the searched reference corpus."}
                />
              </div>
            ) : (
              <div className="mb-4 grid gap-4 lg:grid-cols-[1.25fr_minmax(0,1fr)]">
                <Panel title="Earliest observed matching copy"
                       hint="Earliest match observed within searched reference corpus. Does not imply universal discovery across the entire internet.">
                  <div className="flex flex-wrap items-baseline gap-3">
                    <span className="font-mono text-[19px] font-semibold text-accent">
                      {d.earliest?.label}
                    </span>
                    <Chip tone="accent">{d.earliest?.source_kind}</Chip>
                    <Chip tone="muted" dot={false}>searched corpus item</Chip>
                  </div>

                  {/* Forensic Timestamp Triad */}
                  <div className="mt-4 rounded-lg border border-accent/25 bg-accent/[0.03] p-3">
                    <div className="text-[10px] font-bold uppercase tracking-wider text-accent mb-2.5">
                      Provenance &amp; Custody Timestamps
                    </div>
                    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3 text-[11.5px]">
                      <div className="rounded border border-line bg-surface/80 p-2">
                        <span className="block text-[10px] font-semibold uppercase text-muted">A. Source Observation</span>
                        <div className="font-mono font-medium text-ink mt-1">
                          {d.earliest?.observed_at ? fmtDate(d.earliest.observed_at) : "Source publication time not established."}
                        </div>
                        <span className="text-[10px] text-muted/80 mt-0.5 block">{d.earliest?.source_kind || "Platform event"}</span>
                      </div>
                      <div className="rounded border border-line bg-surface/80 p-2">
                        <span className="block text-[10px] font-semibold uppercase text-muted">B. Collection Event</span>
                        <div className="font-mono font-medium text-ink mt-1">
                          {d.earliest?.collected_at ? fmtDate(d.earliest.collected_at) : "Collection timestamp not recorded"}
                        </div>
                        <span className="text-[10px] text-muted/80 mt-0.5 block">Investigator acquisition</span>
                      </div>
                      <div className="rounded border border-line bg-surface/80 p-2">
                        <span className="block text-[10px] font-semibold uppercase text-muted">C. SROT Ingestion Event</span>
                        <div className="font-mono font-medium text-ink mt-1">
                          {d.evidence_ingested_at ? fmtDate(d.evidence_ingested_at) : "Ingested at upload"}
                        </div>
                        <span className="text-[10px] text-muted/80 mt-0.5 block">Chain-of-custody ingest</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3.5 grid grid-cols-2 gap-x-4 gap-y-3.5">
                    <Field label="Fingerprint similarity">{fmtNum(d.earliest?.similarity)}%</Field>
                    <Field label="Hamming distance">{d.earliest?.hamming} / 64 bits</Field>
                    <Field label="Propagation span in corpus">
                      {d.propagation_span_days != null ? `${d.propagation_span_days} days` : "Indeterminate"}
                    </Field>
                    <Field label="Corpus scope">Searched {d.corpus_size} reference items</Field>
                    <div className="col-span-2">
                      <Field label="Transformation recorded for this copy">{d.earliest?.transform || "None"}</Field>
                    </div>
                    <div className="col-span-2">
                      <Field label="Match normalisation">{d.earliest?.normalisation || "Standard"}</Field>
                    </div>
                  </div>
                  <div className="mt-4">
                    <Notice kind="warn">{d.disclaimer}</Notice>
                  </div>
                </Panel>

                <Panel title="Matching method &amp; calibration"
                       hint="Threshold calibrated against representative media populations to minimise false attribution.">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3.5">
                    <Field label="Method">{d.method}</Field>
                    <Field label="Threshold">{d.threshold}</Field>
                    <Field label="Reference corpus searched">{d.corpus_size} items</Field>
                    <Field label="Qualifying matches">{d.match_count}</Field>
                  </div>
                  <div className="mt-3.5">
                    <div className="lbl mb-1.5">Threshold calibration parameters</div>
                    <pre className="overflow-auto rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-[10.5px] leading-relaxed text-ink2">
{JSON.stringify(d.threshold_calibration, null, 2)}
                    </pre>
                  </div>
                </Panel>
              </div>
            )}

            <Panel title="Reference corpus matches, ordered by first observation"
                   hint="Ordering shows propagation within the searched reference corpus. It does not imply universal discovery across the entire internet.">
              {d.matches.length === 0 ? (
                <EmptyState title="Origin cannot be established from the available reference corpus."
                            detail={d.empty_reason ?? "No qualifying match in the searched reference corpus."} />
              ) : (
                <Table head={["Source observation", "Reference corpus label", "Platform / Kind", "Similarity", "Hamming",
                              "Frames matched", "Transformation", "SHA-256"]}>
                  {d.matches.map((m) => (
                    <Row key={m.corpus_id} tone={m.is_earliest ? "bg-accent/[0.06]" : ""}>
                      <Cell className="whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          {m.is_earliest
                            ? <CheckCircle2 size={12} className="shrink-0 text-accent" />
                            : <Clock3 size={12} className="shrink-0 text-muted" />}
                          {m.observed_at ? fmtDate(m.observed_at) : "Publication time not established"}
                        </div>
                      </Cell>
                      <Cell mono className={m.is_earliest ? "text-accent" : ""}>{m.label}</Cell>
                      <Cell>{m.source_kind}</Cell>
                      <Cell className="w-[120px]">
                        <div className="flex items-center gap-2">
                          <span className="w-[46px] shrink-0 font-mono tabular-nums">
                            {fmtNum(m.similarity)}%
                          </span>
                          <Meter value={m.similarity} tone={m.is_earliest ? "accent" : "muted"} />
                        </div>
                      </Cell>
                      <Cell mono>{m.hamming}/64</Cell>
                      <Cell mono>{m.matched_frames}/{m.total_frames}</Cell>
                      <Cell className="max-w-[190px]">{m.transform || "—"}</Cell>
                      <Cell mono>{shortHash(m.sha256, 8)}</Cell>
                    </Row>
                  ))}
                </Table>
              )}
              {d.matches.some((m) => m.is_synthetic) && (
                <p className="mt-3 text-[11px] leading-relaxed text-muted">
                  Every reference corpus item in this build is synthetic demonstration media generated locally.
                  SROT performs no live social-media scraping and reaches no external service.
                </p>
              )}
            </Panel>

            <div className="mt-4">
              <Ceiling ceiling={d.attribution_ceiling} />
            </div>
          </>
        )}
      </Async>
    </>
  );
}

function Ceiling({ ceiling }: { ceiling: Origin["attribution_ceiling"] }) {
  const steps = ceiling ?? [];
  const lastAuto = [...steps].reverse().find((s) => s.established);

  return (
    <Panel title="Evidence & Attribution Limits"
           hint="What SROT can establish automatically — and what still requires an investigator or authorized external request.">
      {steps.length === 0 ? (
        <EmptyState title="Evidence and attribution limits not available for this evidence." />
      ) : (
        <ol className="space-y-2">
          {steps.map((s) => (
            <li key={s.step}
                className={`flex items-start gap-3 rounded-lg border px-3.5 py-2.5 ${
                  s.established ? "border-lineSoft bg-s2/50" : "border-amber/25 bg-amber/[0.04]"
                }`}>
              {s.established
                ? <CheckCircle2 size={15} className="mt-[1px] shrink-0 text-ok" />
                : <CircleDashed size={15} className="mt-[1px] shrink-0 text-amber" />}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[12.5px] font-semibold text-ink">
                    {s.step}. {s.what}
                  </span>
                  <Chip tone={s.actor === "SROT" ? "accent" : "amber"} dot={false}>{s.actor}</Chip>
                  <span className="text-[10.5px] text-muted">{s.mode}</span>
                </div>
                <p className="mt-1 text-[11.5px] leading-relaxed text-ink2">{s.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
      <div className="mt-4">
        <Notice kind="warn">
          Automated attribution limits stop at
          {lastAuto ? ` step ${lastAuto.step}: ${lastAuto.what.toLowerCase()}.` : " the first step."}{" "}
          Everything beyond it requires an authorised legal request or human investigation. SROT does
          not identify any person and does not resolve who controls an account or an identifier.
        </Notice>
      </div>
    </Panel>
  );
}
