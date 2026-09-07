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
      {(ev) => <Body evidenceRef={ev.evidence_ref} />}
    </RequireEvidence>
  );
}

function Body({ evidenceRef }: { evidenceRef: string }) {
  const o = useApi<Origin>(`/evidence/${evidenceRef}/origin`);

  return (
    <>
      <PageHead
        eyebrow="Step 3 · Origin trace"
        title="Earliest known copy in the searched corpus"
        sub="Perceptual hashes survive re-encoding, rescaling, cropping and metadata removal. Matching
             is done across several normalised views of each frame, and the view that produced the
             match is recorded."
      />

      <Async state={o} rows={6}>
        {(d) => (
          <>
            {!d.established ? (
              <div className="mb-4">
                <EmptyState
                  title="Attribution cannot be established from available data."
                  detail={d.empty_reason ?? "No qualifying near-duplicate was found in the reference corpus."}
                />
              </div>
            ) : (
              <div className="mb-4 grid gap-4 lg:grid-cols-[1.15fr_minmax(0,1fr)]">
                <Panel title="Earliest known copy">
                  <div className="flex flex-wrap items-baseline gap-3">
                    <span className="font-mono text-[19px] font-semibold text-accent">
                      {d.earliest?.label}
                    </span>
                    <Chip tone="accent">{d.earliest?.source_kind}</Chip>
                  </div>
                  <div className="mt-3.5 grid grid-cols-2 gap-x-4 gap-y-3.5">
                    <Field label="Observed">{fmtDate(d.earliest?.observed_at)}</Field>
                    <Field label="Similarity">{fmtNum(d.earliest?.similarity)}%</Field>
                    <Field label="Hamming distance">{d.earliest?.hamming} / 64 bits</Field>
                    <Field label="Propagation span">
                      {d.propagation_span_days != null ? `${d.propagation_span_days} days` : null}
                    </Field>
                    <div className="col-span-2">
                      <Field label="Transformation recorded for this copy">{d.earliest?.transform}</Field>
                    </div>
                    <div className="col-span-2">
                      <Field label="Match normalisation">{d.earliest?.normalisation}</Field>
                    </div>
                  </div>
                  <div className="mt-4">
                    <Notice kind="warn">{d.disclaimer}</Notice>
                  </div>
                </Panel>

                <Panel title="Matching method"
                       hint="The threshold was measured against two populations, not chosen by feel.">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3.5">
                    <Field label="Method">{d.method}</Field>
                    <Field label="Threshold">{d.threshold}</Field>
                    <Field label="Corpus searched">{d.corpus_size} items</Field>
                    <Field label="Qualifying matches">{d.match_count}</Field>
                  </div>
                  <div className="mt-3.5">
                    <div className="lbl mb-1.5">Threshold calibration</div>
                    <pre className="overflow-auto rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-[10.5px] leading-relaxed text-ink2">
{JSON.stringify(d.threshold_calibration, null, 2)}
                    </pre>
                  </div>
                </Panel>
              </div>
            )}

            <Panel title="Corpus matches, ordered by first observation"
                   hint="Ordering shows how the media propagated through the searched corpus. It is not a
                         claim about first publication anywhere.">
              {d.matches.length === 0 ? (
                <EmptyState title="No qualifying matches."
                            detail={d.empty_reason ?? undefined} />
              ) : (
                <Table head={["Observed", "Corpus label", "Kind", "Similarity", "Hamming",
                              "Frames matched", "Transformation", "SHA-256"]}>
                  {d.matches.map((m) => (
                    <Row key={m.corpus_id} tone={m.is_earliest ? "bg-accent/[0.06]" : ""}>
                      <Cell className="whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          {m.is_earliest
                            ? <CheckCircle2 size={12} className="shrink-0 text-accent" />
                            : <Clock3 size={12} className="shrink-0 text-muted" />}
                          {fmtDate(m.observed_at)}
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
                      <Cell className="max-w-[190px]">{m.transform}</Cell>
                      <Cell mono>{shortHash(m.sha256, 8)}</Cell>
                    </Row>
                  ))}
                </Table>
              )}
              {d.matches.some((m) => m.is_synthetic) && (
                <p className="mt-3 text-[11px] leading-relaxed text-muted">
                  Every corpus item in this build is synthetic demonstration media generated locally.
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
    <Panel title="Attribution ceiling"
           hint="How far automated analysis can go, and exactly where the process must hand over to a
                 legal request or a human investigator.">
      {steps.length === 0 ? (
        <EmptyState title="Attribution ceiling not available for this evidence." />
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
          Automated attribution stops at
          {lastAuto ? ` step ${lastAuto.step}: ${lastAuto.what.toLowerCase()}.` : " the first step."}{" "}
          Everything beyond it requires an authorised legal request or human investigation. SROT does
          not identify any person and does not resolve who controls an account or an identifier.
        </Notice>
      </div>
    </Panel>
  );
}
