import { Link, useRouterState } from "@tanstack/react-router";
import {
  Calendar,
  Scissors,
  Users,
  UserCheck,
  MessageCircle,
  Settings,
  Shield,
  ChevronsUpDown,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useAuth } from "@/lib/auth-context";

interface NavItem {
  title: string;
  url: string;
  icon: React.ComponentType<{ className?: string }>;
}

const items: NavItem[] = [
  { title: "Agenda", url: "/dashboard", icon: Calendar },
  { title: "Servicios", url: "/services", icon: Scissors },
  { title: "Equipo", url: "/equipo", icon: UserCheck },
  { title: "Clientes", url: "/clients", icon: Users },
  { title: "Mensajes", url: "/messages", icon: MessageCircle },
  { title: "Ajustes", url: "/settings", icon: Settings },
];

const adminItems: NavItem[] = [
  { title: "Panel global", url: "/dashboard", icon: Shield },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const path = useRouterState({ select: (s) => s.location.pathname });
  const { me } = useAuth();

  const isSuperAdmin = me?.role === 'super_admin';
  const displayName = me?.email?.split('@')[0] ?? 'Usuario';
  const roleLabel = me?.role === 'workspace_owner' ? 'Propietario'
    : me?.role === 'manager' ? 'Manager'
    : me?.role === 'staff' ? 'Staff'
    : 'Usuario';

  const isActive = (url: string) => path === url || path.startsWith(url + "/");

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarHeader className="border-b border-sidebar-border h-16">
        <div className="flex items-center gap-2.5 px-2 py-3">
          <div className="h-9 w-9 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-semibold shrink-0">
            H
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-heading text-sm font-semibold truncate">Hilo</div>
              <div className="text-[11px] text-muted-foreground truncate">Panel de control</div>
            </div>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Operación</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={isActive(item.url)} tooltip={item.title}>
                    <Link to={item.url} className="flex items-center gap-2.5">
                      <item.icon className="h-4 w-4 shrink-0" />
                      <span>{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {isSuperAdmin && (
          <SidebarGroup>
            <SidebarGroupLabel>Administración</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {adminItems.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild tooltip={item.title}>
                      <Link to={item.url} className="flex items-center gap-2.5">
                        <item.icon className="h-4 w-4 shrink-0" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <button
          type="button"
          className="flex w-full items-center gap-2.5 px-2 py-2 text-left rounded-md hover:bg-sidebar-accent transition-colors"
        >
          <div className="h-8 w-8 rounded-md bg-accent/15 text-accent flex items-center justify-center text-xs font-semibold shrink-0">
            {displayName.slice(0, 1).toUpperCase()}
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{displayName}</div>
                <div className="text-[11px] text-muted-foreground truncate">{roleLabel}</div>
              </div>
              <ChevronsUpDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </>
          )}
        </button>
      </SidebarFooter>
    </Sidebar>
  );
}
