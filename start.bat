@echo off
echo =======================================================
echo          Launching Questrix AI Application
echo =======================================================
echo.

echo [1/3] Starting Python AI Engine (Port 8000)...
start "Questrix - Python AI Service (Port 8000)" cmd /k "cd ai-service && python -m uvicorn calqg.api:app --reload --port 8000"

echo [2/3] Starting Express API Gateway (Port 5000)...
start "Questrix - Express Backend (Port 5000)" cmd /k "cd backend && npm run dev"

echo [3/3] Starting React Web Interface (Port 5173)...
start "Questrix - React Frontend (Port 5173)" cmd /k "cd frontend && npm run dev"

echo.
echo All services launched!
echo Open your browser at: http://localhost:5173
echo.
