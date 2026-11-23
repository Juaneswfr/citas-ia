import { createFileRoute } from "@tanstack/react-router";
import { CarteraTab } from "@/components/admin/CarteraTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/cobros")({
  component: () => (
    <ZPage title="Cobros" sub="Lo que se debe, lo que viene y qué falta hacer con cada cuenta de cobro.">
      <CarteraTab />
    </ZPage>
  ),
});
