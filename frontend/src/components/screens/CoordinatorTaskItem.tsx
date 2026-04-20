import { AlertTriangle, CheckCircle, Circle, Loader } from "lucide-react";
import type { Task } from "../../api/coordinatorApi";

interface CoordinatorTaskItemProps {
  task: Task;
}

export function CoordinatorTaskItem({ task }: CoordinatorTaskItemProps) {
  return (
    <div className="rounded-lg bg-zinc-900 p-3">
      <div className="flex items-start gap-3">
        <TaskStatusIcon status={task.status} />
        <div className="min-w-0 flex-1">
          <p className={`text-sm ${task.status === "completed" ? "text-zinc-500 line-through" : "text-zinc-200"}`}>
            {task.description}
          </p>
          {task.assignee && (
            <p className="text-xs text-zinc-500">Assigned to: {task.assignee}</p>
          )}
          {task.result && (
            <p className="mt-2 max-w-4xl whitespace-normal text-xs leading-5 text-zinc-400">
              {task.result}
            </p>
          )}
          {task.trace.length > 0 && (
            <div className="mt-3 space-y-2 border-l border-zinc-700 pl-4">
              {task.trace.map((event, index) => (
                <div key={`${event.stage}-${index}`} className="relative">
                  <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-blue-400" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-zinc-200">{event.title}</span>
                    <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[11px] text-zinc-400">
                      {event.agent}
                    </span>
                    <span className="text-[11px] uppercase text-zinc-600">
                      {event.stage.replaceAll("_", " ")}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-zinc-400">{event.detail}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TaskStatusIcon({ status }: { status: Task["status"] }) {
  if (status === "completed") {
    return <CheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-green-400" />;
  }
  if (status === "running") {
    return <Loader className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-blue-400" />;
  }
  if (status === "failed") {
    return <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />;
  }
  return <Circle className="mt-0.5 h-5 w-5 shrink-0 text-zinc-500" />;
}
