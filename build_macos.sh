#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

ACTIVITY_MONITOR_ICON="/System/Applications/Utilities/Activity Monitor.app/Contents/Resources/AppIcon.icns"
if [ ! -f "$ACTIVITY_MONITOR_ICON" ]; then
  echo "Could not find the native Activity Monitor icon: $ACTIVITY_MONITOR_ICON" >&2
  exit 1
fi

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --icon "$ACTIVITY_MONITOR_ICON" \
  --specpath build \
  --name "m-task-manager" \
  --osx-bundle-identifier "com.mtaskmanager.app" \
  m_task_manager.py
