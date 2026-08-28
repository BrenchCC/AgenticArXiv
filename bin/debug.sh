#!/usr/bin/env bash
set -euo pipefail

# 前台调试启动：后端文件变更自动重启，前端文件变更自动热更新。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/AgenticArxiv"
FRONTEND_DIR="${ROOT_DIR}/AgenticArxivWeb"

CONDA_ENV="${CONDA_ENV:-agent}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

require_cmd() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "[debug] ERROR: command not found: ${command_name}" >&2
    exit 1
  fi
}

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "${BACKEND_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}

require_cmd conda
require_cmd npm

if [[ ! -d "${BACKEND_DIR}" || ! -d "${FRONTEND_DIR}" ]]; then
  echo "[debug] ERROR: project directories are incomplete." >&2
  exit 1
fi

if [[ ! -x "${FRONTEND_DIR}/node_modules/.bin/vite" ]]; then
  echo "[debug] ERROR: frontend dependencies are missing. Run: npm install --prefix AgenticArxivWeb" >&2
  exit 1
fi

PYTHON_BIN="$(conda run -n "${CONDA_ENV}" python -c 'import sys; print(sys.executable)' | tr -d '\r' | sed -n '/^\//{p;q;}')"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[debug] ERROR: Python not found in Conda environment: ${CONDA_ENV}" >&2
  exit 1
fi

trap cleanup EXIT INT TERM

echo "[debug] backend:  http://${BACKEND_HOST}:${BACKEND_PORT} (auto reload enabled)"
echo "[debug] frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT} (Vite HMR enabled)"
echo "[debug] Press Ctrl-C to stop both services."

(
  cd "${BACKEND_DIR}"
  exec "${PYTHON_BIN}" -m uvicorn api.app:app \
    --host "${BACKEND_HOST}" \
    --port "${BACKEND_PORT}" \
    --reload \
    --reload-dir "${BACKEND_DIR}"
) &
BACKEND_PID=$!

cd "${FRONTEND_DIR}"
./node_modules/.bin/vite \
  --host "${FRONTEND_HOST}" \
  --port "${FRONTEND_PORT}"
