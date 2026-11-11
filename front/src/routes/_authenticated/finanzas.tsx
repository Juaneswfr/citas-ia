import { createFileRoute } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { canManageFinance } from "@/lib/nav";
import { usePendingReceiptCount } from "@/hooks/use-receipts";
import { MovementsTab } from "@/components/finanzas/MovementsTab";
import { PurchasesTab } from "@/components/finanzas/PurchasesTab";
import { ReceiptsTab } from "@/components/finanzas/ReceiptsTab";
import { SalesTab } from "@/components/finanzas/SalesTab";
import { SummaryTab } from "@/components/finanzas/SummaryTab";
import { TeamTab } from "@/components/finanzas/TeamTab";
import { ThirdPartiesTab } from "@/components/finanzas/ThirdPartiesTab";
import styles from "@/components/finanzas/Finanzas.module.css";

export const Route = createFileRoute("/_authenticated/finanzas")({
  head: () => ({ meta: [{ title: "Finanzas · Hilo" }] }),
  component: FinanzasPage,
});

type TabId = "resumen" | "ventas" | "comprobantes" | "compras" | "movimientos" | "terceros" | "equipo";

const TABS: { id: TabId; label: string }[] = [
  { id: "resumen", label: "Resumen" },
  { id: "ventas", label: "Ventas" },
  { id: "comprobantes", label: "Comprobantes" },
  { id: "compras", label: "Compras" },
  { id: "movimientos", label: "Movimientos" },
  { id: "terceros", label: "Terceros" },
  { id: "equipo", label: "Equipo y comisiones" },
];

const TAB_CONTENT: Record<TabId, () => ReactNode> = {
  resumen: () => <SummaryTab />,
  ventas: () => <SalesTab />,
  comprobantes: () => <ReceiptsTab />,
  compras: () => <PurchasesTab />,
  movimientos: () => <MovementsTab />,
  terceros: () => <ThirdPartiesTab />,
  equipo: () => <TeamTab />,
};

function FinanzasPage() {
  const { role } = useAuth();
  const [tab, setTab] = useState<TabId>("resumen");
  const pendingReceipts = usePendingReceiptCount();

  // El backend ya devuelve 403 a staff/viewer; aquí evitamos mostrar una pantalla rota.
  if (!canManageFinance(role)) {
    return <div className={styles.fin}><div className={styles.state}>Solo el dueño o un administrador puede ver las finanzas.</div></div>;
  }

  return (
    <div className={styles.fin}>
      <nav className={styles.fin__tabs} aria-label="Secciones de finanzas">
        {TABS.map((item) => (
          <button key={item.id} type="button" onClick={() => setTab(item.id)}
                  className={`${styles.fin__tab} ${tab === item.id ? styles["fin__tab--active"] : ""}`}>
            {item.label}
            {item.id === "comprobantes" && pendingReceipts > 0 && (
              <span className={styles["fin__tab-count"]} aria-label={`${pendingReceipts} por revisar`}>{pendingReceipts}</span>
            )}
          </button>
        ))}
      </nav>
      {TAB_CONTENT[tab]()}
    </div>
  );
}
