import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { Service } from "@/lib/mock-data";

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  service: Service | null;
  onSave: (s: Service) => void;
}

const PRESET_COLORS = [
  "var(--primary)",
  "var(--accent)",
  "oklch(0.55 0.08 25)",
  "oklch(0.45 0.055 18)",
  "oklch(0.6 0.06 50)",
  "oklch(0.5 0.05 35)",
];

export function ServiceFormDialog({ open, onOpenChange, service, onSave }: Props) {
  const [name, setName] = useState("");
  const [duration, setDuration] = useState(30);
  const [price, setPrice] = useState(0);
  const [color, setColor] = useState(PRESET_COLORS[0]);
  const [active, setActive] = useState(true);

  useEffect(() => {
    if (open) {
      setName(service?.name ?? "");
      setDuration(service?.duration ?? 30);
      setPrice(service?.price ?? 0);
      setColor(service?.color ?? PRESET_COLORS[0]);
      setActive(service?.active ?? true);
    }
  }, [open, service]);

  const handleSave = () => {
    if (!name.trim()) return;
    onSave({
      id: service?.id ?? `s-${Date.now()}`,
      name: name.trim(),
      duration,
      price,
      color,
      active,
    });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading">
            {service ? "Editar servicio" : "Nuevo servicio"}
          </DialogTitle>
          <DialogDescription>
            Define como aparecera en la agenda y en WhatsApp.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="s-name">Nombre</Label>
            <Input id="s-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Corte clasico" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="s-dur">Duracion (min)</Label>
              <Input
                id="s-dur"
                type="number"
                min={5}
                step={5}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="s-price">Precio</Label>
              <Input
                id="s-price"
                type="number"
                min={0}
                step={1}
                value={price}
                onChange={(e) => setPrice(Number(e.target.value))}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Color</Label>
            <div className="flex gap-2">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`h-8 w-8 rounded-md border-2 transition-all ${
                    color === c ? "border-foreground scale-110" : "border-transparent"
                  }`}
                  style={{ backgroundColor: c }}
                  aria-label={`Color ${c}`}
                />
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border p-3">
            <div>
              <div className="text-sm font-medium">Activo</div>
              <div className="text-xs text-muted-foreground">Visible para reservas en WhatsApp.</div>
            </div>
            <Switch checked={active} onCheckedChange={setActive} />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button onClick={handleSave}>Guardar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
