import { useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
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

function AppContent() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showShortcuts, setShowShortcuts] = useState(false);

  useKeybinding("global:help", () => setShowShortcuts(true));
  useKeybinding("global:toggle-sidebar", () => setSidebarOpen((o) => !o));

  return (
    <>
      <Routes>
        <Route element={<AppShell sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen((o) => !o)} />}>
          <Route index element={<ChatView />} />
          <Route path="session/:sessionId" element={<ChatView />} />
          <Route path="settings" element={<SettingsScreen />} />
          <Route path="agents" element={<AgentEditorScreen />} />
          <Route path="history" element={<HistoryScreen />} />
          <Route path="history/:sessionId" element={<HistoryDetailScreen />} />
          <Route path="coordinator" element={<CoordinatorScreen />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      <KeyboardShortcutsHelp isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />
    </>
  );
}

export function App() {
  return (
    <BrowserRouter basename="/tenderclaw">
      <KeybindingProvider>
        <AppContent />
      </KeybindingProvider>
    </BrowserRouter>
  );
}
