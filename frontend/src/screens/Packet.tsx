import { useRef, useState } from "react";
import { CheckCircle2, Download, ExternalLink, FileText, Loader2, ShieldAlert, ShieldCheck } from "lucide-react";
import {
  Async, Button, Chip, EmptyState, Field, Notice, PageHead, Panel, Table, Row, Cell,
} from "../components/ui";
import { RequireEvidence } from "../components/guards";
import { api, useApi, fmtDate, authenticatedUrl, getAuthToken } from "../lib/api";
import type { Consistency, Evidence, Packet as PacketPayload } from "../lib/api";

const DOC_LABEL: Record<string, string> = {
  bsa63_certificate: "BSA Section 63 certificate",
  hash_report: "SHA-256 hash report",
  chain_of_custody: "Chain of custody",
  technical_annexure: "Technical forensic annexure",
  preservation_request: "Preservation request",
  forensic_report: "Forensic analysis report",
};

export default function Packet() {
  return <RequireEvidence>{(ev) => <Body evidence={ev} />}</RequireEvidence>;
}

function Body({ evidence }: { evidence: Evidence }) {
  const ref = evidence.evidence_ref;
  const [building, setBuilding] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [downloadingZip, setDownloadingZip] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const [dossierLoading, setDossierLoading] = useState(false);
  const [dossierFeedback, setDossierFeedback] = useState<{ kind: "ok" | "err"; message: string } | null>(null);
  const [openingDoc, setOpeningDoc] = useState<Record<string, boolean>>({});
  const [docFeedback, setDocFeedback] = useState<{ kind: "ok" | "err"; message: string } | null>(null);

  const p = useApi<PacketPayload>(`/evidence/${ref}/court-packet`);
  const c = useApi<Consistency>(`/evidence/${ref}/consistency`);

  const build = async () => {
    setBuilding(true); setErr(null); setDownloadSuccess(null); setDownloadError(null);
    setDossierFeedback(null); setDocFeedback(null);
    try {
      await api.post(`/evidence/${ref}/court-packet`);
      p.reload(); c.reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBuilding(false);
    }
  };

  const handleDownloadExecutiveDossier = async () => {
    if (dossierLoading) return;
    setDossierLoading(true);
    setDossierFeedback(null);
    try {
      const dossierPath = `/api/evidence/${ref}/executive-dossier`;
      const fullUrl = authenticatedUrl(dossierPath);
      const headers: Record<string, string> = {};
      const token = getAuthToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(fullUrl, { headers });
      if (!res.ok) {
        let errMsg = `Server returned HTTP ${res.status}`;
        try {
          const errBody = await res.json();
          if (errBody?.detail) errMsg = errBody.detail;
        } catch { /* ignore non-json */ }
        throw new Error(errMsg);
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const filename = `SROT_Executive_Dossier_${ref}.pdf`;
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
      setDossierFeedback({
        kind: "ok",
        message: `PDF downloaded successfully: ${filename}`,
      });
    } catch (e) {
      setDossierFeedback({
        kind: "err",
        message: `Failed to download Executive Dossier: ${(e as Error).message}`,
      });
    } finally {
      setDossierLoading(false);
    }
  };

  const handleOpenDoc = async (doc: { key: string; name: string; url: string }) => {
    if (openingDoc[doc.key]) return;
    setOpeningDoc((prev) => ({ ...prev, [doc.key]: true }));
    setDocFeedback(null);
    try {
      const cleanUrl = `/api${doc.url.replace(/^\/api/, "")}?inline=true`;
      const fullUrl = authenticatedUrl(cleanUrl);
      const headers: Record<string, string> = {};
      const token = getAuthToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(fullUrl, { headers });
      if (!res.ok) {
        let errMsg = `Server returned HTTP ${res.status}`;
        try {
          const errBody = await res.json();
          if (errBody?.detail) errMsg = errBody.detail;
        } catch { /* ignore non-json */ }
        throw new Error(errMsg);
      }
      const blob = await res.blob();
      const pdfBlob = new Blob([blob], { type: "application/pdf" });
      const blobUrl = URL.createObjectURL(pdfBlob);
      const newWin = window.open(blobUrl, "_blank");
      if (!newWin || newWin.closed || typeof newWin.closed === "undefined") {
        // Fallback: trigger direct download if popup blocked by browser
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = `${doc.name}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setDocFeedback({
          kind: "ok",
          message: `Popup blocked by browser — downloaded ${doc.name}.pdf directly`,
        });
      } else {
        setDocFeedback({
          kind: "ok",
          message: `Opened PDF successfully: ${doc.name}.pdf`,
        });
      }
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (e) {
      setDocFeedback({
        kind: "err",
        message: `Failed to open ${doc.name}: ${(e as Error).message}`,
      });
    } finally {
      setOpeningDoc((prev) => ({ ...prev, [doc.key]: false }));
    }
  };

  const handleDownloadDoc = async (doc: { key: string; name: string; url: string }) => {
    if (openingDoc[doc.key]) return;
    setOpeningDoc((prev) => ({ ...prev, [doc.key]: true }));
    setDocFeedback(null);
    try {
      const cleanUrl = `/api${doc.url.replace(/^\/api/, "")}`;
      const fullUrl = authenticatedUrl(cleanUrl);
      const headers: Record<string, string> = {};
      const token = getAuthToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(fullUrl, { headers });
      if (!res.ok) {
        let errMsg = `Server returned HTTP ${res.status}`;
        try {
          const errBody = await res.json();
          if (errBody?.detail) errMsg = errBody.detail;
        } catch { /* ignore non-json */ }
        throw new Error(errMsg);
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const filename = `${doc.name}.pdf`;
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
      setDocFeedback({
        kind: "ok",
        message: `PDF downloaded successfully: ${filename}`,
      });
    } catch (e) {
      setDocFeedback({
        kind: "err",
        message: `Failed to download ${doc.name}: ${(e as Error).message}`,
      });
    } finally {
      setOpeningDoc((prev) => ({ ...prev, [doc.key]: false }));
    }
  };

  const handleDownloadZip = async (zipUrl: string) => {
    if (downloadingZip) return;
    setDownloadingZip(true);
    setDownloadError(null);
    setDownloadSuccess(null);
    try {
      const cleanUrl = `/api${zipUrl.replace(/^\/api/, "")}`;
      const fullUrl = authenticatedUrl(cleanUrl);
      const headers: Record<string, string> = {};
      const token = getAuthToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(fullUrl, { headers });
      if (!res.ok) {
        throw new Error(`Failed to download packet archive (HTTP ${res.status})`);
      }
      const disp = res.headers.get("content-disposition");
      let filename = `SROT_${ref}_COURT_PACKET.zip`;
      if (disp && disp.includes("filename=")) {
        const match = disp.match(/filename="?([^";]+)"?/);
        if (match && match[1]) filename = match[1];
      }
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);
      setDownloadSuccess(filename);
    } catch (e) {
      setDownloadError((e as Error).message);
    } finally {
      setDownloadingZip(false);
    }
  };

  return (
    <>
      <PageHead
        eyebrow="Step 11 · Court-ready evidence packet"
        title="Structured evidence documentation for examiner and legal review"
        sub="Canonical documentation rendered directly from the analysis record. Figures across certificates, reports, and annexures are derived from identical database values."
        right={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDownloadExecutiveDossier}
              disabled={dossierLoading}
              className="btn btn-ghost text-xs flex items-center gap-1.5"
            >
              {dossierLoading ? (
                <><Loader2 size={13} className="animate-spin text-accent" /> Preparing PDF…</>
              ) : (
                <><Download size={13} /> Executive Dossier (PDF)</>
              )}
            </button>
            <Button onClick={build} disabled={building}>
              {building ? <><Loader2 size={14} className="animate-spin" /> Generating…</>
                        : <><FileText size={14} /> {p.data?.packet_id ? "Regenerate packet" : "Generate packet"}</>}
            </Button>
          </div>
        }
      />

      {dossierFeedback && (
        <div className={`mb-4 flex items-center justify-between gap-2.5 rounded-lg border p-2.5 text-[11.5px] ${
          dossierFeedback.kind === "ok"
            ? "border-ok/30 bg-ok/5 text-ok"
            : "border-danger/30 bg-danger/5 text-danger"
        }`}>
          <div className="flex items-center gap-2">
            {dossierFeedback.kind === "ok" ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
            <span>{dossierFeedback.message}</span>
          </div>
          <button
            type="button"
            onClick={() => setDossierFeedback(null)}
            className="text-xs text-muted hover:text-ink px-1"
          >
            ✕
          </button>
        </div>
      )}

      {err && (
        <div className="mb-4 rounded-lg border border-danger/35 bg-danger/[0.07] px-3.5 py-2.5 text-[11.5px] text-danger">
          {err}
        </div>
      )}

      <div className="mb-4">
        <Notice kind="warn">
          Structured evidence documentation for examiner and legal review. This does not constitute an automatic guarantee of legal admissibility. Legal admissibility is determined by the presiding court. SROT provides objective technical decision support and does not certify anything on anyone's behalf.
        </Notice>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Panel title="Packet documents">
          <Async state={p} rows={4}>
            {(d) => !d.packet_id ? (
              <EmptyState
                title="No packet has been generated for this evidence."
                detail={d.empty_reason ??
                  "Generate the packet to render the six documents and a signed-hash ZIP archive."}
                action={<Button onClick={build} disabled={building}>Generate packet</Button>}
              />
            ) : (
              <>
                <div className="mb-3.5 grid grid-cols-2 gap-x-4 gap-y-3.5">
                  <Field label="Generated">{fmtDate(d.created_at)}</Field>
                  <Field label="Packet ID">#{d.packet_id}</Field>
                  <div className="col-span-2">
                    <Field label="Packet SHA-256" mono>{d.packet_sha256}</Field>
                  </div>
                </div>
                <ul className="space-y-1.5">
                  {d.documents.map((doc, i) => {
                    const isBusy = !!openingDoc[doc.key];
                    return (
                      <li key={doc.key}
                          className="flex items-center gap-3 rounded-lg border border-lineSoft bg-s2/40 px-3.5 py-2.5">
                        <span className="w-5 shrink-0 font-mono text-[10.5px] text-muted">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <FileText size={14} className="shrink-0 text-accent" />
                        <span className="min-w-0 flex-1 truncate text-[12px] text-ink">
                          {DOC_LABEL[doc.key] ?? doc.name}
                        </span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleOpenDoc(doc)}
                            disabled={isBusy}
                            className="btn btn-ghost text-[11px] flex items-center gap-1"
                          >
                            {isBusy ? (
                              <><Loader2 size={12} className="animate-spin" /> Preparing PDF…</>
                            ) : (
                              <><ExternalLink size={12} /> Open PDF</>
                            )}
                          </button>
                          <button
                            type="button"
                            title={`Download ${doc.name}.pdf`}
                            onClick={() => handleDownloadDoc(doc)}
                            disabled={isBusy}
                            className="btn btn-ghost p-1.5 text-muted hover:text-ink"
                          >
                            <Download size={13} />
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>

                {docFeedback && (
                  <div className={`mt-3 flex items-center justify-between gap-2.5 rounded-lg border p-2.5 text-[11.5px] ${
                    docFeedback.kind === "ok"
                      ? "border-ok/30 bg-ok/5 text-ok"
                      : "border-danger/30 bg-danger/5 text-danger"
                  }`}>
                    <div className="flex items-center gap-2">
                      {docFeedback.kind === "ok" ? <CheckCircle2 size={15} /> : <ShieldAlert size={15} />}
                      <span>{docFeedback.message}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setDocFeedback(null)}
                      className="text-xs text-muted hover:text-ink px-1"
                    >
                      ✕
                    </button>
                  </div>
                )}

                <div className="mt-4 pt-3 border-t border-lineSoft space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Button
                      onClick={() => handleDownloadZip(d.zip_url)}
                      disabled={downloadingZip}
                      className="text-[12px]"
                    >
                      {downloadingZip ? (
                        <><Loader2 size={14} className="animate-spin" /> Preparing ZIP archive…</>
                      ) : downloadSuccess ? (
                        <><CheckCircle2 size={14} className="text-ok" /> Packet downloaded ✓</>
                      ) : downloadError ? (
                        <><ShieldAlert size={14} className="text-danger" /> Download failed — Retry</>
                      ) : (
                        <><Download size={14} /> Download full packet (.zip)</>
                      )}
                    </Button>

                    <div className="flex items-center gap-2 text-[11px] text-muted">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-ok" />
                      <span>Packet ready · <b>{d.documents.length} documents</b> · SHA-256 verified · ZIP archive</span>
                    </div>
                  </div>

                  {downloadSuccess && (
                    <div className="flex items-start gap-2.5 rounded-lg border border-ok/30 bg-ok/5 p-2.5 text-[11.5px] text-ok">
                      <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
                      <div className="min-w-0">
                        <div className="font-semibold">Evidence packet downloaded successfully</div>
                        <div className="font-mono text-[10.5px] text-ink2 truncate mt-0.5">{downloadSuccess}</div>
                        <div className="text-[10px] text-muted mt-0.5">Signed ZIP archive saved to your browser downloads.</div>
                      </div>
                    </div>
                  )}

                  {downloadError && (
                    <div className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-2.5 text-[11.5px] text-danger">
                      <ShieldAlert size={14} className="shrink-0" />
                      <span>Download failed: {downloadError}</span>
                    </div>
                  )}
                </div>
              </>
            )}
          </Async>
        </Panel>

        <div className="space-y-4">
          <VerifyHash evidence={evidence} />

          <Panel title="Report consistency check"
                 hint="Compares the database rows, the API payloads and the rendered documents field by field.">
            <Async state={c} rows={3}>
              {(d) => (
                <>
                  <div className={`mb-3 flex items-center gap-2 text-[12px] font-semibold ${
                    d.all_consistent ? "text-ok" : "text-danger"
                  }`}>
                    {d.all_consistent ? <ShieldCheck size={15} /> : <ShieldAlert size={15} />}
                    {d.all_consistent
                      ? "All checked fields agree across database, API and documents"
                      : "Divergence detected between views"}
                  </div>
                  <Table head={["Field", "Database", "API", "Report", ""]}>
                    {d.checks.map((k) => (
                      <Row key={k.field} tone={k.match ? "" : "bg-danger/[0.06]"}>
                        <Cell className="text-ink">{k.field}</Cell>
                        <Cell mono className="max-w-[110px] truncate">{String(k.database)}</Cell>
                        <Cell mono className="max-w-[110px] truncate">{String(k.api)}</Cell>
                        <Cell mono className="max-w-[110px] truncate">{String(k.report)}</Cell>
                        <Cell className="text-right">
                          <Chip tone={k.match ? "ok" : "danger"} dot={false}>
                            {k.match ? "ok" : "divergence"}
                          </Chip>
                        </Cell>
                      </Row>
                    ))}
                  </Table>
                  <p className="mt-2.5 text-[10.5px] text-muted">{d.note}</p>
                </>
              )}
            </Async>
          </Panel>
        </div>
      </div>
    </>
  );
}

function VerifyHash({ evidence }: { evidence: Evidence }) {
  const [file, setFile] = useState<File | null>(null);
  const [res, setRes] = useState<{ match: boolean; message: string; submitted_sha256?: string;
                                    stored_sha256?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const check = async (f: File) => {
    setFile(f); setBusy(true); setErr(null); setRes(null);
    try {
      const form = new FormData();
      form.append("file", f);
      const out = await api.upload<{ match: boolean; message: string;
                                    submitted_sha256?: string; stored_sha256?: string }>(
        `/evidence/${evidence.evidence_ref}/verify-hash`, form,
      );
      setRes(out);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Independent hash verification"
           hint="Upload any copy of the file to verify its SHA-256 against the record established at intake.">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Button onClick={() => fileInput.current?.click()} disabled={busy}>
            {busy ? <><Loader2 size={14} className="animate-spin" /> Verifying…</>
                  : "Select file to verify"}
          </Button>
          <input
            ref={fileInput} type="file" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void check(f); }}
          />
          {file && <span className="font-mono text-[11.5px] text-ink2">{file.name}</span>}
        </div>

        {err && (
          <div className="rounded-lg border border-danger/35 bg-danger/[0.07] px-3.5 py-2 text-[11.5px] text-danger">
            {err}
          </div>
        )}

        {res && (
          <div className={`rounded-lg border p-3 text-[11.5px] ${
            res.match ? "border-ok/35 bg-ok/[0.07] text-ok" : "border-danger/35 bg-danger/[0.07] text-danger"
          }`}>
            <div className="font-semibold flex items-center gap-1.5">
              {res.match ? <CheckCircle2 size={14} /> : <ShieldAlert size={14} />}
              {res.match ? "Cryptographic match" : "Hash mismatch"}
            </div>
            <div className="mt-1 text-ink2">{res.message}</div>
            {res.submitted_sha256 && (
              <div className="mt-2 space-y-1 font-mono text-[10.5px] text-muted">
                <div>stored:    {res.stored_sha256}</div>
                <div>submitted: {res.submitted_sha256}</div>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
