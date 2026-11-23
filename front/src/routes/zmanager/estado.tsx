import { createFileRoute } from "@tanstack/react-router";
import { HealthTab } from "@/components/admin/HealthTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/estado")({
  component: () => (
    <ZPage title="Estado" sub="Si Anthropic y Kapso responden, y cómo van los mensajes de las últimas 24 horas.">
      <HealthTab />
    </ZPage>
  ),
});
