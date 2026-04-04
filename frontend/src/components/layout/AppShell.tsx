/**
 * AppShell — main layout with sidebar + content area.
 * Inspired by OpenClaw's Control UI and Claude Code's terminal layout.
 */

import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { HUD } from "./HUD";
import { Canvas } from "./Canvas";
import { PermissionDialog } from "../tools/PermissionDialog";
import { ws } from "../../api/ws";

export function AppShell() {
  return (
    <div className="flex h-screen bg-zinc-950 font-sans text-zinc-300 relative">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-hidden relative flex">
          <div className="flex-1 overflow-hidden relative flex flex-col">
            <Outlet />
          </div>
          <Canvas />
          <HUD />
        </main>
      </div>
      <PermissionDialog sendPermissionResponse={(id, d) => ws.sendPermissionResponse(id, d)} />
    </div>
  );
}
