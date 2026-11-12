import { useEffect, useState } from "react";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Icon } from "@/components/hilo/icons";
import { Button } from "@/components/hilo/primitives";
import { replyWindowEnd, useSendMessage } from "@/hooks/use-conversations";
import type { ConversationOut } from "@/lib/types/api";

/** Caja para responder al cliente. WhatsApp solo deja escribir texto libre 24 h después de su último mensaje. */
export function MessageComposer({ conv }: { conv: ConversationOut }) {
  const [text, setText] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const send = useSendMessage(conv.id);

  // La ventana se puede cerrar con el chat abierto: se revisa cada minuto.
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => setText(""), [conv.id]);

  const windowEnd = replyWindowEnd(conv);
  const open = !!windowEnd && windowEnd.getTime() > now;

  if (!open) {
    return (
      <div className="chat-composer chat-composer--closed" role="status">
        <Icon name="clock" size={15} />
        <span>
          {windowEnd
            ? "Pasaron más de 24 horas desde el último mensaje del cliente. WhatsApp no permite responder hasta que vuelva a escribir."
            : "El cliente aún no ha escrito por este número. WhatsApp solo permite responder después de que escriba."}
        </span>
      </div>
    );
  }

  const body = text.trim();
  const submit = () => {
    if (!body || send.isPending) return;
    send.mutate(body, { onSuccess: () => setText("") });
  };

  return (
    <form className="chat-composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      <div className="chat-composer__row">
        <textarea
          className="chat-composer__input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
          }}
          placeholder="Escribe una respuesta…"
          aria-label="Respuesta al cliente"
          rows={1}
          maxLength={4096}
        />
        <Button type="submit" icon="arrowUp" disabled={!body || send.isPending}>
          {send.isPending ? "Enviando…" : "Enviar"}
        </Button>
      </div>
      <div className="chat-composer__hint">
        Puedes responder hasta el {format(windowEnd, "EEEE d 'a las' h:mm a", { locale: es })}
      </div>
    </form>
  );
}
