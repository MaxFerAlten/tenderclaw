/** CoordinatorScreen — manage multiple agent tasks. */

import { useState, useEffect } from "react";
import { Plus, CheckCircle, Circle, Loader } from "lucide-react";

interface Task {
  id: string;
  description: string;
  status: "pending" | "running" | "completed" | "failed";
  assignee: string | null;
  result: string | null;
}

interface Coordinator {
  id: string;
  name: string;
  state: string;
  tasks: Task[];
  progress: {
    total: number;
    completed: number;
    running: number;
    pending: number;
    percent: number;
  };
}

const emptyProgress: Coordinator["progress"] = {
  total: 0,
  completed: 0,
  running: 0,
  pending: 0,
  percent: 0,
};

export function CoordinatorScreen() {
  const [coordinators, setCoordinators] = useState<Coordinator[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [newTask, setNewTask] = useState("");

  useEffect(() => {
    fetchCoordinators();
  }, []);

  const fetchCoordinators = async () => {
    const res = await fetch("/api/coordinator");
    if (res.ok) {
      const data = await res.json();
      setCoordinators(Array.isArray(data) ? data.map(normalizeCoordinator) : []);
    }
  };

  const createCoordinator = async () => {
    const name = prompt("Coordinator name:");
    if (!name) return;
    const res = await fetch("/api/coordinator", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      fetchCoordinators();
    }
  };

  const addTask = async (coordinatorId: string) => {
    if (!newTask.trim()) return;
    const res = await fetch(`/api/coordinator/${coordinatorId}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: newTask }),
    });
    if (res.ok) {
      setNewTask("");
      fetchCoordinators();
    }
  };

  const current = coordinators.find((c) => c.id === selected);

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-64 border-r border-zinc-800 p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-zinc-100">Coordinators</h2>
          <button onClick={createCoordinator} className="p-1.5 hover:bg-zinc-800 rounded">
            <Plus className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-1">
          {coordinators.map((c) => (
            <button
              key={c.id}
              onClick={() => setSelected(c.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                selected === c.id ? "bg-blue-500/20 text-blue-400" : "hover:bg-zinc-800 text-zinc-300"
              }`}
            >
              <div>{c.name}</div>
              <div className="text-xs text-zinc-500">{c.progress.completed}/{c.progress.total} tasks</div>
            </button>
          ))}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 p-6">
        {current ? (
          <>
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-xl font-bold text-zinc-100">{current.name}</h1>
              <div className="text-sm text-zinc-400">
                {current.progress.percent}% complete
              </div>
            </div>

            {/* Progress bar */}
            <div className="mb-6">
              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all"
                  style={{ width: `${current.progress.percent}%` }}
                />
              </div>
            </div>

            {/* Add task */}
            <div className="flex gap-2 mb-6">
              <input
                type="text"
                value={newTask}
                onChange={(e) => setNewTask(e.target.value)}
                placeholder="New task..."
                className="flex-1 px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-zinc-200"
                onKeyDown={(e) => e.key === "Enter" && addTask(current.id)}
              />
              <button
                onClick={() => addTask(current.id)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium"
              >
                Add Task
              </button>
            </div>

            {/* Tasks */}
            <div className="space-y-2">
              {current.tasks.map((task) => (
                <div key={task.id} className="flex items-center gap-3 p-3 bg-zinc-900 rounded-lg">
                  {task.status === "completed" ? (
                    <CheckCircle className="w-5 h-5 text-green-400" />
                  ) : task.status === "running" ? (
                    <Loader className="w-5 h-5 text-blue-400 animate-spin" />
                  ) : (
                    <Circle className="w-5 h-5 text-zinc-500" />
                  )}
                  <div className="flex-1">
                    <p className={`text-sm ${task.status === "completed" ? "text-zinc-500 line-through" : "text-zinc-200"}`}>
                      {task.description}
                    </p>
                    {task.assignee && (
                      <p className="text-xs text-zinc-500">Assigned to: {task.assignee}</p>
                    )}
                  </div>
                  {task.result && (
                    <p className="text-xs text-zinc-400 max-w-xs truncate">{task.result}</p>
                  )}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full text-zinc-500">
            Select a coordinator or create a new one
          </div>
        )}
      </div>
    </div>
  );
}

function normalizeCoordinator(coordinator: Partial<Coordinator>): Coordinator {
  return {
    id: coordinator.id ?? "",
    name: coordinator.name ?? "Untitled coordinator",
    state: coordinator.state ?? "idle",
    tasks: Array.isArray(coordinator.tasks) ? coordinator.tasks : [],
    progress: coordinator.progress ?? emptyProgress,
  };
}
