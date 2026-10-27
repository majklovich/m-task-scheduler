#!/bin/sh
set -eu

python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --specpath build \
  --name "m-task-manager" \
  --osx-bundle-identifier "com.mtaskmanager.app" \
  m_task_manager.py
