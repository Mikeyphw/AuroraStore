#!/usr/bin/env bash
# GitHub-only; never retry Kotlin, lint, or test failures.
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_OS:-}" == Linux ]] || { echo AURORA_HOSTED_ONLY >&2; exit 2; }
logdir=$(mktemp -d "${RUNNER_TEMP:?}/aurora-gradle-retry.XXXXXX")
trap 'rm -rf -- "$logdir"' EXIT
for attempt in 1 2 3; do
  log="$logdir/attempt-$attempt.log"
  set +e
  ./gradlew "$@" 2>&1 | tee "$log"
  results=("${PIPESTATUS[@]}")
  set -e
  rc=${results[0]}
  (( results[1] == 0 )) || exit "${results[1]}"
  (( rc == 0 )) && exit 0
  if ! grep -Fq "Plugin [id: 'com.android.application', version: '9.4.1', apply: false] was not found" "$log" || grep -Eq '(^e: |Execution failed for task|Compilation error|There were failing tests)' "$log"; then
    exit "$rc"
  fi
  (( attempt < 3 )) || exit "$rc"
  echo "AURORA_AGP_TRANSIENT_RETRY attempt=$attempt" >&2
  sleep "$((attempt * 10))"
done
