import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Search,
  Trash2,
  Clock,
  MessageSquare,
  DollarSign,
  Download,
  FileText,
  Loader,
  Calendar,
  Bot,
  ChevronDown,
} from "lucide-react";
import { SessionSummary } from "../../types/history";
import { listSessions, deleteSession, exportAllSessions } from "../../api/historyApi";
import { useKeybindingContext } from "../../keybindings";

export function HistoryScreen() {
  const navigate = useNavigate();
  const { setContext } = useKeybindingContext();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    loadSessions();
  }, [searchKeyword, dateFrom, dateTo]);

  useEffect(() => {
    setContext("HistorySearch");
    return () => setContext("Chat");
  }, [setContext]);

  const loadSessions = async (reset = true) => {
    setLoading(true);
    try {
      const result = await listSessions({
        keyword: searchKeyword || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        limit: 20,
        offset: reset ? 0 : offset,
      });
      setSessions(reset ? result.sessions : (prev) => [...prev, ...result.sessions]);
      setHasMore(result.sessions.length === 20);
      setOffset(reset ? 20 : offset + 20);
    } catch (err) {
      console.error("Failed to load sessions:", err);
    } finally {
      setLoading(false);
    }
  };

  const loadMore = () => {
    setLoadingMore(true);
    loadSessions(false).finally(() => setLoadingMore(false));
  };

  const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Delete this session?")) return;
    setDeletingId(sessionId);
    try {
      await deleteSession(sessionId);
      setSessions(sessions.filter((s) => s.session_id !== sessionId));
    } catch (err) {
      console.error("Failed to delete session:", err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleExportAll = async () => {
    setExporting(true);
    try {
      const data = await exportAllSessions();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `tenderclaw-history-${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export sessions:", err);
    } finally {
      setExporting(false);
    }
  };

  const handleSessionClick = (sessionId: string) => {
    navigate(`/history/${sessionId}`);
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="h-screen bg-zinc-950 text-zinc-100 overflow-y-auto">
      <div className="sticky top-0 z-10 bg-zinc-950/95 backdrop-blur border-b border-zinc-800 px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Chat</span>
          </Link>
          <div className="flex items-center gap-3">
            <button
              onClick={handleExportAll}
              disabled={exporting || sessions.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors disabled:opacity-40"
            >
              {exporting ? <Loader className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Export All
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-8 space-y-6">
        <div className="flex items-center gap-3">
          <Clock className="w-8 h-8 text-violet-400" />
          <h1 className="text-2xl font-bold">Session History</h1>
          {sessions.length > 0 && (
            <span className="text-sm text-zinc-500 ml-2">{sessions.length} sessions</span>
          )}
        </div>

        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              placeholder="Search sessions by keyword..."
              className="w-full pl-10 pr-4 py-2.5 bg-zinc-900 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500 transition-colors"
            />
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2.5 bg-zinc-900 border rounded-lg text-sm transition-colors ${
              showFilters || dateFrom || dateTo
                ? "border-violet-500 text-violet-400"
                : "border-zinc-700 text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <Calendar className="w-4 h-4" />
            Filters
            <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? "rotate-180" : ""}`} />
          </button>
        </div>

        {showFilters && (
          <div className="bg-zinc-900 rounded-lg p-4 border border-zinc-800 space-y-4">
            <div className="flex gap-4">
              <div className="flex-1 space-y-1">
                <label className="text-xs text-zinc-500">From date</label>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500"
                />
              </div>
              <div className="flex-1 space-y-1">
                <label className="text-xs text-zinc-500">To date</label>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm focus:outline-none focus:border-violet-500"
                />
              </div>
            </div>
            {(dateFrom || dateTo) && (
              <button
                onClick={() => { setDateFrom(""); setDateTo(""); }}
                className="text-xs text-violet-400 hover:text-violet-300"
              >
                Clear date filters
              </button>
            )}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader className="w-8 h-8 text-violet-400 animate-spin" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-20">
            <FileText className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
            <p className="text-zinc-500">
              {searchKeyword || dateFrom || dateTo
                ? "No sessions match your filters"
                : "No sessions yet"}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {sessions.map((session) => (
              <div
                key={session.session_id}
                onClick={() => handleSessionClick(session.session_id)}
                className="group bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 rounded-lg p-4 cursor-pointer transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Bot className="w-4 h-4 text-violet-400 flex-shrink-0" />
                      <h3 className="font-medium text-zinc-200 truncate">{session.title}</h3>
                    </div>
                    {session.preview && (
                      <p className="text-sm text-zinc-500 truncate mb-2">{session.preview}</p>
                    )}
                    <div className="flex items-center gap-4 text-xs text-zinc-600">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(session.created_at)}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" />
                        {session.message_count} messages
                      </span>
                      {session.model && (
                        <span className="flex items-center gap-1">
                          <Bot className="w-3 h-3" />
                          {session.model}
                        </span>
                      )}
                      {session.total_cost_usd > 0 && (
                        <span className="flex items-center gap-1">
                          <DollarSign className="w-3 h-3" />
                          ${session.total_cost_usd.toFixed(4)}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDelete(session.session_id, e)}
                    disabled={deletingId === session.session_id}
                    className="opacity-0 group-hover:opacity-100 p-2 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all disabled:opacity-50"
                    title="Delete session"
                  >
                    {deletingId === session.session_id ? (
                      <Loader className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            ))}

            {hasMore && (
              <div className="flex justify-center py-4">
                <button
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm text-zinc-300 flex items-center gap-2 disabled:opacity-50"
                >
                  {loadingMore ? (
                    <Loader className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      Load more
                      <ChevronDown className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
