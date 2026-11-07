import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Icon } from "@/components/hilo/icons";
import { Button, Avatar, Tag } from "@/components/hilo/primitives";
import { fmtCOP, hueVar } from "@/lib/hilo-data";
import type { HiloClient } from "@/lib/hilo-data";
import { useCustomers, useUpdateCustomer } from "@/hooks/use-customers";
import { useAppointments } from "@/hooks/use-appointments";
import { useConversations, useMessages } from "@/hooks/use-conversations";
import { createCustomer } from "@/lib/api/conversations";
import { useAuth } from "@/lib/auth-context";

export const Route = createFileRoute("/_authenticated/clients")({
  head: () => ({ meta: [{ title: "Clientes · Hilo" }] }),
  component: ClientsPage,
});

const STATUS_HUE: Record<string, string> = {
  VIP: 'mustard', frecuente: 'wine', activo: 'sage', nuevo: 'steel',
};

function ClientRow({ c, active, onClick }: { c: HiloClient; active: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} style={{
      display:'flex', alignItems:'center', gap:12, padding:'11px 14px', width:'100%', textAlign:'left',
      border:0, borderRadius:'var(--r-md)', cursor:'pointer',
      background: active ? 'var(--surface)' : 'transparent',
      boxShadow: active ? 'var(--shadow-sm)' : 'none',
      transition:'all var(--dur-2) var(--ease-std)',
    }}
    onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'var(--wine-50)'; }}
    onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
      <Avatar name={c.name} hue={STATUS_HUE[c.status] as any} size={38}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <span style={{ font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{c.name}</span>
          {c.status==='VIP' && <Icon name="star" size={12} fill style={{ color:'var(--mustard)' }}/>}
        </div>
        <div style={{ font:'400 12px/1.2 var(--font-sans)', color:'var(--ink-3)', marginTop:2 }}>
          {c.next!=='—' ? `Próx: ${c.next}` : `Última: ${c.last}`}
        </div>
      </div>
      <span className="tnum" style={{ font:'400 11px/1 var(--font-mono)', color:'var(--ink-4)' }}>{c.visits}</span>
    </button>
  );
}

function StatBox({ k, v, hue }: { k: string; v: string; hue?: string }) {
  return (
    <div style={{ flex:1, padding:'12px 14px', background:'var(--surface)', border:'1px solid var(--line)', borderRadius:'var(--r-md)' }}>
      <div className="tnum" style={{ font:'500 20px/1 var(--font-sans)', color: hue||'var(--ink-1)' }}>{v}</div>
      <div style={{ font:'400 11.5px/1 var(--font-sans)', color:'var(--ink-3)', marginTop:5 }}>{k}</div>
    </div>
  );
}

function ClientDetail({ c, isMobile, onBack }: { c: HiloClient; isMobile: boolean; onBack: () => void }) {
  const [note, setNote] = useState(c.note);
  const [noteSaved, setNoteSaved] = useState(true);
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(c.name);
  const [botOn, setBotOn] = useState(c.agent_enabled);
  const updateCustomer = useUpdateCustomer(c.id);

  const handleNoteSave = () => {
    updateCustomer.mutate({ notes: note }, { onSuccess: () => setNoteSaved(true) });
  };
  const handleNameSave = () => {
    if (!name.trim()) return;
    updateCustomer.mutate({ name: name.trim() }, { onSuccess: () => setEditingName(false) });
  };

  const { data: allApts = [] } = useAppointments();
  const history = allApts
    .filter(a => a.customerId === c.id)
    .sort((a, b) => (b.startAt ?? '').localeCompare(a.startAt ?? ''))
    .slice(0, 8);

  const { data: convs = [] } = useConversations();
  const conv = convs.find(cv => cv.customer_id === c.id);
  const { data: messages = [] } = useMessages(conv?.id ?? '');
  const lastMsgs = [...messages]
    .sort((a, b) => (a.sent_at ?? a.received_at ?? a.created_at).localeCompare(b.sent_at ?? b.received_at ?? b.created_at))
    .slice(-5);

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflowY:'auto' }}>
      <div style={{ padding:'20px 22px', borderBottom:'1px solid var(--line)', display:'flex', alignItems:'center', gap:14 }}>
        {isMobile && <Button variant="ghost" size="sm" icon="chevL" onClick={onBack} style={{ padding:'7px' }}/>}
        <Avatar name={name} hue={STATUS_HUE[c.status] as any} size={52}/>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:9 }}>
            {editingName ? (
              <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                <input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  autoFocus
                  onKeyDown={e => { if (e.key==='Enter') handleNameSave(); if (e.key==='Escape') setEditingName(false); }}
                  style={{ font:'500 18px/1.1 var(--font-sans)', color:'var(--ink-1)', border:'1px solid var(--wine)', borderRadius:'var(--r-sm)', padding:'3px 8px', outline:'none', background:'var(--surface)' }}
                />
                <Button variant="primary" size="sm" onClick={handleNameSave} disabled={updateCustomer.isPending}>Ok</Button>
                <Button variant="ghost" size="sm" onClick={() => { setEditingName(false); setName(c.name); }}>×</Button>
              </div>
            ) : (
              <button onClick={() => setEditingName(true)} style={{ background:'none', border:'none', cursor:'pointer', padding:0, display:'flex', alignItems:'center', gap:6 }}>
                <h2 style={{ margin:0, font:'500 21px/1.1 var(--font-sans)', color:'var(--ink-1)' }}>{name}</h2>
                <Icon name="edit" size={13} style={{ color:'var(--ink-4)' }}/>
              </button>
            )}
            <Tag hue={STATUS_HUE[c.status]} style={{ fontSize:11 }}>{c.status}</Tag>
          </div>
          <div className="tnum" style={{ font:'400 13px/1 var(--font-sans)', color:'var(--ink-3)', marginTop:5 }}>{c.phone}</div>
        </div>
        <Button variant="secondary" size="sm" icon="whatsapp" style={{ color:'var(--wa-ink)' }}>
          {!isMobile && 'Escribir'}
        </Button>
      </div>

      <div style={{ padding:'20px 22px', display:'flex', flexDirection:'column', gap:20 }}>
        <div style={{ display:'flex', gap:10 }}>
          <StatBox k="Visitas" v={String(c.visits)}/>
          <StatBox k="Gasto total" v={fmtCOP(c.spend)} hue="var(--clay)"/>
          <StatBox k="Próxima" v={c.next==='—'?'—':c.next.replace('Hoy · ','')} hue="var(--wine)"/>
        </div>

        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'12px 14px',
          background:'var(--surface)', border:'1px solid var(--line)', borderRadius:'var(--r-md)' }}>
          <div>
            <div style={{ font:'500 13.5px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>Bot activo</div>
            <div style={{ font:'400 12px/1.3 var(--font-sans)', color:'var(--ink-3)', marginTop:3 }}>
              El agente responde automáticamente a este cliente
            </div>
          </div>
          <button
            type="button"
            onClick={() => { const next = !botOn; setBotOn(next); updateCustomer.mutate({ agent_enabled: next }); }}
            style={{ width:44, height:26, borderRadius:13, border:0, cursor:'pointer',
              background: botOn ? 'var(--wine)' : 'var(--line-strong)',
              transition:'background var(--dur-2) var(--ease-std)', position:'relative', flexShrink:0 }}>
            <span style={{ position:'absolute', top:3, left: botOn ? 21 : 3, width:20, height:20,
              borderRadius:'50%', background:'white',
              transition:'left var(--dur-2) var(--ease-std)',
              boxShadow:'0 1px 4px rgba(0,0,0,0.2)' }}/>
          </button>
        </div>

        <div>
          <div className="eyebrow" style={{ marginBottom:8 }}>Nota interna</div>
          <textarea
            value={note}
            onChange={e => { setNote(e.target.value); setNoteSaved(false); }}
            placeholder="Preferencias, alergias, recordatorios…"
            style={{ width:'100%', minHeight:60, padding:'11px 13px', borderRadius:'var(--r-md)', resize:'vertical',
              border:'1px solid var(--line)', background:'var(--surface-tint)', color:'var(--ink-1)',
              font:'400 13.5px/1.5 var(--font-sans)', outline:'none' }}/>
          {!noteSaved && (
            <Button variant="primary" size="sm" style={{ marginTop:8 }} onClick={handleNoteSave} disabled={updateCustomer.isPending}>
              {updateCustomer.isPending ? 'Guardando…' : 'Guardar nota'}
            </Button>
          )}
        </div>

        <div>
          <div className="eyebrow" style={{ marginBottom:10 }}>Historial de citas</div>
          {history.length === 0 ? (
            <div style={{ font:'400 13px/1.4 var(--font-sans)', color:'var(--ink-4)' }}>Sin citas registradas.</div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column' }}>
              {history.map((h, i) => {
                const SVC_HUES = ['wine','clay','mustard','steel','sage','plum'];
                const hue = hueVar(SVC_HUES[history.indexOf(h) % SVC_HUES.length] ?? 'wine');
                const dateLabel = h.startAt ? format(parseISO(h.startAt), "d MMM · HH:mm", { locale: es }) : h.time;
                return (
                  <div key={h.id} style={{ display:'grid', gridTemplateColumns:'18px 1fr', gap:12 }}>
                    <div style={{ position:'relative', display:'flex', justifyContent:'center' }}>
                      {i < history.length-1 && <span style={{ position:'absolute', top:12, bottom:-8, width:2, background:'var(--line)' }}/>}
                      <span style={{ marginTop:6, width:9, height:9, borderRadius:'50%', background:hue, zIndex:1, flexShrink:0 }}/>
                    </div>
                    <div style={{ paddingBottom:14 }}>
                      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                        <span style={{ font:'500 13.5px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{h.svc}</span>
                        <Icon name="whatsapp" size={13} style={{ color:'var(--wa-ink)' }}/>
                      </div>
                      <div className="tnum" style={{ font:'400 12px/1.3 var(--font-sans)', color:'var(--ink-3)', marginTop:2 }}>{dateLabel}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {conv && (
          <div>
            <div className="eyebrow" style={{ marginBottom:10 }}>Últimos mensajes</div>
            <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
              {lastMsgs.length === 0 ? (
                <div style={{ font:'400 13px/1.4 var(--font-sans)', color:'var(--ink-4)' }}>Sin mensajes aún.</div>
              ) : lastMsgs.map(m => {
                const isAgent = m.direction === 'outbound';
                return (
                  <div key={m.id} style={{ alignSelf: isAgent ? 'flex-end' : 'flex-start', maxWidth:'85%',
                    padding:'8px 12px', borderRadius: isAgent ? '13px 13px 4px 13px' : '13px 13px 13px 4px',
                    background: isAgent ? 'var(--wine)' : 'var(--surface-2)',
                    color: isAgent ? 'var(--wine-fg)' : 'var(--ink-1)',
                    border: isAgent ? '0' : '1px solid var(--line)',
                    font:'400 13px/1.4 var(--font-sans)' }}>
                    {m.content ?? '[media]'}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

type ClientWithOpen = HiloClient & { __open?: boolean };

function ClientsListSkeleton() {
  return (
    <div style={{ padding:'0 10px 16px', display:'flex', flexDirection:'column', gap:2 }}>
      {[1,2,3,4,5].map(i => (
        <div key={i} style={{ display:'flex', alignItems:'center', gap:12, padding:'11px 14px' }}>
          <div style={{ width:38, height:38, borderRadius:'50%', background:'var(--line)', flexShrink:0 }}/>
          <div style={{ flex:1, display:'flex', flexDirection:'column', gap:6 }}>
            <div style={{ height:14, width:'60%', background:'var(--line)', borderRadius:4 }}/>
            <div style={{ height:11, width:'40%', background:'var(--line)', borderRadius:4 }}/>
          </div>
        </div>
      ))}
    </div>
  );
}

function NewClientModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  const [phone, setPhone] = useState('');
  const [name, setName]   = useState('');

  const mut = useMutation({
    mutationFn: () => createCustomer(workspaceId!, { phone: phone.trim(), name: name.trim() }),
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ['customers', workspaceId] });
      toast.success('Cliente creado');
      onCreated(c.id);
    },
    onError: () => toast.error('Error al crear el cliente'),
  });

  return (
    <div onClick={onClose} style={{ position:'fixed', inset:0, zIndex:200, background:'rgba(0,0,0,0.5)',
      display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div onClick={e => e.stopPropagation()} style={{ background:'var(--surface)', border:'1px solid var(--line)',
        borderRadius:'var(--r-lg)', boxShadow:'var(--shadow-lg)', width:'100%', maxWidth:380, padding:24 }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:20 }}>
          <h3 style={{ margin:0, font:'500 16px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>Nuevo cliente</h3>
          <button onClick={onClose} style={{ background:'none', border:'none', cursor:'pointer', color:'var(--ink-3)', fontSize:14 }}>✕</button>
        </div>
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          <label style={{ display:'flex', flexDirection:'column', gap:5 }}>
            <span style={{ font:'500 12px/1 var(--font-sans)', color:'var(--ink-2)' }}>Teléfono <span style={{ color:'var(--wine)' }}>*</span></span>
            <input
              value={phone}
              onChange={e => setPhone(e.target.value)}
              placeholder="+57 300 000 0000"
              autoFocus
              style={{ padding:'9px 11px', borderRadius:'var(--r-sm)', border:'1px solid var(--line-strong)',
                background:'var(--surface-2)', font:'400 14px/1 var(--font-sans)', color:'var(--ink-1)', outline:'none' }}
              onFocus={e => (e.target.style.borderColor = 'var(--wine)')}
              onBlur={e => (e.target.style.borderColor = 'var(--line-strong)')}
            />
          </label>
          <label style={{ display:'flex', flexDirection:'column', gap:5 }}>
            <span style={{ font:'500 12px/1 var(--font-sans)', color:'var(--ink-2)' }}>Nombre <span style={{ color:'var(--wine)' }}>*</span></span>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Juan García"
              onKeyDown={e => { if (e.key === 'Enter' && phone.trim() && name.trim()) mut.mutate(); }}
              style={{ padding:'9px 11px', borderRadius:'var(--r-sm)', border:'1px solid var(--line-strong)',
                background:'var(--surface-2)', font:'400 14px/1 var(--font-sans)', color:'var(--ink-1)', outline:'none' }}
              onFocus={e => (e.target.style.borderColor = 'var(--wine)')}
              onBlur={e => (e.target.style.borderColor = 'var(--line-strong)')}
            />
          </label>
          <div style={{ display:'flex', justifyContent:'flex-end', gap:8, paddingTop:4, borderTop:'1px solid var(--line)', marginTop:4 }}>
            <Button variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Button>
            <Button
              variant="primary" size="sm"
              disabled={!phone.trim() || !name.trim() || mut.isPending}
              onClick={() => mut.mutate()}
            >
              {mut.isPending ? 'Guardando…' : 'Crear cliente'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ClientsPage() {
  const { workspaceId } = useAuth();
  const [sel, setSel]       = useState<ClientWithOpen | null>(null);
  const [q, setQ]           = useState('');
  const [showNew, setShowNew] = useState(false);
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 880;

  const { data: clients = [], isLoading, isError } = useCustomers();
  const list = clients.filter(c =>
    c.name.toLowerCase().includes(q.toLowerCase()) || c.phone.includes(q),
  );

  useEffect(() => {
    if (isError) toast.error('No se pudieron cargar los clientes.');
  }, [isError]);
  const showDetail = !isMobile || (sel as ClientWithOpen | null)?.__open;

  if (!sel && clients.length > 0 && !isMobile) setSel(clients[0]);

  const ListPane = (
    <div style={{ width:isMobile?'100%':338, flexShrink:0, borderRight: isMobile?'none':'1px solid var(--line)',
      display:'flex', flexDirection:'column', height:'100%', background:'var(--paper)' }}>
      <div style={{ padding:'18px 16px 12px' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:14 }}>
          <h2 style={{ margin:0, font:'400 24px/1 var(--font-serif)', color:'var(--ink-1)' }}>Clientes</h2>
          <Button variant="secondary" size="sm" icon="plus" onClick={() => setShowNew(true)}>Nuevo</Button>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:9, padding:'9px 12px', background:'var(--surface-2)',
          border:'1px solid var(--line-strong)', borderRadius:'var(--r-md)' }}>
          <Icon name="search" size={15} style={{ color:'var(--ink-3)' }}/>
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Buscar nombre o teléfono…"
            style={{ flex:1, border:0, background:'transparent', outline:'none', font:'400 13.5px/1 var(--font-sans)', color:'var(--ink-1)' }}/>
        </div>
      </div>
      <div style={{ flex:1, overflowY:'auto', display:'flex', flexDirection:'column' }}>
        {isLoading ? (
          <ClientsListSkeleton />
        ) : (
          <div style={{ padding:'0 10px 16px', display:'flex', flexDirection:'column', gap:2 }}>
            {list.map(c => (
              <ClientRow key={c.id} c={c} active={!isMobile && sel?.id===c.id}
                onClick={() => setSel(isMobile ? {...c, __open:true} : c)}/>
            ))}
            {!list.length && !isLoading && (
              <div style={{ padding:'40px 16px', textAlign:'center', color:'var(--ink-3)', font:'400 13px/1.4 var(--font-sans)' }}>
                {q ? `Sin resultados para "${q}".` : 'Sin clientes registrados aún.'}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      <div style={{ height:'100%', display:'flex', animation:'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
        {(!isMobile || !showDetail) && ListPane}
        {(!isMobile || showDetail) && (
          <div style={{ flex:1, minWidth:0, height:'100%' }}>
            {sel
              ? <ClientDetail c={sel} isMobile={isMobile} onBack={() => setSel({...sel, __open:false})}/>
              : <div style={{ display:'grid', placeItems:'center', height:'100%', color:'var(--ink-3)' }}>Selecciona un cliente</div>
            }
          </div>
        )}
      </div>
      {showNew && (
        <NewClientModal
          onClose={() => setShowNew(false)}
          onCreated={(id) => {
            setShowNew(false);
            // Seleccionar el nuevo cliente tras refresh
            const found = clients.find(c => c.id === id);
            if (found) setSel(isMobile ? {...found, __open:true} : found);
          }}
        />
      )}
    </>
  );
}
