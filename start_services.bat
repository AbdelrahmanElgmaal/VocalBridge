@echo off
echo Starting VocalBridge Services...

:: Navigate to the project root directory
cd /d "H:\Grad_Proj\ai-dubbging-system_W_BACKEND\VocalBridge-main"

:: 1. Start the .NET Backend
start "Backend" cmd /k "dotnet run --project backend/src/VocalBridge.API"

:: 2. Start the AI Python Server
start "AI Server" cmd /k ".\venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: 3. Start the Frontend Node Server
start "Frontend" cmd /k "cd frontend && npm run dev"

echo All services launched!
exit