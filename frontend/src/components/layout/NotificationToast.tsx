/**
 * NotificationToast — floating toast overlay for real-time HUD notifications.
 *
 * Features:
 * - Stacked toasts with slide-in animation
 * - Auto-dismiss with progress bar
 * - Color-coded by severity level
 * - Dismiss on click
 * - Max 4 visible toasts
 */

import { useEffect, useState } from "react";
import { useNotificationStore, type HUDNotification } from "../../stores/notificationStore";
import {
  AlertCircle,
  CheckCircle2,
  Info,
  AlertTriangle,
  X,
  Bot,
  Wrench,
  GitBranch,
  Server,
  ShieldAlert,
} from "lucide-react";

const LEVEL_STYLES: Record<string, { bg: string; border: string; icon: typeof Info; iconColor: string }> = {
  info: {
    bg: "bg-zinc-900/90",
    border: "border-blue-500/30",
    icon: Info,
    iconColor: "text-blue-400",
  },
  success: {
    bg: "bg-zinc-900/90",
    border: "border-emerald-500/30",
    icon: CheckCircle2,
    iconColor: "text-emerald-400",
  },
  warning: {
    bg: "bg-zinc-900/90",
    border: "border-amber-500/30",
    icon: AlertTriangle,
    iconColor: "text-amber-400",
  },
  error: {
    bg: "bg-zinc-900/90",
    border: "border-rose-500/30",
    icon: AlertCircle,
    iconColor: "text-rose-400",
  },
};

const CATEGORY_ICONS: Record<string, typeof Info> = {
  agent: Bot,
  tool: Wrench,
  pipeline: GitBranch,
  system: Server,
  security: ShieldAlert,
};

function ToastItem({ notification, onDismiss }: { notification: HUDNotification; onDismiss: () => void }) {
  const [progress, setProgress] = useState(100);
  const style = LEVEL_STYLES[notification.level] ?? LEVEL_STYLES.info;
  const LevelIcon = style.icon;
  const CategoryIcon = CATEGORY_ICONS[notification.category] ?? Server;

  useEffect(() => {
    if (notification.autoDismissMs <= 0) return;

    const interval = 50;
    const step = (100 * interval) / notification.autoDismissMs;
    const timer = setInterval(() => {
      setProgress((p) => {
        const next = p - step;
        if (next <= 0) {
          clearInterval(timer);
          return 0;
        }
        return next;
      });
    }, interval);

    return () => clearInterval(timer);
  }, [notification.autoDismissMs]);

  return (
    <div
      className={`
        ${style.bg} backdrop-blur-lg border ${style.border}
        rounded-xl shadow-2xl w-80 overflow-hidden
        transform transition-all duration-300 ease-out
        animate-in slide-in-from-right-5 fade-in
        hover:scale-[1.02] cursor-pointer group
      `}
      onClick={onDismiss}
    >
      <div className="flex items-start gap-3 p-3">
        <div className={`p-1.5 rounded-lg bg-zinc-800/50 ${style.iconColor}`}>
          <LevelIcon className="w-4 h-4" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <CategoryIcon className="w-3 h-3 text-zinc-500" />
            <span className="text-xs font-semibold text-zinc-200 truncate">
              {notification.title}
            </span>
          </div>
          {notification.body && (
            <p className="text-[11px] text-zinc-400 leading-relaxed truncate">
              {notification.body}
            </p>
          )}
          {notification.agentName && (
            <span className="inline-flex items-center gap-1 mt-1 text-[10px] text-zinc-500 bg-zinc-800/50 rounded-full px-2 py-0.5">
              <Bot className="w-2.5 h-2.5" />
              {notification.agentName}
            </span>
          )}
        </div>

        <button
          onClick={(e) => { e.stopPropagation(); onDismiss(); }}
          className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-zinc-700/50"
        >
          <X className="w-3 h-3 text-zinc-500" />
        </button>
      </div>

      {notification.autoDismissMs > 0 && (
        <div className="h-0.5 bg-zinc-800">
          <div
            className={`h-full ${
              notification.level === "error" ? "bg-rose-500/40" :
              notification.level === "warning" ? "bg-amber-500/40" :
              notification.level === "success" ? "bg-emerald-500/40" :
              "bg-blue-500/40"
            } transition-all duration-100 ease-linear`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

export function NotificationToast() {
  const notifications = useNotificationStore((s) => s.notifications);
  const dismissNotification = useNotificationStore((s) => s.dismissNotification);

  const visible = notifications
    .filter((n) => !n.dismissed)
    .slice(0, 4);

  if (visible.length === 0) return null;

  return (
    <div className="fixed top-16 right-4 z-[60] flex flex-col gap-2 pointer-events-auto">
      {visible.map((n) => (
        <ToastItem
          key={n.id}
          notification={n}
          onDismiss={() => dismissNotification(n.id)}
        />
      ))}
    </div>
  );
}
