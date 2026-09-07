import { Async, Chip, EmptyState, Notice, PageHead, Panel } from "../components/ui";
import { useSession } from "../state/session";
import { useApi, fmtDate, fmtNum } from "../lib/api";
import type { Lead, TimelineRow } from "../lib/api";

const KIND_TONE: Record<string, "accent" | "amber" | "violet" | "ok" | "muted"> = {
  corpus_observation: "violet",
  ingest: "accent",
  analysis: "ok",
  recapture: "amber",
};

export default function Timeline() {
  const { caseRef } = useSession();
  const t = useApi<TimelineRow[]>(caseRef ? `/cases/${caseRef}/timeline` : null);
  const l = useApi<Lead[]>(caseRef ? `/cases/${caseRef}/leads` : null);

  return (
    <>
      <PageHead
        eyebrow="Step 9 · Timeline &amp; leads"
        title="What happened, in order — and what to do next"
        sub="The timeline mixes observations recorded about the media with actions SROT performed.
             Leads are ranked from those findings and each one cites what produced it."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.15fr]">
        <Panel title="Case timeline"
               hint="Corpus observation times are properties of the reference corpus, not proof of
                     publication order anywhere else.">
          <Async state={t} rows={4}>
            {(rows) => rows.length === 0 ? (
              <EmptyState title="No timeline events."
                          detail="Events appear once an evidence item completes analysis." />
            ) : (
              <ol className="relative space-y-4 pl-5">
                <span className="absolute left-[5px] top-1.5 bottom-1.5 w-px bg-line" aria-hidden="true" />
                {rows.map((e, i) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-5 top-[5px] h-[9px] w-[9px] rounded-full border-2 border-bg bg-accent" />
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[11px] text-muted">{fmtDate(e.occurred_at)}</span>
                      <Chip tone={KIND_TONE[e.kind] ?? "muted"} dot={false}>{e.kind}</Chip>
                      {e.is_synthetic && <Chip tone="violet" dot={false}>synthetic record</Chip>}
                    </div>
                    <div className="mt-1 text-[12.5px] font-semibold text-ink">{e.title}</div>
                    {e.detail && (
                      <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink2">{e.detail}</p>
                    )}
                    {e.confidence != null && (
                      <p className="mt-0.5 text-[10.5px] text-muted">
                        Confidence {fmtNum(e.confidence, 2)}
                        {e.evidence_ref ? ` · ${e.evidence_ref}` : ""}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Async>
        </Panel>

        <Panel title="Suggested investigative leads"
               hint="Ranked deterministically from the findings above. Nothing here is a directive — each
                     lead states the limitation that applies to it.">
          <Async state={l} rows={4}>
            {(rows) => rows.length === 0 ? (
              <EmptyState title="No leads generated."
                          detail="Nothing in this case met the threshold for a suggested lead." />
            ) : (
              <ol className="space-y-3">
                {rows.map((lead) => (
                  <li key={lead.rank} className="panel-2 px-4 py-3.5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex items-baseline gap-2.5">
                        <span className="font-mono text-[11px] text-muted">#{lead.rank}</span>
                        <span className="text-[12.5px] font-semibold text-ink">{lead.title}</span>
                      </div>
                      <Chip tone={lead.priority === "HIGH" ? "danger"
                                : lead.priority === "MEDIUM" ? "amber" : "muted"}>
                        {lead.priority}
                      </Chip>
                    </div>
                    <p className="mt-1.5 text-[11.5px] leading-relaxed text-ink2">{lead.summary}</p>
                    {lead.reasons?.length > 0 && (
                      <div className="mt-2.5">
                        <div className="lbl mb-1">Based on</div>
                        <ul className="space-y-1">
                          {lead.reasons.map((r, i) => (
                            <li key={i} className="flex justify-between gap-3 border-b border-lineSoft py-1 text-[11px] leading-relaxed last:border-0">
                              <span className="text-muted">{r.text}</span>
                              <span className="shrink-0 text-right font-mono text-ink2">
                                {r.value == null ? "—" : String(r.value)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {lead.limitation && (
                      <p className="mt-2.5 rounded-md border border-amber/25 bg-amber/[0.05] px-2.5 py-1.5 text-[11px] leading-relaxed text-amber">
                        {lead.limitation}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Async>
        </Panel>
      </div>

      <div className="mt-4">
        <Notice kind="warn">
          Suggested investigative leads are starting points for a human investigator. SROT does not
          identify persons, resolve who owns an identifier, or recommend any enforcement action.
        </Notice>
      </div>
    </>
  );
}
