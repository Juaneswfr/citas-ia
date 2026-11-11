// Resumen mensual del dueño: ingresos, gastos, utilidad, por cobrar y por pagar.

import { useState } from 'react';
import { fmtCOP } from '@/lib/hilo-data';
import { useSummary } from '@/hooks/use-accounting';
import type { CategoryTotal } from '@/lib/types/accounting';
import { AsyncState, Field, currentMonth } from './ui';
import styles from './Finanzas.module.css';

interface CategoryBarsProps {
  rows: CategoryTotal[];
  variant: 'income' | 'expense';
}

function CategoryBars({ rows, variant }: CategoryBarsProps) {
  const max = Math.max(...rows.map((r) => r.total_cop), 1);
  if (rows.length === 0) return <div className={styles.state}>Sin movimientos este mes.</div>;
  return (
    <div className={styles.bars}>
      {rows.map((row) => (
        <div key={row.category} className={styles.bar}>
          <span>{row.category}</span>
          <div className={styles.bar__track}>
            {/* Ancho calculado en runtime: excepción válida de estilo inline (front.md §10) */}
            <div className={`${styles.bar__fill} ${variant === 'expense' ? styles['bar__fill--expense'] : ''}`}
                 style={{ width: `${(row.total_cop / max) * 100}%` }} />
          </div>
          <span className={styles.bar__value}>{fmtCOP(row.total_cop)}</span>
        </div>
      ))}
    </div>
  );
}

export function SummaryTab() {
  const [month, setMonth] = useState(currentMonth());
  const { data, isLoading, isError, refetch } = useSummary(month);

  return (
    <>
      <div className={styles.toolbar}>
        <h2 className={styles.toolbar__title}>Resumen del mes</h2>
        <div className={styles.toolbar__actions}>
          <Field label="Mes">
            <input className={styles.field__input} type="month" value={month}
                   onChange={(e) => e.target.value && setMonth(e.target.value)} />
          </Field>
        </div>
      </div>
      <AsyncState isLoading={isLoading} isError={isError} isEmpty={!data} emptyText="Sin datos." onRetry={refetch}>
        {data && (
          <>
            <div className={styles.kpis}>
              <div className={styles.kpi}>
                <div className={styles.kpi__label}>Ingresos</div>
                <div className={`${styles.kpi__value} ${styles['kpi__value--positive']}`}>{fmtCOP(data.income_cop)}</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpi__label}>Gastos</div>
                <div className={`${styles.kpi__value} ${styles['kpi__value--negative']}`}>{fmtCOP(data.expense_cop)}</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpi__label}>Utilidad</div>
                <div className={`${styles.kpi__value} ${data.profit_cop >= 0 ? styles['kpi__value--positive'] : styles['kpi__value--negative']}`}>
                  {fmtCOP(data.profit_cop)}
                </div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpi__label}>Por cobrar</div>
                <div className={styles.kpi__value}>{fmtCOP(data.receivable_cop)}</div>
                <div className={styles.kpi__hint}>Ventas pendientes de cobro</div>
              </div>
              <div className={styles.kpi}>
                <div className={styles.kpi__label}>Por pagar</div>
                <div className={styles.kpi__value}>{fmtCOP(data.payable_cop)}</div>
                <div className={styles.kpi__hint}>Compras pendientes de pago</div>
              </div>
            </div>
            <div className={styles.cols}>
              <section className={styles.panel}>
                <h3 className={styles.panel__title}>Ingresos por categoría</h3>
                <CategoryBars rows={data.income_by_category} variant="income" />
              </section>
              <section className={styles.panel}>
                <h3 className={styles.panel__title}>Gastos por categoría</h3>
                <CategoryBars rows={data.expense_by_category} variant="expense" />
              </section>
            </div>
          </>
        )}
      </AsyncState>
    </>
  );
}
