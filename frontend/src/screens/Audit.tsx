import { useState } from "react";
import { ChevronDown, ShieldAlert, ShieldCheck } from "lucide-react";
import { Async, Chip, EmptyState, Field, Notice, PageHead, Panel } from "../components/ui";
import { useSession } from "../state/session";
import { useApi, fmtDate, shortHash } from "../lib/api";
import type { AuditPayload, AuditRow } from "../lib/api";

export default function Audit() {
  const { caseRef } = useSession();
  const a = useApi<AuditPayload>(caseRef ? `/cases/${caseRef}/audit` : null);

  return (
    <>
      <PageHead
        eyebrow="Step 10 · Audit trail"
        title="Hash-Linked Forensic Audit Chain"
        sub="Each important action is recorded and cryptographically linked to the previous record. This makes later tampering easier to detect. SHA-256 is a cryptographic fingerprint of the file: changing even a single byte changes the fingerprint."
      />

      <Async state={a} rows={5}>
        {(d) => (
          <>
            <div className={`mb-4 flex items-start gap-3 rounded-xl border px-4 py-3.5 ${
              d.chain.verified
                ? "border-ok/35 bg-ok/[0.07]"
                : "border-danger/35 bg-danger/[0.07]"
            }`}>
              {d.chain.verified
                ? <ShieldCheck size={18} className="mt-[1px] shrink-0 text-ok" />
                : <ShieldAlert size={18} className="mt-[1px] shrink-0 text-danger" />}
              <div>
                <div className={`text-[13px] font-semibold ${d.chain.verified ? "text-ok" : "text-danger"}`}>
                  {d.chain.verified ? "Audit chain verified" : "Audit chain integrity failure"}
                </div>
                <p className="mt-1 text-[11.5px] leading-relaxed text-ink2">{d.chain.message}</p>
                {!d.chain.verified && d.chain.broken_at_id != null && (
                  <p className="mt-1 text-[11.5px] text-danger">
                    First discontinuity at entry #{d.chain.broken_at_id}
                    {d.chain.reason ? ` (${d.chain.reason} change)` : ""}.
                  </p>
                )}
              </div>
            </div>

            <Panel title={`Chain entries (${d.entries.length})`}
                   hint="Expand an entry to see the payload that was hashed and the SHA-256 link digests.">
              {d.entries.length === 0 ? (
                <EmptyState title="No audit entries recorded for this case." />
              ) : (
                <ol className="space-y-1.5">
                  {d.entries.map((e, i) => (
                    <Entry key={e.id} row={e} index={i} genesis={i === 0} />
                  ))}
                </ol>
              )}
            </Panel>

            <div className="mt-4">
              <Notice kind="warn">{d.disclaimer}</Notice>
            </div>
          </>
        )}
      </Async>
    </>
  );
}

function Entry({ row, index, genesis }: { row: AuditRow; index: number; genesis: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-lg border border-lineSoft bg-s2/40">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-3.5 py-2.5 text-left hover:bg-s2"
      >
        <span className="mt-[1px] w-7 shrink-0 font-mono text-[10.5px] text-muted">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-medium text-ink">{row.action}</span>
            {genesis && <Chip tone="muted" dot={false}>genesis link</Chip>}
          </span>
          <span className="mt-0.5 flex flex-wrap items-center gap-2 text-[10.5px] text-muted">
            <span className="font-mono">{fmtDate(row.occurred_at)}</span>
            <span>·</span>
            <span>{row.component}</span>
            {row.evidence_ref && <><span>·</span><span className="font-mono">{row.evidence_ref}</span></>}
          </span>
        </span>
        <span className="hidden shrink-0 font-mono text-[10.5px] text-muted sm:block">
          {shortHash(row.current_hash, 8)}
        </span>
        <ChevronDown size={14} className={`mt-[1px] shrink-0 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="border-t border-lineSoft px-3.5 py-3">
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Actor">{row.actor}</Field>
            <Field label="Evidence SHA-256 fingerprint" mono>{row.evidence_hash}</Field>
            <Field label="Previous entry digest" mono>{row.prev_hash}</Field>
            <Field label="This entry digest" mono>{row.current_hash}</Field>
          </div>
          <div className="mt-3">
            <div className="lbl mb-1.5">Hashed payload</div>
            <pre className="max-h-44 overflow-auto rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-[10.5px] leading-relaxed text-ink2">
{JSON.stringify(row.payload ?? {}, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </li>
  );
}
