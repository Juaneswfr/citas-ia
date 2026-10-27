// T025 — Módulo de API de billing

import { apiFetch } from './client';
import type { BillingPlanOut, SubscriptionOut } from '../types/api';

/** GET /billing/plans — endpoint público, no requiere JWT */
export async function listPlans(): Promise<BillingPlanOut[]> {
  return apiFetch<BillingPlanOut[]>('/billing/plans', { public: true });
}

/** GET /billing/workspaces/{workspaceId}/subscription */
export async function getSubscription(workspaceId: string): Promise<SubscriptionOut> {
  return apiFetch<SubscriptionOut>(`/billing/workspaces/${workspaceId}/subscription`);
}
