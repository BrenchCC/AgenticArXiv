#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/AgenticArxiv"
FRONTEND_DIR="${ROOT_DIR}/AgenticArxivWeb"
RUN_DIR="${ROOT_DIR}/.run"

CONDA_ENV="${CONDA_ENV:-agent}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

BACKEND_PID_FILE="${RUN_DIR}/backend.pid"
FRONTEND_PID_FILE="${RUN_DIR}/frontend.pid"
BACKEND_LOG="${RUN_DIR}/backend.log"
FRONTEND_LOG="${RUN_DIR}/frontend.log"

mkdir -p "${RUN_DIR}" "${BACKEND_DIR}/output"

require_cmd() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "[start] ERROR: command not found: ${command_name}" >&2
    exit 1
  fi
}

is_running() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1
}

require_cmd conda
require_cmd npm
require_cmd curl

PYTHON_BIN="$(
  conda run -n "${CONDA_ENV}" python -c 'import sys; print(sys.executable)' \
    | tr -d '\r' \
    | sed -n '/^\//{p;q;}'
)"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[start] ERROR: Python not found in Conda environment: ${CONDA_ENV}" >&2
  exit 1
fi

if [[ ! -x "${FRONTEND_DIR}/node_modules/.bin/vite" ]]; then
  echo "[start] ERROR: frontend dependencies are missing. Run: npm install --prefix AgenticArxivWeb" >&2
  exit 1
fi

if is_running "${BACKEND_PID_FILE}"; then
  echo "[start] backend already running (pid=$(cat "${BACKEND_PID_FILE}"))"
else
  (
    cd "${BACKEND_DIR}"
    nohup "${PYTHON_BIN}" -m uvicorn api.app:app \
      --host "${BACKEND_HOST}" \
      --port "${BACKEND_PORT}" \
      > "${BACKEND_LOG}" 2>&1 &
    echo $! > "${BACKEND_PID_FILE}"
  )
  echo "[start] backend started (pid=$(cat "${BACKEND_PID_FILE}"))"
fi

if is_running "${FRONTEND_PID_FILE}"; then
  echo "[start] frontend already running (pid=$(cat "${FRONTEND_PID_FILE}"))"
else
  (
    cd "${FRONTEND_DIR}"
    nohup ./node_modules/.bin/vite \
      --host "${FRONTEND_HOST}" \
      --port "${FRONTEND_PORT}" \
      > "${FRONTEND_LOG}" 2>&1 &
    echo $! > "${FRONTEND_PID_FILE}"
  )
  echo "[start] frontend started (pid=$(cat "${FRONTEND_PID_FILE}"))"
fi

for _ in {1..30}; do
  if curl --noproxy '*' -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/health" >/dev/null 2>&1 \
    && curl --noproxy '*' -fsS "http://${FRONTEND_HOST}:${FRONTEND_PORT}/" >/dev/null 2>&1; then
    echo "[start] backend ready:  http://${BACKEND_HOST}:${BACKEND_PORT}"
    echo "[start] frontend ready: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
    echo "[start] logs: ${RUN_DIR}"
    exit 0
  fi
  sleep 0.5
done

echo "[start] ERROR: service health check failed. See logs in ${RUN_DIR}" >&2
exit 1
