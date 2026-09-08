import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import {
  LayoutDashboard, Upload, ScanSearch, GitBranch, ScanFace, Type, Share2,
  Layers, Activity, Clock, ShieldCheck, FileText, Circle, WifiOff, Cpu,
  FolderPlus, Plus, BarChart3, LogOut,
} from "lucide-react";
import { useSession } from "../state/session";
import { useAuth } from "../state/auth";
import { Boundary } from "./Boundary";

const NAV = [
  { to: "/",           label: "Case Dashboard",        Icon: LayoutDashboard },
  { to: "/upload",     label: "Evidence Intake",       Icon: Upload },
  { to: "/analysis",   label: "Forensic Analysis",     Icon: ScanSearch },
  { to: "/neural",     label: "AI-Synthetic Signal",   Icon: Cpu },
  { to: "/origin",     label: "Origin Trace",           Icon: GitBranch },
  { to: "/recapture",  label: "Recapture Forensics",   Icon: ScanFace },
  { to: "/entities",   label: "OCR & Identifiers",     Icon: Type },
  { to: "/graph",      label: "Investigation Graph",   Icon: Share2 },
  { to: "/cross-case", label: "Cross-Case Links",      Icon: Layers },
  { to: "/stress",     label: "Laundering Stress Test", Icon: Activity },
  { to: "/timeline",   label: "Timeline & Leads",      Icon: Clock },
  { to: "/benchmark",  label: "Adversarial Benchmark", Icon: BarChart3 },
  { to: "/audit",      label: "Audit Trail",           Icon: ShieldCheck },
  { to: "/packet",     label: "Court Packet",          Icon: FileText },
];

export default function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { officer, logout } = useAuth();
  const { health, healthError, cases, detail, caseRef, setCaseRef, createNewCase, evidence, evidenceRef, setEvidenceRef } = useSession();
  const [showNewCase, setShowNewCase] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState("Synthetic media");
  const [creating, setCreating] = useState(false);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setCreating(true);
    try {
      await createNewCase({ title: newTitle.trim(), category: newCategory });
      setShowNewCase(false);
      setNewTitle("");
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="flex h-full">
      <aside className="no-print flex w-[262px] shrink-0 flex-col border-r border-line bg-surface">
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <Emblem />
          <div className="min-w-0">
            <div className="text-[15px] font-bold tracking-[0.16em] text-ink">SROT</div>
            <div className="text-[8.5px] font-semibold uppercase leading-[1.35] tracking-[0.08em] text-muted">
              Source Tracing &amp; Recapture<br />Origin Toolkit · LogicaLoom
            </div>
          </div>
        </div>

        {/* Case Switcher & Header */}
        <div className="border-b border-line px-5 py-3.5">
          <div className="flex items-center justify-between">
            <label htmlFor="case-select" className="lbl cursor-pointer">Active case</label>
            <button
              onClick={() => setShowNewCase(true)}
              className="flex items-center gap-1 text-[10.5px] font-semibold text-accent hover:underline"
              title="Open a new case record"
            >
              <Plus size={11} /> New
            </button>
          </div>
          {cases.length > 1 ? (
            <select
              id="case-select"
              value={caseRef ?? ""}
              onChange={(e) => setCaseRef(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-line bg-s2 px-2 py-1 font-mono text-[11.5px] text-accent font-semibold outline-none focus:border-accent"
            >
              {cases.map((c) => (
                <option key={c.case_ref} value={c.case_ref}>
                  {c.case_ref} · {c.title}
                </option>
              ))}
            </select>
          ) : (
            <div className="mt-1.5 font-mono text-[13px] font-semibold text-accent">
              {caseRef ?? "—"}
            </div>
          )}
          <div className="mt-1 line-clamp-2 text-[11.5px] leading-snug text-ink2">
            {detail?.title ?? "No case loaded"}
          </div>
        </div>

        {/* New Case Modal Dialog */}
        {showNewCase && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="w-full max-w-md rounded-xl border border-line bg-surface p-5 shadow-2xl">
              <div className="flex items-center gap-2 text-[14px] font-bold text-ink mb-3">
                <FolderPlus size={16} className="text-accent" />
                <span>Open New Forensic Case</span>
              </div>
              <form onSubmit={handleCreate} className="space-y-3.5 text-xs">
                <div>
                  <label className="lbl mb-1 block">Case Title</label>
                  <input
                    type="text"
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g. Circulating Investment Fraud Deepfake Video"
                    className="w-full rounded-lg border border-line bg-s2 px-3 py-2 text-ink outline-none focus:border-accent"
                    required
                  />
                </div>
                <div>
                  <label className="lbl mb-1 block">Investigation Category</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full rounded-lg border border-line bg-s2 px-3 py-2 text-ink outline-none focus:border-accent"
                  >
                    <option value="Synthetic media">Synthetic media / Deepfake</option>
                    <option value="Financial fraud">Financial fraud</option>
                    <option value="Election integrity">Election integrity</option>
                    <option value="Extortion & Harassment">Extortion &amp; Harassment</option>
                    <option value="Other forensic intake">Other forensic intake</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowNewCase(false)}
                    className="btn btn-ghost text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating || !newTitle.trim()}
                    className="btn btn-primary text-xs"
                  >
                    {creating ? "Creating…" : "Register Case"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {evidence.length > 0 && (
          <div className="border-b border-line px-5 py-3">
            <label className="lbl" htmlFor="ev-select">Evidence item</label>
            <select
              id="ev-select"
              value={evidenceRef ?? ""}
              onChange={(e) => setEvidenceRef(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-line bg-s2 px-2.5 py-1.5 font-mono text-[11px] text-ink outline-none focus:border-accent"
            >
              {evidence.map((e) => (
                <option key={e.evidence_ref} value={e.evidence_ref}>
                  {e.evidence_ref} · {e.latest_run?.status ?? "not analysed"}
                </option>
              ))}
            </select>
          </div>
        )}

        <nav className="flex-1 overflow-y-auto px-2.5 py-3">
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `group relative mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] transition-colors ${
                  isActive ? "bg-s3 font-semibold text-ink" : "text-ink2 hover:bg-s2 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute left-0 top-1/2 h-4 w-[2.5px] -translate-y-1/2 rounded-r bg-accent" />}
                  <Icon size={15} className={isActive ? "text-accent" : "text-muted"} />
                  <span className="truncate">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-line px-4 py-2.5">
          <div className="flex items-center justify-between text-[11px] font-medium text-ink2">
            <div className="flex items-center gap-2">
              {healthError ? (
                <><WifiOff size={12} className="text-danger" /><span className="text-danger font-semibold">Backend offline</span></>
              ) : health ? (
                <><Circle size={7} className="fill-ok text-ok" /><span className="text-ink font-semibold">Backend online</span></>
              ) : (
                <><Circle size={7} className="fill-muted text-muted" /><span className="text-muted">Connecting…</span></>
              )}
            </div>
            {health && (
              <span className="text-[10px] text-muted font-mono bg-s2 border border-line px-1.5 py-0.5 rounded">
                offline
              </span>
            )}
          </div>
        </div>

        {/* Officer Session & Logout Gate */}
        <div className="border-t border-line px-4 py-2.5 bg-s2/40">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-ink">
                <ShieldCheck size={12} className="text-accent shrink-0" />
                <span className="truncate font-mono">{officer?.badge_id ?? "DEMO-OFFICER"}</span>
              </div>
              <div className="truncate text-[10px] text-muted leading-tight" title={officer?.name ?? "Forensic Investigator"}>
                {officer?.name ?? "Forensic Investigator"}
              </div>
            </div>
            <button
              type="button"
              onClick={() => logout()}
              className="flex items-center gap-1 rounded border border-line px-2 py-1 text-[10.5px] font-medium text-ink2 hover:bg-s3 hover:text-danger hover:border-danger/40 transition-colors shrink-0"
              title="Terminate officer session and lock forensic console"
            >
              <LogOut size={11} /> Logout
            </button>
          </div>
        </div>
      </aside>

      <main key={pathname} className="fade-in flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1380px] px-6 py-6 lg:px-8">
          <Boundary where={pathname}>{children}</Boundary>
        </div>
      </main>
    </div>
  );
}

function Emblem() {
  return (
    <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-accent/35 bg-accent/10">
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#9B7BFF" strokeWidth="1.9"
           strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 2 4 5.5v6c0 5 3.4 9.2 8 10.5 4.6-1.3 8-5.5 8-10.5v-6z" />
        <circle cx="12" cy="11" r="3" />
        <path d="m14.2 13.2 2.1 2.1" />
      </svg>
    </div>
  );
}
