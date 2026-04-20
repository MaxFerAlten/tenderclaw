/** CoordinatorScreen — manage multiple agent tasks. */

import { useState, useEffect } from "react";
import { Plus, Loader, Play } from "lucide-react";
import {
  addCoordinatorTask,
  createCoordinator as createCoordinatorRequest,
  listCoordinators,
  runCoordinator as runCoordinatorRequest,
  type Coordinator,
} from "../../api/coordinatorApi";
import { CoordinatorTaskItem } from "./CoordinatorTaskItem";

export function CoordinatorScreen() {
  const [coordinators, setCoordinators] = useState<Coordinator[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [newTask, setNewTask] = useState("");
  const [runningId, setRunningId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCoordinators();
  }, []);

  const fetchCoordinators = async () => {
    try {
      setCoordinators(await listCoordinators());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load coordinators");
    }
  };

  const createCoordinator = async () => {
    const name = prompt("Coordinator name:");
    if (!name) return;
    try {
      await createCoordinatorRequest(name);
      fetchCoordinators();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create coordinator");
    }
  };

  const addTask = async (coordinatorId: string) => {
    if (!newTask.trim()) return;
    try {
      await addCoordinatorTask(coordinatorId, newTask);
      setNewTask("");
      fetchCoordinators();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add task");
    }
  };

  const runCoordinator = async (coordinatorId: string) => {
    setRunningId(coordinatorId);
    try {
      const updated = await runCoordinatorRequest(coordinatorId);
      setCoordinators((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run coordinator");
    } finally {
      setRunningId(null);
    }
  };

  const current = coordinators.find((c) => c.id === selected);
  const currentIsRunning = current ? runningId === current.id : false;
  const currentPending = current?.progress.pending ?? 0;

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
              <div className="flex items-center gap-3">
                <div className="text-sm text-zinc-400">
                  {current.progress.percent}% complete
                </div>
                <button
                  onClick={() => runCoordinator(current.id)}
                  disabled={currentIsRunning || currentPending === 0}
                  className="flex h-9 items-center gap-2 rounded-lg bg-emerald-600 px-3 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
                >
                  {currentIsRunning ? (
                    <Loader className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Run
                </button>
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

            {error && (
              <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
                {error}
              </div>
            )}

            {/* Tasks */}
            <div className="space-y-2">
              {current.tasks.map((task) => (
                <CoordinatorTaskItem key={task.id} task={task} />
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
