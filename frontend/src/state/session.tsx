/**
 * Session context: which case and which evidence item the screens are showing.
 *
 * The selection is derived from the live API, not from a constant, so the whole
 * interface follows whatever is actually in the database.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
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
  const [caseRef, setCaseRefState] = useState<string | null>(() => {
    try {
      const saved = localStorage.getItem("srot_case_ref");
      if (saved && saved !== "CASE-2026-001") return saved;
      return "CASE-2026-112";
    } catch {
      return "CASE-2026-112";
    }
  });
  const [evidenceRef, setEvidenceRef] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const pendingCaseRef = useRef<string | null>(null);

  const setCaseRef = useCallback((r: string | null) => {
    pendingCaseRef.current = r;
    setCaseRefState(r);
    try {
      if (r) localStorage.setItem("srot_case_ref", r);
      else localStorage.removeItem("srot_case_ref");
    } catch {}
  }, []);

  const health = useApi<Health>("/health", [tick]);
  const cases = useApi<CaseSummary[]>("/cases", [tick]);
  const detail = useApi<CaseDetail>(caseRef ? `/cases/${caseRef}` : null, [tick]);

  // pick the saved or first case as soon as one exists (prefer CASE-2026-112 hero demo case)
  useEffect(() => {
    if (!cases.data?.length) return;
    if (pendingCaseRef.current && cases.data.some((c) => c.case_ref === pendingCaseRef.current)) {
      pendingCaseRef.current = null;
    }
    // If a user just created or selected a case, let it load into cases.data before fallback
    if (pendingCaseRef.current && pendingCaseRef.current === caseRef) {
      return;
    }

    const hero = cases.data.find((c) => c.case_ref === "CASE-2026-112");
    if (!caseRef) {
      try {
        const saved = localStorage.getItem("srot_case_ref");
        if (saved && saved !== "CASE-2026-001" && cases.data.some((c) => c.case_ref === saved)) {
          setCaseRef(saved);
          return;
        }
      } catch {}
      if (hero) {
        setCaseRef(hero.case_ref);
        return;
      }
      setCaseRef(cases.data[0].case_ref);
    } else if (!cases.data.some((c) => c.case_ref === caseRef)) {
      if (hero) {
        setCaseRef(hero.case_ref);
        return;
      }
      setCaseRef(cases.data[0].case_ref);
    }
  }, [cases.data, caseRef, setCaseRef]);

  const prevDetailCaseRef = useRef<string | null>(null);

  // keep the evidence selection valid for the loaded case
  useEffect(() => {
    const list = detail.data?.evidence ?? [];
    const currentCaseLoaded = detail.data?.case_ref;
    const caseChanged = prevDetailCaseRef.current !== currentCaseLoaded;
    prevDetailCaseRef.current = currentCaseLoaded ?? null;

    if (!list.length) {
      if (!detail.loading) setEvidenceRef(null);
      return;
    }
    if (!evidenceRef || caseChanged) {
      // If evidenceRef is already present in this new list, preserve it
      if (evidenceRef && list.some((e) => e.evidence_ref === evidenceRef)) {
        return;
      }
      const done = list.find((e) => e.latest_run?.status === "completed");
      setEvidenceRef((done ?? list[list.length - 1]).evidence_ref);
    } else if (!detail.loading && currentCaseLoaded === caseRef && !list.some((e) => e.evidence_ref === evidenceRef)) {
      // Only switch evidence fallback after detail loading has finished and the ref definitely isn't in this case
      const done = list.find((e) => e.latest_run?.status === "completed");
      setEvidenceRef((done ?? list[list.length - 1]).evidence_ref);
    }
  }, [detail.data, detail.loading, evidenceRef, caseRef]);

  const hasPending = Boolean(
    detail.data?.evidence?.some(
      (e) => e.latest_run?.status === "queued" || e.latest_run?.status === "running"
    )
  );

  // Auto-poll while any evidence item in the case is queued or running
  useEffect(() => {
    if (!hasPending) return;

    const timer = window.setInterval(() => {
      detail.reload();
      cases.reload();
    }, 1200);
    return () => window.clearInterval(timer);
  }, [hasPending, detail.reload, cases.reload]);

  const refresh = useCallback(() => {
    setTick((t) => t + 1);
  }, []);

  const createNewCase = useCallback(async (payload: { title: string; category?: string; officer?: string; summary?: string }) => {
    const res = await api.post<CaseSummary>("/cases", payload);
    refresh();
    setCaseRef(res.case_ref);
    return res;
  }, [refresh, setCaseRef]);

  const current = useMemo(() => {
    return detail.data?.evidence.find((e) => e.evidence_ref === evidenceRef) ?? null;
  }, [detail.data?.evidence, evidenceRef]);

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
    current,
    refresh,
  }), [health.data, health.error, cases.data, caseRef, detail.data, detail.loading,
       detail.error, evidenceRef, current, refresh, createNewCase, setCaseRef]);

  return <SessionCtx.Provider value={value}>{children}</SessionCtx.Provider>;
}

export function useSession(): Ctx {
  const c = useContext(SessionCtx);
  if (!c) throw new Error("useSession must be used inside SessionProvider");
  return c;
}
