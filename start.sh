#!/usr/bin/env bash
# Start the Stock Analysis Engine: the API (port 8000) and the dashboard (port 5173).
# The first run sets everything up (Python environment, packages). Ctrl+C stops both.
# Usage (macOS, Linux, Git Bash):  ./start.sh
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\n%s\n' "$1" >&2; exit 1; }

# Python inside the environment (Windows Git Bash uses Scripts/)
venv_python() { if [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe; else echo .venv/bin/python; fi; }

# 1. Python environment (first run only)
if [ ! -x "$(venv_python)" ]; then
  BASE=$(command -v python3 || command -v python || true)
  [ -n "$BASE" ] || fail "Python 3.12 or newer is required: https://www.python.org/downloads/"
  step "First run: creating the Python environment in .venv"
  "$BASE" -m venv .venv
  step "Installing Python packages (this takes several minutes the first time)"
  "$(venv_python)" -m pip install --upgrade pip
  "$(venv_python)" -m pip install -r requirements.txt
fi
PY=$(venv_python)

# 2. Website packages (first run only)
command -v npm >/dev/null || fail "Node.js 20.19 or newer is required: https://nodejs.org/"
if [ ! -d frontend/node_modules ]; then
  step "First run: installing the website packages"
  npm --prefix frontend install
fi

# 3. Both ports must be free
for port in 8000 5173; do
  if "$PY" -c "import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(('127.0.0.1',$port)) else 1)"; then :; else
    fail "Port $port is already in use, probably by an earlier run. Stop it and try again."
  fi
done

# 4. The local AI model is optional
if curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama is running: news tagging and the AI thesis are available."
else
  echo "Ollama is not running: everything works except news tagging and the AI thesis."
  echo 'To enable them: install Ollama (https://ollama.com), run "ollama pull qwen2.5:7b-instruct", restart this script.'
fi

# 5. API in the background; stopped when this script exits
step "Starting the API on http://localhost:8000"
"$PY" -m uvicorn src.api.main:app --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

# 6. Open the browser once the website answers
(
  for _ in $(seq 1 90); do
    if curl -s --max-time 1 http://localhost:5173 >/dev/null 2>&1; then
      if command -v open >/dev/null; then open http://localhost:5173
      elif command -v xdg-open >/dev/null; then xdg-open http://localhost:5173 >/dev/null 2>&1
      elif command -v cmd.exe >/dev/null; then cmd.exe /c start http://localhost:5173
      fi
      break
    fi
    sleep 1
  done
) &

# 7. Website in the foreground (Ctrl+C stops both)
step "Starting the website on http://localhost:5173 (press Ctrl+C to stop everything)"
npm --prefix frontend run dev
