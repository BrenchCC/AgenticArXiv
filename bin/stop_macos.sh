#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${ROOT_DIR}/.run"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

stop_pid() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "${pid_file}" ]]; then
    echo "[stop] ${name}: no PID file, skip"
    return 0
  fi

  local pid
  pid="$(cat "${pid_file}" 2>/dev/null || true)"
  if [[ -z "${pid}" ]] || ! kill -0 "${pid}" >/dev/null 2>&1; then
    echo "[stop] ${name}: not running"
    rm -f "${pid_file}"
    return 0
  fi

  kill "${pid}" >/dev/null 2>&1 || true
  for _ in {1..50}; do
    if ! kill -0 "${pid}" >/dev/null 2>&1; then
      rm -f "${pid_file}"
      echo "[stop] ${name}: stopped"
      return 0
    fi
    sleep 0.1
  done

  kill -9 "${pid}" >/dev/null 2>&1 || true
  rm -f "${pid_file}"
  echo "[stop] ${name}: force stopped"
}

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "TCP:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids}" ]]; then
    kill ${pids} >/dev/null 2>&1 || true
  fi
}

stop_pid "backend" "${RUN_DIR}/backend.pid"
stop_pid "frontend" "${RUN_DIR}/frontend.pid"
stop_port "${BACKEND_PORT}"
stop_port "${FRONTEND_PORT}"

echo "[stop] done"
