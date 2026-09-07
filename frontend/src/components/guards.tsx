import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { EmptyState, Notice } from "./ui";
import { useSession } from "../state/session";
import { useApi, usePolling } from "../lib/api";
import type { Evidence, RunSummary } from "../lib/api";

export type ReadinessStatus =
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "INSUFFICIENT_EVIDENCE"
  | "NONE";

/**
 * Authoritative analysis readiness determination.
 * Works for ANY evidence item dynamically.
 */
export function getReadiness(
  run?: {
    status?: string | null;
    error?: string | null;
    assessment?: string | null;
    confidence_band?: string | null;
  } | null
): { status: ReadinessStatus; detail: string | null } {
  if (!run || !run.status || run.status === "none") {
    return { status: "NONE", detail: "This evidence item has not been analysed yet." };
  }
  const s = run.status.toLowerCase();
  if (s === "queued") {
    return { status: "QUEUED", detail: "Analysis is queued in the pipeline." };
  }
  if (s === "running") {
    return { status: "RUNNING", detail: "Analysis is actively processing forensic signals." };
  }
  if (s === "failed") {
    const err = (run.error ?? "").toLowerCase();
    const assess = (run.assessment ?? "").toLowerCase();
    const band = (run.confidence_band ?? "").toUpperCase();
    if (err.includes("insufficient") || assess.includes("insufficient") || band.includes("INSUFFICIENT")) {
      return {
        status: "INSUFFICIENT_EVIDENCE",
        detail: run.error ?? "Insufficient evidence: media could not yield reliable forensic signals.",
      };
    }
    return {
      status: "FAILED",
      detail: run.error ?? "Analysis pipeline recorded a processing failure.",
    };
  }
  if (s === "completed") {
    const err = (run.error ?? "").toLowerCase();
    if (err.includes("insufficient")) {
      return {
        status: "INSUFFICIENT_EVIDENCE",
        detail: run.error ?? "Insufficient evidence: media could not yield reliable forensic signals.",
      };
    }
    return { status: "COMPLETED", detail: null };
  }
  return { status: "NONE", detail: "Unknown status." };
}

/**
 * Authoritative guard: verifies backend analysis run status for the selected evidence item.
 * Never shows 'still running' when backend has finished.
 */
export function RequireEvidence({
  children,
}: { children: (ev: Evidence) => React.ReactNode }) {
  const { current, evidence, detailLoading, detailError, refresh } = useSession();

  // Active polling of the job status while in progress
  const job = usePolling<{
    status: string;
    stage: string | null;
    stages: Record<string, string>;
    error?: string | null;
    assessment?: string | null;
  }>(
    current ? `/evidence/${current.evidence_ref}/job` : null,
    (j) => j.status === "queued" || j.status === "running",
    1200,
  );

  // When job reaches terminal status in polling, trigger session refresh
  useEffect(() => {
    if (job.data?.status === "completed" || job.data?.status === "failed") {
      refresh();
    }
  }, [job.data?.status, refresh]);

  // Live direct fetch of the evidence item so completed fields and latest_run are immediate
  const liveEv = useApi<Evidence>(
    current ? `/evidence/${current.evidence_ref}` : null,
    [job.data?.status]
  );

  if (detailError) {
    return (
      <Notice kind="warn">
        The backend could not be reached: {detailError}. Start it with{" "}
        <code className="font-mono">uvicorn app.main:app --port 8077</code> from the{" "}
        <code className="font-mono">backend/</code> directory.
      </Notice>
    );
  }
  if (detailLoading && !evidence.length) {
    return <EmptyState title="Loading case…" />;
  }
  if (!evidence.length) {
    return (
      <EmptyState
        title="No evidence has been ingested for this case."
        detail="Upload a media file on the Evidence Intake screen. Every panel in this console renders only what was actually computed from an ingested file — nothing is pre-filled."
        action={<Link to="/upload" className="btn btn-primary text-[12px]">Go to Evidence Intake</Link>}
      />
    );
  }
  if (!current) return <EmptyState title="Select an evidence item in the sidebar." />;

  const effectiveEvidence = liveEv.data ?? current;
  const effectiveRun: RunSummary | null =
    effectiveEvidence.latest_run ??
    (job.data
      ? {
          id: 0,
          status: job.data.status,
          stage: job.data.stage,
          stages: job.data.stages,
          assessment: job.data.assessment ?? null,
          confidence_band: null,
          aggregate_score: null,
          dissent: false,
          frames_sampled: null,
          error: job.data.error,
        }
      : null);

  const readiness = getReadiness(effectiveRun);

  if (readiness.status === "COMPLETED") {
    return <div key={effectiveEvidence.evidence_ref} className="contents">{children(effectiveEvidence)}</div>;
  }

  if (readiness.status === "INSUFFICIENT_EVIDENCE") {
    return (
      <EmptyState
        title="Insufficient evidence for forensic analysis."
        detail={
          readiness.detail ??
          "Available signals are insufficient to form a confident manipulation or authenticity conclusion."
        }
        action={<Link to="/upload" className="btn btn-ghost text-[12px]">View intake &amp; media probe</Link>}
      />
    );
  }

  if (readiness.status === "FAILED") {
    return (
      <EmptyState
        title="Analysis failed for this evidence item."
        detail={readiness.detail ?? "The forensic pipeline encountered a processing failure."}
        action={<Link to="/upload" className="btn btn-ghost text-[12px]">View job progress</Link>}
      />
    );
  }

  if (readiness.status === "RUNNING") {
    const stage = job.data?.stage ?? effectiveEvidence.latest_run?.stage ?? "active analysis";
    return (
      <EmptyState
        title="Analysis in progress for this evidence item."
        detail={`Forensic pipeline is executing (stage: ${stage}). Results will render dynamically upon completion.`}
        action={
          <div className="flex items-center gap-2 text-accent">
            <Loader2 size={14} className="animate-spin" />
            <Link to="/upload" className="btn btn-ghost text-[12px]">View live progress</Link>
          </div>
        }
      />
    );
  }

  if (readiness.status === "QUEUED") {
    return (
      <EmptyState
        title="Analysis queued."
        detail="This evidence item is queued in the pipeline. Execution will begin momentarily."
        action={<Link to="/upload" className="btn btn-ghost text-[12px]">View job progress</Link>}
      />
    );
  }

  return (
    <EmptyState
      title="This evidence item has not been analysed yet."
      detail="Results appear here once the pipeline finishes. Progress is shown on the Evidence Intake screen."
      action={<Link to="/upload" className="btn btn-ghost text-[12px]">View job progress</Link>}
    />
  );
}
