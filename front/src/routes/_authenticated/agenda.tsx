import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo, useEffect } from "react";
import { toast } from "sonner";
import { startOfWeek, endOfWeek, addDays, format, getDay } from "date-fns";
import { es } from "date-fns/locale";
import { useQuery } from "@tanstack/react-query";
import { Icon } from "@/components/hilo/icons";
import { Button, Avatar, Segmented } from "@/components/hilo/primitives";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import HILO from "@/lib/hilo-data";
import { useAuth } from "@/lib/auth-context";
import { useAppointments, useWeekAppointments, useCreateAppointment } from "@/hooks/use-appointments";
import { useTeamMembers } from "@/hooks/use-team";
import { useCustomers } from "@/hooks/use-customers";
import { useServices } from "@/hooks/use-services";
import { listCalendars, listChannels } from "@/lib/api/channels";
import type { CalendarEvent } from "@/hooks/use-appointments";
import type { ServiceOut } from "@/lib/types/api";

export const Route = createFileRoute("/_authenticated/agenda")({
  head: () => ({ meta: [{ title: "Agenda · Hilo" }] }),
  component: AgendaPage,
});

const HOURS = [9,10,11,12,13,14,15,16,17,18,19];
const PX_PER_HOUR = 64;
const WEEK_DAYS = 6; // Lun–Sáb

function svcHueFromName(name: string): string {
  const s = HILO.services.find(x => x.name === name);
  return s ? HILO.hueVar(s.hue) : 'var(--wine)';
}

function WeekView({ weekStart, events, isLoading, onSlotClick }: {
  weekStart: Date;
  events: CalendarEvent[];
  isLoading: boolean;
  onSlotClick: (date: string, time: string) => void;
}) {
  const today = new Date();
  const todayDayIdx = getDay(today); // 0=Dom,1=Lun…6=Sáb
  // Convertir a índice Mon-Sat: lunes=0 … sábado=5
  const todayWeekIdx = todayDayIdx === 0 ? -1 : todayDayIdx - 1;

  const days = Array.from({ length: WEEK_DAYS }, (_, i) => {
    const date = addDays(weekStart, i);
    return {
      label: format(date, 'EEE', { locale: es }).replace(/^\w/, c => c.toUpperCase()),
      num: format(date, 'd'),
      isToday: format(date, 'yyyy-MM-dd') === format(today, 'yyyy-MM-dd'),
    };
  });

  return (
    <div className="card" style={{ overflow:'hidden' }}>
      <div style={{ display:'grid', gridTemplateColumns:`56px repeat(${WEEK_DAYS}, 1fr)`, borderBottom:'1px solid var(--line)' }}>
        <div/>
        {days.map((d, i) => (
          <div key={i} style={{ padding:'12px 8px', textAlign:'center', borderLeft:'1px solid var(--line)',
            background: d.isToday ? 'var(--wine-50)' : 'transparent' }}>
            <div style={{ font:'500 11px/1 var(--font-sans)', textTransform:'uppercase', letterSpacing:'0.08em',
              color: d.isToday ? 'var(--wine)' : 'var(--ink-3)' }}>{d.label}</div>
            <div className="tnum" style={{ font:'500 19px/1.2 var(--font-sans)', marginTop:4,
              color: d.isToday ? 'var(--wine)' : 'var(--ink-1)' }}>{d.num}</div>
          </div>
        ))}
      </div>
      <div style={{ display:'grid', gridTemplateColumns:`56px repeat(${WEEK_DAYS}, 1fr)`, position:'relative', overflowX:'auto' }}>
        <div>
          {HOURS.map(h => (
            <div key={h} style={{ height:PX_PER_HOUR, position:'relative' }}>
              <span className="tnum" style={{ position:'absolute', top:-7, right:8, font:'400 11px/1 var(--font-mono)', color:'var(--ink-4)' }}>{h}:00</span>
            </div>
          ))}
        </div>
        {days.map((d, di) => (
          <div key={di}
            onClick={e => {
              const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
              const offsetY = e.clientY - rect.top;
              const hourIdx = Math.min(Math.floor(offsetY / PX_PER_HOUR), HOURS.length - 1);
              const minRaw = ((offsetY % PX_PER_HOUR) / PX_PER_HOUR) * 60;
              const min = Math.round(minRaw / 15) * 15 % 60;
              const hour = HOURS[hourIdx];
              const date = format(addDays(weekStart, di), 'yyyy-MM-dd');
              const time = `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`;
              onSlotClick(date, time);
            }}
            style={{ position:'relative', borderLeft:'1px solid var(--line)', cursor:'crosshair',
              background: d.isToday ? 'color-mix(in srgb, var(--wine) 3%, transparent)' : 'transparent' }}>
            {HOURS.map(h => <div key={h} style={{ height:PX_PER_HOUR, borderBottom:'1px solid var(--line-soft)' }}/>)}
            {d.isToday && (
              <div style={{ position:'absolute', left:0, right:0,
                top:(new Date().getHours() + new Date().getMinutes()/60 - HOURS[0]) * PX_PER_HOUR,
                height:2, background:'var(--wine)', zIndex:3 }}>
                <span style={{ position:'absolute', left:-4, top:-3, width:8, height:8, borderRadius:'50%', background:'var(--wine)' }}/>
              </div>
            )}
            {isLoading ? (
              // Skeleton placeholder mientras carga
              <div style={{ position:'absolute', left:3, right:3, top: PX_PER_HOUR,
                height: PX_PER_HOUR * 0.75, borderRadius:'var(--r-sm)',
                background:'var(--line)', opacity: 0.4 }} />
            ) : (
              events.filter(e => e.d === di).map((e, i) => {
                const hue = svcHueFromName(e.svc);
                return (
                  <div key={i} title={`${e.client} · ${e.svc}`} style={{
                    position:'absolute', left:3, right:3,
                    top:(e.s - HOURS[0]) * PX_PER_HOUR + 1,
                    height: e.m / 60 * PX_PER_HOUR - 2,
                    borderRadius:'var(--r-sm)', padding:'5px 7px', overflow:'hidden', cursor:'pointer', zIndex:2,
                    background:`color-mix(in srgb, ${hue} 13%, var(--surface))`,
                    borderLeft:`2.5px solid ${hue}`, boxShadow:'var(--shadow-sm)',
                    transition:'transform var(--dur-1)',
                  }}
                  onMouseEnter={e2=>(e2.currentTarget as HTMLElement).style.transform='scale(1.015)'}
                  onMouseLeave={e2=>(e2.currentTarget as HTMLElement).style.transform='scale(1)'}>
                    <div style={{ font:'500 11.5px/1.15 var(--font-sans)', color:'var(--ink-1)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{e.client}</div>
                    {e.m >= 40 && <div style={{ font:'400 10.5px/1.3 var(--font-sans)', color:hue, marginTop:2 }}>{e.svc}</div>}
                    {e.m >= 55 && <div style={{ font:'400 10px/1 var(--font-mono)', color:'var(--ink-3)', marginTop:3 }}>{e.pro}</div>}
                  </div>
                );
              })
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function DayView({ isLoading }: { isLoading: boolean }) {
  const today = format(new Date(), 'yyyy-MM-dd');
  const { data: appointments = [], isLoading: dayLoading } = useAppointments({ from_date: today, to_date: today });
  const loading = isLoading || dayLoading;

  return (
    <div className="card" style={{ padding:'8px 20px 6px', maxWidth:760 }}>
      <div style={{ padding:'12px 0 6px' }}>
        <h3 style={{ margin:0, font:'400 20px/1 var(--font-serif)', color:'var(--ink-1)' }}>
          {format(new Date(), "EEEE d · 'hoy'", { locale: es })}
        </h3>
      </div>
      {loading ? (
        <div style={{ padding:'24px 0', display:'flex', flexDirection:'column', gap:12 }}>
          {[1,2,3].map(i => (
            <div key={i} style={{ display:'grid', gridTemplateColumns:'62px 24px 1fr', alignItems:'start' }}>
              <div style={{ height:13, margin:'12px 14px 0 0', background:'var(--line)', borderRadius:4 }}/>
              <div/>
              <div style={{ height:50, margin:'8px 0 12px', background:'var(--surface)', border:'1px solid var(--line)', borderRadius:'var(--r-md)' }}/>
            </div>
          ))}
        </div>
      ) : appointments.length === 0 ? (
        <div style={{ padding:'24px 0', textAlign:'center', color:'var(--ink-3)', font:'400 13px/1.4 var(--font-sans)' }}>Sin citas para hoy</div>
      ) : (
        appointments.map((a, i) => {
          const svcObj = HILO.services.find(s => s.name === a.svc);
          const hue = HILO.hueVar(svcObj?.hue || 'wine');
          return (
            <div key={a.id} style={{ display:'grid', gridTemplateColumns:'62px 24px 1fr', alignItems:'start' }}>
              <div style={{ textAlign:'right', paddingRight:14, paddingTop:12 }}>
                <div className="tnum" style={{ font:'500 13px/1 var(--font-sans)', color:'var(--ink-1)' }}>{a.time}</div>
                <div className="tnum" style={{ font:'400 11px/1.4 var(--font-mono)', color:'var(--ink-4)' }}>{a.end}</div>
              </div>
              <div style={{ position:'relative', display:'flex', justifyContent:'center' }}>
                {i < appointments.length - 1 && <span style={{ position:'absolute', top:14, bottom:-2, width:2, background:'var(--wine-200)' }}/>}
                <span style={{ marginTop:13, width:11, height:11, borderRadius:'50%', background:hue, zIndex:1, flexShrink:0 }}/>
              </div>
              <div style={{ padding:'8px 0 12px' }}>
                <div style={{ background:'var(--surface)', border:'1px solid var(--line)', borderRadius:'var(--r-md)',
                  borderLeft:`3px solid ${hue}`, padding:'10px 13px', display:'flex', alignItems:'center', gap:10 }}>
                  <div style={{ flex:1 }}>
                    <div style={{ font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{a.client}</div>
                    <div style={{ font:'400 12px/1 var(--font-sans)', color:'var(--ink-3)', marginTop:3 }}>{a.svc} · {a.pro || 'Sin asignar'}</div>
                  </div>
                  {a.via==='wa' && <Icon name="whatsapp" size={15} style={{ color:'var(--wa-ink)' }}/>}
                </div>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function MonthView() {
  const start = -3;
  const cells = Array.from({length:35}, (_,i) => i+start);
  const today = new Date().getDate();
  const withAppt: Record<number,number> = {4:2,8:3,11:1,12:4,15:2,18:5,19:3,20:1,22:2,25:4,26:1,27:3,28:6,29:2};
  return (
    <div className="card" style={{ overflow:'hidden' }}>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(7,1fr)' }}>
        {['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'].map(d => (
          <div key={d} style={{ padding:'10px', textAlign:'center', font:'500 11px/1 var(--font-sans)',
            textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--ink-3)', borderBottom:'1px solid var(--line)' }}>{d}</div>
        ))}
        {cells.map((n,i) => {
          const valid = n>=1 && n<=31;
          const isToday = n===today;
          const cnt = withAppt[n];
          return (
            <div key={i} style={{ minHeight:92, padding:'8px', borderLeft: i%7 ? '1px solid var(--line-soft)' : 'none',
              borderBottom:'1px solid var(--line-soft)', background: isToday?'var(--wine-50)':'transparent' }}>
              {valid && (
                <>
                  <div className="tnum" style={{ font:`${isToday?500:400} 13px/1 var(--font-sans)`,
                    color: isToday?'var(--wine-fg)':'var(--ink-2)', marginBottom:6,
                    display:'inline-grid', placeItems:'center', width:24, height:24, borderRadius:'50%',
                    background: isToday?'var(--wine)':'transparent' }}>{n}</div>
                  {cnt && (
                    <div style={{ display:'flex', flexWrap:'wrap', gap:3 }}>
                      {Array.from({length:Math.min(cnt,5)}).map((_,k) => (
                        <span key={k} style={{ width:6, height:6, borderRadius:'50%', background:'var(--wine-300)' }}/>
                      ))}
                      {cnt>5 && <span style={{ font:'400 10px/1 var(--font-mono)', color:'var(--ink-3)' }}>+{cnt-5}</span>}
                    </div>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const HUES = ['clay','wine','mustard','steel','sage','plum','teal'];
const memberHue = (id: string) => HUES[id.charCodeAt(0) % HUES.length];

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--line-strong)', background: 'var(--surface-2)',
  font: '400 14px/1.3 var(--font-sans)', color: 'var(--ink-1)', outline: 'none',
};

function NewAppointmentDialog({ open, onClose, initialDate, initialTime }: {
  open: boolean; onClose: () => void;
  initialDate?: string; initialTime?: string;
}) {
  const { workspaceId } = useAuth();
  const { data: customers = [] } = useCustomers();
  const { data: services = [] } = useServices(true);
  const { data: calendars = [] } = useQuery({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });
  const { data: channels = [] } = useQuery({
    queryKey: ['channels', workspaceId],
    queryFn: () => listChannels(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });

  const [customerId, setCustomerId] = useState('');
  const [serviceId, setServiceId] = useState('');
  const [date, setDate] = useState(initialDate ?? format(new Date(), 'yyyy-MM-dd'));
  const [time, setTime] = useState(initialTime ?? '09:00');

  // Sincronizar cuando se abre el modal con nuevos valores iniciales
  useEffect(() => { if (open && initialDate) setDate(initialDate); }, [open, initialDate]);
  useEffect(() => { if (open && initialTime) setTime(initialTime); }, [open, initialTime]);

  const createMutation = useCreateAppointment();
  const activeCalendar = calendars.find(c => c.sync_status === 'active');
  const activeChannel = channels.find(c => c.status === 'active');
  const selectedService = services.find((s: ServiceOut) => s.id === serviceId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customerId || !serviceId || !activeCalendar || !activeChannel) return;
    const start_at = new Date(`${date}T${time}:00`).toISOString();
    await createMutation.mutateAsync({
      customer_id: customerId,
      service_id: serviceId,
      channel_id: activeChannel.id,
      calendar_id: activeCalendar.id,
      start_at,
      price_cop: selectedService?.price_cop ?? 0,
    });
    onClose();
  };

  const labelSt: React.CSSProperties = { font: '500 12px/1 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 6, display: 'block' };
  const blocked = !activeCalendar || !activeChannel;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent style={{ maxWidth: 440 }}>
        <DialogHeader>
          <DialogTitle>Nueva cita</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 4 }}>
          {!activeCalendar && (
            <div style={{ font: '400 12.5px/1.4 var(--font-sans)', color: 'var(--wine)', padding: '8px 12px', borderRadius: 'var(--r-sm)', background: 'var(--wine-50)', border: '1px solid var(--wine-200)' }}>
              Sin calendario activo — conecta Google Calendar en Ajustes
            </div>
          )}
          {!activeChannel && (
            <div style={{ font: '400 12.5px/1.4 var(--font-sans)', color: 'var(--wine)', padding: '8px 12px', borderRadius: 'var(--r-sm)', background: 'var(--wine-50)', border: '1px solid var(--wine-200)' }}>
              Sin canal activo — conecta WhatsApp en Ajustes
            </div>
          )}
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={labelSt}>Cliente</span>
            <select value={customerId} onChange={e => setCustomerId(e.target.value)} required style={inputStyle}>
              <option value="">— Seleccionar —</option>
              {customers.map(c => (
                <option key={c.id} value={c.id}>{c.name ?? c.phone}</option>
              ))}
            </select>
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={labelSt}>Servicio</span>
            <select value={serviceId} onChange={e => setServiceId(e.target.value)} required style={inputStyle}>
              <option value="">— Seleccionar —</option>
              {services.map((s: ServiceOut) => (
                <option key={s.id} value={s.id}>{s.name} · {HILO.fmtCOP(s.price_cop)} · {s.duration_minutes}min</option>
              ))}
            </select>
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={labelSt}>Fecha</span>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} required style={inputStyle} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={labelSt}>Hora</span>
              <input type="time" value={time} onChange={e => setTime(e.target.value)} required style={inputStyle} />
            </label>
          </div>
          <Button variant="primary" size="sm" disabled={createMutation.isPending || blocked} style={{ alignSelf: 'flex-end' }}>
            {createMutation.isPending ? 'Guardando…' : 'Crear cita'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function AgendaPage() {
  const [view, setView] = useState<'day'|'week'|'month'>('week');
  const [newCitaOpen, setNewCitaOpen] = useState(false);
  const [slotDate, setSlotDate] = useState<string | undefined>();
  const [slotTime, setSlotTime] = useState<string | undefined>();

  const handleSlotClick = (date: string, time: string) => {
    setSlotDate(date);
    setSlotTime(time);
    setNewCitaOpen(true);
  };
  const [weekOffset, setWeekOffset] = useState(0);
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 880;

  const weekStart = useMemo(() => {
    const base = startOfWeek(new Date(), { weekStartsOn: 1 });
    return addDays(base, weekOffset * 7);
  }, [weekOffset]);

  const weekEnd = useMemo(() => endOfWeek(weekStart, { weekStartsOn: 1 }), [weekStart]);

  const weekLabel = useMemo(() => {
    const s = format(weekStart, 'd MMM', { locale: es });
    const e = format(weekEnd, 'd MMM', { locale: es });
    return `${s} – ${e}`;
  }, [weekStart, weekEnd]);

  const { data: weekEvents = [], isLoading: weekLoading, isError: weekError } = useWeekAppointments({ weekStart, weekEnd });
  const { data: team = [] } = useTeamMembers();

  useEffect(() => {
    if (weekError) toast.error('No se pudo cargar la agenda semanal.');
  }, [weekError]);

  return (
    <div style={{ maxWidth:1180, margin:'0 auto', padding: isMobile?'16px 14px 28px':'24px 30px 40px',
      animation:'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
      <NewAppointmentDialog open={newCitaOpen} onClose={() => setNewCitaOpen(false)} initialDate={slotDate} initialTime={slotTime} />
      <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap', marginBottom:18 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <Button variant="secondary" size="sm" icon="chevL" style={{ padding:'8px' }} onClick={() => setWeekOffset(o => o - 1)}/>
          <h2 style={{ margin:0, font:'400 22px/1 var(--font-serif)', color:'var(--ink-1)', minWidth:160 }}>{weekLabel}</h2>
          <Button variant="secondary" size="sm" icon="chev" style={{ padding:'8px' }} onClick={() => setWeekOffset(o => o + 1)}/>
          <Button variant="ghost" size="sm" onClick={() => setWeekOffset(0)}>Hoy</Button>
        </div>
        <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:10 }}>
          <Segmented
            options={[{value:'day',label:'Día'},{value:'week',label:'Semana'},{value:'month',label:'Mes'}]}
            value={view}
            onChange={v => setView(v as 'day'|'week'|'month')}
          />
          {!isMobile && <Button variant="secondary" size="sm" icon="block">Bloquear</Button>}
          <Button variant="primary" size="sm" icon="plus" onClick={() => setNewCitaOpen(true)}>{isMobile?'':'Nueva cita'}</Button>
        </div>
      </div>

      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:16, flexWrap:'wrap' }}>
        <span className="eyebrow">Equipo</span>
        {team.map(m => (
          <span key={m.id} style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'4px 11px 4px 5px',
            borderRadius:'var(--r-full)', background:'var(--surface)', border:'1px solid var(--line)', cursor:'pointer' }}>
            <Avatar name={m.name ?? m.email ?? '?'} hue={memberHue(m.id)} size={22}/>
            <span style={{ font:'500 12.5px/1 var(--font-sans)', color:'var(--ink-1)' }}>{(m.name ?? m.email ?? '?').split(' ')[0]}</span>
          </span>
        ))}
      </div>

      {view==='day' && <DayView isLoading={false} />}
      {view==='week' && <WeekView weekStart={weekStart} events={weekEvents} isLoading={weekLoading} onSlotClick={handleSlotClick} />}
      {view==='month' && <MonthView/>}
    </div>
  );
}
