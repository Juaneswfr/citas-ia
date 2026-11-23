import { createFileRoute } from "@tanstack/react-router";
import { OverviewTab } from "@/components/admin/OverviewTab";
import { AnalysisTab } from "@/components/zmanager/analisis/AnalysisTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/")({
  component: () => (
    <ZPage title="Dashboard" sub="Todos los negocios y usuarios de Zumit, y cómo van el ingreso, el costo y las citas semana a semana.">
      <OverviewTab />
      <AnalysisTab />
    </ZPage>
  ),
});
