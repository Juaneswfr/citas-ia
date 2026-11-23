import { createFileRoute } from "@tanstack/react-router";
import { WorkspacesTab } from "@/components/admin/WorkspacesTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/negocios")({
  component: () => (
    <ZPage title="Negocios" sub="Cada negocio con su plan, su equipo y las acciones de cobro y suspensión.">
      <WorkspacesTab />
    </ZPage>
  ),
});
