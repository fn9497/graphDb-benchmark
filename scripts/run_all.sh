#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python scripts/download_dataset.py

for platform in cognodb aura; do
  echo "== Loading $platform =="
  python scripts/loader.py --platform "$platform"
  echo "== Benchmarking $platform =="
  python scripts/benchmark.py --platform "$platform"
done

echo "== Report =="
python scripts/report.py | tee results/REPORT.md
