/** HistoryDetailScreen — view and manage a single session's history. */

import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { 
  ArrowLeft, 
  Trash2, 
  Download, 
  MessageSquare, 
  Clock,
  DollarSign,
  Copy,
  ChevronLeft,
  Loader,
} from "lucide-react";
import { 
  getSession,
  getMessages,
  deleteSession as deleteSessionApi,
  exportSession,
  type MessagePage,
} from "../../api/historyApi";

interface SessionDetail {
  session_id: string;
  title: string;
  created_at: string;
  message_count: number;
  model: string;
  total_cost_usd: number;
}

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
    if (messages?.has_more) {
      const lastMsg = messages.messages[0];
      loadMessages(lastMsg?.message_id);
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
      {/* Header */}
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

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {messages?.messages.map((msg, i) => (
          <div key={msg.message_id || i} className="px-6 py-4 border-b border-zinc-800/50 group">
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                msg.role === "user" 
                  ? "bg-blue-500/20 text-blue-400" 
                  : "bg-emerald-500/20 text-emerald-400"
              }`}>
                {msg.role}
              </span>
              <span className="text-xs text-zinc-500">
                {msg.timestamp && new Date(msg.timestamp).toLocaleTimeString()}
              </span>
              <button
                onClick={() => navigator.clipboard.writeText(typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content))}
                className="p-1 hover:bg-zinc-800 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                title="Copy"
              >
                <Copy className="w-3 h-3 text-zinc-500" />
              </button>
            </div>
            <div className="text-sm text-zinc-300">
              {typeof msg.content === "string" ? (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              ) : (
                <pre className="text-xs bg-zinc-900 p-2 rounded overflow-x-auto">
                  {JSON.stringify(msg.content, null, 2)}
                </pre>
              )}
            </div>
          </div>
        ))}

        {/* Load more */}
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
