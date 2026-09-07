import { Async, Chip, EmptyState, Field, Meter, Notice, PageHead, Panel, Table, Row, Cell } from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { useApi, fmtNum } from "../lib/api";

type RecapturePayload = {
  likelihood: string; score: number | null;
  letterbox: Record<string, unknown> | null;
  static_bands: Record<string, unknown> | null;
  fft: Record<string, unknown> | null;
  regions_scanned: unknown;
  recovered_handles: { handle: string; frame_index: number; region: string;
                       bbox: number[]; confidence: number; method: string }[] | null;
  note: string; metadata_status: string; provenance_status: string;
};

const tone = (l: string) =>
  l === "HIGH" ? "danger" : l === "MEDIUM" ? "amber" : l === "LOW" ? "accent" : "muted";

export default function Recapture() {
  return <RequireEvidence>{(ev) => <Body evidenceRef={ev.evidence_ref} />}</RequireEvidence>;
}

function Body({ evidenceRef }: { evidenceRef: string }) {
  const r = useApi<RecapturePayload>(`/evidence/${evidenceRef}/recapture`);

  return (
    <>
      <PageHead
        eyebrow="Step 4 · Recapture forensics"
        title="Was this copy screen-recorded from another screen?"
        sub="When metadata is stripped and the filename changed, the interface around the media often
             survives. SROT measures the geometry of that interface and reads whatever text is
             actually legible in it."
      />

      <Async state={r} rows={5}
             empty={<EmptyState title="No recapture analysis for this evidence." />}>
        {(d) => {
          const handles = d.recovered_handles ?? [];
          return (
            <>
              <div className="mb-4 grid gap-4 lg:grid-cols-[1fr_1.2fr]">
                <Panel title="Recapture indication"
                       hint="Visual characteristics commonly associated with recording a display were detected.">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-[22px] font-bold leading-none text-ink">
                      Recapture Indication: {d.likelihood}
                    </span>
                    <Chip tone={tone(d.likelihood)}>Recapture Score: {fmtNum(d.score, 1)} / 100</Chip>
                  </div>
                  <div className="mt-3.5">
                    <Meter value={d.score ?? 0} tone={tone(d.likelihood)} />
                  </div>
                  <div className="mt-4 grid grid-cols-1 gap-3.5">
                    <Field label="Metadata">{d.metadata_status}</Field>
                    <Field label="Available File History / Provenance">{d.provenance_status}</Field>
                  </div>
                  <div className="mt-4">
                    <Notice kind="info">
                      Visual characteristics commonly associated with recording a display were detected. Recapture indicators describe physical playback and recording traces; they do not by themselves indicate malicious content manipulation.
                    </Notice>
                  </div>
                </Panel>

                <Panel title="Recovered source handle"
                       hint="Read by OCR from interface regions. A candidate is a reading, not an
                             identification — character confusions such as 0/O and 1/l are common at
                             this resolution.">
                  {handles.length === 0 ? (
                    <EmptyState
                      title="Recapture indicators detected, but no reliable source handle recovered."
                      detail={d.note}
                    />
                  ) : (
                    <>
                      <Table head={["Candidate", "Region", "Frame", "OCR confidence", "Bounding box"]}>
                        {handles.map((h, i) => (
                          <Row key={`${h.handle}-${i}`} tone={i === 0 ? "bg-accent/[0.06]" : ""}>
                            <Cell mono className={i === 0 ? "text-accent" : ""}>{h.handle}</Cell>
                            <Cell>{h.region}</Cell>
                            <Cell mono>{h.frame_index}</Cell>
                            <Cell>
                              <div className="flex items-center gap-2">
                                <span className="w-[34px] shrink-0 font-mono tabular-nums">
                                  {fmtNum(h.confidence, 0)}
                                </span>
                                <Meter value={h.confidence} tone={h.confidence >= 70 ? "accent" : "amber"} />
                              </div>
                            </Cell>
                            <Cell mono>[{h.bbox.join(", ")}]</Cell>
                          </Row>
                        ))}
                      </Table>
                      <div className="mt-3">
                        <Notice kind="warn">
                          {d.note} A candidate is a reading of pixels, not an identification: it must
                          be verified by a person before it is used in an investigation, and SROT
                          does not establish who controls the account.
                        </Notice>
                      </div>
                    </>
                  )}
                </Panel>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <MeasurementPanel title="Letterbox / pillarbox geometry"
                                  hint="Uniform borders around the content area."
                                  data={d.letterbox} />
                <MeasurementPanel title="Static interface bands"
                                  hint="Rows whose pixels barely change over time — the signature of a
                                        fixed interface over moving content."
                                  data={d.static_bands} />
                <MeasurementPanel title="Rescale / moiré response"
                                  hint="Narrow peaks in the frequency spectrum left by re-photographing
                                        or rescaling a display."
                                  data={d.fft} />
              </div>
            </>
          );
        }}
      </Async>
    </>
  );
}

function MeasurementPanel({ title, hint, data }:
  { title: string; hint: string; data: Record<string, unknown> | null }) {
  const detected = data && (data as { detected?: boolean }).detected;
  return (
    <Panel title={title} hint={hint}
           right={<Chip tone={detected ? "accent" : "muted"} dot={false}>
             {data == null ? "Not measured" : detected ? "Detected" : "Not detected"}
           </Chip>}>
      {data == null ? (
        <span className="text-[11.5px] text-muted">This measurement was not recorded for this file.</span>
      ) : (
        <div className="space-y-1 text-[11px]">
          {Object.entries(data).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3 border-b border-lineSoft py-1 last:border-0">
              <span className="text-muted">{k}</span>
              <span className="font-mono tabular-nums text-ink2">
                {typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(4)) : String(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
