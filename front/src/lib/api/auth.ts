// T006 — Módulo de autenticación del backend

import { apiFetch } from './client';
import type { TokenResponse, MeResponse } from '../types/api';

/** POST /auth/login — obtiene JWT del backend con credenciales Supabase */
export async function loginToBackend(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    public: true,
  });
}

/**
 * POST /auth/refresh — renueva el JWT del backend usando el refresh token de Supabase.
 * Usado en la restauración de sesión al recargar la página.
 */
export async function refreshBackendToken(supabaseRefreshToken: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: supabaseRefreshToken }),
    public: true,
  });
}

/** GET /auth/me — datos del usuario autenticado (requiere JWT en header) */
export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/me');
}

/**
 * GET /auth/google/calendar/url — obtiene la URL de autorización OAuth de Google Calendar.
 * El frontend redirige al usuario a esa URL para conectar su calendario.
 */
export async function getGoogleCalendarUrl(workspaceId: string, returnTo: 'onboarding' | 'settings' = 'onboarding'): Promise<{ url: string }> {
  return apiFetch<{ url: string }>(
    `/auth/google/calendar/url?workspace_id=${encodeURIComponent(workspaceId)}&return_to=${returnTo}`,
  );
}

/**
 * POST /auth/register — crea usuario + workspace en un solo paso.
 * Usa la admin API del backend para confirmar el email automáticamente.
 */
export async function registerToBackend(
  email: string,
  password: string,
  workspaceName: string,
  workspaceSlug: string,
): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
      workspace_name: workspaceName,
      workspace_slug: workspaceSlug,
    }),
    public: true,
  });
}
