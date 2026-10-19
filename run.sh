#!/usr/bin/env bash
# Arranca OS LAB con el interprete virtual si existe.
set -euo pipefail
cd "$(dirname "$0")"

if [ -x .venv/bin/streamlit ]; then
  STREAMLIT=.venv/bin/streamlit
else
  STREAMLIT=streamlit
fi

exec "$STREAMLIT" run app.py "$@"
