#!/usr/bin/env bash
set -euo pipefail

WHEEL="${1:?usage: smoke_install_check.sh <wheel>}"
TMPDIR_BASE=$(mktemp -d)
trap 'rm -rf "$TMPDIR_BASE"' EXIT

VENV_DIR="$TMPDIR_BASE/venv"
EMPTY_DIR="$TMPDIR_BASE/empty"
mkdir -p "$VENV_DIR" "$EMPTY_DIR"

# Create temp venv and pip install the wheel
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet "$WHEEL"

# Set cache dirs under the temp dir so doctor sees a clean machine.
HF_HOME="$TMPDIR_BASE/cache/hf"
XDG_CACHE_HOME="$TMPDIR_BASE/cache/xtf"
SENTENCE_TRANSFORMERS_HOME="$TMPDIR_BASE/cache/transformers"

# Run doctor in an empty directory with HF offline, capture exit code without set -e aborting first
set +e
cd "$EMPTY_DIR"
OUTPUT=$(HF_HUB_OFFLINE=1 HF_HOME="$HF_HOME" XDG_CACHE_HOME="$XDG_CACHE_HOME" SENTENCE_TRANSFORMERS_HOME="$SENTENCE_TRANSFORMERS_HOME" "$VENV_DIR/bin/upii" doctor)
RC=$?
set -e

echo "$OUTPUT"

if [ "$RC" -ne 0 ]; then
    echo "smoke_install_check: FAILED — upii doctor exited non-zero on fresh install (rc=$RC)" >&2
    exit 1
fi

if echo "$OUTPUT" | grep -q 'doctor: FAIL'; then
    echo "smoke_install_check: FAILED — upii doctor printed FAIL on fresh install" >&2
    exit 1
fi

if ! echo "$OUTPUT" | grep -q 'doctor: PASS'; then
    echo "smoke_install_check: FAILED — 'doctor: PASS' not found in output" >&2
    exit 1
fi

echo "smoke_install_check: PASSED"
