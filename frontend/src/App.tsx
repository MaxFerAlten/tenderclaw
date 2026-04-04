import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ChatView } from "./components/chat/ChatView";

export function App() {
  return (
    <BrowserRouter basename="/tenderclaw">
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<ChatView />} />
          <Route path="session/:sessionId" element={<ChatView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
