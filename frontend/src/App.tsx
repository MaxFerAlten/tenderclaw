import { useState } from "react";
import {
  createBrowserRouter,
  createRoutesFromElements,
  RouterProvider,
  Navigate,
  Route,
  Outlet,
} from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ChatView } from "./components/chat/ChatView";
import { SettingsScreen } from "./components/screens/SettingsScreen";
import { AgentEditorScreen } from "./components/screens/AgentEditorScreen";
import { HistoryScreen } from "./components/screens/HistoryScreen";
import { HistoryDetailScreen } from "./components/screens/HistoryDetailScreen";
import { CoordinatorScreen } from "./components/screens/CoordinatorScreen";
import { KeybindingProvider } from "./keybindings/KeybindingContext";
import { KeyboardShortcutsHelp } from "./components/shared/KeyboardShortcutsHelp";
import { useKeybinding } from "./keybindings";

function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showShortcuts, setShowShortcuts] = useState(false);

  useKeybinding("global:help", () => setShowShortcuts(true));
  useKeybinding("global:toggle-sidebar", () => setSidebarOpen((o) => !o));

  return (
    <>
      <AppShell sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((o) => !o)}>
        <Outlet />
      </AppShell>
      <KeyboardShortcutsHelp isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />
    </>
  );
}

const routes = createRoutesFromElements(
  <Route element={<AppLayout />}>
    <Route index element={<ChatView />} />
    <Route path="session/:sessionId" element={<ChatView />} />
    <Route path="settings" element={<SettingsScreen />} />
    <Route path="agents" element={<AgentEditorScreen />} />
    <Route path="history" element={<HistoryScreen />} />
    <Route path="history/:sessionId" element={<HistoryDetailScreen />} />
    <Route path="coordinator" element={<CoordinatorScreen />} />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route>,
);

const router = createBrowserRouter(routes, { basename: "/tenderclaw" });

export function App() {
  return (
    <KeybindingProvider>
      <RouterProvider router={router} />
    </KeybindingProvider>
  );
}
