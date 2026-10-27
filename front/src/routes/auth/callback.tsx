// OAuth callback — OAuth eliminado. Esta ruta redirige al login.
import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/auth/callback")({
  beforeLoad: () => {
    throw redirect({ to: "/login" });
  },
  component: () => null,
});
