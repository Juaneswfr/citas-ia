// Auth context — JWT propio del FastAPI, sin Supabase.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { loginToBackend, refreshBackendToken, getMe, registerToBackend } from "./api/auth";
import { setApiToken, registerUnauthorizedHandler } from "./api/client";
import type { MeResponse } from "./types/api";

const JWT_KEY = "hilo_jwt";

// ── Types ─────────────────────────────────────────────────────────────────────

interface AuthContextType {
  backendJwt: string | null;
  me: MeResponse | null;
  isAuthenticated: boolean;
  initializing: boolean;
  workspaceId: string | null;
  role: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<'verify-email' | 'authenticated'>;
  register: (email: string, password: string, workspaceName: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signInWithFacebook: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

/** Decodifica el payload de un JWT (sin verificar firma — solo lectura client-side). */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, b64] = token.split(".");
    return JSON.parse(atob(b64.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

/** Retorna true si el token no ha expirado. */
function isTokenValid(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") return false;
  return payload.exp * 1000 > Date.now();
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [backendJwt, setBackendJwt] = useState<string | null>(null);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [initializing, setInitializing] = useState(true);
  const loggingOutRef = useRef(false);

  const applyToken = useCallback((token: string | null) => {
    setApiToken(token);
    setBackendJwt(token);
    if (token) {
      localStorage.setItem(JWT_KEY, token);
    } else {
      localStorage.removeItem(JWT_KEY);
    }
  }, []);

  const clearAuth = useCallback(() => {
    applyToken(null);
    setMe(null);
  }, [applyToken]);

  const logout = useCallback(async () => {
    loggingOutRef.current = true;
    clearAuth();
    loggingOutRef.current = false;
    window.location.href = "/login";
  }, [clearAuth]);

  // Registrar handler de 401 al montar
  useEffect(() => {
    registerUnauthorizedHandler(() => {
      if (!loggingOutRef.current) {
        clearAuth();
        window.location.href = "/login";
      }
    });
  }, [clearAuth]);

  // Restaurar sesión desde localStorage al cargar
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const stored = localStorage.getItem(JWT_KEY);
        if (!stored || !isTokenValid(stored)) {
          localStorage.removeItem(JWT_KEY);
          return;
        }
        setApiToken(stored);
        setBackendJwt(stored);

        // Intentar renovar el token si tiene < 2h de vida
        const payload = decodeJwtPayload(stored);
        const expiresIn = ((payload?.exp as number) || 0) * 1000 - Date.now();
        if (expiresIn < 2 * 60 * 60 * 1000) {
          try {
            const resp = await refreshBackendToken(stored);
            if (!cancelled) applyToken(resp.access_token);
          } catch { /* sigue con el token actual */ }
        }

        const meData = await getMe();
        if (!cancelled) setMe(meData);
      } catch {
        clearAuth();
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }

    init();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /** Login explícito con email + password */
  const login = useCallback(async (email: string, password: string) => {
    const tokenResp = await loginToBackend(email, password);
    applyToken(tokenResp.access_token);
    const meData = await getMe();
    setMe(meData);
  }, [applyToken]);

  /** signup: en el nuevo sistema redirige al register completo */
  const signup = useCallback(async (email: string, password: string): Promise<'verify-email' | 'authenticated'> => {
    // Sin Supabase no hay verify-email — el registro es inmediato via /auth/register
    // Esta función queda como stub; el flujo real usa register()
    return 'verify-email';
  }, []);

  /** Registro completo: crea usuario + workspace en el backend. */
  const register = useCallback(async (email: string, password: string, workspaceName: string): Promise<void> => {
    const slug = workspaceName
      .toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "mi-negocio";

    const tokenResp = await registerToBackend(email, password, workspaceName, slug);
    applyToken(tokenResp.access_token);
    const meData = await getMe();
    setMe(meData);
  }, [applyToken]);

  /** OAuth eliminado — mostrar mensaje al usuario */
  const signInWithGoogle = useCallback(async () => {
    throw new Error("El login con Google no está disponible. Usa email y contraseña.");
  }, []);

  const signInWithFacebook = useCallback(async () => {
    throw new Error("El login con Facebook no está disponible. Usa email y contraseña.");
  }, []);

  const value = useMemo<AuthContextType>(() => ({
    backendJwt,
    me,
    isAuthenticated: !!backendJwt && !!me,
    initializing,
    workspaceId: me?.workspace_id ?? null,
    role: me?.role ?? null,
    login,
    signup,
    register,
    signInWithGoogle,
    signInWithFacebook,
    logout,
  }), [backendJwt, me, initializing, login, signup, register, signInWithGoogle, signInWithFacebook, logout]);

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-6 w-6 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
