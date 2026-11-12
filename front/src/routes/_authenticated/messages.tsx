import { useIsMobile } from '@/hooks/use-is-mobile';
import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { formatDistanceToNow, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import { Icon } from "@/components/hilo/icons";
import { Avatar, Button, Dot, Tag } from "@/components/hilo/primitives";
import { fmtCOP } from "@/lib/hilo-data";
import { useConversations, useMessages } from "@/hooks/use-conversations";
import { useCustomers } from "@/hooks/use-customers";
import { MessageComposer } from "@/components/mensajes/MessageComposer";
import type { ConversationOut, MessageOut } from "@/lib/types/api";
import type { HiloClient } from "@/lib/hilo-data";

export const Route = createFileRoute("/_authenticated/messages")({
  head: () => ({ meta: [{ title: "Mensajes · Hilo" }] }),
  component: MessagesPage,
});

const STATUS_HUE: Record<string, string> = {
  VIP: 'mustard', frecuente: 'wine', activo: 'sage', nuevo: 'steel',
};

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try { return formatDistanceToNow(parseISO(iso), { locale: es, addSuffix: true }); }
  catch { return '—'; }
}

interface ConvRow { conv: ConversationOut; client: HiloClient | undefined; }

// ── Fila de conversación ───────────────────────────────────────────────────

function ConversationItem({ row, active, onClick }: { row: ConvRow; active: boolean; onClick: () => void }) {
  const { conv, client } = row;
  const name   = client?.name ?? conv.customer_id.slice(0, 8);
  const time   = relativeTime(conv.last_message_at);
  const intent = conv.current_intent ?? conv.status;

  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 11, padding: '12px 14px',
        width: '100%', textAlign: 'left', border: 0, borderRadius: 0, cursor: 'pointer',
        background: active ? 'var(--wine-50)' : 'transparent',
        borderBottom: '1px solid var(--line)',
        transition: 'background var(--dur-2)',
      }}
      onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'var(--surface-tint)'; }}
      onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
    >
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <Avatar name={name} hue={client ? (STATUS_HUE[client.status] as any) : 'wine'} size={40} />
        {conv.needs_review && (
          <span style={{ position: 'absolute', top: 0, right: 0, width: 10, height: 10, borderRadius: '50%',
            background: 'var(--wine)', border: '2px solid var(--paper)' }} />
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Fila nombre + tiempo */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ font: '500 13.5px/1.2 var(--font-sans)', color: 'var(--ink-1)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {name}
          </span>
          <span style={{ font: '400 10.5px/1 var(--font-mono)', color: 'var(--ink-4)', flexShrink: 0 }}>{time}</span>
        </div>

        {/* Intent o teléfono */}
        {intent && (
          <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2,
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {intent}
          </div>
        )}

        {/* Tokens: último servicio · visitas · estado */}
        {client && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 6, flexWrap: 'wrap' }}>
            {client.fav && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4,
                padding: '2px 7px', borderRadius: 'var(--r-full)',
                background: 'var(--surface-2)', border: '1px solid var(--line)',
                font: '400 11px/1 var(--font-sans)', color: 'var(--ink-2)', whiteSpace: 'nowrap' }}>
                <Icon name="scissors" size={10} />
                {client.fav}
              </span>
            )}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '2px 7px', borderRadius: 'var(--r-full)',
              background: 'var(--surface-2)', border: '1px solid var(--line)',
              font: '400 11px/1 var(--font-mono)', color: 'var(--ink-3)', whiteSpace: 'nowrap' }}>
              {client.visits} cita{client.visits !== 1 ? 's' : ''}
            </span>
            {client.status === 'VIP' && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3,
                padding: '2px 7px', borderRadius: 'var(--r-full)',
                background: 'color-mix(in srgb, var(--mustard) 15%, var(--surface))',
                border: '1px solid color-mix(in srgb, var(--mustard) 30%, transparent)',
                font: '500 10.5px/1 var(--font-sans)', color: 'var(--mustard)' }}>
                <Icon name="star" size={10} />VIP
              </span>
            )}
          </div>
        )}
      </div>
    </button>
  );
}

// ── Burbuja de mensaje ─────────────────────────────────────────────────────

// Quién envió cada mensaje saliente y por dónde: icono + etiqueta al pie de la burbuja.
function messageOrigin(msg: MessageOut): { icon: string; label: string } | null {
  if (msg.direction !== 'outbound') return null;
  if (msg.sender_type === 'agent') return { icon: 'sparkle', label: 'Agente' };
  if (msg.sender_type === 'system') return { icon: 'bolt', label: 'Automático' };
  if (msg.sent_via === 'business_app') return { icon: 'phone', label: 'Desde el celular' };
  if (msg.sent_via === 'hilo') return { icon: 'thread', label: 'Desde Hilo' };
  return null;
}

function MessageBubble({ msg }: { msg: MessageOut }) {
  const isAgent = msg.direction === 'outbound';
  const time = msg.sent_at ?? msg.received_at ?? msg.created_at;
  const origin = messageOrigin(msg);
  return (
    <div style={{ alignSelf: isAgent ? 'flex-end' : 'flex-start', maxWidth: '85%',
      padding: '8px 12px',
      borderRadius: isAgent ? '13px 13px 4px 13px' : '13px 13px 13px 4px',
      background: isAgent ? 'var(--wine)' : 'var(--surface-2)',
      color: isAgent ? 'var(--wine-fg)' : 'var(--ink-1)',
      border: isAgent ? '0' : '1px solid var(--line)',
      font: '400 13px/1.4 var(--font-sans)',
    }}>
      {msg.content ?? '[media]'}
      {time && (
        <div style={{ font: '400 10px/1 var(--font-mono)', marginTop: 4,
          color: isAgent ? 'rgba(255,255,255,0.55)' : 'var(--ink-4)',
          textAlign: 'right' }}>
          {relativeTime(time)}
          {origin && (
            <span className="chat-origin" title={origin.label}>
              <Icon name={origin.icon} size={11} />{origin.label}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Detalle de conversación ────────────────────────────────────────────────

function ConversationDetail({ conv, client, onBack }: {
  conv: ConversationOut;
  client: HiloClient | undefined;
  /** Solo en móvil: vuelve a la lista de conversaciones. */
  onBack?: () => void;
}) {
  const { data: messages = [], isLoading } = useMessages(conv.id);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const name = client?.name ?? conv.customer_id.slice(0, 8);
  const phone = client?.phone ?? '';
  const sorted = [...messages].sort(
    (a, b) => (a.sent_at ?? a.received_at ?? a.created_at).localeCompare(b.sent_at ?? b.received_at ?? b.created_at),
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Header con info del cliente */}
      <div className="chat-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: client ? 12 : 0 }}>
          {onBack && (
            <Button variant="ghost" size="sm" icon="chevL" aria-label="Volver a conversaciones" onClick={onBack} className="chat-back" />
          )}
          <Avatar name={name} hue={client ? (STATUS_HUE[client.status] as any) : 'wine'} size={38} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ font: '500 15px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{name}</span>
              {client?.status && (
                <Tag hue={STATUS_HUE[client.status] as any} style={{ fontSize: 11 }}>{client.status}</Tag>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 3 }}>
              <Dot color="var(--wa)" size={6} />
              <span style={{ font: '400 11.5px/1 var(--font-sans)', color: 'var(--ink-3)' }}>WhatsApp</span>
              {phone && <span style={{ font: '400 11px/1 var(--font-mono)', color: 'var(--ink-4)' }}>{phone}</span>}
              {conv.needs_review && (
                <Tag hue="wine" style={{ fontSize: 10.5 }}>Necesita revisión</Tag>
              )}
            </div>
          </div>
        </div>

        {/* Stat tokens */}
        {client && (
          <div className="chat-head__chips">
            <StatChip icon="calendar" label={`${client.visits} cita${client.visits !== 1 ? 's' : ''}`} />
            {client.spend > 0 && <StatChip icon="money" label={fmtCOP(client.spend)} />}
            {client.fav && <StatChip icon="scissors" label={client.fav} accent />}
            {client.last && client.last !== '—' && (
              <StatChip icon="clock" label={`Última: ${client.last}`} />
            )}
            {client.next && client.next !== '—' && (
              <StatChip icon="sparkle" label={`Próx: ${client.next}`} accent />
            )}
            {conv.current_intent && (
              <StatChip icon="thread" label={conv.current_intent} />
            )}
          </div>
        )}
      </div>

      {/* Mensajes */}
      <div className="chat-scroll">
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{ alignSelf: i % 2 === 0 ? 'flex-end' : 'flex-start',
                width: '45%', height: 40, background: 'var(--line)', borderRadius: 12 }} />
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--ink-3)', font: '400 13px/1.4 var(--font-sans)', padding: 32 }}>
            Sin mensajes aún
          </div>
        ) : (
          sorted.map(msg => <MessageBubble key={msg.id} msg={msg} />)
        )}
        <div ref={bottomRef} />
      </div>

      <MessageComposer conv={conv} />
    </div>
  );
}

// ── Chip stat reutilizable ─────────────────────────────────────────────────

function StatChip({ icon, label, accent }: { icon: string; label: string; accent?: boolean }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 9px',
      borderRadius: 'var(--r-full)',
      background: accent ? 'var(--wine-50)' : 'var(--surface-2)',
      border: `1px solid ${accent ? 'color-mix(in srgb, var(--wine) 25%, transparent)' : 'var(--line)'}`,
      font: '400 11.5px/1 var(--font-sans)',
      color: accent ? 'var(--wine)' : 'var(--ink-2)',
      whiteSpace: 'nowrap',
    }}>
      <Icon name={icon} size={11} />
      {label}
    </span>
  );
}

function EmptyConversation() {
  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}>
      <div style={{ textAlign: 'center', maxWidth: 280 }}>
        <span style={{ width: 48, height: 48, borderRadius: 'var(--r-md)', background: 'var(--wine-50)',
          display: 'grid', placeItems: 'center', margin: '0 auto 12px', color: 'var(--wine)' }}>
          <Icon name="chat" size={24} />
        </span>
        <div style={{ font: '400 14px/1.5 var(--font-sans)', color: 'var(--ink-3)' }}>
          Selecciona una conversación para ver los mensajes
        </div>
      </div>
    </div>
  );
}

// ── Página principal ───────────────────────────────────────────────────────

function MessagesPage() {
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const isMobile = useIsMobile();

  const { data: conversations = [], isLoading: convsLoading, isError: convsError } = useConversations();
  const { data: clients = [] } = useCustomers();

  useEffect(() => {
    if (convsError) toast.error('No se pudieron cargar las conversaciones.');
  }, [convsError]);

  const clientMap = new Map<string, HiloClient>(clients.map(c => [c.id, c]));

  const rows: ConvRow[] = [...conversations]
    .sort((a, b) => (b.last_message_at ?? '').localeCompare(a.last_message_at ?? ''))
    .map(conv => ({ conv, client: clientMap.get(conv.customer_id) }));

  const selectedRow = rows.find(r => r.conv.id === selectedConvId);
  const showDetail = !isMobile || !!selectedConvId;

  return (
    <div style={{ height: '100%', display: 'flex', animation: 'hilo-fade-up var(--dur-3) var(--ease-out)' }}>

      {/* Lista */}
      {(!isMobile || !showDetail) && (
        <div style={{ width: isMobile ? '100%' : 320, flexShrink: 0, display: 'flex', flexDirection: 'column',
          borderRight: '1px solid var(--line)', background: 'var(--paper)', height: '100%' }}>
          <div style={{ padding: '18px 16px 14px', borderBottom: '1px solid var(--line)' }}>
            <h2 style={{ margin: 0, font: '400 24px/1 var(--font-serif)', color: 'var(--ink-1)' }}>Conversaciones</h2>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {convsLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {[1, 2, 3, 4].map(i => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', borderBottom: '1px solid var(--line)' }}>
                    <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--line)', flexShrink: 0 }} />
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ height: 13, width: '55%', background: 'var(--line)', borderRadius: 4 }} />
                      <div style={{ height: 10, width: '35%', background: 'var(--line)', borderRadius: 4 }} />
                    </div>
                  </div>
                ))}
              </div>
            ) : rows.length === 0 ? (
              <div style={{ padding: '40px 16px', textAlign: 'center', color: 'var(--ink-3)', font: '400 13px/1.4 var(--font-sans)' }}>
                Sin conversaciones aún
              </div>
            ) : (
              rows.map(row => (
                <ConversationItem
                  key={row.conv.id}
                  row={row}
                  active={selectedConvId === row.conv.id}
                  onClick={() => setSelectedConvId(row.conv.id)}
                />
              ))
            )}
          </div>
        </div>
      )}

      {/* Detalle */}
      {(!isMobile || showDetail) && (
        <div style={{ flex: 1, minWidth: 0, height: '100%' }}>
          {selectedRow ? (
            <ConversationDetail
              conv={selectedRow.conv}
              client={selectedRow.client}
              onBack={isMobile ? () => setSelectedConvId(null) : undefined}
            />
          ) : (
            <EmptyConversation />
          )}
        </div>
      )}
    </div>
  );
}
