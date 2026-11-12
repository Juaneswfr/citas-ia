import { createFileRoute } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { OverviewTab } from "@/components/admin/OverviewTab";
import { UsersTab } from "@/components/admin/UsersTab";
import { WorkspacesTab } from "@/components/admin/WorkspacesTab";
import { useAuth } from "@/lib/auth-context";
import { isPlatformAdmin } from "@/lib/nav";
import styles from "@/components/admin/Admin.module.css";

export const Route = createFileRoute("/_authenticated/admin")({
  head: () => ({ meta: [{ title: "Plataforma · Hilo" }] }),
  component: AdminPage,
});

type TabId = "resumen" | "negocios" | "usuarios";

const TABS: { id: TabId; label: string }[] = [
  { id: "resumen", label: "Resumen" },
  { id: "negocios", label: "Negocios" },
  { id: "usuarios", label: "Usuarios" },
];

const TAB_CONTENT: Record<TabId, () => ReactNode> = {
  resumen: () => <OverviewTab />,
  negocios: () => <WorkspacesTab />,
  usuarios: () => <UsersTab />,
};

function AdminPage() {
  const { role } = useAuth();
  const [tab, setTab] = useState<TabId>("resumen");

  // El backend responde 403 a cualquier otro rol; aquí solo evitamos una pantalla rota.
  if (!isPlatformAdmin(role)) {
    return <div className={styles.admin}><p className={styles.admin__sub}>Esta sección es solo para el equipo de Hilo.</p></div>;
  }

  return (
    <div className={`${styles.admin} page-enter`}>
      <header className={styles.admin__head}>
        <h2 className={styles.admin__title}>Plataforma</h2>
        <p className={styles.admin__sub}>Todos los negocios y usuarios de Hilo.</p>
      </header>
      <nav className={styles.admin__tabs} aria-label="Secciones del panel de plataforma">
        {TABS.map((item) => (
          <button key={item.id} type="button" onClick={() => setTab(item.id)}
                  aria-current={tab === item.id ? "page" : undefined}
                  className={`${styles.admin__tab} ${tab === item.id ? styles["admin__tab--active"] : ""}`}>
            {item.label}
          </button>
        ))}
      </nav>
      {/* key: al cambiar de pestaña el contenido vuelve a entrar con la transición suave */}
      <div key={tab} className="tab-enter">{TAB_CONTENT[tab]()}</div>
    </div>
  );
}
