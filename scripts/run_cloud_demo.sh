#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env ]]; then
  cp config/env.cloud.example .env
  echo "Created .env from config/env.cloud.example."
  echo "Add NVIDIA_API_KEY to .env, then run this script again."
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

if [[ -z "${NVIDIA_API_KEY:-}" ]]; then
  echo "NVIDIA_API_KEY is empty in .env."
  echo "Add it locally to .env. The file is ignored by Git."
  exit 1
fi

python3 scripts/check_cloud_nim_config.py --env-file .env

backend_pid=""
cleanup() {
  if [[ -n "${backend_pid}" ]]; then
    kill "${backend_pid}" 2>/dev/null || true
    wait "${backend_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

uv run python -m src.pipeline \
  --host 127.0.0.1 \
  --port "${VOICE_BACKEND_PORT:-7860}" \
  --workers "${WORKERS:-1}" &
backend_pid=$!

export VOICE_BACKEND_PORT="${VOICE_BACKEND_PORT:-7860}"

python3 - <<'PY'
import os
import time
import urllib.request

port = os.environ.get("VOICE_BACKEND_PORT", "7860")
url = f"http://127.0.0.1:{port}/docs"
deadline = time.time() + 30
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=1):
            raise SystemExit(0)
    except Exception:
        time.sleep(0.5)

raise SystemExit(f"Backend did not become ready at {url}")
PY

echo "Backend ready at http://127.0.0.1:${VOICE_BACKEND_PORT}"
echo "Starting UI at http://127.0.0.1:${VOICE_UI_PORT:-9000}"

cd frontend/webrtc_ui
if [[ ! -d node_modules ]]; then
  echo "Missing frontend dependencies."
  echo "Run: npm --prefix frontend/webrtc_ui ci"
  exit 1
fi
export VITE_VOICE_BACKEND_PORT="${VOICE_BACKEND_PORT}"
npm run dev -- --host 127.0.0.1 --port "${VOICE_UI_PORT:-9000}"
