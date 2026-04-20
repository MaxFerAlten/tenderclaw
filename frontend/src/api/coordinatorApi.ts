export type TaskStatus = "pending" | "running" | "completed" | "failed";

export interface Task {
  id: string;
  description: string;
  status: TaskStatus;
  assignee: string | null;
  result: string | null;
  trace: TaskTraceEvent[];
}

export interface TaskTraceEvent {
  stage: string;
  agent: string;
  title: string;
  detail: string;
}

export interface CoordinatorProgress {
  total: number;
  completed: number;
  running: number;
  pending: number;
  percent: number;
}

export interface Coordinator {
  id: string;
  name: string;
  state: string;
  tasks: Task[];
  progress: CoordinatorProgress;
}

const emptyProgress: CoordinatorProgress = {
  total: 0,
  completed: 0,
  running: 0,
  pending: 0,
  percent: 0,
};

export async function listCoordinators(): Promise<Coordinator[]> {
  const res = await fetch("/api/coordinator");
  if (!res.ok) {
    throw new Error("Failed to load coordinators");
  }
  const data = await res.json();
  return Array.isArray(data) ? data.map(normalizeCoordinator) : [];
}

export async function createCoordinator(name: string): Promise<Coordinator> {
  const res = await fetch("/api/coordinator", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) {
    throw new Error("Failed to create coordinator");
  }
  return normalizeCoordinator(await res.json());
}

export async function addCoordinatorTask(coordinatorId: string, description: string): Promise<void> {
  const res = await fetch(`/api/coordinator/${coordinatorId}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) {
    throw new Error("Failed to add task");
  }
}

export async function runCoordinator(coordinatorId: string): Promise<Coordinator> {
  const res = await fetch(`/api/coordinator/${coordinatorId}/run`, { method: "POST" });
  if (!res.ok) {
    throw new Error("Failed to run coordinator");
  }
  const data = await res.json();
  return normalizeCoordinator(data.coordinator ?? data);
}

function normalizeCoordinator(coordinator: Partial<Coordinator>): Coordinator {
  return {
    id: coordinator.id ?? "",
    name: coordinator.name ?? "Untitled coordinator",
    state: coordinator.state ?? "idle",
    tasks: Array.isArray(coordinator.tasks) ? coordinator.tasks.map(normalizeTask) : [],
    progress: coordinator.progress ?? emptyProgress,
  };
}

function normalizeTask(task: Partial<Task>): Task {
  return {
    id: task.id ?? "",
    description: task.description ?? "",
    status: task.status ?? "pending",
    assignee: task.assignee ?? null,
    result: task.result ?? null,
    trace: Array.isArray(task.trace) ? task.trace : [],
  };
}
