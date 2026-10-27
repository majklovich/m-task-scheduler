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

## Features

- Live process list with search, sorting, CPU and memory usage, and a confirmed
  End task action.
- Performance charts for CPU and memory, plus system-wide disk and network
  activity.
- Process details, logged-in users, launchd startup items, and launchd services.
- App history accumulates process CPU time only while m-task-manager is open.
- Startup agents and daemons can be disabled or re-enabled through launchd.

The first process scan runs in the background so the window opens immediately.
Process data refreshes every five seconds while performance charts continue
updating between scans. Pages and their system inventories are kept in memory,
so revisiting a section does not rebuild or rescan it.
Use **Refresh** on Startup apps or Services to reload those lists. Disabling a
system daemon may require administrator approval; the app changes its launchd
override and does not remove the original plist.

macOS does not expose per-process disk and network activity through the APIs
used here, so those two columns are intentionally shown as unavailable. Disk
and network activity on the Performance page are system-wide.
