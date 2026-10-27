import { useNavigate, useRouterState } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth-context";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LogOut, Settings, Plus } from "lucide-react";

const TITLES: Record<string, string> = {
  "/dashboard": "Agenda",
  "/services": "Servicios",
  "/clients": "Clientes",
  "/messages": "Mensajes",
  "/settings": "Ajustes",
  "/onboarding": "Configura tu negocio",
};

function roleLabel(role: string | null) {
  if (role === 'workspace_owner') return 'Propietario';
  if (role === 'manager') return 'Manager';
  if (role === 'staff') return 'Staff';
  return 'Usuario';
}

export function AppHeader() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  const title = TITLES[path] ?? "Panel";

  const displayName = me?.email?.split('@')[0] ?? '';
  const initials = displayName.slice(0, 2).toUpperCase() || '?';

  return (
    <header className="h-16 border-b border-border bg-card/70 backdrop-blur sticky top-0 z-30 flex items-center px-4 md:px-6 gap-3">
      <SidebarTrigger className="hidden md:flex" />
      <div className="hidden md:block h-5 w-px bg-border mx-1" />

      <div className="flex flex-col min-w-0 flex-1">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          Hilo
        </div>
        <div className="font-heading text-base font-semibold truncate">{title}</div>
      </div>

      <div className="hidden md:flex">
        <Button size="sm" className="gap-1.5">
          <Plus className="h-4 w-4" />
          Nueva cita
        </Button>
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="flex items-center gap-2.5 px-1.5 py-1 rounded-md hover:bg-muted transition-colors">
            <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-semibold">
              {initials}
            </div>
            <div className="hidden sm:flex flex-col items-start">
              <span className="text-sm font-medium leading-tight">{displayName || me?.email}</span>
              <Badge variant="secondary" className="h-4 px-1.5 text-[10px] font-medium mt-0.5">
                {roleLabel(me?.role ?? null)}
              </Badge>
            </div>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col">
              <span className="font-medium">{displayName || 'Usuario'}</span>
              <span className="text-xs text-muted-foreground">{me?.email}</span>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => navigate({ to: "/settings" as never })}>
            <Settings className="h-4 w-4 mr-2" /> Ajustes
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={() => { logout(); }}
            className="text-destructive focus:text-destructive"
          >
            <LogOut className="h-4 w-4 mr-2" /> Cerrar sesión
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
