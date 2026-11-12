import { useIsMobile } from '@/hooks/use-is-mobile';
import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Icon } from "@/components/hilo/icons";
import { Button, Avatar } from "@/components/hilo/primitives";
import type { HiloClient } from "@/lib/hilo-data";
import { useCustomers } from "@/hooks/use-customers";
import { ClientDetail } from "@/components/clientes/ClientDetail";
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
      display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
      <div onClick={e => e.stopPropagation()} style={{ background:'var(--surface)', border:'1px solid var(--line)',
        borderRadius:'var(--r-lg)', boxShadow:'var(--shadow-lg)', width:'100%', maxWidth:380, maxHeight:'100%', overflowY:'auto', padding:24 }}>
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
  const isMobile = useIsMobile();

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
