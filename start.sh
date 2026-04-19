#!/usr/bin/env bash
set -euo pipefail

PID_FILE=".tenderclaw.pid"
HOST="localhost"
PORT="7000"
started_backend=0

is_running() {
    local pid="$1"
    kill -0 "$pid" 2>/dev/null
}

cleanup() {
    local exit_code=$?

    if [ "$started_backend" != "1" ]; then
        return "$exit_code"
    fi

    if [ -n "${pid:-}" ] && is_running "$pid"; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    return "$exit_code"
}

handle_interrupt() {
    echo
    echo "[TenderClaw] Interrupt received, stopping backend..."
    if [ "$started_backend" = "1" ] && [ -n "${pid:-}" ]; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
    exit 130
}

cleanup_pid_file() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if ! is_running "$pid"; then
            rm -f "$PID_FILE"
        fi
    fi
}

stop() {
    cleanup_pid_file
    echo "[TenderClaw] Stopping..."
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if is_running "$pid"; then
            kill "$pid"
            echo "Killed PID $pid"
        else
            echo "Process $pid not found"
        fi
        rm -f "$PID_FILE"
        exit 0
    fi

    local pids=()
    mapfile -t pids < <(lsof -ti "tcp:$PORT" 2>/dev/null || true)
    if [ "${#pids[@]}" -gt 0 ]; then
        for pid in "${pids[@]}"; do
            if [ -n "$pid" ]; then
                kill "$pid"
                echo "Killed PID $pid (port $PORT)"
            fi
        done
    else
        echo "No process found on port $PORT"
    fi
    exit 0
}

select_backend_command() {
    local candidate

    for candidate in ".venv/bin/python" "venv/bin/python"; do
        if [ -x "$candidate" ] && "$candidate" -c "import bs4, uvicorn" >/dev/null 2>&1; then
            BACKEND_CMD=("$candidate" -m uvicorn backend.main:app --host "$HOST" --port "$PORT" --log-level info)
            return 0
        fi
    done

    for candidate in python python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import bs4, uvicorn" >/dev/null 2>&1; then
            BACKEND_CMD=("$candidate" -m uvicorn backend.main:app --host "$HOST" --port "$PORT" --log-level info)
            return 0
        fi
    done

    if command -v uv >/dev/null 2>&1 && uv --version >/dev/null 2>&1; then
        BACKEND_CMD=("uv" "run" "python" "-m" "uvicorn" "backend.main:app" "--host" "$HOST" "--port" "$PORT" "--log-level" "info")
        return 0
    fi

    return 1
}

cleanup_pid_file
trap cleanup EXIT
trap handle_interrupt INT TERM

if [ "${1:-}" = "stop" ]; then
    stop
fi

if [ -f "$PID_FILE" ]; then
    existing_pid=$(cat "$PID_FILE")
    echo "[TenderClaw] Already running with PID $existing_pid on http://$HOST:$PORT/tenderclaw"
    exit 0
fi

echo "[TenderClaw] Building frontend..."
(
    cd frontend
    npm install --silent
    npm run build
)

if ! select_backend_command; then
    echo "[TenderClaw] No Python runtime with required backend dependencies found."
    echo "[TenderClaw] Run 'uv sync' or install backend dependencies in a virtualenv, then retry."
    exit 1
fi

echo "[TenderClaw] Starting backend on http://$HOST:$PORT/tenderclaw"
"${BACKEND_CMD[@]}" &
pid=$!
started_backend=1
echo "$pid" > "$PID_FILE"

sleep 2
if ! is_running "$pid"; then
    rm -f "$PID_FILE"
    echo "[TenderClaw] Backend exited during startup. Check the log output above."
    exit 1
fi

echo "[TenderClaw] PID $pid saved to $PID_FILE"
wait "$pid"
