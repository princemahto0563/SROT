import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import {
  LayoutDashboard, Upload, ScanSearch, GitBranch, ScanFace, Type, Share2,
  Layers, Activity, Clock, ShieldCheck, FileText, Circle, WifiOff, Cpu,
  FolderPlus, Plus, BarChart3, LogOut, Sun, Moon, Database, ChevronRight, FileDigit
} from "lucide-react";
import { useSession } from "../state/session";
import { useAuth } from "../state/auth";
import { useTheme } from "../state/theme";
import { SrotLogo } from "./SrotLogo";
import { Boundary } from "./Boundary";

const NAV_GROUPS = [
  {
    group: "OVERVIEW",
    items: [
      { to: "/", label: "Case Dashboard", Icon: LayoutDashboard },
    ],
  },
  {
    group: "EVIDENCE & INTAKE",
    items: [
      { to: "/upload", label: "Evidence Intake", Icon: Upload },
    ],
  },
  {
    group: "FORENSIC SIGNALS",
    items: [
      { to: "/analysis", label: "Forensic Analysis", Icon: ScanSearch },
      { to: "/neural", label: "AI-Synthetic Signal", Icon: Cpu },
      { to: "/recapture", label: "Recapture Forensics", Icon: ScanFace },
    ],
  },
  {
    group: "INVESTIGATION & GRAPH",
    items: [
      { to: "/origin", label: "Origin Trace", Icon: GitBranch },
      { to: "/entities", label: "OCR & Identifiers", Icon: Type },
      { to: "/graph", label: "Investigation Graph", Icon: Share2 },
      { to: "/cross-case", label: "Cross-Case Links", Icon: Layers },
      { to: "/timeline", label: "Timeline & Leads", Icon: Clock },
    ],
  },
  {
    group: "VERIFICATION & LEGAL",
    items: [
      { to: "/stress", label: "Laundering Stress Test", Icon: Activity },
      { to: "/benchmark", label: "Adversarial Benchmark", Icon: BarChart3 },
      { to: "/audit", label: "Audit Trail", Icon: ShieldCheck },
      { to: "/packet", label: "Court Packet", Icon: FileText },
    ],
  },
];

export default function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { officer, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const {
    health, healthError, cases, detail, caseRef, setCaseRef,
    createNewCase, evidence, evidenceRef, setEvidenceRef,
  } = useSession();

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

  const currentNav = NAV_GROUPS.flatMap((g) => g.items).find((i) =>
    i.to === "/" ? pathname === "/" : pathname.startsWith(i.to)
  );

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg text-ink selection:bg-accent/30">
      {/* ── Left Sidebar Navigation ────────────────────────────────────────── */}
      <aside className="no-print flex w-[256px] shrink-0 flex-col border-r border-line bg-surface transition-colors duration-150">
        {/* Brand Header */}
        <div className="flex h-14 items-center justify-between border-b border-line px-4">
          <SrotLogo size="md" showSubtitle={false} />
        </div>

        {/* Case Selector Quick Widget */}
        <div className="border-b border-line px-3.5 py-3 bg-s2/40">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
              <Database size={11} className="text-accent" />
              <span>Active Case</span>
            </div>
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
              className="w-full rounded-md border border-line bg-surface px-2 py-1 font-mono text-[11px] font-semibold text-ink outline-none focus:border-accent"
            >
              {cases.map((c) => (
                <option key={c.case_ref} value={c.case_ref}>
                  {c.case_ref} · {c.title}
                </option>
              ))}
            </select>
          ) : (
            <div className="rounded-md border border-line bg-surface px-2 py-1 font-mono text-[11px] font-semibold text-ink truncate">
              {caseRef ?? "No case loaded"}
            </div>
          )}

          {evidence.length > 0 && (
            <div className="mt-2">
              <div className="mb-1 flex items-center justify-between text-[9.5px] font-semibold uppercase tracking-wider text-muted">
                <span>Active Evidence</span>
                <span className="font-mono text-[9px] text-ink2">{evidence.length} file{evidence.length > 1 ? "s" : ""}</span>
              </div>
              <select
                id="ev-select"
                value={evidenceRef ?? ""}
                onChange={(e) => setEvidenceRef(e.target.value)}
                className="w-full rounded-md border border-line bg-surface px-2 py-1 font-mono text-[10.5px] text-ink outline-none focus:border-accent"
              >
                {evidence.map((e) => (
                  <option key={e.evidence_ref} value={e.evidence_ref}>
                    {e.evidence_ref} · {e.latest_run?.status ?? "pending"}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Categorized Navigation Tree */}
        <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.group}>
              <div className="px-2.5 pb-1 text-[9px] font-bold tracking-[0.14em] uppercase text-muted/80 select-none">
                {group.group}
              </div>
              <div className="space-y-0.5">
                {group.items.map(({ to, label, Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === "/"}
                    className={({ isActive }) =>
                      `group relative flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[12px] font-medium transition-colors ${
                        isActive
                          ? "bg-s2 font-semibold text-ink border-l-2 border-accent"
                          : "text-ink2 hover:bg-s2/60 hover:text-ink"
                      }`
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          size={15}
                          className={`shrink-0 transition-colors ${
                            isActive ? "text-accent" : "text-muted group-hover:text-ink2"
                          }`}
                        />
                        <span className="truncate">{label}</span>
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Sidebar Footer: Health Status & Officer Session */}
        <div className="border-t border-line px-3.5 py-2.5 bg-s2/30 space-y-2">
          {/* Health Indicator */}
          <div className="flex items-center justify-between text-[10.5px] font-medium text-ink2">
            <div className="flex items-center gap-1.5">
              {healthError ? (
                <>
                  <WifiOff size={12} className="text-danger" />
                  <span className="font-semibold text-danger">Backend offline</span>
                </>
              ) : health ? (
                <>
                  <Circle size={6} className="fill-ok text-ok" />
                  <span className="font-semibold text-ink">Engine online</span>
                </>
              ) : (
                <>
                  <Circle size={6} className="fill-muted text-muted" />
                  <span className="text-muted">Connecting…</span>
                </>
              )}
            </div>
            <span className="rounded border border-line bg-surface px-1.5 py-[1px] font-mono text-[9px] text-muted">
              offline air-gapped
            </span>
          </div>

          {/* Officer Session Profile */}
          <div className="flex items-center justify-between gap-2 border-t border-line/60 pt-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1 text-[11px] font-bold text-ink">
                <ShieldCheck size={12} className="text-accent shrink-0" />
                <span className="truncate font-mono">{officer?.badge_id ?? "DEMO-OFFICER"}</span>
              </div>
              <div
                className="truncate text-[9.5px] text-muted leading-tight"
                title={officer?.name ?? "Forensic Examiner"}
              >
                {officer?.name ?? "Forensic Examiner"}
              </div>
            </div>
            <button
              type="button"
              onClick={() => logout()}
              className="flex items-center gap-1 rounded border border-line bg-surface px-2 py-1 text-[10px] font-semibold text-ink2 hover:bg-danger/10 hover:text-danger hover:border-danger/40 transition-colors shrink-0"
              title="Terminate officer session and lock console"
            >
              <LogOut size={11} /> Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main Workspace Body ────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Top Operational Context Bar */}
        <header className="no-print flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-6 transition-colors duration-150">
          {/* Breadcrumb Workspace Tracker */}
          <div className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-ink2">
              <Database size={13} className="text-accent" />
              <span>{detail?.title ? `Case ${detail.case_ref}` : "Forensic Console"}</span>
            </div>
            <ChevronRight size={12} className="text-muted" />
            <div className="flex items-center gap-1.5 font-medium text-ink">
              {currentNav?.Icon && <currentNav.Icon size={13} className="text-accent" />}
              <span>{currentNav?.label ?? "Console"}</span>
            </div>
          </div>

          {/* Quick Context Chips */}
          <div className="flex items-center gap-3">
            {caseRef && (
              <div className="hidden sm:flex items-center gap-2 rounded-lg border border-line bg-s2/60 px-2.5 py-1 text-[11px]">
                <span className="text-muted font-mono">Case:</span>
                <span className="font-mono font-bold text-ink">{caseRef}</span>
                {detail?.category && (
                  <span className="rounded bg-accent/10 px-1.5 py-[1px] text-[10px] font-semibold text-accent">
                    {detail.category}
                  </span>
                )}
              </div>
            )}
            {evidenceRef && (
              <div className="hidden md:flex items-center gap-2 rounded-lg border border-line bg-s2/60 px-2.5 py-1 text-[11px]">
                <FileDigit size={12} className="text-accent" />
                <span className="font-mono font-medium text-ink">{evidenceRef}</span>
              </div>
            )}
            <button
              type="button"
              onClick={toggleTheme}
              className="flex items-center gap-1.5 rounded-lg border border-line bg-s2 px-2.5 py-1 text-[11px] font-medium text-ink2 hover:bg-s3 hover:text-ink transition-colors"
              title="Toggle dark/light theme"
            >
              {theme === "dark" ? (
                <>
                  <Sun size={12} className="text-amber" />
                  <span className="hidden sm:inline">Light</span>
                </>
              ) : (
                <>
                  <Moon size={12} className="text-accent" />
                  <span className="hidden sm:inline">Dark</span>
                </>
              )}
            </button>
          </div>
        </header>

        {/* Scrollable Canvas */}
        <main key={pathname} className="fade-in flex-1 overflow-y-auto bg-bg transition-colors duration-150">
          <div className="mx-auto max-w-[1400px] px-6 py-6 lg:px-8">
            <Boundary where={pathname}>{children}</Boundary>
          </div>
        </main>
      </div>

      {/* ── New Case Modal Dialog ──────────────────────────────────────────── */}
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
    </div>
  );
}
