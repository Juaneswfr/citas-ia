import { createFileRoute } from "@tanstack/react-router";
import { CostsTab } from "@/components/admin/CostsTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/costos")({
  component: () => (
    <ZPage title="Costos" sub="Cuánto cuesta la IA de cada negocio y de cada cita que agenda el asistente.">
      <CostsTab />
    </ZPage>
  ),
});
