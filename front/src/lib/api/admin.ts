// API del panel de administración de la plataforma. Todas las rutas exigen super_admin.

import { apiFetch } from './client';
import type {
  AdminHealth, AdminOverview, AdminUserList, AdminWorkspaceDetail, AdminWorkspaceFilters,
  AdminWorkspaceList, AdminWorkspaceUpdate,
} from '../types/admin';

const BASE_URL = '/admin';

export const ADMIN_PAGE_SIZE = 50;

export const adminService = {
  /** GET /admin/overview — totales y repartos de la plataforma */
  getOverview(): Promise<AdminOverview> {
    return apiFetch<AdminOverview>(`${BASE_URL}/overview`);
  },

  /** GET /admin/health — prueba las claves de Anthropic y Kapso y resume los envíos de 24 h */
  getHealth(): Promise<AdminHealth> {
    return apiFetch<AdminHealth>(`${BASE_URL}/health`);
  },

  /** GET /admin/workspaces — negocios, con búsqueda y filtros */
  listWorkspaces(filters: AdminWorkspaceFilters, page: number): Promise<AdminWorkspaceList> {
    const query = new URLSearchParams({
      limit: String(ADMIN_PAGE_SIZE),
      offset: String(page * ADMIN_PAGE_SIZE),
    });
    if (filters.search.trim()) query.set('search', filters.search.trim());
    if (filters.businessType) query.set('business_type', filters.businessType);
    if (filters.status) query.set('is_active', String(filters.status === 'active'));
    return apiFetch<AdminWorkspaceList>(`${BASE_URL}/workspaces?${query}`);
  },

  /** GET /admin/workspaces/{id} — ficha con equipo, canales y calendarios */
  getWorkspace(workspaceId: string): Promise<AdminWorkspaceDetail> {
    return apiFetch<AdminWorkspaceDetail>(`${BASE_URL}/workspaces/${workspaceId}`);
  },

  /** PATCH /admin/workspaces/{id} — suspender, reactivar o corregir el tipo de negocio */
  updateWorkspace(workspaceId: string, body: AdminWorkspaceUpdate): Promise<AdminWorkspaceDetail> {
    return apiFetch<AdminWorkspaceDetail>(`${BASE_URL}/workspaces/${workspaceId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
  },

  /** GET /admin/users — usuarios de la plataforma */
  listUsers(search: string, page: number): Promise<AdminUserList> {
    const query = new URLSearchParams({
      limit: String(ADMIN_PAGE_SIZE),
      offset: String(page * ADMIN_PAGE_SIZE),
    });
    if (search.trim()) query.set('search', search.trim());
    return apiFetch<AdminUserList>(`${BASE_URL}/users?${query}`);
  },

  /** PATCH /admin/users/{id} — bloquear o desbloquear el acceso */
  async setUserActive(userId: string, isActive: boolean): Promise<void> {
    await apiFetch(`${BASE_URL}/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    });
  },
};
