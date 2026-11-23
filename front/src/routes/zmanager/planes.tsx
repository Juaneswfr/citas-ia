import { createFileRoute } from "@tanstack/react-router";
import { PlansTab } from "@/components/zmanager/planes/PlansTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/planes")({
  component: () => (
    <ZPage title="Planes" sub="Cada plan con su configuración y sus números: cuántos negocios, cuánto ingreso, cuánto uso y cuánto margen.">
      <PlansTab />
    </ZPage>
  ),
});
