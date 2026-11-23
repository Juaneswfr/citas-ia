import { createFileRoute } from "@tanstack/react-router";
import { BillingTab } from "@/components/admin/BillingTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/facturacion")({
  component: () => (
    <ZPage title="Facturación" sub="Ingresos, cobranza, riesgo y margen real. El cobro es manual: aquí se confirman los pagos.">
      <BillingTab />
    </ZPage>
  ),
});
