#!/usr/bin/env bash
set -euo pipefail

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is not installed."
  echo "Install example: sudo apt install android-tools-adb"
  exit 1
fi

echo "Connected Android devices:"
adb devices

echo "Setting adb reverse tcp:8000 -> tcp:8000"
adb reverse tcp:8000 tcp:8000

echo "Done. Open this URL on Android Chrome:"
echo "http://127.0.0.1:8000/android"
