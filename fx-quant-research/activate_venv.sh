#!/bin/bash
# Wrapper to activate virtual environment safely with paths containing spaces
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VIRTUAL_ENV_DISABLE_PROMPT=1
source "$SCRIPT_DIR/venv/bin/activate"
# Manually set a simple PS1 prefix if it succeeded
if [ $? -eq 0 ]; then
    export PS1="(venv) $PS1"
fi
