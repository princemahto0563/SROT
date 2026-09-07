import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ShieldCheck, Lock, UserCheck, AlertCircle, KeyRound, Terminal, CheckCircle2 } from "lucide-react";
import { useAuth } from "../state/auth";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [badgeId, setBadgeId] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || "/";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!badgeId.trim() || !password) {
      setError("Officer Badge ID and authorization password are required.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await login(badgeId.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError((err as Error).message || "Authentication failed. Access denied.");
    } finally {
      setLoading(false);
    }
  };

  const fillDemoCredentials = () => {
    setBadgeId("DEMO-OFFICER");
    setPassword("Forensic#2026!SecOps");
    setError(null);
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-[#090D14] px-4 py-8 text-ink selection:bg-accent/30">
      {/* Background ambient forensic grid */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(76,166,232,0.12),rgba(255,255,255,0))]" />

      <div className="relative w-full max-w-md">
        {/* Header Branding */}
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3.5 flex h-14 w-14 items-center justify-center rounded-xl border border-accent/40 bg-accent/10 shadow-[0_0_24px_rgba(76,166,232,0.18)]">
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#4CA6E8"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 2 4 5.5v6c0 5 3.4 9.2 8 10.5 4.6-1.3 8-5.5 8-10.5v-6z" />
              <circle cx="12" cy="11" r="3" />
              <path d="m14.2 13.2 2.1 2.1" />
            </svg>
          </div>
          <div className="font-mono text-2xl font-bold tracking-[0.2em] text-ink">SROT</div>
          <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
            Source Tracing &amp; Recapture Origin Toolkit
          </div>
          <div className="mt-0.5 text-[10px] text-muted">
            LogicaLoom · Law Enforcement Digital Forensics Console
          </div>
        </div>

        {/* Main Card */}
        <div className="rounded-xl border border-line bg-surface/90 p-6 shadow-2xl backdrop-blur-md">
          {/* Gate Badge */}
          <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-accent" />
              <span className="text-xs font-semibold uppercase tracking-wider text-ink">
                Police Forensic Access Gate
              </span>
            </div>
            <span className="rounded border border-accent/30 bg-accent/10 px-2 py-0.5 font-mono text-[9.5px] uppercase font-bold text-accent">
              SECURE SESSION
            </span>
          </div>

          {/* Statutory / Warning notice */}
          <div className="mb-5 rounded-lg border border-line/60 bg-s2/50 p-2.5 text-[10.5px] leading-relaxed text-muted">
            <span className="font-semibold text-ink2">AUTHORIZED LAW ENFORCEMENT &amp; FORENSICS ACCESS ONLY:</span>{" "}
            Unauthorized access attempts are monitored and recorded. Cryptographic evidence chains are sealed.
          </div>

          {/* Error Banner */}
          {error && (
            <div
              role="alert"
              className="mb-4 flex items-start gap-2.5 rounded-lg border border-danger/40 bg-danger/10 p-3 text-xs text-danger"
            >
              <AlertCircle size={15} className="mt-0.5 shrink-0" />
              <div className="leading-snug">{error}</div>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="badge-id"
                className="mb-1.5 flex items-center justify-between text-[11px] font-semibold text-ink2"
              >
                <span>Officer Badge ID / Service No.</span>
                <span className="font-mono text-[10px] text-muted">DEMO-OFFICER</span>
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted">
                  <UserCheck size={15} />
                </div>
                <input
                  id="badge-id"
                  type="text"
                  autoComplete="username"
                  required
                  value={badgeId}
                  onChange={(e) => setBadgeId(e.target.value)}
                  placeholder="e.g. DEMO-OFFICER"
                  className="w-full rounded-lg border border-line bg-s2 pl-9 pr-3 py-2 font-mono text-xs text-ink placeholder:text-muted/60 outline-none transition focus:border-accent focus:ring-1 focus:ring-accent"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1.5 flex items-center justify-between text-[11px] font-semibold text-ink2"
              >
                <span>Authorization Password</span>
                <span className="font-mono text-[10px] text-muted">Forensic#2026!SecOps</span>
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted">
                  <Lock size={15} />
                </div>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••••••••••"
                  className="w-full rounded-lg border border-line bg-s2 pl-9 pr-3 py-2 font-mono text-xs text-ink placeholder:text-muted/60 outline-none transition focus:border-accent focus:ring-1 focus:ring-accent"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-accent/80 bg-accent py-2.5 text-xs font-semibold text-[#090D14] shadow-md transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[#090D14] border-t-transparent" />
                  <span>Verifying Credentials…</span>
                </>
              ) : (
                <>
                  <KeyRound size={14} />
                  <span>Authenticate &amp; Access Console</span>
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Credential Helper for Hackathon Judges */}
          <div className="mt-5 border-t border-line pt-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted">
                <Terminal size={12} className="text-accent" />
                <span>Hackathon Evaluation Account</span>
              </div>
              <button
                type="button"
                onClick={fillDemoCredentials}
                className="flex items-center gap-1 rounded border border-line/80 bg-s2 px-2 py-0.5 text-[10.5px] font-medium text-accent hover:border-accent hover:bg-s3 transition"
              >
                <CheckCircle2 size={11} /> Auto-fill Demo
              </button>
            </div>
            <div className="mt-2 rounded bg-s2/70 p-2 font-mono text-[10.5px] text-ink2">
              <div className="flex justify-between">
                <span className="text-muted">Badge:</span>
                <span className="font-semibold text-ink">DEMO-OFFICER</span>
              </div>
              <div className="mt-1 flex justify-between">
                <span className="text-muted">Password:</span>
                <span className="font-semibold text-ink">Forensic#2026!SecOps</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer info & disclaimer */}
        <div className="mt-5 text-center text-[10.5px] text-muted leading-relaxed">
          <div>Offline Air-Gapped Operation · Cryptographic Evidence Seal · PBKDF2-HMAC-SHA256</div>
          <div className="mt-1 text-[9.5px] text-muted/70">
            For academic and hackathon forensic evaluation. Not an official law enforcement agency website.
          </div>
        </div>
      </div>
    </div>
  );
}
