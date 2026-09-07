/**
 * Session context: which case and which evidence item the screens are showing.
 *
 * The selection is derived from the live API, not from a constant, so the whole
 * interface follows whatever is actually in the database.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, useApi } from "../lib/api";
import type { CaseDetail, CaseSummary, Evidence, Health } from "../lib/api";

type Ctx = {
  health: Health | null;
  healthError: string | null;
  cases: CaseSummary[];
  caseRef: string | null;
  setCaseRef: (r: string) => void;
  detail: CaseDetail | null;
  detailLoading: boolean;
  detailError: string | null;
  evidence: Evidence[];
  evidenceRef: string | null;
  setEvidenceRef: (r: string | null) => void;
  createNewCase: (payload: { title: string; category?: string; officer?: string; summary?: string }) => Promise<CaseSummary>;
  current: Evidence | null;
  refresh: () => void;
};

const SessionCtx = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [caseRef, setCaseRef] = useState<string | null>(null);
  const [evidenceRef, setEvidenceRef] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const health = useApi<Health>("/health", [tick]);
  const cases = useApi<CaseSummary[]>("/cases", [tick]);
  const detail = useApi<CaseDetail>(caseRef ? `/cases/${caseRef}` : null, [tick]);

  // pick the first case as soon as one exists
  useEffect(() => {
    if (!caseRef && cases.data?.length) setCaseRef(cases.data[0].case_ref);
  }, [cases.data, caseRef]);

  // keep the evidence selection valid for the loaded case
  useEffect(() => {
    const list = detail.data?.evidence ?? [];
    if (!list.length) { setEvidenceRef(null); return; }
    if (!evidenceRef || !list.some((e) => e.evidence_ref === evidenceRef)) {
      const done = list.find((e) => e.latest_run?.status === "completed");
      setEvidenceRef((done ?? list[list.length - 1]).evidence_ref);
    }
  }, [detail.data, evidenceRef]);

  // Auto-poll while any evidence item in the case is queued or running
  useEffect(() => {
    const list = detail.data?.evidence ?? [];
    const hasPending = list.some(
      (e) => e.latest_run?.status === "queued" || e.latest_run?.status === "running"
    );
    if (!hasPending) return;

    const timer = window.setInterval(() => {
      detail.reload();
      cases.reload();
    }, 1200);
    return () => window.clearInterval(timer);
  }, [detail.data?.evidence, detail.reload, cases.reload]);

  const refresh = useCallback(() => {
    setTick((t) => t + 1);
    detail.reload();
    cases.reload();
  }, [detail.reload, cases.reload]);

  const createNewCase = useCallback(async (payload: { title: string; category?: string; officer?: string; summary?: string }) => {
    const res = await api.post<CaseSummary>("/cases", payload);
    refresh();
    setCaseRef(res.case_ref);
    return res;
  }, [refresh]);

  const value = useMemo<Ctx>(() => ({
    health: health.data,
    healthError: health.error,
    cases: cases.data ?? [],
    caseRef,
    setCaseRef: (r: string) => { setCaseRef(r); setEvidenceRef(null); },
    createNewCase,
    detail: detail.data,
    detailLoading: detail.loading,
    detailError: detail.error,
    evidence: detail.data?.evidence ?? [],
    evidenceRef,
    setEvidenceRef,
    current: detail.data?.evidence.find((e) => e.evidence_ref === evidenceRef) ?? null,
    refresh,
  }), [health.data, health.error, cases.data, caseRef, detail.data, detail.loading,
       detail.error, evidenceRef, refresh, createNewCase]);

  return <SessionCtx.Provider value={value}>{children}</SessionCtx.Provider>;
}

export function useSession(): Ctx {
  const c = useContext(SessionCtx);
  if (!c) throw new Error("useSession must be used inside SessionProvider");
  return c;
}

/** Create the demonstration case if the database is empty. */
export async function createDemoCase(): Promise<CaseSummary> {
  return api.post<CaseSummary>("/cases", {
    case_ref: `CASE-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 900) + 100)}`,
    title: "New case",
    category: "Synthetic media",
    officer: "Investigating Officer",
    summary: "Created from the SROT console.",
  });
}
