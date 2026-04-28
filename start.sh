#!/bin/bash
set -e

echo "Starting MethaneX..."

# Load env
export $(grep -v '^#' .env | xargs)

# Start FastAPI backend in background
echo "Starting backend on port 8000..."
cd server
pip install -r requirements.txt -q
cd ..
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend..."
until curl -s http://localhost:8000/ping > /dev/null; do
  sleep 1
done
echo "Backend is up."

# Start Vite frontend
echo "Starting frontend on port 3000..."
cd client
npm install -q
npm run dev &
FRONTEND_PID=$!

echo ""
echo "MethaneX is running:"
echo "  Frontend → http://localhost:3000"
echo "  Backend  → http://localhost:8000"
echo "  Docs     → http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

# On Ctrl+C kill both
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
