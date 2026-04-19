/** HistoryDetailScreen — view and manage a single session's history. */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ChevronLeft, Clock, DollarSign, Download, Loader, MessageSquare, Trash2 } from "lucide-react";
import { deleteSession as deleteSessionApi, exportSession, getMessages, getSession, type MessagePage } from "../../api/historyApi";
import type { SessionDetail } from "../../types/history";
import { HistoryMessageBubble, historyMessageText } from "../history/HistoryMessageBubble";

export function HistoryDetailScreen() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [messages, setMessages] = useState<MessagePage | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const loadSession = useCallback(async () => {
    if (!sessionId) return;
    try {
      const data = await getSession(sessionId);
      setSession(data);
    } catch (err) {
      console.error("Failed to load session:", err);
    }
  }, [sessionId]);

  const loadMessages = useCallback(async (beforeId?: string) => {
    if (!sessionId) return;
    setLoadingMessages(true);
    try {
      const data = await getMessages(sessionId, { before_id: beforeId });
      setMessages((prev) => {
        if (beforeId && prev) {
          return {
            ...data,
            messages: [...prev.messages, ...data.messages],
          };
        }
        return data;
      });
    } catch (err) {
      console.error("Failed to load messages:", err);
    } finally {
      setLoadingMessages(false);
    }
  }, [sessionId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadSession(), loadMessages()]).finally(() => setLoading(false));
  }, [loadSession, loadMessages]);

  const handleDelete = async () => {
    if (!sessionId || !confirm("Delete this session? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteSessionApi(sessionId);
      navigate("/history");
    } catch (err) {
      console.error("Failed to delete:", err);
      setDeleting(false);
    }
  };

  const handleExport = async () => {
    if (!sessionId) return;
    try {
      const data = await exportSession(sessionId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `session-${sessionId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export:", err);
    }
  };

  const loadMore = () => {
    if (messages?.has_more && messages.cursor) {
      loadMessages(messages.cursor);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader className="w-6 h-6 text-violet-400 animate-spin" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-zinc-400 mb-4">Session not found</p>
        <button onClick={() => navigate("/history")} className="text-violet-400 hover:underline">
          Back to history
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      <div className="flex items-center gap-4 px-6 py-4 border-b border-zinc-800">
        <button
          onClick={() => navigate("/history")}
          className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-zinc-400" />
        </button>
        
        <div className="flex-1">
          <h1 className="text-lg font-semibold text-zinc-100">{session.title || "Untitled Session"}</h1>
          <div className="flex items-center gap-4 text-sm text-zinc-500 mt-1">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {new Date(session.created_at).toLocaleString()}
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare className="w-3 h-3" />
              {session.message_count} messages
            </span>
            <span className="flex items-center gap-1">
              <DollarSign className="w-3 h-3" />
              ${session.total_cost_usd.toFixed(4)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-zinc-200"
            title="Export"
          >
            <Download className="w-5 h-5" />
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-red-400 disabled:opacity-50"
            title="Delete"
          >
            {deleting ? <Loader className="w-5 h-5 animate-spin" /> : <Trash2 className="w-5 h-5" />}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-4 space-y-4">
          {messages?.messages.map((msg, i) => (
            <HistoryMessageBubble
              key={msg.message_id || i}
              message={msg}
              onCopy={() => navigator.clipboard.writeText(historyMessageText(msg))}
            />
          ))}
        </div>

        {messages?.has_more && (
          <div className="flex justify-center py-4">
            <button
              onClick={loadMore}
              disabled={loadingMessages}
              className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm text-zinc-300 flex items-center gap-2 disabled:opacity-50"
            >
              {loadingMessages ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <ChevronLeft className="w-4 h-4" />
                  Load more
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
