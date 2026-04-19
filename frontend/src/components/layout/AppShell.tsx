/**
 * AppShell — main layout with sidebar + content area.
 * Inspired by OpenClaw's Control UI and Claude Code's terminal layout.
 */

import { Outlet } from "react-router-dom";
import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { HUD } from "./HUD";
import { Canvas } from "./Canvas";
import { NotificationToast } from "./NotificationToast";
import { PermissionDialog } from "../tools/PermissionDialog";
import { ws } from "../../api/ws";

interface AppShellProps {
  sidebarOpen?: boolean;
  onToggleSidebar?: () => void;
  children?: ReactNode;
}

export function AppShell({ sidebarOpen = true, onToggleSidebar, children }: AppShellProps) {
  return (
    <div className="flex h-screen bg-zinc-950 font-sans text-zinc-300 relative">
      {sidebarOpen && <Sidebar onToggleSidebar={onToggleSidebar} />}
      <div className="flex flex-1 flex-col min-w-0">
        <Header onToggleSidebar={onToggleSidebar} />
        <main className="flex-1 overflow-hidden relative flex">
          <div className="flex-1 overflow-hidden relative flex flex-col">
            {children ?? <Outlet />}
          </div>
          <Canvas />
          <HUD />
          <NotificationToast />
        </main>
      </div>
      <PermissionDialog sendPermissionResponse={(id, d) => ws.sendPermissionResponse(id, d)} />
    </div>
  );
}

