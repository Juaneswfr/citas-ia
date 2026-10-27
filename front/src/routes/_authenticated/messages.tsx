import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { formatDistanceToNow, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import { Icon } from "@/components/hilo/icons";
import { Avatar, Dot } from "@/components/hilo/primitives";
import { useConversations, useMessages } from "@/hooks/use-conversations";
import { useCustomers } from "@/hooks/use-customers";
import type { ConversationOut, MessageOut } from "@/lib/types/api";
import type { HiloClient } from "@/lib/hilo-data";

export const Route = createFileRoute("/_authenticated/messages")({
  head: () => ({ meta: [{ title: "Mensajes · Hilo" }] }),
  component: MessagesPage,
});

function relativeTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return formatDistanceToNow(parseISO(iso), { locale: es, addSuffix: true });
  } catch {
    return '—';
  }
}

interface ConvRow {
  conv: ConversationOut;
  client: HiloClient | undefined;
}

function ConversationItem({
  row,
  active,
  onClick,
}: {
  row: ConvRow;
  active: boolean;
  onClick: () => void;
}) {
  const name = row.client?.name ?? row.conv.customer_id;
  const time = relativeTime(row.conv.last_message_at);
  const intent = row.conv.current_intent ?? row.conv.status;

  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px',
        width: '100%', textAlign: 'left', border: 0, borderRadius: 0, cursor: 'pointer',
        background: active ? 'var(--wine-50)' : 'transparent',
        borderBottom: '1px solid var(--line)',
        transition: 'background var(--dur-2)',
      }}
      onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'var(--surface-tint)'; }}
      onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
    >
      <Avatar name={name} hue="wine" size={40} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {name}
          </span>
          <span style={{ font: '400 11px/1 var(--font-mono)', color: 'var(--ink-4)', flexShrink: 0, marginLeft: 8 }}>{time}</span>
        </div>
        <div style={{ font: '400 12.5px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {intent}
        </div>
      </div>
      {row.conv.needs_review && (
        <Dot color="var(--wine)" size={8} />
      )}
    </button>
  );
}

function MessageBubble({ msg }: { msg: MessageOut }) {
  const isAgent = msg.sender_type === 'agent' || msg.direction === 'outbound';
  const text = msg.content ?? '[media]';
  const time = msg.sent_at ?? msg.received_at ?? msg.created_at;

  return (
    <div style={{ alignSelf: isAgent ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
      <div style={{
        padding: '9px 13px',
        borderRadius: isAgent ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
        background: isAgent ? 'var(--wine)' : 'var(--surface-2)',
        color: isAgent ? 'var(--wine-fg)' : 'var(--ink-1)',
        border: isAgent ? 'none' : '1px solid var(--line)',
        font: '400 13px/1.4 var(--font-sans)',
        boxShadow: 'var(--shadow-sm)',
      }}>
        {text}
      </div>
      {time && (
        <div style={{
          font: '400 10px/1 var(--font-mono)', color: 'var(--ink-4)', marginTop: 3,
          textAlign: isAgent ? 'right' : 'left',
        }}>
          {relativeTime(time)}{isAgent ? ' · agente' : ''}
        </div>
      )}
    </div>
  );
}

function EmptyConversation() {
  return (
    <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: 'var(--ink-3)' }}>
      <div style={{ textAlign: 'center', maxWidth: 280 }}>
        <span style={{ width: 48, height: 48, borderRadius: 'var(--r-md)', background: 'var(--wine-50)', display: 'grid', placeItems: 'center', margin: '0 auto 12px', color: 'var(--wine)' }}>
          <Icon name="chat" size={24} />
        </span>
        <div style={{ font: '400 14px/1.5 var(--font-sans)', color: 'var(--ink-3)' }}>
          Selecciona una conversación para ver los mensajes
        </div>
      </div>
    </div>
  );
}

function ConversationDetail({ convId, clientName }: { convId: string; clientName: string }) {
  const { data: messages = [], isLoading } = useMessages(convId);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 12 }}>
        <Avatar name={clientName} hue="wine" size={36} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '500 15px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{clientName}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
            <Dot color="var(--wa)" size={6} />
            <span style={{ font: '400 11.5px/1 var(--font-sans)', color: 'var(--ink-3)' }}>WhatsApp</span>
          </div>
        </div>
      </div>

      <div style={{
        flex: 1, overflowY: 'auto', padding: '16px 20px',
        display: 'flex', flexDirection: 'column', gap: 10,
        background: 'var(--surface-tint)',
      }}>
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[1, 2, 3].map(i => (
              <div key={i} style={{ alignSelf: i % 2 === 0 ? 'flex-end' : 'flex-start', width: '50%', height: 40, background: 'var(--line)', borderRadius: 12 }} />
            ))}
          </div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--ink-3)', font: '400 13px/1.4 var(--font-sans)', padding: 24 }}>
            Sin mensajes
          </div>
        ) : (
          messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)
        )}
      </div>
    </div>
  );
}

function MessagesPage() {
  const [selectedConvId, setSelectedConvId] = useState<string | null>(null);
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 880;

  const { data: conversations = [], isLoading: convsLoading, isError: convsError } = useConversations();
  const { data: clients = [] } = useCustomers();

  useEffect(() => {
    if (convsError) toast.error('No se pudieron cargar las conversaciones.');
  }, [convsError]);

  const clientMap = new Map<string, HiloClient>(clients.map(c => [c.id, c]));

  const rows: ConvRow[] = conversations.map(conv => ({
    conv,
    client: clientMap.get(conv.customer_id),
  }));

  const selectedRow = rows.find(r => r.conv.id === selectedConvId);
  const selectedClientName = selectedRow?.client?.name ?? selectedRow?.conv.customer_id ?? '';

  const showDetail = !isMobile || !!selectedConvId;

  return (
    <div style={{ height: '100%', display: 'flex', animation: 'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
      {/* Lista de conversaciones */}
      {(!isMobile || !showDetail) && (
        <div style={{ width: isMobile ? '100%' : 340, flexShrink: 0, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--line)', background: 'var(--paper)', height: '100%' }}>
          <div style={{ padding: '18px 16px 12px', borderBottom: '1px solid var(--line)' }}>
            <h2 style={{ margin: 0, font: '400 24px/1 var(--font-serif)', color: 'var(--ink-1)' }}>Conversaciones</h2>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {convsLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {[1, 2, 3, 4].map(i => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', borderBottom: '1px solid var(--line)' }}>
                    <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--line)', flexShrink: 0 }} />
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ height: 14, width: '55%', background: 'var(--line)', borderRadius: 4 }} />
                      <div style={{ height: 11, width: '35%', background: 'var(--line)', borderRadius: 4 }} />
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

      {/* Detalle de conversación */}
      {(!isMobile || showDetail) && (
        <div style={{ flex: 1, minWidth: 0, height: '100%' }}>
          {selectedConvId ? (
            <ConversationDetail convId={selectedConvId} clientName={selectedClientName} />
          ) : (
            <EmptyConversation />
          )}
        </div>
      )}
    </div>
  );
}
