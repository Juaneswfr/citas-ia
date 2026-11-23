import { createFileRoute } from "@tanstack/react-router";
import { IssuerTab } from "@/components/admin/IssuerTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/configuracion")({
  component: () => (
    <ZPage title="Configuración" sub="Quién cobra y qué dice la cuenta de cobro.">
      <IssuerTab />
    </ZPage>
  ),
});
