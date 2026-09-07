import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { UploadCloud, CheckCircle2, XCircle, Loader2, FileCheck2 } from "lucide-react";
import {
  Button, Chip, EmptyState, Field, Notice, PageHead, Panel,
} from "../components/ui";
import { useSession } from "../state/session";
import { api, useApi, usePolling, fmtBytes, fmtDate } from "../lib/api";
import type { Evidence, RunSummary } from "../lib/api";

const STAGE_LABEL: Record<string, string> = {
  INGEST: "Container & metadata",
  ANALYSIS: "Forensic signal ensemble",
  TRACE: "Origin trace (corpus search)",
  OCR: "OCR & identifier extraction",
  RECAPTURE: "Recapture forensics",
  GRAPH: "Investigation graph",
  LEADS: "Lead generation",
};

export default function Intake() {
  const { caseRef, refresh, setEvidenceRef, current, createNewCase } = useSession();
  const [busy, setBusy] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [justUploaded, setJustUploaded] = useState<Evidence | null>(null);
  const [targetMode, setTargetMode] = useState<"new_case" | "existing_case">("new_case");
  const fileInput = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  const watched = justUploaded?.evidence_ref ?? current?.evidence_ref ?? null;
  const job = usePolling<{ status: string; stage: string | null; stages: Record<string, string>;
                           error?: string | null; assessment?: string | null }>(
    watched ? `/evidence/${watched}/job` : null,
    (d) => d.status === "queued" || d.status === "running",
    1200,
  );

  // When job reaches terminal status, trigger session refresh
  useEffect(() => {
    if (job.data?.status === "completed" || job.data?.status === "failed") {
      refresh();
      if (job.data?.status === "completed") {
        setJustUploaded(null);
      }
    }
  }, [job.data?.status, refresh]);

  const send = useCallback(async (file: File) => {
    setBusy(true); setUploadErr(null);
    try {
      let activeCaseRef = caseRef;
      if (targetMode === "new_case" || !activeCaseRef) {
        const cleanName = file.name.replace(/[^\w.-]/g, "_");
        const nc = await createNewCase({
          title: `Forensic Intake · ${cleanName}`,
          category: "Digital Media Forensics",
          officer: "Forensic Examiner",
          summary: `Independent intake for uploaded media file '${cleanName}'. Isolated from pre-existing case campaigns.`,
        });
        activeCaseRef = nc.case_ref;
      }
      const form = new FormData();
      form.append("file", file);
      form.append("analyse", "true");
      const res = await api.upload<{ evidence: Evidence }>(`/cases/${activeCaseRef}/evidence`, form);
      setJustUploaded(res.evidence);
      setEvidenceRef(res.evidence.evidence_ref);
      refresh();
    } catch (e) {
      setUploadErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [caseRef, targetMode, createNewCase, refresh, setEvidenceRef]);

  const shown = (current && current.evidence_ref === watched) ? current : (justUploaded ?? current);
  const stages = job.data?.stages ?? {};
  const stageKeys = Object.keys(stages);
  const done = stageKeys.filter((k) => stages[k] === "completed").length;
  const pct = stageKeys.length ? Math.round((done / stageKeys.length) * 100) : 0;

  return (
    <>
      <PageHead
        eyebrow="Step 1 · Evidence intake"
        title="Ingest media and run the pipeline"
        sub="The file is written to immutable evidence storage and its SHA-256 is computed before any
             analysis touches it, so the integrity record precedes every derived finding."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_1.15fr]">
        <Panel title="Upload evidence"
               hint="Video, image, or audio. Maximum 300 MB. Filenames are sanitised and isolated.">
          <div className="mb-3.5 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line bg-surface/60 p-2 text-[11px]">
            <span className="font-semibold text-ink">Intake Container:</span>
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => setTargetMode("new_case")}
                className={`rounded px-2 py-1 transition-colors ${targetMode === "new_case" ? "bg-accent text-accent-ink font-semibold" : "text-muted hover:text-ink"}`}
              >
                ● New Independent Case (Default)
              </button>
              <button
                type="button"
                onClick={() => setTargetMode("existing_case")}
                className={`rounded px-2 py-1 transition-colors ${targetMode === "existing_case" ? "bg-accent text-accent-ink font-semibold" : "text-muted hover:text-ink"}`}
              >
                Attach to {caseRef ?? "Active Case"}
              </button>
            </div>
          </div>

          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault(); setDrag(false);
              const f = e.dataTransfer.files?.[0];
              if (f) void send(f);
            }}
            className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors ${
              drag ? "border-accent bg-accent/[0.06]" : "border-line bg-s2/40"
            }`}
          >
            <UploadCloud size={30} className={drag ? "text-accent" : "text-muted"} />
            <div className="text-[12.5px] text-ink2">
              Drop a file here, or
            </div>
            <Button onClick={() => fileInput.current?.click()} disabled={busy}>
              {busy ? <><Loader2 size={14} className="animate-spin" /> Uploading…</> : "Choose a file"}
            </Button>
            <input
              ref={fileInput} type="file" className="hidden"
              accept="video/*,image/*,audio/*,.wav,.mp3,.m4a,.aac,.flac,.ogg"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) void send(f); e.target.value = ""; }}
            />
            <p className="max-w-[46ch] text-[11px] leading-relaxed text-muted">
              Supported: Video (MP4, MKV, MOV, WebM), Image (JPEG, PNG, WebP), Audio (WAV, MP3, AAC, FLAC).
              Every upload is analyzed dynamically from its own raw bytes.
            </p>
          </div>

          {uploadErr && (
            <div className="mt-4 rounded-lg border border-danger/35 bg-danger/[0.07] px-3.5 py-2.5 text-[11.5px] text-danger">
              {uploadErr}
            </div>
          )}
        </Panel>

        <Panel title="Pipeline progress"
               hint="Seven stages run in the background. Each stage writes its own rows; a failure is
                     recorded rather than hidden.">
          {!shown ? (
            <EmptyState title="No evidence selected."
                        detail="Upload a file, or pick an existing item in the sidebar." />
          ) : (
            <>
              <div className="mb-4 grid grid-cols-2 gap-x-4 gap-y-3.5">
                <Field label="Evidence reference"><span className="font-mono text-accent">{shown.evidence_ref}</span></Field>
                <Field label="Ingested">{fmtDate(shown.ingested_at)}</Field>
                <Field label="File">{shown.filename}</Field>
                <Field label="Size">{fmtBytes(shown.size_bytes)}</Field>
                <div className="col-span-2">
                  <Field label="SHA-256 computed at ingest" mono>{shown.sha256}</Field>
                </div>
              </div>

              <div className="mb-2 flex items-center justify-between">
                <span className="lbl">Stages</span>
                <span className="text-[11px] tabular-nums text-muted">{pct}%</span>
              </div>
              <div className="mb-3 h-[6px] w-full overflow-hidden rounded-full bg-s3">
                <div className="h-full rounded-full bg-accent transition-all duration-500"
                     style={{ width: `${Math.max(pct, 2)}%` }} />
              </div>

              <ul className="space-y-1.5">
                {(stageKeys.length ? stageKeys : Object.keys(STAGE_LABEL)).map((k) => {
                  const st = stages[k] ?? "queued";
                  return (
                    <li key={k} className="flex items-center gap-2.5 text-[11.5px]">
                      {st === "completed" ? <CheckCircle2 size={14} className="text-ok" />
                        : st === "running" ? <Loader2 size={14} className="animate-spin text-accent" />
                        : st === "failed" ? <XCircle size={14} className="text-danger" />
                        : <span className="h-[14px] w-[14px] rounded-full border border-line" />}
                      <span className={st === "completed" ? "text-ink2" : st === "running" ? "text-ink" : "text-muted"}>
                        {STAGE_LABEL[k] ?? k}
                      </span>
                    </li>
                  );
                })}
              </ul>

              {job.data?.status === "failed" && (
                <div className="mt-4 rounded-lg border border-danger/35 bg-danger/[0.07] px-3.5 py-2.5 text-[11.5px] text-danger">
                  Analysis failed: {job.data.error ?? "no error message recorded"}
                </div>
              )}

              {job.data?.status === "completed" && (
                <div className="mt-4 flex flex-wrap items-center gap-2.5">
                  <Chip tone="ok"><FileCheck2 size={11} /> Analysis complete</Chip>
                  <Link to="/analysis" className="btn btn-primary text-[12px]">View forensic analysis</Link>
                </div>
              )}
            </>
          )}
        </Panel>
      </div>

      <div className="mt-5">
        <Notice kind="info">
          The stored copy is never modified. All frame extraction, variant generation and rendering
          happen on working copies, and the original's hash is re-verifiable at any time from the
          Court Packet screen.
        </Notice>
      </div>

      {shown && <EvidenceViewer evidence={shown} run={job.data as RunSummary | null} />}
    </>
  );
}

function EvidenceViewer({ evidence, run }: { evidence: Evidence; run: RunSummary | null }) {
  // Live dynamic query for latest evidence probe data
  const live = useApi<Evidence>(`/evidence/${evidence.evidence_ref}`, [run?.status, run?.stage]);
  const ev = live.data ?? evidence;
  const ready = run?.status === "completed" || ev.latest_run?.status === "completed";
  return (
    <div className="mt-4">
      <Panel title="Evidence viewer"
             hint="The ingested file, played from immutable storage. Container facts are read from the
                   file itself; fields the file does not carry are shown as not available.">
        <div className="grid gap-5 md:grid-cols-[minmax(0,280px)_1fr]">
          <div className="mx-auto w-fit overflow-hidden rounded-lg border border-line bg-black">
            {ev.media_kind === "image" ? (
              <img src={`/api/evidence/${ev.evidence_ref}/media`} alt="Ingested evidence"
                   className="block max-h-[420px] w-auto" />
            ) : (
              <video src={`/api/evidence/${ev.evidence_ref}/media`} controls muted
                     className="block max-h-[420px] w-auto" />
            )}
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-3.5 md:grid-cols-3">
            <Field label="Media kind">{ev.media_kind}</Field>
            <Field label="Container">{ev.container_format}</Field>
            <Field label="Source resolution">
              {ev.width && ev.height ? `${ev.width} × ${ev.height}` : null}
            </Field>
            <Field label="Duration">
              {ev.duration_s != null ? `${ev.duration_s.toFixed(2)} s` : null}
            </Field>
            <Field label="Frame rate">{ev.fps != null ? `${ev.fps} fps` : null}</Field>
            <Field label="Video codec">{ev.video_codec}</Field>
            <Field label="Audio">
              {ev.has_audio ? (ev.audio_codec ?? "present") : "No audio stream"}
            </Field>
            <Field label="Encoder tag">{ev.encoder_tag}</Field>
            <Field label="EXIF fields">
              {ev.exif_fields > 0 ? String(ev.exif_fields) : "None present"}
            </Field>
            <div className="col-span-2 md:col-span-3">
              <Field label="Provenance (C2PA)">
                <span className={ev.c2pa_present ? "text-ok" : "text-ink2"}>
                  {ev.c2pa_present ? "Manifest marker present" : "No C2PA manifest found"}
                </span>
                <p className="mt-1 text-[11px] leading-relaxed text-muted">{ev.c2pa_note}</p>
              </Field>
            </div>
          </div>
        </div>
        {!ready && (
          <p className="mt-4 text-[11.5px] text-muted">
            Container fields populate once the ingest stage completes.
          </p>
        )}
      </Panel>
    </div>
  );
}
