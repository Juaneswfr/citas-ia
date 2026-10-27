import { useMemo } from "react";
import type { Appointment } from "@/lib/mock-data";

interface Props {
  appointments: Appointment[];
  weekStart: Date;
  startHour?: number;
  endHour?: number;
}

const DAYS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"];

export function WeeklyCalendar({ appointments, weekStart, startHour = 8, endHour = 20 }: Props) {
  const hours = useMemo(
    () => Array.from({ length: endHour - startHour }, (_, i) => startHour + i),
    [startHour, endHour]
  );

  const days = useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => {
        const d = new Date(weekStart);
        d.setDate(d.getDate() + i);
        return d;
      }),
    [weekStart]
  );

  const isSameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  const today = new Date();
  const minutesFromStart = (h: number, m: number) => (h - startHour) * 60 + m;
  const totalMinutes = (endHour - startHour) * 60;

  const ROW_HEIGHT = 56; // px per hour

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      {/* Day header */}
      <div className="grid grid-cols-[60px_repeat(7,minmax(0,1fr))] border-b border-border bg-muted/30">
        <div className="border-r border-border" />
        {days.map((d, i) => {
          const active = isSameDay(d, today);
          return (
            <div
              key={i}
              className={`px-3 py-3 text-center border-r last:border-r-0 border-border ${
                active ? "bg-accent/10" : ""
              }`}
            >
              <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                {DAYS[i]}
              </div>
              <div
                className={`text-base font-heading mt-0.5 ${
                  active ? "text-accent font-semibold" : "text-foreground"
                }`}
              >
                {d.getDate()}
              </div>
            </div>
          );
        })}
      </div>

      {/* Body */}
      <div className="relative grid grid-cols-[60px_repeat(7,minmax(0,1fr))]">
        {/* Hour column */}
        <div className="border-r border-border">
          {hours.map((h) => (
            <div
              key={h}
              className="text-[10px] text-muted-foreground pr-2 text-right pt-1"
              style={{ height: ROW_HEIGHT }}
            >
              {String(h).padStart(2, "0")}:00
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((day, di) => {
          const dayAppts = appointments.filter((a) => isSameDay(new Date(a.start), day));
          return (
            <div
              key={di}
              className="relative border-r last:border-r-0 border-border"
              style={{ height: hours.length * ROW_HEIGHT }}
            >
              {/* Hour grid lines */}
              {hours.map((h, i) => (
                <div
                  key={h}
                  className="absolute left-0 right-0 border-t border-border/60"
                  style={{ top: i * ROW_HEIGHT }}
                />
              ))}

              {/* Now indicator */}
              {isSameDay(day, today) &&
                today.getHours() >= startHour &&
                today.getHours() < endHour && (
                  <div
                    className="absolute left-0 right-0 z-10 pointer-events-none"
                    style={{
                      top:
                        (minutesFromStart(today.getHours(), today.getMinutes()) / 60) * ROW_HEIGHT,
                    }}
                  >
                    <div className="h-px bg-accent" />
                    <div className="absolute -top-1 -left-1 h-2 w-2 rounded-full bg-accent" />
                  </div>
                )}

              {/* Appointment blocks */}
              {dayAppts.map((a) => {
                const start = new Date(a.start);
                const top =
                  (minutesFromStart(start.getHours(), start.getMinutes()) / 60) * ROW_HEIGHT;
                const height = (a.durationMin / 60) * ROW_HEIGHT - 2;
                if (top < 0 || top > totalMinutes) return null;
                return (
                  <button
                    key={a.id}
                    className="absolute left-1 right-1 rounded-md border text-left px-2 py-1.5 hover:shadow-md transition-all overflow-hidden group"
                    style={{
                      top,
                      height,
                      backgroundColor: `color-mix(in oklab, ${a.color ?? "var(--primary)"} 18%, var(--card))`,
                      borderColor: `color-mix(in oklab, ${a.color ?? "var(--primary)"} 50%, transparent)`,
                      borderLeftWidth: 3,
                      borderLeftColor: a.color ?? "var(--primary)",
                    }}
                  >
                    <div className="text-[10px] text-foreground/70 font-medium">
                      {start.toTimeString().slice(0, 5)}
                    </div>
                    <div className="text-xs font-semibold text-foreground leading-tight mt-0.5 truncate">
                      {a.clientName}
                    </div>
                    {height > 38 && (
                      <div className="text-[10px] text-muted-foreground truncate mt-0.5">
                        {a.serviceName}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Augment Appointment locally with color from service
declare module "@/lib/mock-data" {
  interface Appointment {
    color?: string;
  }
}
