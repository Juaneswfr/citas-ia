import { ArrowDownRight, ArrowUpRight } from "lucide-react";

interface Props {
  label: string;
  value: string;
  hint?: string;
  delta?: { value: string; positive: boolean };
  icon?: React.ComponentType<{ className?: string }>;
}

export function KpiCard({ label, value, hint, delta, icon: Icon }: Props) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
          {label}
        </div>
        {Icon && (
          <div className="h-7 w-7 rounded-md bg-accent/10 text-accent flex items-center justify-center">
            <Icon className="h-3.5 w-3.5" />
          </div>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <div className="text-2xl font-heading font-semibold tracking-tight">{value}</div>
        {delta && (
          <div
            className={`inline-flex items-center text-[11px] font-medium gap-0.5 ${
              delta.positive ? "text-accent" : "text-destructive"
            }`}
          >
            {delta.positive ? (
              <ArrowUpRight className="h-3 w-3" />
            ) : (
              <ArrowDownRight className="h-3 w-3" />
            )}
            {delta.value}
          </div>
        )}
      </div>
      {hint && <div className="text-[11px] text-muted-foreground mt-1">{hint}</div>}
    </div>
  );
}
