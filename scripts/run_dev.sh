#!/usr/bin/env bash
set -e

# Script to run DogovorAI using the project virtual environment.
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
  echo "Error: .venv virtual environment not found." >&2
  echo "Create it with: python3 -m venv .venv" >&2
  exit 1
fi

exec .venv/bin/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
