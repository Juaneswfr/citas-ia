import { useNavigate } from '@tanstack/react-router';
import { Icon } from '@/components/hilo/icons';
import { Button } from '@/components/hilo/primitives';
import { CountUp } from '@/components/hilo/CountUp';
import { useDashboardInsights } from '@/hooks/use-dashboard-insights';
import { useActionTarget } from '@/hooks/use-action-target';
import {
  actionItems, busiestDay, busiestInsight, cop, customersInsight, dayName, lostInsight, pct, rates, revenueInsight,
  servicesInsight, weekInsight,
} from '@/lib/dashboard-insights';
import { AreaChart, Donut, HBars, Heatmap, StackedBars } from './charts';
import styles from './Insights.module.css';

function Skeleton({ height }: { height: number }) {
  return <span className={styles.skeleton} style={{ height }} aria-hidden />;
}

// ── Para hacer hoy ────────────────────────────────────────────────────────────

export function ActionsPanel() {
  const { data, isLoading, isError, refetch } = useDashboardInsights();
  const open = useActionTarget(data);
  const items = data ? actionItems(data.actions) : [];

  return (
    <section className={`card ${styles.actions}`} aria-labelledby="actions-title">
      <header className={styles.actionsHead}>
        <div>
          <div className="eyebrow">Para hacer hoy</div>
          <h3 id="actions-title" className={styles.cardTitle}>Lo que necesita tu <span className="serif-i">atención</span></h3>
        </div>
        {data && items.length > 0 && <span className={styles.actionsCount}><CountUp value={items.length} /> pendiente{items.length === 1 ? '' : 's'}</span>}
      </header>

      {isLoading && <div className={styles.actionList}><Skeleton height={58} /><Skeleton height={58} /></div>}

      {isError && (
        <div className={styles.soft}>
          No se pudieron cargar los pendientes.{' '}
          <Button variant="ghost" size="sm" onClick={() => refetch()}>Reintentar</Button>
        </div>
      )}

      {data && items.length === 0 && (
        <div className={styles.allClear}>
          <span className={styles.allClearIcon}><Icon name="checkCircle" size={22} /></span>
          <div>
            <strong>Todo al día</strong>
            <span>No hay citas por cerrar, cobros ni comprobantes esperando.</span>
          </div>
        </div>
      )}

      {items.length > 0 && (
        <ul className={`${styles.actionList} stagger`}>
          {items.map((item) => (
            <li key={item.key} className={styles.actionRow}>
              <span className={`${styles.actionBadge} ${item.urgent ? styles.actionBadgeUrgent : ''}`}>
                {item.key === 'receivable' ? <Icon name="money" size={18} /> : <CountUp value={item.count} />}
              </span>
              <div className={styles.actionText}>
                <strong>{item.label}</strong>
                <span>{item.hint}</span>
              </div>
              <Button variant={item.urgent ? 'primary' : 'secondary'} size="sm" iconRight="arrowR" onClick={() => open(item)}>
                {item.cta}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── Gráficas ──────────────────────────────────────────────────────────────────

function Card({ title, explain, span, children, insight, tip }: {
  title: string; explain: string; span: 5 | 7 | 12; children: React.ReactNode; insight?: string | null; tip?: React.ReactNode;
}) {
  return (
    <section className={`card ${styles.card} ${styles[`span${span}`]}`}>
      <header>
        <h3 className={styles.cardTitle}>{title}</h3>
        <p className={styles.explain}>{explain}</p>
      </header>
      {children}
      {insight && (
        <p className={styles.insight}><Icon name="sparkle" size={14} /><span>{insight}</span></p>
      )}
      {tip}
    </section>
  );
}

function Delta({ now, before }: { now: number; before: number }) {
  if (before <= 0) return null;
  const change = Math.round(((now - before) / before) * 100);
  if (change === 0) return <span className={styles.delta}>igual que antes</span>;
  return (
    <span className={`${styles.delta} ${change > 0 ? styles.deltaUp : styles.deltaDown}`}>
      <Icon name={change > 0 ? 'arrowUp' : 'arrowDn'} size={12} />{Math.abs(change)} %
    </span>
  );
}

export function InsightsCharts() {
  const { data, isLoading, isError, refetch } = useDashboardInsights();
  const navigate = useNavigate();

  if (isError) {
    return (
      <div className={`card ${styles.errorCard}`}>
        No se pudieron cargar las gráficas.{' '}
        <Button variant="secondary" size="sm" onClick={() => refetch()}>Reintentar</Button>
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className={styles.grid}>
        {[7, 5, 5, 7].map((span, i) => (
          <div key={i} className={`card ${styles.card} ${styles[`span${span}`]}`}><Skeleton height={26} /><Skeleton height={190} /></div>
        ))}
      </div>
    );
  }

  const s = data.status_30d;
  const r = rates(s);
  const lost = lostInsight(s);
  const totalClosedOpen = s.completed + s.cancelled + s.noshow + s.open;
  const day = busiestDay(data.busy_hours);
  const mixTotal = data.customers.new + data.customers.returning;
  const revenue = data.revenue;

  return (
    <div className={`${styles.grid} stagger`}>
      <Card
        span={7}
        title="Citas de los últimos 14 días"
        explain="Cada barra es un día. Verde: ya completadas. Azul: por atender. Naranja: se perdieron (canceladas o no asistió)."
        insight={weekInsight(data.week)}
      >
        <StackedBars days={data.days} todayKey={data.today} />
      </Card>

      {revenue ? (
        <Card
          span={5}
          title="Ingresos cobrados · 30 días"
          explain="Dinero que ya entró, día por día. No incluye lo agendado que aún no se paga."
          insight={revenueInsight(revenue.collected, revenue.previous)}
        >
          <div className={styles.kpiLine}>
            <strong><CountUp value={revenue.collected} format={(n) => cop(n)} /></strong>
            <Delta now={revenue.collected} before={revenue.previous} />
            {revenue.booked_open > 0 && <span className={styles.kpiSide}>+ {cop(revenue.booked_open)} agendado por atender</span>}
          </div>
          <AreaChart points={revenue.days.map((d) => ({ date: d.date, value: d.amount_cop }))} money={cop} />
        </Card>
      ) : null}

      <Card
        span={5}
        title="Cómo terminaron tus citas"
        explain="Las citas de los últimos 30 días según su estado. El círculo muestra qué parte de los clientes que debían venir sí vino."
        insight={lost?.text ?? null}
        tip={lost?.tip ? (
          <button type="button" className={styles.tipLink} onClick={() => navigate({ to: '/whatsapp' })}>
            <Icon name="bolt" size={14} />{lost.tip}<Icon name="arrowR" size={13} />
          </button>
        ) : null}
      >
        {totalClosedOpen === 0 ? (
          <p className={styles.soft}>Todavía no hay citas en los últimos 30 días.</p>
        ) : (
          <Donut
            centerValue={r.attendancePct ?? 0}
            centerLabel={r.attendancePct === null ? 'sin datos aún' : 'asistencia'}
            slices={[
              { key: 'completed', label: 'Completadas', value: s.completed, color: 'var(--sage)' },
              { key: 'open', label: 'Por atender', value: s.open, color: 'var(--steel)' },
              { key: 'cancelled', label: 'Canceladas', value: s.cancelled, color: 'var(--clay)' },
              { key: 'noshow', label: 'No asistió', value: s.noshow, color: 'var(--mustard)' },
            ]}
          />
        )}
      </Card>

      <Card
        span={7}
        title="Tus horas más llenas"
        explain="Cada cuadro es una hora de un día de la semana, con las citas de los últimos 60 días. Más oscuro, más citas."
        insight={busiestInsight(data.busy_hours) ?? (day ? `${dayName(day.dow)[0].toUpperCase()}${dayName(day.dow).slice(1)} es tu día más movido.` : null)}
      >
        {data.busy_hours.length === 0 ? <p className={styles.soft}>Aún no hay suficientes citas para ver patrones.</p> : <Heatmap cells={data.busy_hours} />}
      </Card>

      <Card
        span={revenue ? 7 : 5}
        title="Servicios más pedidos"
        explain="Los cinco servicios con más citas en 30 días, sin contar las perdidas."
        insight={servicesInsight(data.top_services)}
      >
        {data.top_services.length === 0
          ? <p className={styles.soft}>Aún no hay citas para comparar servicios.</p>
          : <HBars items={data.top_services} money={revenue ? cop : undefined} />}
      </Card>

      <Card
        span={revenue ? 5 : 12}
        title="Clientes nuevos y recurrentes"
        explain="De las personas que vinieron en 30 días: las que estrenaron su primera cita y las que ya eran clientes."
        insight={customersInsight(data.customers)}
      >
        {mixTotal === 0 ? <p className={styles.soft}>Aún no hay clientes atendidos en este periodo.</p> : (
          <div className={styles.mix}>
            <div className={styles.mixBar} role="img" aria-label={`${data.customers.new} nuevos y ${data.customers.returning} recurrentes`}>
              {data.customers.new > 0 && <span className={styles.mixNew} style={{ flexGrow: data.customers.new }} />}
              {data.customers.returning > 0 && <span className={styles.mixBack} style={{ flexGrow: data.customers.returning }} />}
            </div>
            <div className={styles.mixLegend}>
              <span><i className={styles.mixNew} />Nuevos <b><CountUp value={data.customers.new} /></b></span>
              <span><i className={styles.mixBack} />Recurrentes <b><CountUp value={data.customers.returning} /></b>
                {pct(data.customers.returning, mixTotal) !== null && <em> · {pct(data.customers.returning, mixTotal)} %</em>}</span>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
