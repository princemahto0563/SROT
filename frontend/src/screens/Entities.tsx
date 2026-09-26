import { useState } from "react";
import { Async, Button, Chip, EmptyState, Field, Meter, Notice, PageHead, Panel, Table, Row, Cell } from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { useSession } from "../state/session";
import { useApi, fmtNum, authenticatedUrl } from "../lib/api";
import type { CaseComparisonPayload } from "../lib/api";
import { Scale, QrCode } from "lucide-react";

type Ent = {
  value: string; entity_type: string; raw_text: string; language: string;
  frame_index: number; frame_number: number | null; timestamp_s: number | null;
  bbox: number[] | null; ocr_confidence: number | null; method: string; region: string;
  frame_image_url: string;
};

type Payload = {
  entities: Ent[]; count: number;
  languages_available?: string[]; ocr_languages_available?: string[];
  scripts_detected?: string[]; empty_reason?: string | null; disclaimer?: string;
};

const typeTone = (t: string) =>
  t === "UPI" || t === "WALLET" ? "danger"
  : t === "PHONE" ? "amber"
  : t === "HANDLE" ? "accent"
  : t === "URL" ? "violet" : "muted";

export default function Entities() {
  return <RequireEvidence>{(ev) => <Body key={ev.evidence_ref} evidenceRef={ev.evidence_ref} />}</RequireEvidence>;
}

function Body({ evidenceRef }: { evidenceRef: string }) {
  const e = useApi<Payload>(`/evidence/${evidenceRef}/entities`);
  const { caseRef } = useSession();
  const comparison = useApi<CaseComparisonPayload>(caseRef ? `/cases/${caseRef}/comparison` : null);
  const [sel, setSel] = useState<number>(0);
  const [showLanguages, setShowLanguages] = useState(false);
  const [mode, setMode] = useState<"current" | "diff">("current");

  const activeComp = comparison.data?.comparisons?.find(
    (c) => c.derivative_evidence_ref === evidenceRef
  );
  const isRef = comparison.data?.reference?.evidence_ref === evidenceRef;

  return (
    <>
      <PageHead
        eyebrow="Step 5 · OCR &amp; media-derived identifiers"
        title="Text and identifiers found in the media"
        sub="Every identifier below was read by OCR from a specific frame, at a specific pixel location,
             with a recorded confidence. They are media-derived identifiers — SROT does not resolve
             who owns them."
      />

      {/* Forensic Differencing Perspective Switch */}
      {comparison.data?.has_reference && comparison.data.reference && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-accent/25 bg-accent/[0.03] p-3 shadow-sm">
          <div className="flex items-center gap-2">
            <Scale size={15} className="text-accent" />
            <span className="text-[11.5px] font-bold text-ink">Comparative Text Perspective:</span>
            <span className="text-[11.5px] text-muted">
              {isRef ? "Reference Item Baseline" : `Case Reference: ${comparison.data.reference.evidence_ref} ⟷ Derivative: ${evidenceRef}`}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              tone={mode === "current" ? "primary" : "ghost"}
              className="text-xs py-0.5 px-2.5"
              onClick={() => setMode("current")}
            >
              Current Item Identifiers
            </Button>
            {!isRef && (
              <Button
                tone={mode === "diff" ? "primary" : "ghost"}
                className="text-xs py-0.5 px-2.5"
                onClick={() => setMode("diff")}
              >
                Text Differences (Diff View)
              </Button>
            )}
          </div>
        </div>
      )}

      {mode === "diff" && activeComp ? (
        <div className="space-y-4 mb-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Added in derivative */}
            <div className="rounded-lg border border-danger/30 bg-danger/[0.04] p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-danger uppercase tracking-wider">
                  Added in Derivative (+{activeComp.identifiers.added_count})
                </span>
                <Chip tone="danger">{activeComp.identifiers.added_count}</Chip>
              </div>
              {activeComp.identifiers.added.length === 0 ? (
                <div className="text-[11.5px] text-muted py-2">No new text elements added.</div>
              ) : (
                <ul className="space-y-2">
                  {activeComp.identifiers.added.map((it, idx) => (
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

            {/* Removed from reference */}
            <div className="rounded-lg border border-line bg-s2/40 p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-muted uppercase tracking-wider">
                  Removed from Reference (-{activeComp.identifiers.removed_count})
                </span>
                <Chip tone="muted">{activeComp.identifiers.removed_count}</Chip>
              </div>
              {activeComp.identifiers.removed.length === 0 ? (
                <div className="text-[11.5px] text-muted py-2">No reference text was erased.</div>
              ) : (
                <ul className="space-y-2">
                  {activeComp.identifiers.removed.map((it, idx) => (
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

            {/* QR Code & Payment Matrix Card */}
            <div className="rounded-lg border border-accent/30 bg-accent/[0.04] p-3.5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[11px] font-bold text-accent uppercase tracking-wider flex items-center gap-1">
                  <QrCode size={13} />
                  <span>QR Code &amp; UPI Matrix</span>
                </span>
                <Chip tone={activeComp.identifiers.qr?.detected ? "amber" : "muted"}>
                  {activeComp.identifiers.qr?.detected ? "DETECTED" : "NONE"}
                </Chip>
              </div>

              {activeComp.identifiers.qr?.detected ? (
                <div className="space-y-2 text-[11.5px]">
                  <div className="rounded border border-line bg-surface p-2">
                    <span className="block text-[10px] uppercase font-semibold text-muted">QR Status</span>
                    <span className="font-semibold text-ink">{activeComp.identifiers.qr.status}</span>
                  </div>
                  {activeComp.identifiers.qr.coordinates && (
                    <div className="rounded border border-line bg-surface p-2">
                      <span className="block text-[10px] uppercase font-semibold text-muted">Bounding Box Coordinates</span>
                      <span className="font-mono text-[11px] text-accent">
                        [x={activeComp.identifiers.qr.coordinates[0]}, y={activeComp.identifiers.qr.coordinates[1]}, w={activeComp.identifiers.qr.coordinates[2]}, h={activeComp.identifiers.qr.coordinates[3]}]
                      </span>
                    </div>
                  )}
                  <div className="text-[10.5px] text-muted leading-relaxed mt-2">
                    Evidence Label: <span className="font-semibold text-ink2">{activeComp.identifiers.evidence_label}</span> (does not identify recipient).
                  </div>
                </div>
              ) : (
                <div className="text-[11.5px] text-muted py-2">
                  No QR matrix detected in this derivative.
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}

      <Async state={e} rows={5}>
        {(d) => {
          const ents = d.entities ?? [];
          const langs = d.ocr_languages_available ?? d.languages_available ?? [];
          const chosen = ents[Math.min(sel, ents.length - 1)];
          return ents.length === 0 ? (
            <EmptyState
              title="No text was reliably extracted by OCR from the sampled frames."
              detail={d.empty_reason ??
                "This is a normal outcome for low-resolution, heavily compressed or text-free media. Nothing is inferred in its place."}
            />
          ) : (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-2.5">
                <Chip tone="muted" dot={false}>{ents.length} identifiers in this file</Chip>
                {langs.length > 0 && (
                  <div className="flex items-center gap-2">
                    <Chip tone="muted" dot={false}>
                      OCR languages: {langs.length >= 50 ? "50+ installed" : `${langs.length} installed`}
                    </Chip>
                    <button
                      type="button"
                      onClick={() => setShowLanguages(!showLanguages)}
                      className="text-[11px] font-semibold text-accent hover:underline"
                    >
                      {showLanguages ? "Hide supported languages" : "View supported languages"}
                    </button>
                  </div>
                )}
                {(d.scripts_detected ?? []).map((s) => (
                  <Chip key={s} tone="violet" dot={false}>{s}</Chip>
                ))}
              </div>

              {showLanguages && langs.length > 0 && (
                <div className="mb-4 rounded-lg border border-line bg-s2/60 p-3 text-[11px]">
                  <div className="font-semibold text-ink mb-1.5">Supported OCR Languages ({langs.length}):</div>
                  <div className="flex flex-wrap gap-1 font-mono text-[10.5px] text-ink2 max-h-36 overflow-y-auto">
                    {langs.map((l) => (
                      <span key={l} className="rounded bg-s3 px-1.5 py-0.5 border border-lineSoft">{l}</span>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
                <Panel title="Extracted identifiers"
                       hint="Select a row to see the exact frame and region it was read from.">
                  <Table head={["Type", "Value", "Frame", "Timestamp", "Confidence", "Script"]}>
                    {ents.map((x, i) => (
                      <Row key={`${x.entity_type}-${x.value}-${i}`}
                           tone={i === Math.min(sel, ents.length - 1) ? "bg-accent/[0.06]" : ""}>
                        <Cell>
                          <button onClick={() => setSel(i)} className="text-left">
                            <Chip tone={typeTone(x.entity_type)} dot={false}>{x.entity_type}</Chip>
                          </button>
                        </Cell>
                        <Cell mono className="text-ink">
                          <button onClick={() => setSel(i)} className="text-left hover:text-accent">
                            {x.value}
                          </button>
                        </Cell>
                        <Cell mono>{x.frame_number ?? x.frame_index}</Cell>
                        <Cell mono>{x.timestamp_s != null ? `${x.timestamp_s.toFixed(2)}s` : "—"}</Cell>
                        <Cell className="w-[112px]">
                          <div className="flex items-center gap-2">
                            <span className="w-[30px] shrink-0 font-mono tabular-nums">
                              {fmtNum(x.ocr_confidence, 0)}
                            </span>
                            <Meter value={x.ocr_confidence ?? 0}
                                   tone={(x.ocr_confidence ?? 0) >= 70 ? "accent" : "amber"} />
                          </div>
                        </Cell>
                        <Cell>{x.language}</Cell>
                      </Row>
                    ))}
                  </Table>
                </Panel>

                <Panel title="Source frame"
                       hint="The identifier is highlighted at the coordinates OCR actually returned.">
                  {chosen && <Highlighted ent={chosen} />}
                </Panel>
              </div>

              <div className="mt-4">
                <Notice kind="warn">
                  {d.disclaimer ??
                    "These are media-derived identifiers. SROT does not perform subscriber lookup, " +
                    "bank or UPI ownership resolution, or any identification of a person. Each value " +
                    "requires human verification and, where applicable, an authorised legal request."}
                </Notice>
              </div>
            </>
          );
        }}
      </Async>
    </>
  );
}

function Highlighted({ ent }: { ent: Ent }) {
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  const box = ent.bbox;

  return (
    <>
      <div className="relative mx-auto w-fit overflow-hidden rounded-lg border border-line bg-black">
        <img
          key={ent.frame_image_url}
          src={authenticatedUrl(ent.frame_image_url)}
          alt={`Frame ${ent.frame_index} containing ${ent.entity_type}`}
          className="block max-h-[420px] w-auto"
          onLoad={(evt) => {
            const el = evt.currentTarget;
            setDims({ w: el.naturalWidth, h: el.naturalHeight });
          }}
        />
        {box && dims && (
          <div
            className="pointer-events-none absolute rounded-[3px] border-2 border-accent shadow-[0_0_0_9999px_rgba(8,9,13,0.65)]"
            style={{
              left: `${(box[0] / dims.w) * 100}%`,
              top: `${(box[1] / dims.h) * 100}%`,
              width: `${(box[2] / dims.w) * 100}%`,
              height: `${(box[3] / dims.h) * 100}%`,
            }}
          />
        )}
      </div>
      <div className="mt-3.5 grid grid-cols-2 gap-x-4 gap-y-3.5">
        <Field label="Value" mono>{ent.value}</Field>
        <Field label="Raw OCR text" mono>{ent.raw_text}</Field>
        <Field label="Region">{ent.region}</Field>
        <Field label="Bounding box" mono>{box ? `[${box.join(", ")}]` : null}</Field>
        <div className="col-span-2">
          <Field label="Method">{ent.method}</Field>
        </div>
      </div>
    </>
  );
}
