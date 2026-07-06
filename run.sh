#!/usr/bin/env bash
# Run Django using the project venv packages (works even if venv python is misconfigured)
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)/venv/lib/python3.14/site-packages${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3.14 manage.py "$@"
