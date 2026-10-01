#!/usr/bin/env bash
# Runs every tests/check_*.tscn headless and reports PASS/FAIL per scene.
# Usage: GODOT=/path/to/Godot_console.exe tools/run_tests.sh
set -u
cd "$(dirname "$0")/.."
GODOT="${GODOT:-godot}"

# Refresh the class cache so new `class_name` scripts resolve.
"$GODOT" --headless --path . --import >/dev/null 2>&1

failed=0
for scene in tests/check_*.tscn; do
	output=$(timeout 120 "$GODOT" --headless --path . "res://$scene" 2>&1)
	code=$?
	if [ $code -eq 0 ] && ! grep -q "SCRIPT ERROR\|Parse Error" <<<"$output"; then
		echo "PASS $scene"
	else
		echo "FAIL $scene (exit $code)"
		grep -v "^Godot Engine\|^$" <<<"$output" | tail -20 | sed 's/^/    /'
		failed=1
	fi
done
exit $failed
