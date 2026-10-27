// T005 — HTTP client base con JWT y manejo de errores tipado

/** Token del backend almacenado en memoria (no en localStorage) */
let _apiToken: string | null = null;

/** Callback registrado por AuthProvider para manejar 401 → logout + redirect */
let _onUnauthorized: (() => void) | null = null;

/** Llamado por auth-context después de login/restore para inyectar el JWT */
export function setApiToken(token: string | null): void {
  _apiToken = token;
}

/** Registra el handler de 401 — llamado por AuthProvider al montar */
export function registerUnauthorizedHandler(handler: () => void): void {
  _onUnauthorized = handler;
}

/** Error tipado para respuestas HTTP del backend */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

interface ApiFetchOptions extends RequestInit {
  /** Si true, omite el header Authorization (endpoints públicos) */
  public?: boolean;
}

/**
 * Wrapper sobre fetch que:
 * - Usa VITE_API_URL como base
 * - Adjunta Authorization: Bearer <backendJwt> (salvo public: true)
 * - Lanza ApiError con status y detail en caso de error HTTP
 * - Llama _onUnauthorized en 401
 */
export async function apiFetch<T>(path: string, options?: ApiFetchOptions): Promise<T> {
  const base = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';
  const url = `${base}${path}`;

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  if (options?.headers) {
    Object.assign(headers, options.headers as Record<string, string>);
  }

  if (!options?.public && _apiToken) {
    headers['Authorization'] = `Bearer ${_apiToken}`;
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new ApiError(0, 'Sin conexión, verifica tu red');
  }

  if (response.status === 401) {
    _onUnauthorized?.();
    throw new ApiError(401, 'Sesión expirada, inicia sesión de nuevo');
  }

  if (!response.ok) {
    let detail = 'Error desconocido';
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') {
        detail = body.detail;
      } else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        detail = body.detail[0].msg;
      } else if (typeof body?.message === 'string') {
        detail = body.message;
      }
    } catch { /* ignore parse errors */ }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
