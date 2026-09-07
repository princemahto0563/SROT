import { useState } from "react";
import { Async, Chip, EmptyState, Meter, Notice, PageHead, Panel, Stat, Table, Row, Cell } from "../components/ui";
import { useSession } from "../state/session";
import { useApi, fmtDate, fmtNum } from "../lib/api";

type Payload = {
  matches: {
    other_case_ref: string;
    other_evidence_ref: string;
    evidence_ref?: string;
    similarity: number;
    hamming: number;
    hash_type?: string;
    seen_at: string | null;
  }[];
  count: number;
  ledger_entries: number;
  wording: string;
  empty_reason: string | null;
};

export default function CrossCase() {
  const { caseRef, evidenceRef } = useSession();
  const [filterByEvidence, setFilterByEvidence] = useState(false);
  const endpoint = caseRef
    ? `/cases/${caseRef}/campaign-matches${filterByEvidence && evidenceRef ? `?evidence_ref=${evidenceRef}` : ""}`
    : null;
  const c = useApi<Payload>(endpoint, [caseRef, filterByEvidence, evidenceRef]);

  return (
    <>
      <PageHead
        eyebrow="Step 7 · Cross-case linking"
        title="Has this media appeared in another case?"
        sub="Every fingerprint SROT ingests is added to a department-level ledger. A new upload is
             compared against the fingerprints of other cases before its own rows are written, so a
             case can never match itself."
      />

      <Async state={c} rows={4}>
        {(d) => (
          <>
            <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
              <Stat label="Potential campaign links" value={String(d.count)}
                    sub="other cases with highly similar media" />
              <Stat label="Fingerprint ledger" value={String(d.ledger_entries)}
                    sub="perceptual hashes across all cases" />
              <Stat label="Current case" value={caseRef ?? "—"} sub="compared against all others" />
              <Stat label="Selected evidence" value={evidenceRef ?? "All"} sub={filterByEvidence ? "filtered" : "all items in case"} />
            </div>

            {evidenceRef && (
              <div className="mb-3.5 flex items-center justify-between rounded-lg border border-line bg-surface/60 p-2.5 text-[11.5px]">
                <span className="text-muted">Scope cross-case comparison:</span>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => setFilterByEvidence(false)}
                    className={`rounded px-2 py-1 transition-colors ${!filterByEvidence ? "bg-accent text-accent-ink font-semibold" : "text-muted hover:text-ink"}`}
                  >
                    All Evidence in {caseRef ?? "Case"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilterByEvidence(true)}
                    className={`rounded px-2 py-1 transition-colors ${filterByEvidence ? "bg-accent text-accent-ink font-semibold" : "text-muted hover:text-ink"}`}
                  >
                    Selected Item Only ({evidenceRef})
                  </button>
                </div>
              </div>
            )}

            <Panel title="Matches in other cases"
                   hint="Similarity is computed from multi-view perceptual hashes (Hamming distance on frame views).">
              {d.matches.length === 0 ? (
                <EmptyState
                  title="No qualifying cross-case match found."
                  detail={d.empty_reason ??
                    "No other case in the ledger contains media similar enough to meet the matching threshold."}
                />
              ) : (
                <Table head={["Current evidence", "Other case", "Other evidence", "Directly observed", "Hamming distance", "Inference classification", "Recorded"]}>
                  {d.matches.map((m, i) => (
                    <Row key={`${m.other_case_ref}-${m.other_evidence_ref}-${i}`}>
                      <Cell mono className="text-accent">{m.evidence_ref || evidenceRef || "Current"}</Cell>
                      <Cell mono className="text-ink font-medium">{m.other_case_ref}</Cell>
                      <Cell mono>{m.other_evidence_ref}</Cell>
                      <Cell className="w-[160px]">
                        <div className="flex items-center gap-2">
                          <span className="w-[46px] shrink-0 font-mono tabular-nums">
                            {fmtNum(m.similarity)}%
                          </span>
                          <Meter value={m.similarity} tone="violet" />
                        </div>
                      </Cell>
                      <Cell mono>{m.hamming} / 64 bits</Cell>
                      <Cell>
                        <Chip tone="violet" dot={false}>INFERRED: CAMPAIGN</Chip>
                      </Cell>
                      <Cell>{fmtDate(m.seen_at)}</Cell>
                    </Row>
                  ))}
                </Table>
              )}
            </Panel>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-ok/30 bg-ok/[0.04] p-3.5 text-[11.5px]">
                <div className="font-semibold text-ok mb-1">DIRECTLY OBSERVED EVIDENCE</div>
                <p className="text-muted leading-relaxed">
                  Perceptual hash distance (multi-view pHash) is an empirical mathematical measurement of pixel structure similarity between extracted frames.
                </p>
              </div>
              <div className="rounded-lg border border-accent/30 bg-accent/[0.04] p-3.5 text-[11.5px]">
                <div className="font-semibold text-accent mb-1">INFERRED HYPOTHESIS</div>
                <p className="text-muted leading-relaxed">
                  A cross-case match represents a candidate syndicated campaign relationship warranting joint review. It does <strong>not</strong> prove identical person, group, or physical capture device.
                </p>
              </div>
            </div>

            {d.matches.length > 0 && (
              <div className="mt-4 space-y-3">
                <Notice kind="warn">{d.wording}</Notice>
              </div>
            )}

            <div className="mt-4">
              <Notice kind="info">
                Forensic Safety Standard: Visual similarity between media items in separate cases indicates potential media reuse or syndication. It must never be represented as legal proof of identical author or operator identity without independent corroborating evidence.
              </Notice>
            </div>
          </>
        )}
      </Async>
    </>
  );
}
