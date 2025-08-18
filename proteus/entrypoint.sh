#!/usr/bin/env bash
set -euo pipefail

# If there are command-line arguments, run them as a command.
if [ $# -gt 0 ]; then
  exec "$@"
else
  # Default: start the FastAPI/uvicorn server
  exec uvicorn main:app --host 0.0.0.0 --port 8000
fi