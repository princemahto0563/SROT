/**
 * Police Authentication State & Route Protection.
 *
 * Enforces session verification with the backend, stores session tokens
 * in localStorage, and handles login/logout lifecycles.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, getAuthToken, setAuthToken } from "../lib/api";

export type OfficerProfile = {
  badge_id: string;
  name: string;
  role: string;
  unit: string;
  last_login_at?: string | null;
};

type LoginResponse = {
  token: string;
  officer: OfficerProfile;
  expires_at: string;
};

type SessionResponse = {
  authenticated: boolean;
  officer: OfficerProfile;
};

type AuthContextType = {
  officer: OfficerProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (badge_id: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [officer, setOfficer] = useState<OfficerProfile | null>(null);
  const [token, setToken] = useState<string | null>(getAuthToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const checkSession = useCallback(async () => {
    const existingToken = getAuthToken();
    if (!existingToken) {
      setOfficer(null);
      setToken(null);
      setIsLoading(false);
      return;
    }
    try {
      const res = await api.get<SessionResponse>("/auth/session");
      if (res.authenticated && res.officer) {
        setOfficer(res.officer);
        setToken(existingToken);
      } else {
        setAuthToken(null);
        setOfficer(null);
        setToken(null);
      }
    } catch {
      setAuthToken(null);
      setOfficer(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  // Listen for unauthorized 401 events emitted by the API client
  useEffect(() => {
    const handleUnauthorized = () => {
      setAuthToken(null);
      setOfficer(null);
      setToken(null);
    };
    window.addEventListener("srot:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("srot:unauthorized", handleUnauthorized);
  }, []);

  const login = useCallback(async (badge_id: string, password: string) => {
    const res = await api.post<LoginResponse>("/auth/login", { badge_id, password });
    if (res.token && res.officer) {
      setAuthToken(res.token);
      setToken(res.token);
      setOfficer(res.officer);
    } else {
      throw new Error("Invalid response received from authentication service.");
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Ignore backend logout errors; ensure client-side state is cleared
    } finally {
      setAuthToken(null);
      setOfficer(null);
      setToken(null);
    }
  }, []);

  const value = useMemo<AuthContextType>(() => ({
    officer,
    token,
    isAuthenticated: Boolean(officer && token),
    isLoading,
    login,
    logout,
  }), [officer, token, isLoading, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#08090D] text-ink">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          <div className="font-mono text-xs text-muted">Verifying police credentials…</div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
