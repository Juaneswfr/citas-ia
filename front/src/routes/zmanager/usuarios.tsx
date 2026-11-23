import { createFileRoute } from "@tanstack/react-router";
import { UsersTab } from "@/components/admin/UsersTab";
import { ZPage } from "@/components/zmanager/ZManagerShell";

export const Route = createFileRoute("/zmanager/usuarios")({
  component: () => (
    <ZPage title="Usuarios" sub="Quién tiene acceso a la plataforma. Aquí se bloquea o se desbloquea.">
      <UsersTab />
    </ZPage>
  ),
});
