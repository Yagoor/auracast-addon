#!/usr/bin/env bash
#
# Smoke-tests a built image: the player starts, reads its options, loads the LC3 codec, and
# fails cleanly when there is no controller. No Bluetooth hardware is needed, which is the point:
# this runs on any CI runner.
#
# Usage: scripts/smoke_test.sh IMAGE

set -euo pipefail

image="${1:?usage: scripts/smoke_test.sh IMAGE}"
player=/opt/venv/bin/auracast-player
options_dir="$(mktemp -d)"
trap 'rm -rf "$options_dir"' EXIT
failures=0

# check NAME EXPECTED_STATUS EXPECTED_TEXT [player arguments...]
check() {
  local name="$1" want_status="$2" want_text="$3"
  shift 3
  local output status=0
  output="$(docker run --rm --volume "$options_dir:/opt/test:ro" --entrypoint "$player" "$image" "$@" 2>&1)" || status=$?
  if [ "$status" = "$want_status" ] && grep -qF -- "$want_text" <<<"$output"; then
    echo "  ok   $name"
  else
    echo "  FAIL $name (exit $status, wanted $want_status and '$want_text')"
    echo "$output" | head -20 | sed 's/^/       /'
    failures=$((failures + 1))
  fi
}

state=(--state-dir /tmp/state)

echo '{}' >"$options_dir/no-controller.json"
echo '{"auracast_controller": "/dev/does-not-exist"}' >"$options_dir/missing-port.json"

check "prints its usage" 0 "usage: auracast-player" --help
check "refuses a missing options file" 1 "Cannot read the add-on options" \
  --options /opt/test/nothing.json "${state[@]}"
check "asks for a controller when none is selected" 1 "Select the Auracast controller" \
  --options /opt/test/no-controller.json "${state[@]}"
# Reaching the serial port means the options parsed and the LC3 codec loaded.
check "stops cleanly when the controller cannot be opened" 1 "The Auracast broadcast stopped" \
  --options /opt/test/missing-port.json "${state[@]}"

[ "$failures" = 0 ] || {
  echo "smoke test: $failures check(s) failed"
  exit 1
}
echo "smoke test: all checks passed"
