import { Link } from "react-router-dom";
import { ArrowRight, ShieldCheck, ShieldAlert, ScanSearch, Activity, FileText, Eye } from "lucide-react";
import {
  Async, Chip, EmptyState, Field, Notice, PageHead, Panel, Stat, Table, Row, Cell,
} from "../components/ui";
import { useSession } from "../state/session";
import { useApi, fmtBytes, fmtDate } from "../lib/api";
import type { CampaignPayload, Lead } from "../lib/api";

const bandTone = (b?: string | null) =>
  b === "HIGH" ? "danger" : b === "MEDIUM" ? "amber" : b === "LOW" ? "accent" : "muted";

/** Keep the table row on one line; the full wording stays as the cell's title. */
const shortAssessment = (a?: string | null) =>
  !a ? "—"
  : /^no strong/i.test(a) ? "No strong indicators"
  : /^potentially/i.test(a) ? "Potentially manipulated"
  : a;

export default function Dashboard() {
  const { detail, detailLoading, detailError, caseRef, health, healthError, refresh, setEvidenceRef } = useSession();
  const leads = useApi<Lead[]>(caseRef ? `/cases/${caseRef}/leads` : null);
  const campaign = useApi<CampaignPayload>(caseRef ? `/cases/${caseRef}/campaign-matches` : null);

  const evidence = detail?.evidence ?? [];
  const analysed = evidence.filter((e) => e.latest_run?.status === "completed");
  const chain = detail?.audit_chain;

  return (
    <>
      <PageHead
        eyebrow="Case dashboard · Forensic triage & status"
        title={detail?.title ?? (detailLoading ? "Loading case…" : "No case loaded")}
        sub={detail?.summary}
        right={
          <div className="flex items-center gap-2">
            <button onClick={refresh} className="btn btn-ghost text-[12px]">Refresh</button>
            <Link to="/upload" className="btn btn-primary text-[12px]">
              Add evidence <ArrowRight size={14} />
            </Link>
          </div>
        }
      />

      {healthError && (
        <div className="mb-5">
          <Notice kind="warn">
            The SROT backend is not reachable. Start it with{" "}
            <code className="font-mono">uvicorn app.main:app --port 8077</code>, then refresh.
            No screen in this console falls back to sample data.
          </Notice>
        </div>
      )}

      {detailError && !healthError && (
        <div className="mb-5"><Notice kind="warn">{detailError}</Notice></div>
      )}

      {/* Case Quick Action & Triage Bar */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface/70 px-4 py-3">
        <div className="flex items-center gap-2 text-[12px] font-semibold text-ink">
          <ShieldCheck size={16} className="text-accent" />
          <span>Case Triage &amp; Quick Access:</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to="/analysis" className="btn btn-ghost text-xs py-1 px-2.5 flex items-center gap-1.5">
            <ScanSearch size={13} className="text-accent" />
            <span>Forensic Assessment</span>
          </Link>
          <Link to="/origin" className="btn btn-ghost text-xs py-1 px-2.5 flex items-center gap-1.5">
            <Eye size={13} className="text-ok" />
            <span>Visual Traces</span>
          </Link>
          <Link to="/stress" className="btn btn-ghost text-xs py-1 px-2.5 flex items-center gap-1.5">
            <Activity size={13} className="text-amber" />
            <span>Stress Validation</span>
          </Link>
          <Link to="/packet" className="btn btn-ghost text-xs py-1 px-2.5 flex items-center gap-1.5">
            <FileText size={13} className="text-ink2" />
            <span>Court Packet (PDF)</span>
          </Link>
        </div>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Evidence items" value={String(evidence.length)}
              sub={`${analysed.length} fully analysed`} />
        <Stat label="Reference corpus" value={String(health?.corpus_items ?? "—")}
              sub="items searched for near-duplicates" />
        <Stat label="Cross-case links" value={String(campaign.data?.count ?? "—")}
              sub="potential campaign relationships" />
        <Stat
          label="Audit chain"
          value={chain ? (chain.verified ? "Verified" : "Broken") : "—"}
          tone={chain && !chain.verified ? "danger" : "ink"}
          sub={chain ? `${chain.entries} hash-linked entries` : undefined}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr]">
        <Panel title="Evidence in this case"
               hint="Each row is a file that was actually ingested and hashed on receipt. Click to inspect.">
          {detailLoading && !evidence.length ? (
            <EmptyState title="Loading…" />
          ) : !evidence.length ? (
            <EmptyState
              title="No evidence ingested yet."
              detail="Upload a video or image to run the full pipeline."
              action={<Link to="/upload" className="btn btn-primary text-[12px]">Evidence Intake</Link>}
            />
          ) : (
            <Table head={["Reference", "File", "Size", "Ingested", "Assessment", "Action"]}>
              {evidence.map((e) => (
                <Row key={e.evidence_ref}>
                  <Cell mono className="text-accent">{e.evidence_ref}</Cell>
                  <Cell className="max-w-[190px] truncate">{e.filename}</Cell>
                  <Cell>{fmtBytes(e.size_bytes)}</Cell>
                  <Cell>{fmtDate(e.ingested_at)}</Cell>
                  <Cell className="whitespace-nowrap">
                    {e.latest_run?.status === "completed" ? (
                      <span title={e.latest_run.assessment ?? ""}>
                        <Chip tone={bandTone(e.latest_run.confidence_band)}>
                          {shortAssessment(e.latest_run.assessment)}
                        </Chip>
                      </span>
                    ) : (
                      <Chip tone="muted">{e.latest_run?.status ?? "not analysed"}</Chip>
                    )}
                  </Cell>
                  <Cell>
                    <Link
                      to="/analysis"
                      onClick={() => setEvidenceRef(e.evidence_ref)}
                      className="text-xs font-semibold text-accent hover:underline flex items-center gap-1"
                    >
                      Inspect →
                    </Link>
                  </Cell>
                </Row>
              ))}
            </Table>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel title="Suggested investigative leads"
                 hint="Ranked from findings actually produced by this case. Each lead cites its evidence.">
            <Async state={leads} rows={3}
                   empty={<EmptyState title="No leads yet." detail="Leads are generated once an evidence item completes analysis." />}>
              {(rows) => rows.length === 0 ? (
                <EmptyState title="No leads generated."
                            detail="Nothing in this case met the threshold for a suggested lead." />
              ) : (
                <ol className="space-y-2.5">
                  {rows.slice(0, 5).map((l) => (
                    <li key={l.rank} className="panel-2 px-3.5 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="text-[12.5px] font-semibold text-ink">{l.title}</div>
                        <Chip tone={l.priority === "HIGH" ? "danger" : l.priority === "MEDIUM" ? "amber" : "muted"}>
                          {l.priority}
                        </Chip>
                      </div>
                      <p className="mt-1.5 text-[11.5px] leading-relaxed text-ink2">{l.summary}</p>
                    </li>
                  ))}
                </ol>
              )}
            </Async>
            <div className="mt-3">
              <Link to="/timeline" className="link text-[11.5px]">All leads and case timeline →</Link>
            </div>
          </Panel>

          <Panel title="Case record">
            <div className="grid grid-cols-2 gap-x-4 gap-y-3.5">
              <Field label="Case reference"><span className="font-mono">{detail?.case_ref}</span></Field>
              <Field label="Category">{detail?.category}</Field>
              <Field label="Officer">{detail?.officer}</Field>
              <Field label="Opened">{fmtDate(detail?.opened_at)}</Field>
            </div>
            {chain && (
              <div className={`mt-4 flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-[11.5px] ${
                chain.verified ? "border-ok/35 bg-ok/[0.07] text-ok" : "border-danger/35 bg-danger/[0.07] text-danger"
              }`}>
                {chain.verified ? <ShieldCheck size={14} className="mt-[1px] shrink-0" />
                                : <ShieldAlert size={14} className="mt-[1px] shrink-0" />}
                <span>{chain.message}</span>
              </div>
            )}
          </Panel>
        </div>
      </div>

      <div className="mt-5">
        <Notice kind="info">
          SROT reports measured indicators and suggested investigative leads. It does not classify
          media as definitively real or fake, identify any person, resolve identifier ownership, or
          determine legal admissibility. Every finding requires human verification.
        </Notice>
      </div>
    </>
  );
}
