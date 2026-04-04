@echo off
setlocal

if "%1"=="stop" goto :stop

echo [TenderClaw] Building frontend...
cd frontend
call npm install --silent
call npm run build
if errorlevel 1 (
    echo [ERROR] Frontend build failed.
    exit /b 1
)
cd ..

echo [TenderClaw] Starting backend on http://localhost:7000/tenderclaw
python -m uvicorn backend.main:app --host localhost --port 7000 --log-level info
goto :eof

:stop
echo [TenderClaw] Stopping...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":7000 " ^| findstr "LISTENING"') do (
    echo Killing PID %%p on port 7000
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /fo csv /nh 2^>nul') do (
    taskkill /PID %%~p /F >nul 2>&1
)
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python3.12.exe" /fo csv /nh 2^>nul') do (
    taskkill /PID %%~p /F >nul 2>&1
)
echo [TenderClaw] Stopped.
