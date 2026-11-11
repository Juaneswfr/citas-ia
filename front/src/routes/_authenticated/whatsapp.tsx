import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { getAgentConfig, updateAgentConfig, getAgentHours, updateAgentHours } from "@/lib/api/agent";
import type { AgentHoursOut } from "@/lib/types/api";
import { canManageFinance } from "@/lib/nav";
import { FollowupsSection } from "@/components/seguimiento/FollowupsSection";

export const Route = createFileRoute("/_authenticated/whatsapp")({
  head: () => ({ meta: [{ title: "WhatsApp · Hilo" }] }),
  component: WhatsAppAgentPage,
});

// ── Constants ─────────────────────────────────────────────────────────────────

const DAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
const DAYS_FULL = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

type PresetId = "247" | "7dias" | "oficina" | "personalizado";

const PRESETS: { id: PresetId; label: string; desc: string }[] = [
  { id: "247",        label: "24/7",           desc: "Siempre activo" },
  { id: "7dias",      label: "7 días",          desc: "Lun–Dom · 9 am–9 pm" },
  { id: "oficina",    label: "Horario oficina", desc: "Lun–Vie · 9 am–6 pm" },
  { id: "personalizado", label: "Personalizado", desc: "Define cada día" },
];

function makeHours(preset: PresetId): AgentHoursOut[] {
  return Array.from({ length: 7 }, (_, i) => {
    if (preset === "247")     return { day_of_week: i, open_time: "00:00", close_time: "23:59", is_active: true };
    if (preset === "7dias")   return { day_of_week: i, open_time: "09:00", close_time: "21:00", is_active: true };
    if (preset === "oficina") return { day_of_week: i, open_time: "09:00", close_time: "18:00", is_active: i < 5 };
    return { day_of_week: i, open_time: "09:00", close_time: "21:00", is_active: i < 6 }; // personalizado default
  });
}

function detectPreset(hours: AgentHoursOut[]): PresetId {
  if (!hours.length) return "personalizado";
  const all247  = hours.every(h => h.is_active && h.open_time === "00:00" && h.close_time === "23:59");
  const all7d   = hours.every(h => h.is_active && h.open_time === "09:00" && h.close_time === "21:00");
  const isOfi   = hours.every((h, i) => h.open_time === "09:00" && h.close_time === "18:00" && h.is_active === (i < 5));
  if (all247) return "247";
  if (all7d)  return "7dias";
  if (isOfi)  return "oficina";
  return "personalizado";
}

// ── Primitives ────────────────────────────────────────────────────────────────

function TogglePill({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!on)} style={{
      width: 40, height: 24, borderRadius: 12, border: 0, cursor: "pointer",
      background: on ? "var(--wine)" : "var(--line-strong)",
      transition: "background var(--dur-2) var(--ease-std)",
      position: "relative", flexShrink: 0,
    }}>
      <span style={{
        position: "absolute", top: 2, left: on ? 18 : 2, width: 20, height: 20,
        borderRadius: "50%", background: "white",
        transition: "left var(--dur-2) var(--ease-std)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.25)",
      }} />
    </button>
  );
}

function TimeInput({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled?: boolean }) {
  return (
    <input type="time" value={value} onChange={e => onChange(e.target.value)} disabled={disabled} style={{
      padding: "4px 8px", borderRadius: "var(--r-sm)",
      border: "1px solid var(--line-strong)", background: disabled ? "transparent" : "var(--surface-2)",
      font: "400 13px/1 var(--font-mono)", color: disabled ? "var(--ink-4)" : "var(--ink-1)",
      outline: "none", cursor: disabled ? "default" : "text",
    }} />
  );
}

// ── Hours visual strip (read-only summary) ────────────────────────────────────

function HoursStrip({ hours }: { hours: AgentHoursOut[] }) {
  // 24h grid: each column = 1h, each row = 1 day
  const TOTAL = 24;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Hour labels */}
      <div style={{ display: "grid", gridTemplateColumns: `44px repeat(${TOTAL}, 1fr)`, gap: 1 }}>
        <div />
        {Array.from({ length: TOTAL }, (_, h) => (
          <div key={h} style={{
            font: "400 9px/1 var(--font-mono)", color: "var(--ink-4)",
            textAlign: "center", paddingBottom: 2,
          }}>
            {h % 6 === 0 ? `${h}h` : ""}
          </div>
        ))}
      </div>
      {/* Day rows */}
      {hours.map((h, i) => {
        const [openH, openM] = h.open_time.split(":").map(Number);
        const [closeH, closeM] = h.close_time.split(":").map(Number);
        const startFrac = openH + openM / 60;
        const endFrac = Math.min(closeH + closeM / 60, 24);
        return (
          <div key={i} style={{ display: "grid", gridTemplateColumns: `44px repeat(${TOTAL}, 1fr)`, gap: 1, alignItems: "center" }}>
            <div style={{ font: "500 11px/1 var(--font-sans)", color: h.is_active ? "var(--ink-2)" : "var(--ink-4)", paddingRight: 6, textAlign: "right" }}>
              {DAYS[i]}
            </div>
            {Array.from({ length: TOTAL }, (_, col) => {
              const active = h.is_active && col >= Math.floor(startFrac) && col < Math.ceil(endFrac);
              return (
                <div key={col} style={{
                  height: 10, borderRadius: 2,
                  background: active ? "var(--wine)" : "var(--line)",
                  opacity: active ? (col === Math.floor(startFrac) || col === Math.ceil(endFrac) - 1 ? 0.7 : 1) : 1,
                }} />
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function WhatsAppAgentPage() {
  const { workspaceId, role } = useAuth();
  const qc = useQueryClient();

  // ── Config (global toggle + OOH message) ────────────────────────────────────
  const { data: cfg, isLoading: cfgLoading } = useQuery({
    queryKey: ["agent-config", workspaceId],
    queryFn: () => getAgentConfig(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });

  const cfgMut = useMutation({
    mutationFn: (body: Parameters<typeof updateAgentConfig>[1]) => updateAgentConfig(workspaceId!, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["agent-config", workspaceId] }); toast.success("Guardado"); },
    onError: () => toast.error("Error al guardar"),
  });

  const [oohMsg, setOohMsg] = useState("");
  const [oohDirty, setOohDirty] = useState(false);
  useEffect(() => { if (cfg) { setOohMsg(cfg.out_of_hours_message); setOohDirty(false); } }, [cfg]);

  // ── Hours ────────────────────────────────────────────────────────────────────
  const { data: hoursData, isLoading: hoursLoading } = useQuery({
    queryKey: ["agent-hours", workspaceId],
    queryFn: () => getAgentHours(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });

  const [hours, setHours] = useState<AgentHoursOut[]>([]);
  const [preset, setPreset] = useState<PresetId>("personalizado");
  const [hoursDirty, setHoursDirty] = useState(false);

  useEffect(() => {
    if (hoursData) {
      setHours(hoursData);
      setPreset(detectPreset(hoursData));
      setHoursDirty(false);
    }
  }, [hoursData]);

  const applyPreset = useCallback((id: PresetId) => {
    setPreset(id);
    if (id !== "personalizado") {
      setHours(makeHours(id));
    }
    setHoursDirty(true);
  }, []);

  const updateHour = (idx: number, field: keyof AgentHoursOut, value: string | boolean) => {
    setHours(prev => prev.map((h, i) => i === idx ? { ...h, [field]: value } : h));
    setPreset("personalizado");
    setHoursDirty(true);
  };

  const hoursMut = useMutation({
    mutationFn: () => updateAgentHours(workspaceId!, hours),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent-hours", workspaceId] });
      toast.success("Horario guardado");
      setHoursDirty(false);
    },
    onError: () => toast.error("Error al guardar horario"),
  });

  if (cfgLoading || hoursLoading) {
    return <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--ink-3)" }}>Cargando…</div>;
  }

  const botOn = cfg?.agent_enabled ?? true;

  return (
    <div style={{ maxWidth: 680, margin: "0 auto", padding: "32px 24px 64px", display: "flex", flexDirection: "column", gap: 36, animation: "hilo-fade-up var(--dur-3) var(--ease-out)" }}>

      {/* Header */}
      <div>
        <h1 style={{ margin: 0, font: "400 28px/1 var(--font-serif)", color: "var(--ink-1)" }}>Agente WhatsApp</h1>
        <p style={{ margin: "8px 0 0", font: "400 14px/1.5 var(--font-sans)", color: "var(--ink-3)" }}>
          Controla cuándo y cómo responde el bot. Separado del horario de citas.
        </p>
      </div>

      {/* ── Global toggle ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px",
        background: botOn ? "var(--wine)" : "var(--surface)", border: `1px solid ${botOn ? "var(--wine)" : "var(--line)"}`,
        borderRadius: "var(--r-lg)", transition: "background var(--dur-2) var(--ease-std), border-color var(--dur-2) var(--ease-std)" }}>
        <div>
          <div style={{ font: "600 15px/1.2 var(--font-sans)", color: botOn ? "var(--wine-fg)" : "var(--ink-1)" }}>
            {botOn ? "Bot activo" : "Bot pausado"}
          </div>
          <div style={{ font: "400 12.5px/1.4 var(--font-sans)", color: botOn ? "rgba(255,255,255,0.75)" : "var(--ink-3)", marginTop: 3 }}>
            {botOn ? "Respondiendo automáticamente en WhatsApp" : "El agente no responde mientras esté pausado"}
          </div>
        </div>
        <button type="button" onClick={() => cfgMut.mutate({ agent_enabled: !botOn })} style={{
          width: 48, height: 28, borderRadius: 14, border: 0, cursor: "pointer",
          background: botOn ? "rgba(255,255,255,0.3)" : "var(--line-strong)",
          transition: "background var(--dur-2) var(--ease-std)", position: "relative", flexShrink: 0,
        }}>
          <span style={{
            position: "absolute", top: 3, left: botOn ? 23 : 3, width: 22, height: 22,
            borderRadius: "50%", background: "white",
            transition: "left var(--dur-2) var(--ease-std)",
            boxShadow: "0 1px 4px rgba(0,0,0,0.3)",
          }} />
        </button>
      </div>

      {/* ── Horario ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="eyebrow">Horario del agente</div>

        {/* Preset chips */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {PRESETS.map(p => (
            <button key={p.id} type="button" onClick={() => applyPreset(p.id)} style={{
              padding: "7px 14px", borderRadius: "var(--r-md)", border: "1px solid",
              borderColor: preset === p.id ? "var(--wine)" : "var(--line-strong)",
              background: preset === p.id ? "var(--wine)" : "var(--surface)",
              color: preset === p.id ? "var(--wine-fg)" : "var(--ink-2)",
              font: "500 13px/1 var(--font-sans)", cursor: "pointer",
              transition: "all var(--dur-1) var(--ease-std)",
            }}>
              {p.label}
              <span style={{ marginLeft: 6, font: "400 11px/1 var(--font-sans)", opacity: 0.75 }}>{p.desc}</span>
            </button>
          ))}
        </div>

        {/* Visual strip */}
        {hours.length > 0 && (
          <div style={{ padding: "14px 16px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--r-md)" }}>
            <HoursStrip hours={hours} />
          </div>
        )}

        {/* Per-day editor — always visible for precision */}
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {hours.map((h, i) => (
            <div key={h.day_of_week} style={{
              display: "flex", alignItems: "center", gap: 12, padding: "8px 14px",
              background: h.is_active ? "var(--surface)" : "transparent",
              border: "1px solid", borderColor: h.is_active ? "var(--line)" : "transparent",
              borderRadius: "var(--r-md)", transition: "all var(--dur-1) var(--ease-std)",
            }}>
              <TogglePill on={h.is_active} onChange={v => updateHour(i, "is_active", v)} />
              <span style={{ width: 68, font: "500 13px/1 var(--font-sans)", color: h.is_active ? "var(--ink-1)" : "var(--ink-4)" }}>
                {DAYS_FULL[h.day_of_week]}
              </span>
              {h.is_active ? (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <TimeInput value={h.open_time} onChange={v => updateHour(i, "open_time", v)} />
                  <span style={{ color: "var(--ink-4)", font: "400 12px/1 var(--font-sans)" }}>→</span>
                  <TimeInput value={h.close_time} onChange={v => updateHour(i, "close_time", v)} />
                </div>
              ) : (
                <span style={{ font: "400 12.5px/1 var(--font-sans)", color: "var(--ink-4)" }}>Cerrado</span>
              )}
            </div>
          ))}
        </div>

        {/* Save button */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button type="button" onClick={() => hoursMut.mutate()} disabled={!hoursDirty || hoursMut.isPending} style={{
            padding: "9px 20px", borderRadius: "var(--r-md)",
            background: hoursDirty ? "var(--wine)" : "var(--line)",
            color: hoursDirty ? "var(--wine-fg)" : "var(--ink-4)",
            border: 0, font: "500 13.5px/1 var(--font-sans)",
            cursor: hoursDirty ? "pointer" : "default",
            transition: "all var(--dur-2) var(--ease-std)",
          }}>
            {hoursMut.isPending ? "Guardando…" : "Guardar horario"}
          </button>
          {!hoursDirty && <span style={{ font: "400 12px/1 var(--font-sans)", color: "var(--ink-4)" }}>Sin cambios</span>}
        </div>
      </div>

      {/* ── Mensaje fuera de horario ── */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="eyebrow">Mensaje fuera de horario</div>
        <div style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "var(--r-md)", padding: "14px 18px" }}>
          <p style={{ margin: "0 0 10px", font: "400 13px/1.5 var(--font-sans)", color: "var(--ink-3)" }}>
            Se envía automáticamente cuando alguien escribe fuera del horario del agente.
          </p>
          <textarea value={oohMsg} onChange={e => { setOohMsg(e.target.value); setOohDirty(true); }} rows={3} style={{
            width: "100%", padding: "10px 12px", borderRadius: "var(--r-sm)",
            border: "1px solid var(--line-strong)", background: "var(--surface-2)",
            font: "400 14px/1.5 var(--font-sans)", color: "var(--ink-1)",
            outline: "none", resize: "vertical", boxSizing: "border-box",
          }} />
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 10 }}>
            <button type="button" onClick={() => { cfgMut.mutate({ out_of_hours_message: oohMsg }); setOohDirty(false); }}
              disabled={!oohDirty || cfgMut.isPending} style={{
                padding: "9px 20px", borderRadius: "var(--r-md)",
                background: oohDirty ? "var(--wine)" : "var(--line)",
                color: oohDirty ? "var(--wine-fg)" : "var(--ink-4)",
                border: 0, font: "500 13.5px/1 var(--font-sans)",
                cursor: oohDirty ? "pointer" : "default",
                transition: "all var(--dur-2) var(--ease-std)",
              }}>
              {cfgMut.isPending ? "Guardando…" : "Guardar mensaje"}
            </button>
            {!oohDirty && <span style={{ font: "400 12px/1 var(--font-sans)", color: "var(--ink-4)" }}>Sin cambios</span>}
          </div>
        </div>
      </div>

      {/* ── Seguimiento automático (solo dueño o administrador; el backend exige manager) ── */}
      {canManageFinance(role) && <FollowupsSection />}

    </div>
  );
}
