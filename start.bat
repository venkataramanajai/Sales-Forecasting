@echo off
color 0A
echo =======================================================
echo     SALES FORECASTING ML PROJECT     
echo =======================================================
echo.
echo Starting the full-stack architecture...
echo.

:: Start FastAPI Backend in a new terminal window
echo [1/2] Starting FastAPI Backend API (Port 8000)...
start "FastAPI Backend Server" cmd /k "python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000"

:: Start React Frontend in a new terminal window
echo [2/2] Starting React Dashboard (Port 5173)...
start "React Frontend Server" cmd /k "cd frontend && npm run dev"

echo.
echo =======================================================
echo Everything is running! 
echo.
echo 🌐 Open your browser to view the Dashboard:
echo    http://localhost:5173
echo.
echo ⚙️  View the API Documentation (Swagger):
echo    http://localhost:8000/docs
echo =======================================================
echo Close the two newly opened terminal windows to stop the servers.
pause
