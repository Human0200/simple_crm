#!/usr/bin/env bash
# Запускает backend (FastAPI) и frontend (Vite) одновременно.
# Остановка: Ctrl+C.

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

if [ ! -d "$BACKEND_DIR/venv" ]; then
  echo "Создаю venv для backend..."
  python3 -m venv "$BACKEND_DIR/venv"
  "$BACKEND_DIR/venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Устанавливаю зависимости frontend..."
  (cd "$FRONTEND_DIR" && npm install)
fi

cleanup() {
  echo
  echo "Останавливаю сервисы..."
  pkill -P "$BACKEND_PID" 2>/dev/null || true
  pkill -P "$FRONTEND_PID" 2>/dev/null || true
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(cd "$BACKEND_DIR" && source venv/bin/activate && exec uvicorn app.main:app --port 8000) &
BACKEND_PID=$!

(cd "$FRONTEND_DIR" && exec ./node_modules/.bin/vite --port 5173) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""

wait "$BACKEND_PID" "$FRONTEND_PID"
