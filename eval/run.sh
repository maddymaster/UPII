#!/usr/bin/env bash
# One command, end-to-end: (re)build the labelled dataset from the fixed corpus,
# then run the eval and write eval/results/REPORT.md.
#
#   ./eval/run.sh              # build labels + evaluate
#   ./eval/run.sh --target 0.9 # pass extra flags through to run_eval.py
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"

echo ">> Building labelled dataset from corpus …"
"$PY" eval/build_dataset.py build

echo
echo ">> Running evaluation …"
"$PY" eval/run_eval.py "$@"
