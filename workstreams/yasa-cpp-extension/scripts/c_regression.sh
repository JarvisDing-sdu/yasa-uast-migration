#!/usr/bin/env bash
# C regression for the C++ work. See c_regression.py for what is checked.
#   c_regression.sh OUT_DIR                      run and write OUT_DIR/summary.json
#   c_regression.sh OUT_DIR --compare BASE_DIR   run, then compare with a baseline run
#   c_regression.sh OUT_DIR --skip juliet,curl   skip the slow parts (not for baselines)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
out="${1:?usage: c_regression.sh OUT_DIR [--compare BASE_DIR] [--skip parts]}"
shift
compare=""
skip=()
while [ $# -gt 0 ]; do
  case "$1" in
    --compare) compare="${2:?}"; shift 2 ;;
    --skip) skip=(--skip "${2:?}"); shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
python3 "$here/c_regression.py" run "$out" ${skip[@]+"${skip[@]}"}
if [ -n "$compare" ]; then
  python3 "$here/c_regression.py" compare "$out" "$compare"
fi
