import { useState } from "react";
import { Async, Chip, EmptyState, Field, Meter, Notice, PageHead, Panel, Table, Row, Cell } from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { useApi, fmtNum } from "../lib/api";

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
  return <RequireEvidence>{(ev) => <Body evidenceRef={ev.evidence_ref} />}</RequireEvidence>;
}

function Body({ evidenceRef }: { evidenceRef: string }) {
  const e = useApi<Payload>(`/evidence/${evidenceRef}/entities`);
  const [sel, setSel] = useState<number>(0);

  return (
    <>
      <PageHead
        eyebrow="Step 5 · OCR &amp; media-derived identifiers"
        title="Identifiers read from inside the media"
        sub="Every identifier below was read by OCR from a specific frame, at a specific pixel location,
             with a recorded confidence. They are media-derived identifiers — SROT does not resolve
             who owns them."
      />

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
                <Chip tone="muted" dot={false}>{ents.length} identifiers</Chip>
                {langs.length > 0 && (
                  <Chip tone="muted" dot={false}>OCR languages installed: {langs.join(", ")}</Chip>
                )}
                {(d.scripts_detected ?? []).map((s) => (
                  <Chip key={s} tone="violet" dot={false}>{s}</Chip>
                ))}
              </div>

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
          src={ent.frame_image_url}
          alt={`Frame ${ent.frame_index} containing ${ent.entity_type}`}
          className="block max-h-[420px] w-auto"
          onLoad={(evt) => {
            const el = evt.currentTarget;
            setDims({ w: el.naturalWidth, h: el.naturalHeight });
          }}
        />
        {box && dims && (
          <div
            className="pointer-events-none absolute rounded-[3px] border-2 border-accent shadow-[0_0_0_9999px_rgba(6,14,22,0.55)]"
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
