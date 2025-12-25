import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  LayoutDashboard,
  GitPullRequest,
  PanelLeft,
  Users,
  UsersRound,
  MessageSquare,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

interface MenuItem {
  readonly title: string;
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly path: string;
}

const menuItems: readonly MenuItem[] = [
  { title: "Overview", icon: LayoutDashboard, path: "/" },
  { title: "Contributors", icon: Users, path: "/contributors" },
  { title: "Team Dynamics", icon: UsersRound, path: "/team-dynamics" },
  { title: "Comment Resolution", icon: MessageSquare, path: "/comment-resolution" },
];

export function AppSidebar(): React.ReactElement {
  const location = useLocation();
  const { toggleSidebar } = useSidebar();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2">
          {/* Collapse button on left, aligned with menu icons below */}
          <button
            type="button"
            onClick={toggleSidebar}
            className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-sidebar-accent"
            aria-label="Toggle Sidebar"
          >
            <PanelLeft className="h-4 w-4" />
          </button>
          {/* Title hides when collapsed */}
          <div className="flex items-center gap-2 group-data-[state=collapsed]:hidden">
            <GitPullRequest className="h-5 w-5" />
            <span className="font-semibold">GitHub Metrics</span>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {menuItems.map((item) => {
                const isActive =
                  location.pathname === item.path || location.pathname.startsWith(item.path + "/");
                return (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton asChild isActive={isActive} tooltip={item.title}>
                      <Link to={item.path}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center justify-between px-4 py-2 group-data-[state=collapsed]:hidden">
          <span className="text-xs text-muted-foreground">GitHub Metrics v1.0</span>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
