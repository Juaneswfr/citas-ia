// Maquetas de la plataforma (datos de ejemplo, no reales).

const AGENDA: ReadonlyArray<readonly [string, string, boolean]> = [
  ["09:00", "Mateo · Corte clásico", false],
  ["11:00", "Sebastián · En curso", true],
  ["14:30", "Felipe · Corte + barba", false],
];
const SERVICIOS = [
  ["Corte clásico", "$38.000", "40 min · activo"],
  ["Corte + barba", "$55.000", "60 min · activo"],
] as const;
const CONEXIONES = [
  ["WA", "WhatsApp", "Coexistencia activa"],
  ["GC", "Google Calendar", "Sincronizado hace 1 min"],
] as const;

export function AgendaMock() {
  return (
    <div className="home-mock">
      <div className="home-mock__title">El día de hoy</div>
      {AGENDA.map(([time, name, active]) => (
        <div key={time} className={`home-mock__row${active ? " home-mock__row--active" : ""}`}>
          <span className="home-mock__time">{time}</span>
          <span className="home-mock__name">{name}</span>
        </div>
      ))}
    </div>
  );
}

export function ServiciosMock() {
  return (
    <div className="home-mock">
      {SERVICIOS.map(([name, price, detail]) => (
        <div key={name} className="home-mock__row home-mock__row--between">
          <div>
            <div className="home-mock__strong">{name}</div>
            <div className="home-mock__meta">{detail}</div>
          </div>
          <div className="home-mock__price">{price}</div>
        </div>
      ))}
    </div>
  );
}

export function ClienteMock() {
  return (
    <div className="home-mock">
      <div className="home-mock__who">
        <span className="home-mock__avatar">FA</span>
        <div className="home-mock__main">
          <div className="home-mock__client">Felipe Arango</div>
          <div className="home-mock__sub">Cliente frecuente · 14 visitas</div>
        </div>
        <span className="home-mock__badge">VIP</span>
      </div>
      <div className="home-mock__note">"Prefiere a Julián. Tijera, no máquina en los lados."</div>
    </div>
  );
}

export function ConexionesMock() {
  return (
    <div className="home-mock">
      {CONEXIONES.map(([code, name, status]) => (
        <div key={name} className="home-mock__row home-mock__row--roomy">
          <span className="home-mock__avatar home-mock__avatar--soft">{code}</span>
          <div className="home-mock__main">
            <div className="home-mock__strong">{name}</div>
            <div className="home-mock__meta">{status}</div>
          </div>
          <span className="home-mock__status" />
        </div>
      ))}
    </div>
  );
}
