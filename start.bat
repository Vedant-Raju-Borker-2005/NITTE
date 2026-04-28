@echo off
echo Starting MethaneX...

start "MethaneX Backend" cmd /k "python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 4 /nobreak > nul

start "MethaneX Frontend" cmd /k "cd client && npm install && npm run dev"

echo.
echo MethaneX is starting...
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
