// Los precios de la landing: se leen de los planes reales y, mientras llegan (o si el servidor no responde), se muestran
// los de siempre. La página se dibuja completa en el servidor con esos valores y se actualiza sola al llegar los reales.

import { useQuery } from '@tanstack/react-query';
import { getPricing } from '@/lib/api/billing';
import { FALLBACK_PRICING, buildPricingView, type PricingView } from '@/components/landing/pricing-data';

export function usePricing(): PricingView {
  const { data } = useQuery({
    queryKey: ['billing', 'pricing'],
    queryFn: getPricing,
    staleTime: 5 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
    placeholderData: FALLBACK_PRICING,
  });
  return buildPricingView(data ?? FALLBACK_PRICING);
}
