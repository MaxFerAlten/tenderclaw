#!/usr/bin/env bash
set -e

PID_FILE=".tenderclaw.pid"

stop() {
    echo "[TenderClaw] Stopping..."
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null && echo "Killed PID $PID" || echo "Process $PID not found"
        rm -f "$PID_FILE"
    else
        # Fallback: kill by port
        PID=$(lsof -ti tcp:7000 2>/dev/null)
        if [ -n "$PID" ]; then
            kill $PID && echo "Killed PID $PID (port 7000)"
        else
            echo "No process found on port 7000"
        fi
    fi
    exit 0
}

if [ "$1" = "stop" ]; then
    stop
fi

echo "[TenderClaw] Building frontend..."
cd frontend
npm install --silent
npm run build
cd ..

echo "[TenderClaw] Starting backend on http://localhost:7000/tenderclaw"
python -m uvicorn backend.main:app --host localhost --port 7000 --log-level info &
echo $! > "$PID_FILE"
echo "[TenderClaw] PID $! saved to $PID_FILE"
wait
