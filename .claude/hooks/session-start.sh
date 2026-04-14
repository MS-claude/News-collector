#!/bin/bash
set -euo pipefail

# Only run in Claude Code on the web
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

VENV_DIR="${CLAUDE_PROJECT_DIR}/.venv"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel --quiet

echo "Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "Installing flake8 for linting..."
pip install flake8 --quiet

# Persist activation for the session
echo "export PATH=\"$VENV_DIR/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
echo "export VIRTUAL_ENV=\"$VENV_DIR\"" >> "$CLAUDE_ENV_FILE"

echo "Done."
