import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ReactFlow, Background, Controls, MarkerType, type Edge, type Node, type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Async, Chip, EmptyState, Field, Notice, PageHead, Panel } from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { useApi, fmtDate, fmtNum } from "../lib/api";

type GNode = {
  key: string; kind: string; label: string; sublabel: string | null;
  frame_number: number | null; extraction_method: string | null;
  confidence: number | null; is_synthetic: boolean; observed_at: string | null;
  attrs: Record<string, unknown>; degree: number; position: { x: number; y: number };
};
type GEdge = {
  id: string; source: string; target: string; relation: string; reason: string;
  observation: string; confidence: number | null; evidence_ref: string | null;
};
type Payload = {
  nodes: GNode[]; edges: GEdge[];
  stats: { nodes: number; edges: number; directly_observed: number; inferred: number };
};

const KIND: Record<string, { colour: string; label: string }> = {
  case:       { colour: "#9B96E8", label: "Case" },
  evidence:   { colour: "#4CA6E8", label: "Evidence" },
  hash:       { colour: "#00B4D8", label: "SHA-256 Digest" },
  analysis:   { colour: "#A370F7", label: "Analysis Run" },
  trace:      { colour: "#F77F00", label: "Spatial Visual Trace" },
  frame:      { colour: "#6C7F94", label: "Frame" },
  extraction: { colour: "#3FB98A", label: "Extraction step" },
  identifier: { colour: "#E9A33A", label: "Media-derived identifier" },
  origin:     { colour: "#E5605C", label: "Corpus copy / origin" },
  copy:       { colour: "#E5605C", label: "Near-duplicate copy" },
  campaign:   { colour: "#9B96E8", label: "Cross-case link" },
  account:    { colour: "#D97706", label: "Recovered Account Handle" },
};

export default function GraphScreen() {
  return <RequireEvidence>{(ev) => <Body evidenceRef={ev.evidence_ref} />}</RequireEvidence>;
}

function Body({ evidenceRef }: { evidenceRef: string }) {
  const g = useApi<Payload>(`/evidence/${evidenceRef}/graph`);
  const [sel, setSel] = useState<GNode | null>(null);

  return (
    <>
      <PageHead
        eyebrow="Step 6 · Investigation graph"
        title="What SROT observed and how the connections were made"
        sub="Every node in this graph was extracted from the media. Edges distinguish DIRECTLY OBSERVED relationships from INFERRED relationships."
      />

      <Async state={g} rows={5}>
        {(d) => d.nodes.length === 0 ? (
          <EmptyState
            title="The graph is empty."
            detail="Nodes are built from findings produced by an analysed evidence item. Removing the evidence removes everything derived from it."
          />
        ) : (
          <GraphView data={d} sel={sel} setSel={setSel} />
        )}
      </Async>
    </>
  );
}

function GraphView({ data, sel, setSel }: {
  data: Payload; sel: GNode | null; setSel: (n: GNode | null) => void;
}) {
  const byKey = useMemo(
    () => Object.fromEntries(data.nodes.map((n) => [n.key, n])),
    [data.nodes],
  );

  const nodes: Node[] = useMemo(() => data.nodes.map((n) => {
    const c = KIND[n.kind]?.colour ?? "#6C7F94";
    const active = sel?.key === n.key;
    return {
      id: n.key,
      position: n.position,
      data: {
        label: (
          <div className="px-1 text-left">
            <div className="text-[10px] font-semibold uppercase tracking-[0.08em]" style={{ color: c }}>
              {KIND[n.kind]?.label ?? n.kind}
            </div>
            <div className="mt-[3px] max-w-[152px] truncate text-[11.5px] font-semibold text-ink">
              {n.label}
            </div>
            {n.sublabel && (
              <div className="max-w-[152px] truncate text-[10px] text-muted">{n.sublabel}</div>
            )}
          </div>
        ),
      },
      style: {
        background: "#121A24",
        border: `1.5px solid ${active ? c : "#223141"}`,
        boxShadow: active ? `0 0 0 3px ${c}33` : "0 6px 18px rgba(0,0,0,.32)",
        borderRadius: 10,
        padding: "7px 6px",
        width: 168,
      },
    };
  }), [data.nodes, sel]);

  const edges: Edge[] = useMemo(() => data.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.relation,
    animated: e.observation !== "DIRECTLY_OBSERVED",
    style: {
      stroke: e.observation === "DIRECTLY_OBSERVED" ? "#2C4157" : "#9B96E8",
      strokeWidth: 1.4,
      strokeDasharray: e.observation === "DIRECTLY_OBSERVED" ? undefined : "5 4",
    },
    markerEnd: { type: MarkerType.ArrowClosed, color: "#2C4157", width: 14, height: 14 },
  })), [data.edges]);

  const onNodeClick = useCallback<NodeMouseHandler>((_, node) => {
    setSel(byKey[node.id] ?? null);
  }, [byKey, setSel]);

  const selEdges = sel ? data.edges.filter((e) => e.source === sel.key || e.target === sel.key) : [];

  return (
    <>
      <div className="mb-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone="muted" dot={false}>{data.stats.nodes} nodes</Chip>
          <Chip tone="muted" dot={false}>{data.stats.edges} edges</Chip>
          <Chip tone="accent" dot={false} title="Taken directly from the media or evidence record.">{data.stats.directly_observed} directly observed</Chip>
          <Chip tone="violet" dot={false} title="Suggested from relationships between observed evidence. Not proof of identity or involvement.">{data.stats.inferred} inferred</Chip>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-ink2 bg-s2 border border-line px-3 py-1.5 rounded-lg">
          <div className="flex items-center gap-1.5" title="Taken directly from the media or evidence record.">
            <span className="inline-block w-4 h-[2px] bg-[#4CA6E8]"></span>
            <span className="font-medium text-ink">Directly Observed</span>
          </div>
          <div className="flex items-center gap-1.5" title="Suggested from relationships between observed evidence. Not proof of identity or involvement.">
            <span className="inline-block w-4 h-[2px] border-b-2 border-dashed border-[#9B96E8]"></span>
            <span className="font-medium text-ink">Inferred</span>
          </div>
        </div>
      </div>

      <div className="panel shadow-panel mb-4 overflow-hidden" style={{ height: 470 }}>
        <ReactFlow
          nodes={nodes} edges={edges} onNodeClick={onNodeClick}
          fitView fitViewOptions={{ padding: 0.06 }}
          minZoom={0.15} maxZoom={2} proOptions={{ hideAttribution: true }}
          nodesDraggable nodesConnectable={false} elementsSelectable
        >
          <Background color="#1A2634" gap={22} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.35fr_1fr]">
        <div>
          <Panel title={sel ? "Selected node" : "Node inspector"}
                 hint={sel ? undefined : "Click any node to see exactly how it was derived."}>
            {!sel ? (
              <EmptyState title="No node selected."
                          detail="Every node records the method that produced it and the evidence it came from." />
            ) : (
              <>
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[15px] font-semibold text-ink">{sel.label}</span>
                    <Chip tone="muted" dot={false}>{KIND[sel.kind]?.label ?? sel.kind}</Chip>
                    {sel.is_synthetic && <Chip tone="violet" dot={false}>synthetic demo record</Chip>}
                  </div>
                  <div>
                    {sel.kind === "evidence" && <Link to="/analysis" className="text-xs font-semibold text-accent hover:underline">Inspect Analysis →</Link>}
                    {sel.kind === "analysis" && <Link to="/analysis" className="text-xs font-semibold text-accent hover:underline">View Forensic Assessment →</Link>}
                    {sel.kind === "trace" && <Link to="/analysis" className="text-xs font-semibold text-accent hover:underline">View Visual Traces →</Link>}
                    {sel.kind === "identifier" && <Link to="/entities" className="text-xs font-semibold text-accent hover:underline">View OCR Identifiers →</Link>}
                    {sel.kind === "account" && <Link to="/recapture" className="text-xs font-semibold text-accent hover:underline">View Recapture →</Link>}
                    {(sel.kind === "origin" || sel.kind === "copy") && <Link to="/origin" className="text-xs font-semibold text-accent hover:underline">View Origin Trace →</Link>}
                    {sel.kind === "campaign" && <Link to="/cross-case" className="text-xs font-semibold text-accent hover:underline">View Cross-Case Links →</Link>}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-3.5">
                  <Field label="Detail">{sel.sublabel}</Field>
                  <Field label="Confidence">
                    {sel.confidence != null ? fmtNum(sel.confidence, 2) : null}
                  </Field>
                  <Field label="Derived by">{sel.extraction_method}</Field>
                  <Field label="Observed at">
                    {sel.observed_at ? fmtDate(sel.observed_at) : null}
                  </Field>
                  <Field label="Connections">{sel.degree}</Field>
                  <Field label="Frame">{sel.frame_number ?? null}</Field>
                </div>
                {Object.keys(sel.attrs ?? {}).length > 0 && (
                  <div className="mt-3.5">
                    <div className="lbl mb-1.5">Recorded attributes</div>
                    <pre className="max-h-40 overflow-auto rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-[10.5px] leading-relaxed text-ink2">
{JSON.stringify(sel.attrs, null, 2)}
                    </pre>
                  </div>
                )}
                {selEdges.length > 0 && (
                  <div className="mt-3.5">
                    <div className="lbl mb-1.5">Relationships</div>
                    <ul className="space-y-1.5">
                      {selEdges.map((e) => (
                        <li key={e.id} className="rounded-lg border border-lineSoft bg-s2/50 px-3 py-2">
                          <div className="flex items-center gap-2 text-[11.5px]">
                            <span className="font-semibold text-ink">{e.relation}</span>
                            <Chip tone={e.observation === "DIRECTLY_OBSERVED" ? "accent" : "violet"} dot={false} title={e.observation === "DIRECTLY_OBSERVED" ? "Taken directly from the media or evidence record." : "Suggested from relationships between observed evidence. Not proof of identity or involvement."}>
                              {e.observation === "DIRECTLY_OBSERVED" ? "Directly observed" : "Inferred"}
                            </Chip>
                          </div>
                          <p className="mt-1 text-[11px] leading-relaxed text-muted">{e.reason}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </Panel>
        </div>

        <div>
          <Panel title="Legend">
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(KIND).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-[11px] text-ink2">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: v.colour }} />
                  {v.label}
                </div>
              ))}
            </div>
            <div className="mt-4 space-y-2.5 text-[11px] text-muted border-t border-line pt-3">
              <div className="flex items-start gap-2">
                <svg width="24" height="12" className="mt-1 flex-shrink-0"><line x1="0" y1="6" x2="24" y2="6" stroke="#2C4157" strokeWidth="2" /></svg>
                <div>
                  <span className="font-semibold text-ink">Directly observed:</span> Taken directly from the media or evidence record.
                </div>
              </div>
              <div className="flex items-start gap-2">
                <svg width="24" height="12" className="mt-1 flex-shrink-0"><line x1="0" y1="6" x2="24" y2="6" stroke="#9B96E8" strokeWidth="2" strokeDasharray="5 4" /></svg>
                <div>
                  <span className="font-semibold text-ink">Inferred:</span> Suggested from relationships between observed evidence. Not proof of identity or involvement.
                </div>
              </div>
            </div>
          </Panel>
        </div>
      </div>

      <div className="mt-4">
        <Notice kind="warn">
          A connection in this graph is an investigative lead, not proof of identity, ownership, or intent.
          It represents a relationship between artefacts observed in media and requires independent examiner verification.
        </Notice>
      </div>
    </>
  );
}
