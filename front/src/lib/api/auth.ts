// T006 — Módulo de autenticación del backend

import { apiFetch } from './client';
import type { TokenResponse, MeResponse } from '../types/api';

/** POST /auth/login — obtiene el JWT del backend con correo y contraseña. */
export async function loginToBackend(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    public: true,
  });
}

/**
 * POST /auth/refresh — renueva el JWT del backend con el JWT vigente.
 * Usado en la restauración de sesión al recargar la página.
 */
export async function refreshBackendToken(currentToken: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: currentToken }),
    public: true,
  });
}

/** GET /auth/google/login/url — URL de Google para crear cuenta o entrar, con el calendario incluido. */
export async function getGoogleLoginUrl(): Promise<{ url: string }> {
  return apiFetch<{ url: string }>('/auth/google/login/url', { public: true });
}

/** GET /auth/facebook/login/url — URL de Facebook para crear cuenta o entrar. */
export async function getFacebookLoginUrl(): Promise<{ url: string }> {
  return apiFetch<{ url: string }>('/auth/facebook/login/url', { public: true });
}

/** POST /auth/google/ticket — cambia el ticket que dejó el callback de Google o de Facebook por la sesión. */
export async function exchangeGoogleTicket(ticket: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/google/ticket', {
    method: 'POST',
    body: JSON.stringify({ ticket }),
    public: true,
  });
}

/** POST /auth/oauth/link — vincula Google (o Facebook) a la cuenta de correo existente, con su contraseña. */
export async function linkOAuthAccount(ticket: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>('/auth/oauth/link', {
    method: 'POST',
    body: JSON.stringify({ ticket, password }),
    public: true,
  });
}

/** POST /auth/forgot-password — manda el enlace para elegir contraseña nueva. Responde igual exista o no el correo. */
export async function requestPasswordReset(email: string): Promise<void> {
  await apiFetch<{ ok: boolean }>('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
    public: true,
  });
}

/** POST /auth/reset-password — guarda la contraseña nueva con el token del enlace del correo. */
export async function resetPassword(token: string, password: string): Promise<void> {
  await apiFetch<{ ok: boolean }>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
    public: true,
  });
}

/** GET /auth/me — datos del usuario autenticado (requiere JWT en header) */
export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/me');
}

/** PATCH /auth/me — cambia el nombre de la propia cuenta. */
export async function updateMyName(name: string): Promise<{ name: string }> {
  return apiFetch<{ name: string }>('/auth/me', { method: 'PATCH', body: JSON.stringify({ name }) });
}

/**
 * GET /auth/google/calendar/url — obtiene la URL de autorización OAuth de Google Calendar.
 * El frontend redirige al usuario a esa URL para conectar su calendario.
 */
export async function getGoogleCalendarUrl(
  workspaceId: string,
  returnTo: 'onboarding' | 'settings' | 'equipo' = 'onboarding',
  memberId?: string,
): Promise<{ url: string }> {
  const params = new URLSearchParams({ workspace_id: workspaceId, return_to: returnTo });
  if (memberId) params.set('member_id', memberId);
  return apiFetch<{ url: string }>(`/auth/google/calendar/url?${params}`);
}

/**
 * POST /auth/register — crea usuario + workspace en un solo paso.
 * El registro es inmediato: no hay verificación de correo.
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
