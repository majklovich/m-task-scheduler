# m-task-manager

A Python desktop task manager for macOS, with a familiar process-and-performance
workflow in a macOS-style window.

The interface follows the macOS light/dark appearance and uses Czech when the
system language is Czech; otherwise it starts in English. The window stays
above other windows, and its compact layout is designed to fit more information
on screen.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python m_task_manager.py
```

## macOS app

Install the requirements above, then build the Finder-launchable app bundle:

```bash
./build_macos.sh
```

The app is created at `dist/m-task-manager.app`. To set up the global shortcut:

1. If desired, move `m-task-manager.app` to `/Applications` before opening it.
2. Open the app once from Finder. This installs a background listener that
   starts automatically when you log in.
3. In **System Settings → Privacy & Security → Accessibility**, allow
   **m-task-manager** to monitor keyboard input. macOS requires this permission
   for global shortcuts.
4. Press **Command + Option + Backspace**. Either the left or right Command and
   Option keys work. The shortcut opens the app even after you have quit it.

If you move the app after setup, open it once from its new location to update the
background listener.

The macOS build reuses the native Activity Monitor icon for the app's Finder and
Dock icon.

## Features

- Live process list with search, sorting, CPU, memory, disk, network, and GPU
  columns in a Windows-style layout, heatmap coloring,
  and separate End task / Force end task actions. End task requests a normal
  stop; Force end task terminates the process immediately. Neither action asks
  for confirmation.
  App icons appear beside main app processes; other processes are grouped under
  a collapsible Others row. The list starts sorted by memory use (highest first).
- Performance charts for CPU and memory, plus system-wide disk and network
  activity. Charts use a colored filled area and line.
- Process details, logged-in users, launchd startup items, and launchd services.
- Startup items use readable app names and icons when macOS provides them, with
  their technical launchd labels available in the details column. The Users
  page lists regular local accounts with their display names.
- App history accumulates process CPU time only while m-task-manager is open.
- Startup agents and daemons can be disabled or re-enabled through launchd.
- Navigation uses horizontal tabs, and process actions sit at the bottom right.

Process scans, launchd inventories, process details, and task termination run in
the background so the interface stays responsive while they complete.
The first process scan starts immediately and the list is updated as soon as
the background scan finishes. Process data refreshes every 2.5 seconds, and
ending a task triggers an immediate scan so the list reacts promptly.
Performance charts continue updating between scans. Pages and their system
inventories are kept in memory, so revisiting a section does not rebuild or
rescan it.
Use **Refresh** on Startup apps or Services to reload those lists. Disabling a
system daemon may require administrator approval; the app changes its launchd
override and does not remove the original plist.

macOS does not expose per-process disk, network, or GPU activity through the
APIs used here, so those columns are intentionally shown as unavailable. Disk
and network activity on the Performance page are system-wide.
