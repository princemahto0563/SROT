export function SrotMark({
  size = 24,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${className}`}
      aria-label="SROT Forensic Mark"
    >
      {/* Precision forensic coordinate aperture */}
      <rect
        x="3.5"
        y="3.5"
        width="25"
        height="25"
        rx="6.5"
        className="stroke-accent"
        strokeWidth="1.8"
      />
      {/* 4 Cardinal optical sensor crosshairs */}
      <path
        d="M16 3.5V7M16 25V28.5M3.5 16H7M25 16H28.5"
        className="stroke-accent"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      {/* Inner provenance ring */}
      <circle
        cx="16"
        cy="16"
        r="5.25"
        className="stroke-accent"
        strokeWidth="1.4"
      />
      {/* Calibrated origin core focal point */}
      <circle
        cx="16"
        cy="16"
        r="2"
        className="fill-accent"
      />
    </svg>
  );
}

export function SrotLogo({
  size = "md",
  showSubtitle = true,
  className = "",
}: {
  size?: "sm" | "md" | "lg";
  showSubtitle?: boolean;
  className?: string;
}) {
  if (size === "lg") {
    return (
      <div className={`flex flex-col items-center text-center ${className}`}>
        <div className="relative mb-3.5 flex h-14 w-14 items-center justify-center rounded-xl border border-line bg-surface p-2.5 shadow-sm transition-colors">
          <SrotMark size={32} />
        </div>
        <div className="font-mono text-2xl font-bold tracking-[0.2em] text-ink">
          SROT
        </div>
        <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
          Source Tracing &amp; Recapture Origin Toolkit
        </div>
        {showSubtitle && (
          <div className="mt-0.5 text-[10.5px] font-medium text-muted">
            LogicaLoom · Digital Evidence Forensics Console
          </div>
        )}
      </div>
    );
  }

  if (size === "sm") {
    return (
      <div className={`flex items-center gap-2.5 ${className}`}>
        <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-line bg-s2/60">
          <SrotMark size={16} />
        </div>
        <div className="font-mono text-sm font-bold tracking-widest text-ink">
          SROT
        </div>
      </div>
    );
  }

  // Default "md" for sidebar / header
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-s2/60 transition-colors">
        <SrotMark size={20} />
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[14px] font-bold tracking-[0.18em] text-ink">
            SROT
          </span>
          <span className="rounded border border-line bg-s2 px-1 py-[1px] font-mono text-[9px] font-medium text-muted">
            v2.6
          </span>
        </div>
        {showSubtitle && (
          <div className="truncate text-[9.5px] font-medium uppercase tracking-[0.06em] text-muted">
            Forensics Console · LogicaLoom
          </div>
        )}
      </div>
    </div>
  );
}
