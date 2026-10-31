from __future__ import annotations

import plistlib
import os
import pwd
import re
import shlex
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.parsers.expat import ExpatError

import psutil
from AppKit import NSApplicationActivationPolicyRegular, NSWorkspace
from Foundation import NSLocale
from pynput import keyboard
from PySide6.QtCore import QFileInfo, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFileIconProvider,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


SECTIONS = [
    ("Processes", "▦"),
    ("Performance", "◔"),
    ("Startup apps", "↗"),
    ("Users", "◉"),
    ("Details", "☷"),
    ("App history", "◷"),
    ("Services", "⚙"),
]

TRANSLATIONS = {
    "cs": {
        "Processes": "Procesy",
        "Performance": "Výkon",
        "App history": "Historie aplikací",
        "Startup apps": "Aplikace po spuštění",
        "Users": "Uživatelé",
        "Details": "Podrobnosti",
        "Services": "Služby",
        "Live system overview\nProcesses refresh every 2.5 seconds": "Živý přehled systému\nProcesy se obnovují každých 2,5 sekundy",
        "Search by name or PID": "Hledat podle názvu nebo PID",
        "End task": "Ukončit úlohu",
        "Force end task": "Vynutit ukončení",
        "Apps ({count})": "Aplikace ({count})",
        "Others ({count})": "Ostatní ({count})",
        "Disable": "Zakázat",
        "Enable": "Povolit",
        "Refresh": "Obnovit",
        "Enabled": "Povoleno",
        "Disabled": "Zakázáno",
        "Unknown": "Neznámý",
        "Change startup item?": "Změnit položku po spuštění?",
        "Disable “{name}” at login?": "Zakázat „{name}“ při přihlášení?",
        "Enable “{name}” at login?": "Povolit „{name}“ při přihlášení?",
        "Select a startup item first.": "Nejprve vyberte položku po spuštění.",
        "Could not update startup item: {error}": "Položku po spuštění nelze změnit: {error}",
        "Could not read disabled startup items: {error}": "Nelze načíst zakázané položky po spuštění: {error}",
        "Could not read startup items: {error}": "Nelze načíst položky po spuštění: {error}",
        "Could not read process details: {error}": "Nelze načíst podrobnosti procesu: {error}",
        "Could not start the global shortcut: {error}": (
            "Nelze spustit globální klávesovou zkratku: {error}"
        ),
        "Updating startup item “{name}”…": "Aktualizuje se položka po spuštění „{name}“…",
        "Updated startup item “{name}”.": "Položka po spuštění „{name}“ byla aktualizována.",
        "Ready": "Připraveno",
        "Collecting system information…": "Načítají se informace o systému…",
        "Could not refresh system data: {error}": "Systémová data nelze obnovit: {error}",
        "See what is running and how much of your Mac it is using.": "Přehled spuštěných procesů a jejich využití Macu.",
        "Live system resource usage and activity.": "Živé využití systémových prostředků a aktivita.",
        "CPU time observed since m-task-manager was opened.": "Čas procesoru zaznamenaný od spuštění m-task-manageru.",
        "Launch agents and daemons registered on this Mac.": "Agenti a démoni registrovaní v tomto Macu.",
        "Logged-in accounts and their running processes.": "Přihlášené účty a jejich spuštěné procesy.",
        "Detailed, sortable information for every process.": "Podrobné informace o všech procesech.",
        "Services registered with macOS launchd.": "Služby registrované v macOS launchd.",
        "Name": "Název",
        "Status": "Stav",
        "CPU": "Procesor",
        "Memory": "Paměť",
        "Disk": "Disk",
        "Network": "Síť",
        "GPU": "GPU",
        "PID": "PID",
        "User": "Uživatel",
        "Threads": "Vlákna",
        "Path": "Cesta",
        "App / process": "Aplikace / proces",
        "CPU time observed": "Zaznamenaný čas CPU",
        "Type": "Typ",
        "Location": "Umístění",
        "Details label": "Technické údaje",
        "Account": "Účet",
        "Full name": "Jméno",
        "Service": "Služba",
        "Total processor utilization": "Celkové využití procesoru",
        "Swap": "Odkládací paměť",
        "Read": "Čtení",
        "Write": "Zápis",
        "Sent": "Odesílání",
        "Received": "Příjem",
        "logical processors": "logických procesorů",
        "processes": "procesů",
        "Uptime": "Doba běhu",
        "User launch agent": "Uživatelský agent",
        "System launch agent": "Systémový agent",
        "System launch daemon": "Systémový démon",
        "Per-process disk activity is not exposed by macOS.": "macOS nezpřístupňuje aktivitu disku pro jednotlivé procesy.",
        "Per-process network activity is not exposed by macOS.": "macOS nezpřístupňuje síťovou aktivitu pro jednotlivé procesy.",
        "Per-process GPU activity is not exposed by macOS.": "macOS nezpřístupňuje aktivitu GPU pro jednotlivé procesy.",
        "Could not read launchd services: {error}": "Nelze načíst služby launchd: {error}",
        "Select a process first.": "Nejprve vyberte proces.",
        "Process is still running.": "Proces stále běží.",
        "“{name}” is still running.": "Proces „{name}“ stále běží.",
        "Could not force quit process: {error}": "Proces nelze vynuceně ukončit: {error}",
        "Global shortcut is unavailable: {error}": "Globální klávesová zkratka není dostupná: {error}",
        "Allow m-task-manager in macOS Privacy & Security > Accessibility, then restart the app.": (
            "Povolte m-task-manager v macOS Soukromí a zabezpečení > Zpřístupnění a poté aplikaci restartujte."
        ),
        "Could not end process: {error}": "Proces nelze ukončit: {error}",
        "Sent a quit signal to {name} (PID {pid}).": "Procesu {name} (PID {pid}) byl odeslán signál k ukončení.",
        "Force quit {name} (PID {pid}).": "Proces {name} (PID {pid}) byl vynuceně ukončen.",
        "Cancel": "Zrušit",
        "Yes": "Ano",
        "Disk activity": "Aktivita disku",
        "CPU time": "Čas CPU",
        " h ": " h ",
        " min": " min",
        " s": " s",
        "Sleeping": "Spící",
        "Running": "Běží",
        "Stopped": "Zastavený",
        "Zombie": "Zombie",
        "Waiting": "Čeká",
        "Idle": "Nečinný",
    }
}


def system_language() -> str:
    for locale in NSLocale.preferredLanguages():
        language = str(locale).replace("_", "-").split("-", 1)[0].lower()
        if language in ("cs", "en"):
            return language
    return "en"


def tr(text: str, language: str) -> str:
    return TRANSLATIONS.get(language, {}).get(text, text)


HOTKEY_AGENT_LABEL = "com.mtaskmanager.hotkey"


def install_hotkey_agent() -> None:
    if not getattr(sys, "frozen", False):
        return

    app_bundle = Path(sys.executable).resolve().parents[2]
    agent_executable = app_bundle / "Contents" / "MacOS" / "m-task-manager"
    agent_directory = Path.home() / "Library" / "LaunchAgents"
    agent_path = agent_directory / f"{HOTKEY_AGENT_LABEL}.plist"
    log_path = Path.home() / "Library" / "Logs" / "m-task-manager-hotkey.log"
    domain = f"gui/{os.getuid()}"
    arguments = [str(agent_executable), "--hotkey-daemon"]
    agent = {
        "Label": HOTKEY_AGENT_LABEL,
        "ProgramArguments": arguments,
        "RunAtLoad": True,
        "KeepAlive": True,
        "LimitLoadToSessionType": "Aqua",
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }

    agent_directory.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    current_agent = None
    if agent_path.exists():
        with agent_path.open("rb") as agent_file:
            current_agent = plistlib.load(agent_file)
    if current_agent != agent:
        subprocess.run(
            ["launchctl", "bootout", domain, str(agent_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        temporary_path = agent_path.with_suffix(".plist.tmp")
        with temporary_path.open("wb") as agent_file:
            plistlib.dump(agent, agent_file)
        temporary_path.replace(agent_path)

    loaded = subprocess.run(
        ["launchctl", "print", f"{domain}/{HOTKEY_AGENT_LABEL}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if loaded.returncode != 0:
        subprocess.run(["launchctl", "bootstrap", domain, str(agent_path)], check=True)


def run_hotkey_daemon() -> int:
    activate = lambda: subprocess.Popen(
        ["/usr/bin/open", "-a", str(Path(sys.executable).resolve().parents[2])]
    )
    hotkeys = {
        f"<{command}>+<{option}>+<backspace>": activate
        for command in ("cmd_l", "cmd_r")
        for option in ("alt_l", "alt_r")
    }
    listener = keyboard.GlobalHotKeys(hotkeys)
    listener.start()
    try:
        listener.join()
    finally:
        listener.stop()
    return 0


@dataclass
class ProcessInfo:
    pid: int
    name: str
    username: str
    status: str
    cpu: float
    memory: int
    create_time: float
    cpu_time: float
    executable: str
    is_application: bool


@dataclass(frozen=True)
class StartupItem:
    name: str
    display_name: str
    kind: str
    path: str
    domain: str
    disabled: bool | None
    app_bundle: str | None


class SystemMonitor:
    def __init__(self) -> None:
        self.processes: list[ProcessInfo] = []
        self.history: dict[str, float] = defaultdict(float)
        self._previous_cpu: dict[tuple[int, float], float] = {}
        self._previous_disk = psutil.disk_io_counters()
        self._previous_network = psutil.net_io_counters()
        self._previous_sample = time.monotonic()
        self.process_refresh_interval = 2.5
        self._previous_process_sample = time.monotonic() - self.process_refresh_interval
        self._process_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="process-scan")
        self._process_future: Future[list[ProcessInfo]] | None = None
        psutil.cpu_percent(interval=None)

    def shutdown(self) -> None:
        self._process_executor.shutdown(wait=False, cancel_futures=True)

    def sample(
        self,
        refresh_processes: bool = False,
        force_process_refresh: bool = False,
    ) -> dict[str, float | int | str]:
        now = time.monotonic()
        elapsed = max(now - self._previous_sample, 0.001)
        self._previous_sample = now

        processes_refreshed = self._collect_process_refresh()
        if (
            refresh_processes
            and self._process_future is None
            and (
                force_process_refresh
                or now - self._previous_process_sample >= self.process_refresh_interval
            )
        ):
            self._process_future = self._process_executor.submit(self._read_processes)
            self._previous_process_sample = now
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        disk = psutil.disk_io_counters()
        disk_read = 0 if disk is None else disk.read_bytes
        disk_write = 0 if disk is None else disk.write_bytes
        disk_read_rate = 0
        disk_write_rate = 0
        if disk is not None and self._previous_disk is not None:
            disk_read_rate = max(disk_read - self._previous_disk.read_bytes, 0) / elapsed
            disk_write_rate = max(disk_write - self._previous_disk.write_bytes, 0) / elapsed
        self._previous_disk = disk

        network = psutil.net_io_counters()
        sent_rate = 0
        received_rate = 0
        if network is not None and self._previous_network is not None:
            sent_rate = max(network.bytes_sent - self._previous_network.bytes_sent, 0) / elapsed
            received_rate = max(network.bytes_recv - self._previous_network.bytes_recv, 0) / elapsed
        self._previous_network = network

        return {
            "cpu": cpu,
            "memory_percent": memory.percent,
            "memory_used": memory.used,
            "memory_total": memory.total,
            "swap_used": swap.used,
            "disk_read_rate": disk_read_rate,
            "disk_write_rate": disk_write_rate,
            "network_sent_rate": sent_rate,
            "network_received_rate": received_rate,
            "process_count": len(self.processes),
            "uptime": time.time() - psutil.boot_time(),
            "processes_refreshed": processes_refreshed,
        }

    def _collect_process_refresh(self) -> bool:
        future = self._process_future
        if future is None or not future.done():
            return False
        self._process_future = None
        self.processes = future.result()
        cpu_totals: dict[tuple[int, float], float] = {}
        for process in self.processes:
            key = (process.pid, process.create_time)
            cpu_totals[key] = process.cpu_time
            previous = self._previous_cpu.get(key)
            if previous is not None:
                self.history[process.name] += max(process.cpu_time - previous, 0)
        self._previous_cpu = cpu_totals
        return True

    @staticmethod
    def _read_processes() -> list[ProcessInfo]:
        processes: list[ProcessInfo] = []
        running_app_pids = {
            application.processIdentifier()
            for application in NSWorkspace.sharedWorkspace().runningApplications()
            if application.activationPolicy() == NSApplicationActivationPolicyRegular
        }
        for process in psutil.process_iter(
            [
                "pid", "name", "username", "status", "memory_info", "cpu_percent",
                "create_time", "cpu_times", "exe",
            ]
        ):
            try:
                info = process.info
                cpu_times = info["cpu_times"]
                executable = info["exe"] or ""
                processes.append(
                    ProcessInfo(
                        pid=info["pid"],
                        name=info["name"] or "Unknown",
                        username=info["username"] or "—",
                        status=info["status"] or "unknown",
                        cpu=(info["cpu_percent"] or 0.0) / (psutil.cpu_count(logical=True) or 1),
                        memory=info["memory_info"].rss if info["memory_info"] else 0,
                        create_time=info["create_time"] or 0.0,
                        cpu_time=cpu_times.user + cpu_times.system if cpu_times else 0.0,
                        executable=executable,
                        is_application=info["pid"] in running_app_pids,
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return processes


def format_bytes(value: float | int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def format_rate(value: float | int) -> str:
    return f"{format_bytes(value)}/s"


def format_duration(seconds: float, language: str = "en") -> str:
    total = max(int(seconds), 0)
    hours, remainder = divmod(total, 3600)
    minutes, _ = divmod(remainder, 60)
    if hours:
        return f"{hours}{tr(' h ', language)}{minutes}{tr(' min', language)}"
    if minutes:
        return f"{minutes}{tr(' min', language)}"
    return f"{total}{tr(' s', language)}"


class MetricCard(QFrame):
    def __init__(self, title: str, color: str, detail: str = "") -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.color = QColor(color)
        self.samples: deque[float] = deque([0] * 60, maxlen=60)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 9)
        layout.setSpacing(3)

        heading = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        self.value_label = QLabel("—")
        self.value_label.setObjectName("metricValue")
        heading.addWidget(title_label)
        heading.addStretch()
        heading.addWidget(self.value_label)
        layout.addLayout(heading)

        self.chart = Sparkline(self.color, self.samples)
        layout.addWidget(self.chart, 1)
        self.detail_label = QLabel(detail)
        self.detail_label.setObjectName("muted")
        layout.addWidget(self.detail_label)

    def update_value(self, value: float, display: str, detail: str = "") -> None:
        self.samples.append(max(0, min(value, 100)))
        self.value_label.setText(display)
        if detail:
            self.detail_label.setText(detail)
        self.chart.update()


class Sparkline(QWidget):
    def __init__(self, color: QColor, samples: deque[float]) -> None:
        super().__init__()
        self.color = color
        self.grid_color = QColor("#e9edf2")
        self.samples = samples
        self.setMinimumHeight(78)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 8, -2, -8)
        values = list(self.samples)
        if len(values) >= 2:
            points = [
                (
                    rect.left() + rect.width() * index / (len(values) - 1),
                    rect.bottom() - rect.height() * min(value, 100) / 100,
                )
                for index, value in enumerate(values)
            ]
            area = QPainterPath()
            area.moveTo(points[0][0], rect.bottom())
            area.lineTo(points[0][0], points[0][1])
            for point in points[1:]:
                area.lineTo(point[0], point[1])
            area.lineTo(points[-1][0], rect.bottom())
            area.closeSubpath()
            fill = QColor(self.color)
            fill.setAlpha(25)
            painter.fillPath(area, fill)

            line = QPainterPath()
            line.moveTo(points[0][0], points[0][1])
            for point in points[1:]:
                line.lineTo(point[0], point[1])
            painter.setPen(QPen(self.color, 2))
            painter.drawPath(line)

        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DashLine))
        for fraction in (0.25, 0.5, 0.75):
            y = rect.top() + rect.height() * fraction
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))


class ProportionalTable(QTableWidget):
    def __init__(self, columns: int) -> None:
        super().__init__(0, columns)
        self._column_weights: tuple[float, ...] | None = None

    def set_column_weights(self, weights: tuple[float, ...]) -> None:
        if len(weights) != self.columnCount():
            raise ValueError("Column weights must match the table column count")
        self._column_weights = weights
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._resize_weighted_columns()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_weighted_columns()

    def _resize_weighted_columns(self) -> None:
        if self._column_weights is None:
            return
        visible_columns = [
            index for index, weight in enumerate(self._column_weights)
            if weight > 0 and not self.isColumnHidden(index)
        ]
        if not visible_columns:
            return
        available_width = max(self.viewport().width() - len(visible_columns), 0)
        total_weight = sum(self._column_weights[index] for index in visible_columns)
        assigned_width = 0
        for column in visible_columns[:-1]:
            width = int(available_width * self._column_weights[column] / total_weight)
            self.setColumnWidth(column, width)
            assigned_width += width
        self.setColumnWidth(visible_columns[-1], available_width - assigned_width)


def make_table(
    headers: list[str],
    language: str,
    stretch_last: bool = True,
    column_weights: tuple[float, ...] | None = None,
) -> QTableWidget:
    table = (
        ProportionalTable(len(headers))
        if column_weights is not None
        else QTableWidget(0, len(headers))
    )
    table.setHorizontalHeaderLabels([tr(header, language) for header in headers])
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(29)
    header = table.horizontalHeader()
    header.setHighlightSections(False)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    for column, label in enumerate(headers):
        width = min(max(table.fontMetrics().horizontalAdvance(tr(label, language)) + 24, 72), 220)
        table.setColumnWidth(column, width)
    if "PID" in headers:
        pid_column = headers.index("PID")
        minimum_pid_width = table.fontMetrics().horizontalAdvance("88888888") + 16
        table.setColumnWidth(pid_column, max(table.columnWidth(pid_column), minimum_pid_width))
    if stretch_last:
        table.horizontalHeader().setStretchLastSection(True)
    if column_weights is not None:
        assert isinstance(table, ProportionalTable)
        table.set_column_weights(column_weights)
    table.setSortingEnabled(True)
    return table


class SortableItem(QTableWidgetItem):
    def __init__(self, text: str, sort_value) -> None:
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class HotkeyBridge(QObject):
    activated = Signal()
    failed = Signal(str)


class BackgroundTaskBridge(QObject):
    finished = Signal(str, object, object)


class MainWindow(QMainWindow):
    GROUP_ROW_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("m-task-manager")
        self.setMinimumSize(740, 480)
        self.resize(980, 620)
        self.language = system_language()
        self.dark_mode = self._system_prefers_dark()
        self.metric_cards: dict[str, MetricCard] = {}
        self.monitor = SystemMonitor()
        self.section = "Processes"
        self.latest_stats: dict[str, float | int | str] = {}
        self.search_text = ""
        self.process_table_signatures: dict[str, tuple[object, ...]] = {}
        self.others_expanded = False
        self.process_details: dict[tuple[int, float], tuple[int, str]] = {}
        self.process_icons: dict[str, QIcon] = {}
        self.icon_provider = QFileIconProvider()
        self.startup_items: list[StartupItem] = []
        self._startup_loaded = False
        self.service_entries: list[tuple[str, str, str]] = []
        self._services_loaded = False
        self._background_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="system-inventory"
        )
        self._background_tasks: set[str] = set()
        self.pages: dict[str, QWidget] = {}
        self._initial_process_scan_pending = True
        self._process_refresh_fast_poll = False
        self._build_shell()
        self._apply_style()
        QApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.background_bridge = BackgroundTaskBridge(self)
        self.background_bridge.finished.connect(self._background_task_finished)
        if getattr(sys, "frozen", False):
            self._submit_background("hotkey-agent", install_hotkey_agent)
        else:
            self.hotkey_bridge = HotkeyBridge(self)
            self.hotkey_bridge.activated.connect(self._activate_window)
            self.hotkey_bridge.failed.connect(self._hotkey_failed)
            self._start_hotkey_listener()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.setInterval(250)
        self.timer.start()
        self.show_section("Processes")

    def _start_hotkey_listener(self) -> None:
        activate = self.hotkey_bridge.activated.emit
        hotkeys = {
            f"<{command}>+<{option}>+<backspace>": activate
            for command in ("cmd_l", "cmd_r")
            for option in ("alt_l", "alt_r")
        }
        self.hotkey_listener = keyboard.GlobalHotKeys(hotkeys)
        self.hotkey_listener.start()
        self.hotkey_monitor = threading.Thread(
            target=self._monitor_hotkey_listener,
            name="m-task-manager-hotkey",
            daemon=True,
        )
        self.hotkey_monitor.start()

    def _monitor_hotkey_listener(self) -> None:
        try:
            self.hotkey_listener.wait()
            self.hotkey_listener.join()
        except (OSError, RuntimeError) as error:
            self.hotkey_bridge.failed.emit(str(error))

    def _activate_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _hotkey_failed(self, error: str) -> None:
        message = tr("Global shortcut is unavailable: {error}", self.language).format(error=error)
        permission_hint = tr(
            "Allow m-task-manager in macOS Privacy & Security > Accessibility, then restart the app.",
            self.language,
        )
        self.statusBar().showMessage(f"{message} {permission_hint}")


    def _build_shell(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        main = QVBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 12, 18, 14)
        content_layout.setSpacing(10)

        navigation = QHBoxLayout()
        navigation.setSpacing(4)
        self.nav_buttons: dict[str, QPushButton] = {}
        for name, icon in SECTIONS:
            button = QPushButton(f"{icon}  {tr(name, self.language)}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, section=name: self.show_section(section))
            self.nav_buttons[name] = button
            navigation.addWidget(button)
        navigation.addStretch()
        content_layout.addLayout(navigation)

        top = QHBoxLayout()
        title_stack = QVBoxLayout()
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_description = QLabel()
        self.page_description.setObjectName("muted")
        title_stack.addWidget(self.page_title)
        title_stack.addWidget(self.page_description)
        top.addLayout(title_stack)
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search by name or PID", self.language))
        self.search.setFixedWidth(190)
        self.search.textChanged.connect(self._search_changed)
        top.addWidget(self.search)
        self.startup_toggle_button = QPushButton()
        self.startup_toggle_button.setObjectName("primaryButton")
        self.startup_toggle_button.clicked.connect(self.toggle_startup_item)
        top.addWidget(self.startup_toggle_button)
        self.refresh_button = QPushButton(tr("Refresh", self.language))
        self.refresh_button.clicked.connect(self.refresh_current_section)
        top.addWidget(self.refresh_button)
        content_layout.addLayout(top)
        self.page_stack = QStackedWidget()
        content_layout.addWidget(self.page_stack, 1)
        main.addWidget(content, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(tr("Ready", self.language))

    def _apply_style(self) -> None:
        colors = (
            {
                "background": "#202124",
                "sidebar": "#191a1c",
                "border": "#34363a",
                "text": "#e8eaed",
                "muted": "#a0a5ad",
                "nav_text": "#c5c9d0",
                "nav_hover": "#2b2d31",
                "nav_selected": "#263b57",
                "nav_selected_text": "#9cc6ff",
                "input": "#292b2f",
                "surface": "#25272b",
                "surface_border": "#35373c",
                "table_alt": "#292b2f",
                "header": "#292b2f",
                "selection": "#324762",
                "selection_text": "#f0f5fc",
                "status": "#202124",
                "grid": "#41444a",
            }
            if self.dark_mode
            else {
                "background": "#f5f6f8",
                "sidebar": "#eef0f4",
                "border": "#e1e4e9",
                "text": "#20242b",
                "muted": "#737b87",
                "nav_text": "#454c57",
                "nav_hover": "#e4e7ed",
                "nav_selected": "#dce9ff",
                "nav_selected_text": "#145fc3",
                "input": "#ffffff",
                "surface": "#ffffff",
                "surface_border": "#e7e9ed",
                "table_alt": "#fafbfd",
                "header": "#f7f8fa",
                "selection": "#e1edff",
                "selection_text": "#17212f",
                "status": "#f5f6f8",
                "grid": "#e9edf2",
            }
        )
        for card in self.metric_cards.values():
            card.chart.grid_color = QColor(colors["grid"])
            card.chart.update()
        self.setStyleSheet(
            f"""
            QWidget#root, QWidget#content {{ background: {colors["background"]}; color: {colors["text"]}; }}
            QLabel#pageTitle {{ font-size: 21px; font-weight: 700; }}
            QLabel#muted {{ color: {colors["muted"]}; font-size: 11px; }}
            QPushButton#navButton {{
                text-align: center; border: 0; border-radius: 6px;
                padding: 8px 10px; color: {colors["nav_text"]}; font-size: 12px;
            }}
            QPushButton#navButton:hover {{ background: {colors["nav_hover"]}; }}
            QPushButton#navButton:checked {{
                background: {colors["nav_selected"]}; color: {colors["nav_selected_text"]};
                font-weight: 600; border-bottom: 2px solid #1677e8;
            }}
            QPushButton#primaryButton, QPushButton#endTaskButton {{
                background: #1677e8; color: white; border: 0; border-radius: 6px;
                padding: 7px 12px; font-weight: 600;
            }}
            QPushButton#primaryButton:hover, QPushButton#endTaskButton:hover {{ background: #0968d5; }}
            QPushButton#primaryButton:disabled, QPushButton#endTaskButton:disabled {{
                background: #636a74; color: #d7dbe0;
            }}
            QPushButton#forceEndTaskButton {{
                background: {colors["header"]}; color: {colors["text"]};
                border: 1px solid {colors["border"]}; border-radius: 6px;
                padding: 7px 12px; font-weight: 600;
            }}
            QPushButton#forceEndTaskButton:hover {{ background: {colors["nav_hover"]}; }}
            QPushButton#forceEndTaskButton:disabled {{ color: {colors["muted"]}; }}
            QLineEdit, QComboBox {{
                background: {colors["input"]}; color: {colors["text"]};
                border: 1px solid {colors["border"]}; border-radius: 6px;
                padding: 6px 8px; selection-background-color: #1677e8;
            }}
            QFrame#surface, QFrame#metricCard {{
                background: {colors["surface"]}; border: 1px solid {colors["surface_border"]}; border-radius: 8px;
            }}
            QLabel#cardTitle {{ color: {colors["muted"]}; font-size: 12px; font-weight: 600; }}
            QLabel#metricValue {{ font-size: 17px; font-weight: 700; }}
            QTableWidget {{
                background: {colors["surface"]}; color: {colors["text"]};
                alternate-background-color: {colors["table_alt"]}; border: 0;
                gridline-color: {colors["border"]}; selection-background-color: {colors["selection"]};
                selection-color: {colors["selection_text"]};
            }}
            QHeaderView::section {{
                background: {colors["header"]}; color: {colors["muted"]}; border: 0;
                border-bottom: 1px solid {colors["border"]}; padding: 7px 6px; font-weight: 600;
            }}
            QStatusBar {{ background: {colors["status"]}; color: {colors["muted"]}; }}
            """
        )

    @staticmethod
    def _system_prefers_dark() -> bool:
        hints = QApplication.styleHints()
        if hints.colorScheme() == Qt.ColorScheme.Dark:
            return True
        if hints.colorScheme() == Qt.ColorScheme.Light:
            return False
        return QApplication.palette().color(QApplication.palette().ColorRole.Window).lightnessF() < 0.5

    def _system_theme_changed(self, _scheme: Qt.ColorScheme) -> None:
        self.dark_mode = self._system_prefers_dark()
        self._apply_style()

    def show_section(self, section: str) -> None:
        self.section = section
        for name, button in self.nav_buttons.items():
            button.setChecked(name == section)

        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.search_text = ""
        self.others_expanded = False
        self.search.setVisible(section in ("Processes", "Details"))
        self.startup_toggle_button.setVisible(section == "Startup apps")
        self.refresh_button.setVisible(section in ("Startup apps", "Services"))

        descriptions = {
            "Processes": "See what is running and how much of your Mac it is using.",
            "Performance": "Live system resource usage and activity.",
            "App history": "CPU time observed since m-task-manager was opened.",
            "Startup apps": "Launch agents and daemons registered on this Mac.",
            "Users": "Logged-in accounts and their running processes.",
            "Details": "Detailed, sortable information for every process.",
            "Services": "Services registered with macOS launchd.",
        }
        self.page_title.setText(tr(section, self.language))
        self.page_description.setText(tr(descriptions[section], self.language))
        if section not in self.pages:
            page = self._build_page(section)
            self.pages[section] = page
            self.page_stack.addWidget(page)
        self.page_stack.setCurrentWidget(self.pages[section])
        self._update_process_action_state()
        self.refresh()

    def _build_page(self, section: str) -> QWidget:
        if section == "Performance":
            return self._performance_page()
        if section == "App history":
            return self._history_page()
        if section == "Startup apps":
            return self._startup_page()
        if section == "Users":
            return self._users_page()
        if section == "Services":
            return self._services_page()
        return self._process_page(details=section == "Details")

    @staticmethod
    def _surface() -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("surface")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        return frame, layout

    def _process_page(self, details: bool = False) -> QWidget:
        frame, layout = self._surface()
        headers = (
            ["Name", "PID", "User", "Status", "CPU", "Memory", "Threads", "Path"]
            if details
            else ["Name", "CPU", "Memory", "Disk", "Network", "GPU", "PID"]
        )
        weights = None if details else (2, 1, 1, 1, 1, 1, 0)
        table = make_table(
            headers,
            self.language,
            stretch_last=details,
            column_weights=weights,
        )
        if not details:
            table.setColumnHidden(6, True)
            table.horizontalHeaderItem(3).setToolTip(
                tr("Per-process disk activity is not exposed by macOS.", self.language)
            )
            table.horizontalHeaderItem(4).setToolTip(
                tr("Per-process network activity is not exposed by macOS.", self.language)
            )
            table.horizontalHeaderItem(5).setToolTip(
                tr("Per-process GPU activity is not exposed by macOS.", self.language)
            )
        table.setObjectName("processTable")
        table.cellClicked.connect(self._process_group_clicked)
        if details:
            table.itemSelectionChanged.connect(self._process_selection_changed)
        else:
            table.itemSelectionChanged.connect(self._update_process_action_state)
        memory_column = 5 if details else 2
        table.horizontalHeader().setSortIndicator(memory_column, Qt.SortOrder.DescendingOrder)
        table.horizontalHeader().sortIndicatorChanged.connect(self._process_sort_changed)
        layout.addWidget(table)
        actions = QHBoxLayout()
        actions.addStretch()
        end_button = QPushButton(tr("End task", self.language))
        end_button.clicked.connect(self.end_selected_process)
        force_button = QPushButton(tr("Force end task", self.language))
        force_button.clicked.connect(self.force_end_selected_process)
        for button, object_name in (
            (end_button, "endTaskButton"),
            (force_button, "forceEndTaskButton"),
        ):
            button.setObjectName(object_name)
            button.setEnabled(False)
            actions.addWidget(button)
        layout.addLayout(actions)
        frame.table = table
        return frame

    def _performance_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        grid = QHBoxLayout()
        grid.setSpacing(10)
        left = QVBoxLayout()
        right = QVBoxLayout()
        left.setSpacing(10)
        right.setSpacing(10)
        self.metric_cards = {
            "cpu": MetricCard(tr("CPU", self.language), "#2583e8"),
            "memory": MetricCard(tr("Memory", self.language), "#9467dc"),
            "disk": MetricCard(tr("Disk activity", self.language), "#e7a12d"),
            "network": MetricCard(tr("Network", self.language), "#22a482"),
        }
        left.addWidget(self.metric_cards["cpu"], 1)
        left.addWidget(self.metric_cards["memory"], 1)
        right.addWidget(self.metric_cards["disk"], 1)
        right.addWidget(self.metric_cards["network"], 1)
        grid.addLayout(left, 1)
        grid.addLayout(right, 1)
        outer.addLayout(grid, 1)

        summary = QFrame()
        summary.setObjectName("surface")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(18, 14, 18, 14)
        self.performance_summary = QLabel(tr("Collecting system information…", self.language))
        self.performance_summary.setObjectName("muted")
        summary_layout.addWidget(self.performance_summary)
        outer.addWidget(summary)
        return container

    def _history_page(self) -> QWidget:
        frame, layout = self._surface()
        table = make_table(
            ["App / process", "CPU time observed"],
            self.language,
            stretch_last=False,
            column_weights=(4, 1),
        )
        table.setObjectName("historyTable")
        layout.addWidget(table)
        frame.table = table
        return frame

    def _startup_page(self) -> QWidget:
        frame, layout = self._surface()
        table = make_table(["Name", "Type", "Status", "Details label"], self.language)
        header = table.horizontalHeader()
        for column in range(3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        table.setObjectName("startupTable")
        table.itemSelectionChanged.connect(self._startup_selection_changed)
        layout.addWidget(table)
        frame.table = table
        return frame

    def _users_page(self) -> QWidget:
        frame, layout = self._surface()
        table = make_table(["Full name", "Account", "Processes", "CPU", "Memory"], self.language)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setObjectName("usersTable")
        layout.addWidget(table)
        frame.table = table
        return frame

    def _services_page(self) -> QWidget:
        frame, layout = self._surface()
        table = make_table(["PID", "Status", "Service"], self.language)
        table.setObjectName("servicesTable")
        layout.addWidget(table)
        frame.table = table
        return frame

    def _search_changed(self, text: str) -> None:
        self.search_text = text.casefold().strip()
        if self.section == "Processes":
            self.others_expanded = bool(self.search_text)
            self._update_process_table(details=False)
        elif self.section == "Details":
            self.others_expanded = bool(self.search_text)
            self._update_process_table(details=True)

    def _process_sort_changed(self, _column: int, _order: Qt.SortOrder) -> None:
        if self.section in ("Processes", "Details"):
            self.process_table_signatures.pop(self.section, None)
            self._update_process_table(details=self.section == "Details")

    def refresh_current_section(self) -> None:
        if self.section == "Services":
            self._services_loaded = False
        self.refresh(refresh_section=True)

    def refresh(
        self,
        refresh_section: bool = False,
        force_process_refresh: bool = False,
    ) -> None:
        wants_processes = self.section in ("Processes", "Details", "App history", "Users")
        try:
            self.latest_stats = self.monitor.sample(
                refresh_processes=wants_processes,
                force_process_refresh=force_process_refresh,
            )
        except (OSError, psutil.Error) as error:
            self.statusBar().showMessage(
                tr("Could not refresh system data: {error}", self.language).format(error=error)
            )
            return
        processes_refreshed = bool(self.latest_stats["processes_refreshed"])
        if processes_refreshed and (
            self._initial_process_scan_pending or self._process_refresh_fast_poll
        ):
            self._initial_process_scan_pending = False
            self._process_refresh_fast_poll = False
            self.timer.setInterval(1500)
        self.statusBar().showMessage(
            f"{self.latest_stats['process_count']} {tr('processes', self.language)}  ·  "
            f"{tr('Uptime', self.language)} {format_duration(float(self.latest_stats['uptime']), self.language)}"
        )
        if self.section == "Performance":
            self._update_performance()
        elif self.section == "Processes":
            if (
                processes_refreshed
                or self.section not in self.process_table_signatures
                or self.process_table_signatures[self.section][0] != self.search_text
            ):
                self._update_process_table(details=False)
        elif self.section == "Details":
            if (
                processes_refreshed
                or self.section not in self.process_table_signatures
                or self.process_table_signatures[self.section][0] != self.search_text
            ):
                self._update_process_table(details=True)
        elif self.section == "App history":
            if processes_refreshed or refresh_section:
                self._update_history()
        elif self.section == "Startup apps":
            if (refresh_section or not self._startup_loaded) and "startup" not in self._background_tasks:
                self._update_startup()
        elif self.section == "Users":
            if processes_refreshed or refresh_section:
                self._update_users()
        elif self.section == "Services":
            if (refresh_section or not self._services_loaded) and "services" not in self._background_tasks:
                self._update_services()

    def _submit_background(self, task_name: str, function: Callable[[], object]) -> None:
        if task_name in self._background_tasks:
            return
        self._background_tasks.add(task_name)
        future = self._background_executor.submit(function)

        def finish(completed: Future) -> None:
            try:
                result = completed.result()
            except Exception as error:
                self.background_bridge.finished.emit(task_name, None, error)
            else:
                self.background_bridge.finished.emit(task_name, result, None)

        future.add_done_callback(finish)

    def _background_task_finished(self, task_name: str, result: object, error: object) -> None:
        self._background_tasks.discard(task_name)
        if error is not None:
            if task_name == "startup":
                message = tr("Could not read startup items: {error}", self.language)
            elif task_name == "services":
                message = tr("Could not read launchd services: {error}", self.language)
            elif task_name == "startup-action":
                message = tr("Could not update startup item: {error}", self.language)
            elif task_name == "hotkey-agent":
                message = tr("Could not start the global shortcut: {error}", self.language)
            elif task_name.startswith("process-details:"):
                message = tr("Could not read process details: {error}", self.language)
            elif task_name.startswith(("end-process:", "force-process:")):
                message_key = (
                    "Could not force quit process: {error}"
                    if task_name.startswith("force-process:")
                    else "Could not end process: {error}"
                )
                message = tr(message_key, self.language)
            else:
                self.statusBar().showMessage(str(error))
                if task_name == "startup-action":
                    self._startup_selection_changed()
                return
            self.statusBar().showMessage(message.format(error=error))
            if task_name == "startup-action":
                self._startup_selection_changed()
            return

        if task_name == "startup":
            entries, errors = result
            self._populate_startup(entries, errors)
        elif task_name == "services":
            self.service_entries = result
            self._services_loaded = True
            self._populate_services()
        elif task_name.startswith("process-details:"):
            pid, key, details = result
            self.process_details[key] = details
            table = self._table("processTable") if self.section == "Details" else None
            if table is not None:
                process_info = next(
                    (process for process in self.monitor.processes if process.pid == pid),
                    None,
                )
                group_index = 1 if process_info and process_info.is_application else 3
                rank = self._sort_group_rank(
                    group_index, table.horizontalHeader().sortIndicatorOrder()
                )
                for row in range(table.rowCount()):
                    pid_item = table.item(row, 1)
                    if pid_item is not None and pid_item.text() == str(pid):
                        for column, value in ((6, str(details[0]) if details[0] else "—"), (7, details[1])):
                            item = table.item(row, column)
                            if item is not None:
                                raw_value = details[column - 6]
                                item.sort_value = (
                                    rank,
                                    raw_value.casefold() if isinstance(raw_value, str) else raw_value,
                                )
                                item.setText(value)
                        break
        elif task_name == "startup-action":
            self.statusBar().showMessage(
                tr("Updated startup item “{name}”.", self.language).format(name=result)
            )
            self._startup_loaded = False
            self._update_startup()
        elif task_name.startswith("end-process:"):
            pid, process_name, return_code = result
            if return_code is None:
                self.statusBar().showMessage(
                    tr("“{name}” is still running.", self.language).format(name=process_name)
                )
            else:
                self.statusBar().showMessage(
                    tr("Sent a quit signal to {name} (PID {pid}).", self.language).format(
                        name=process_name, pid=pid
                    )
                )
                self._refresh_processes_after_action()
        elif task_name.startswith("force-process:"):
            self.statusBar().showMessage(
                tr("Force quit {name} (PID {pid}).", self.language).format(
                    name=result[1], pid=result[0]
                )
            )
            self._refresh_processes_after_action()

    def _refresh_processes_after_action(self) -> None:
        self._process_refresh_fast_poll = True
        self.timer.setInterval(100)
        self.refresh(force_process_refresh=True)

    def _table(self, object_name: str) -> QTableWidget | None:
        current_page = self.page_stack.currentWidget()
        return current_page.findChild(QTableWidget, object_name) if current_page else None

    @staticmethod
    def _set_cell(
        table: QTableWidget,
        row: int,
        column: int,
        text: str,
        sort_value=None,
        icon: QIcon | None = None,
        group: str | None = None,
    ) -> None:
        item = SortableItem(text, sort_value if sort_value is not None else text.casefold())
        if icon is not None and not icon.isNull():
            item.setIcon(icon)
        if group is not None:
            item.setData(MainWindow.GROUP_ROW_ROLE, group)
        table.setItem(row, column, item)

    def _process_icon(self, executable: str) -> QIcon | None:
        if not executable:
            return None
        executable_path = Path(executable)
        app_bundle = next(
            (path for path in (executable_path, *executable_path.parents) if path.suffix == ".app"),
            None,
        )
        if app_bundle is None:
            return None
        bundle_path = str(app_bundle)
        if bundle_path not in self.process_icons:
            self.process_icons[bundle_path] = self.icon_provider.icon(QFileInfo(bundle_path))
        return self.process_icons[bundle_path]

    def _process_group_clicked(self, row: int, column: int) -> None:
        table = self._table("processTable")
        item = table.item(row, column) if table is not None else None
        if item is not None and item.data(self.GROUP_ROW_ROLE) == "others":
            table.clearSelection()
            self._update_process_action_state()
            self.others_expanded = not self.others_expanded
            self._update_process_table(details=self.section == "Details")

    @staticmethod
    def _sort_group_rank(group_index: int, order: Qt.SortOrder) -> int:
        return group_index if order == Qt.SortOrder.AscendingOrder else 3 - group_index

    def _update_process_table(self, details: bool) -> None:
        table = self._table("processTable")
        if table is None:
            return
        processes = self.monitor.processes
        pid_column = 1 if details else 6
        filtered_processes = processes
        if self.search_text:
            filtered_processes = [
                process
                for process in processes
                if self.search_text in process.name.casefold()
                or self.search_text in str(process.pid)
                or self.search_text in process.username.casefold()
            ]
        applications = [process for process in filtered_processes if process.is_application]
        others = [process for process in filtered_processes if not process.is_application]
        if details:
            if applications:
                name_width = max(
                    table.fontMetrics().horizontalAdvance(process.name) + 48
                    for process in applications
                )
            else:
                name_width = table.fontMetrics().horizontalAdvance(tr("Name", self.language)) + 24
            table.setColumnWidth(0, name_width)
        signature = (
            self.search_text,
            tuple((process.pid, process.create_time, process.is_application) for process in filtered_processes),
            self.others_expanded,
        )
        rebuild = self.process_table_signatures.get(self.section) != signature
        selected_rows = table.selectionModel().selectedRows()
        selected_pid = (
            table.item(selected_rows[0].row(), pid_column).text()
            if selected_rows and table.item(selected_rows[0].row(), pid_column)
            else None
        )
        order = table.horizontalHeader().sortIndicatorOrder()
        group_rank = lambda group: self._sort_group_rank(group, order)
        if rebuild:
            table.setSortingEnabled(False)
            visible_processes = applications + (others if self.others_expanded else [])
            group_headers = int(bool(applications)) + int(bool(others))
            table.setRowCount(len(visible_processes) + group_headers)
            row = 0
            if applications:
                self._add_process_group_row(
                    table,
                    row,
                    tr("Apps ({count})", self.language).format(count=len(applications)),
                    group_rank(0),
                )
                row += 1
            for process in applications:
                self._add_process_row(table, row, process, details, group_rank(1))
                row += 1
            if others:
                label = tr("Others ({count})", self.language).format(count=len(others))
                marker = "▾" if self.others_expanded else "▸"
                self._add_process_group_row(
                    table, row, f"{marker}  {label}", group_rank(2), group="others"
                )
                row += 1
            if self.others_expanded:
                for process in others:
                    self._add_process_row(table, row, process, details, group_rank(3))
                    row += 1
            self.process_table_signatures[self.section] = signature
            table.setSortingEnabled(True)
        else:
            rows_by_pid = {
                int(table.item(row, pid_column).text()): row
                for row in range(table.rowCount())
                if table.item(row, pid_column) is not None
                and table.item(row, pid_column).text().isdigit()
            }
            pending_updates: list[tuple[int, int, str, object, QTableWidgetItem]] = []
            sort_section = table.horizontalHeader().sortIndicatorSection()
            for process in applications + (others if self.others_expanded else []):
                row = rows_by_pid.get(process.pid)
                if row is None:
                    continue
                if details:
                    values = [
                        process.name,
                        str(process.pid),
                        process.username,
                        self._localized_status(process.status),
                        f"{process.cpu:.1f}%",
                        format_bytes(process.memory),
                        str(self.process_details.get((process.pid, process.create_time), (0, "—"))[0]),
                        self.process_details.get((process.pid, process.create_time), (0, "—"))[1],
                    ]
                    raw_sort_values = [
                        process.name.casefold(), process.pid, process.username.casefold(),
                        process.status, process.cpu, process.memory,
                        self.process_details.get((process.pid, process.create_time), (0, "—"))[0],
                        self.process_details.get((process.pid, process.create_time), (0, "—"))[1].casefold(),
                    ]
                    data_columns = (0, 2, 3, 4, 5)
                else:
                    values = [
                        process.name,
                        f"{process.cpu:.1f}%",
                        format_bytes(process.memory),
                        "—",
                        "—",
                        "—",
                        str(process.pid),
                    ]
                    raw_sort_values = [
                        process.name.casefold(), process.cpu,
                        process.memory, 0, 0, 0, process.pid,
                    ]
                    data_columns = (0, 1, 2, 3, 4, 5)
                rank = group_rank(1 if process.is_application else 3)
                for column in data_columns:
                    item = table.item(row, column)
                    sort_value = (rank, raw_sort_values[column])
                    text = values[column]
                    if item is not None and (item.text() != text or item.sort_value != sort_value):
                        pending_updates.append((row, column, text, sort_value, item))
                self._apply_usage_heatmap(table, row, process, details)
            resort = any(column == sort_section for _, column, _, _, _ in pending_updates)
            if resort:
                table.setSortingEnabled(False)
            for _, _, text, sort_value, item in pending_updates:
                item.sort_value = sort_value
                if item.text() != text:
                    item.setText(text)
            if resort:
                table.setSortingEnabled(True)

        if selected_pid is not None and rebuild:
            for row in range(table.rowCount()):
                item = table.item(row, pid_column)
                if item is not None and item.text() == selected_pid:
                    table.selectRow(row)
                    break
        self._update_process_action_state()

    def _add_process_group_row(
        self,
        table: QTableWidget,
        row: int,
        label: str,
        rank: int,
        group: str | None = None,
    ) -> None:
        for column in range(table.columnCount()):
            text = label if column == 0 else ""
            self._set_cell(
                table,
                row,
                column,
                text,
                (rank, text.casefold()),
                group=group if column == 0 else None,
            )

    def _add_process_row(
        self,
        table: QTableWidget,
        row: int,
        process: ProcessInfo,
        details: bool,
        rank: int,
    ) -> None:
        detail_values = self.process_details.get((process.pid, process.create_time), (0, "—"))
        if details:
            values = [
                process.name,
                str(process.pid),
                process.username,
                self._localized_status(process.status),
                f"{process.cpu:.1f}%",
                format_bytes(process.memory),
                str(detail_values[0]) if detail_values[0] else "—",
                detail_values[1],
            ]
            sort_values = [
                process.name.casefold(), process.pid, process.username.casefold(),
                process.status, process.cpu, process.memory, detail_values[0],
                detail_values[1].casefold(),
            ]
        else:
            values = [
                process.name,
                f"{process.cpu:.1f}%",
                format_bytes(process.memory),
                "—",
                "—",
                "—",
                str(process.pid),
            ]
            sort_values = [
                process.name.casefold(), process.cpu,
                process.memory, 0, 0, 0, process.pid,
            ]
        for column, (value, sort_value) in enumerate(zip(values, sort_values)):
            icon = self._process_icon(process.executable) if column == 0 else None
            self._set_cell(table, row, column, value, (rank, sort_value), icon)
        self._apply_usage_heatmap(table, row, process, details)

    def _apply_usage_heatmap(
        self, table: QTableWidget, row: int, process: ProcessInfo, details: bool
    ) -> None:
        cpu_column, memory_column = (4, 5) if details else (1, 2)
        total_memory = float(self.latest_stats.get("memory_total", 1))
        heat_color = QColor("#806321" if self.dark_mode else "#ffdf80")
        base_color = QColor("#25272b" if self.dark_mode else "#ffffff")
        for column, intensity in (
            (cpu_column, min(max(process.cpu / 25, 0), 1)),
            (memory_column, min(max(process.memory / total_memory / 0.1, 0), 1)),
        ):
            item = table.item(row, column)
            if item is None:
                continue
            amount = int(38 * intensity)
            color = QColor(
                base_color.red() + (heat_color.red() - base_color.red()) * amount // 38,
                base_color.green() + (heat_color.green() - base_color.green()) * amount // 38,
                base_color.blue() + (heat_color.blue() - base_color.blue()) * amount // 38,
            )
            item.setBackground(color)

    def _process_selection_changed(self) -> None:
        self._update_process_action_state()
        if self.section != "Details":
            return
        table = self._table("processTable")
        if table is None or not table.selectionModel().hasSelection():
            return
        row = table.selectionModel().selectedRows()[0].row()
        pid_item = table.item(row, 1)
        if pid_item is None:
            return
        pid = int(pid_item.text())
        process_info = next((process for process in self.monitor.processes if process.pid == pid), None)
        if process_info is None:
            return
        key = (process_info.pid, process_info.create_time)
        details = self.process_details.get(key)
        if details is None:
            task_name = f"process-details:{pid}"
            if task_name in self._background_tasks:
                return

            def read_details():
                try:
                    process = psutil.Process(pid)
                    return process.num_threads(), process_info.executable or "—"
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    return 0, "—"

            self._submit_background(task_name, lambda: (pid, key, read_details()))
            return
        for column, value in ((6, str(details[0]) if details[0] else "—"), (7, details[1])):
            item = table.item(row, column)
            if item is not None:
                item.sort_value = details[column - 6]
                item.setText(value)

    def _localized_status(self, status: str) -> str:
        labels = {
            "running": "Running",
            "sleeping": "Sleeping",
            "disk-sleep": "Sleeping",
            "stopped": "Stopped",
            "tracing-stop": "Stopped",
            "zombie": "Zombie",
            "dead": "Stopped",
            "wake-kill": "Waiting",
            "waking": "Waiting",
            "parked": "Idle",
            "idle": "Idle",
            "locked": "Waiting",
            "waiting": "Waiting",
            "suspended": "Stopped",
        }
        return tr(labels.get(status.lower(), "Unknown"), self.language)

    def _update_process_action_state(self) -> None:
        if not hasattr(self, "page_stack"):
            return
        page = self.page_stack.currentWidget()
        table = self._table("processTable")
        selected = False
        if table is not None and table.selectionModel().hasSelection():
            row = table.selectionModel().selectedRows()[0].row()
            pid_column = 1 if self.section == "Details" else 6
            pid_item = table.item(row, pid_column)
            selected = pid_item is not None and pid_item.text().isdigit()
        for object_name in ("endTaskButton", "forceEndTaskButton"):
            button = page.findChild(QPushButton, object_name) if page else None
            if button is not None:
                button.setEnabled(selected)

    def _update_performance(self) -> None:
        stats = self.latest_stats
        cpu = float(stats["cpu"])
        memory_percent = float(stats["memory_percent"])
        memory_detail = (
            f"{format_bytes(stats['memory_used'])} / {format_bytes(stats['memory_total'])}"
            f"  ·  {tr('Swap', self.language)} {format_bytes(stats['swap_used'])}"
        )
        disk_read = float(stats["disk_read_rate"])
        disk_write = float(stats["disk_write_rate"])
        net_sent = float(stats["network_sent_rate"])
        net_received = float(stats["network_received_rate"])

        self.metric_cards["cpu"].update_value(
            cpu, f"{cpu:.1f}%", tr("Total processor utilization", self.language)
        )
        self.metric_cards["memory"].update_value(memory_percent, f"{memory_percent:.1f}%", memory_detail)
        self.metric_cards["disk"].update_value(
            min((disk_read + disk_write) / 1024 / 1024, 100),
            f"{format_rate(disk_read + disk_write)}",
            f"{tr('Read', self.language)} {format_rate(disk_read)}  ·  "
            f"{tr('Write', self.language)} {format_rate(disk_write)}",
        )
        self.metric_cards["network"].update_value(
            min((net_sent + net_received) / 1024 / 1024, 100),
            f"{format_rate(net_sent + net_received)}",
            f"{tr('Sent', self.language)} {format_rate(net_sent)}  ·  "
            f"{tr('Received', self.language)} {format_rate(net_received)}",
        )
        self.performance_summary.setText(
            f"{psutil.cpu_count(logical=True) or '—'} {tr('logical processors', self.language)}"
            f"     ·     {stats['process_count']} {tr('processes', self.language)}"
            f"     ·     {tr('Uptime', self.language)} "
            f"{format_duration(float(stats['uptime']), self.language)}"
        )

    def _update_history(self) -> None:
        table = self._table("historyTable")
        if table is None:
            return
        entries = sorted(self.monitor.history.items(), key=lambda entry: entry[1], reverse=True)
        table.setSortingEnabled(False)
        table.setRowCount(len(entries))
        for row, (name, seconds) in enumerate(entries):
            self._set_cell(table, row, 0, name, name.casefold())
            self._set_cell(table, row, 1, format_duration(seconds, self.language), seconds)
        table.setSortingEnabled(True)

    def _update_startup(self) -> None:
        self._submit_background("startup", self._read_startup_items)

    def _read_startup_items(self) -> tuple[list[StartupItem], list[str]]:
        current_gui_domain = f"gui/{os.getuid()}"
        domains = {current_gui_domain, "system"}
        disabled_by_domain: dict[str, set[str] | None] = {}
        errors: list[str] = []
        for domain in domains:
            try:
                result = subprocess.run(
                    ["launchctl", "print-disabled", domain],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                disabled_by_domain[domain] = set(
                    re.findall(r'"([^"]+)"\s*=>\s*disabled', result.stdout)
                )
            except (OSError, subprocess.SubprocessError) as error:
                disabled_by_domain[domain] = None
                errors.append(f"{domain}: {error}")

        folders = [
            (
                Path.home() / "Library/LaunchAgents",
                tr("User launch agent", self.language),
                current_gui_domain,
            ),
            (
                Path("/Library/LaunchAgents"),
                tr("System launch agent", self.language),
                current_gui_domain,
            ),
            (Path("/Library/LaunchDaemons"), tr("System launch daemon", self.language), "system"),
        ]
        entries: list[StartupItem] = []
        for folder, kind, domain in folders:
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.plist")):
                try:
                    with path.open("rb") as stream:
                        data = plistlib.load(stream)
                    name = data.get("Label", path.stem) if isinstance(data, dict) else path.stem
                except (OSError, plistlib.InvalidFileException, ValueError, ExpatError):
                    data = {}
                    name = path.stem
                app_bundle = self._startup_app_bundle(data)
                display_name = self._startup_display_name(str(name), app_bundle)
                disabled_labels = disabled_by_domain[domain]
                disabled = None if disabled_labels is None else str(name) in disabled_labels
                entries.append(
                    StartupItem(
                        name=str(name),
                        display_name=display_name,
                        kind=kind,
                        path=str(path),
                        domain=domain,
                        disabled=disabled,
                        app_bundle=app_bundle,
                    )
                )

        return entries, errors

    @staticmethod
    def _startup_app_bundle(data: object) -> str | None:
        if not isinstance(data, dict):
            return None
        candidates = []
        program = data.get("Program")
        if isinstance(program, str):
            candidates.append(program)
        arguments = data.get("ProgramArguments")
        if isinstance(arguments, list):
            candidates.extend(argument for argument in arguments[:3] if isinstance(argument, str))
        for candidate in candidates:
            path = Path(candidate)
            for parent in (path, *path.parents):
                if parent.suffix == ".app":
                    return str(parent)
        return None

    @staticmethod
    def _startup_display_name(label: str, app_bundle: str | None) -> str:
        if app_bundle:
            info_path = Path(app_bundle) / "Contents" / "Info.plist"
            try:
                with info_path.open("rb") as stream:
                    info = plistlib.load(stream)
                if isinstance(info, dict):
                    name = info.get("CFBundleDisplayName") or info.get("CFBundleName")
                    if isinstance(name, str) and name.strip():
                        return name.strip()
            except (OSError, plistlib.InvalidFileException, ValueError):
                pass

        parts = label.split(".")
        if len(parts) > 1 and parts[0].lower() in {"com", "org", "net", "io"}:
            parts.pop(0)
        return " ".join(
            word.capitalize()
            for part in parts
            for word in re.split(r"[_\-\s]+", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", part))
            if word
        )

    def _populate_startup(self, entries: list[StartupItem], errors: list[str]) -> None:
        table = self._table("startupTable")
        if table is None:
            return
        self.startup_items = entries
        table.setSortingEnabled(False)
        table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            status_key = "Unknown" if entry.disabled is None else "Disabled" if entry.disabled else "Enabled"
            values = (
                entry.display_name,
                entry.kind,
                tr(status_key, self.language),
                entry.name,
            )
            for column, value in enumerate(values):
                icon = (
                    self._process_icon(entry.app_bundle) if column == 0 else None
                )
                self._set_cell(table, row, column, value, icon=icon)
            table.item(row, 0).setToolTip(entry.path)
            table.item(row, 3).setData(Qt.ItemDataRole.UserRole, entry.path)
            table.item(row, 3).setToolTip(entry.path)
        for column in range(3):
            table.resizeColumnToContents(column)
        table.setSortingEnabled(True)
        self._startup_loaded = True
        if errors:
            self.statusBar().showMessage(
                tr("Could not read disabled startup items: {error}", self.language).format(
                    error="; ".join(errors)
                )
            )
        self._startup_selection_changed()

    def _startup_selection_changed(self) -> None:
        if not hasattr(self, "startup_toggle_button"):
            return
        table = self._table("startupTable")
        if table is None or not table.selectionModel().hasSelection():
            self.startup_toggle_button.setEnabled(False)
            self.startup_toggle_button.setText(tr("Disable", self.language))
            return
        selected_row = table.selectionModel().selectedRows()[0].row()
        name_item = table.item(selected_row, 0)
        status_item = table.item(selected_row, 2)
        if name_item is None or status_item is None:
            self.startup_toggle_button.setEnabled(False)
            return
        disabled_label = tr("Disabled", self.language)
        unknown_label = tr("Unknown", self.language)
        if status_item.text() == unknown_label:
            self.startup_toggle_button.setEnabled(False)
            self.startup_toggle_button.setText(tr("Disable", self.language))
            return
        is_disabled = status_item.text() == disabled_label
        self.startup_toggle_button.setText(
            tr("Enable" if is_disabled else "Disable", self.language)
        )
        self.startup_toggle_button.setEnabled(True)

    def _startup_item_for_row(self, row: int) -> StartupItem | None:
        table = self._table("startupTable")
        if table is None or table.item(row, 3) is None:
            return None
        path = table.item(row, 3).data(Qt.ItemDataRole.UserRole)
        return next((entry for entry in self.startup_items if entry.path == path), None)

    def toggle_startup_item(self) -> None:
        table = self._table("startupTable")
        if table is None or not table.selectionModel().hasSelection():
            self.statusBar().showMessage(tr("Select a startup item first.", self.language))
            return
        row = table.selectionModel().selectedRows()[0].row()
        item = self._startup_item_for_row(row)
        if item is None:
            self.statusBar().showMessage(tr("Select a startup item first.", self.language))
            return
        action = "enable" if item.disabled else "disable"
        prompt = "Enable “{name}” at login?" if item.disabled else "Disable “{name}” at login?"
        if not self._confirm(
            tr("Change startup item?", self.language),
            tr(prompt, self.language).format(name=item.display_name),
        ):
            return
        target = f"{item.domain}/{item.name}"
        self.startup_toggle_button.setEnabled(False)
        self.statusBar().showMessage(
            tr("Updating startup item “{name}”…", self.language).format(name=item.display_name)
        )
        self._submit_background(
            "startup-action",
            lambda: (
                self._run_launchctl_action(action, target, item.domain == "system"),
                item.display_name,
            )[1],
        )

    @staticmethod
    def _run_launchctl_action(action: str, target: str, needs_admin: bool) -> None:
        command = ["launchctl", action, target]
        if not needs_admin:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
            return
        shell_command = shlex.join(command)
        apple_script = (
            'do shell script "'
            + shell_command.replace("\\", "\\\\").replace('"', '\\"')
            + '" with administrator privileges'
        )
        subprocess.run(
            ["osascript", "-e", apple_script],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _update_users(self) -> None:
        table = self._table("usersTable")
        if table is None:
            return
        totals: dict[str, list[float | int]] = defaultdict(lambda: [0, 0.0, 0])
        for process in self.monitor.processes:
            totals[process.username][0] += 1
            totals[process.username][1] += process.cpu
            totals[process.username][2] += process.memory
        users = [
            user
            for user in pwd.getpwall()
            if user.pw_uid >= 500
            and not user.pw_name.startswith("_")
            and user.pw_shell not in {"/usr/bin/false", "/usr/sbin/nologin", "/bin/false"}
            and Path(user.pw_dir).is_dir()
        ]
        users.sort(key=lambda user: (user.pw_gecos.split(",", 1)[0] or user.pw_name).casefold())
        table.setSortingEnabled(False)
        table.setRowCount(len(users))
        for row, user in enumerate(users):
            username = user.pw_name
            full_name = user.pw_gecos.split(",", 1)[0].strip() or username
            count, cpu, memory = totals[username]
            values = [full_name, username, str(count), f"{cpu:.1f}%", format_bytes(memory)]
            sort_values = [full_name.casefold(), username.casefold(), count, cpu, memory]
            for column, (value, sort_value) in enumerate(zip(values, sort_values)):
                self._set_cell(table, row, column, value, sort_value)
        table.resizeColumnsToContents()
        table.setSortingEnabled(True)

    def _update_services(self) -> None:
        self._submit_background("services", self._read_services)

    @staticmethod
    def _read_services() -> list[tuple[str, str, str]]:
        result = subprocess.run(
            ["launchctl", "list"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        entries: list[tuple[str, str, str]] = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split("\t", 2)
            if len(parts) == 3:
                pid, status, label = parts
                entries.append((pid if pid != "-" else "—", status, label))
        return entries

    def _populate_services(self) -> None:
        table = self._table("servicesTable")
        if table is None:
            return
        table.setSortingEnabled(False)
        table.setRowCount(len(self.service_entries))
        for row, entry in enumerate(self.service_entries):
            for column, value in enumerate(entry):
                self._set_cell(table, row, column, value)
        table.setSortingEnabled(True)

    def end_selected_process(self) -> None:
        self._request_end_selected_process(force=False)

    def force_end_selected_process(self) -> None:
        self._request_end_selected_process(force=True)

    def _request_end_selected_process(self, force: bool) -> None:
        table = self._table("processTable")
        if table is None or not table.selectionModel().hasSelection():
            self.statusBar().showMessage(tr("Select a process first.", self.language))
            return
        row = table.selectionModel().selectedRows()[0].row()
        pid_column = 1 if self.section == "Details" else 6
        pid_item = table.item(row, pid_column)
        if pid_item is None:
            return
        pid = int(pid_item.text())
        process_name = table.item(row, 0).text()
        if force:
            self._submit_background(
                f"force-process:{pid}",
                lambda: self._force_end_process(pid, process_name),
            )
            return
        self._submit_background(
            f"end-process:{pid}",
            lambda: self._terminate_process(pid, process_name),
        )

    @staticmethod
    def _terminate_process(pid: int, process_name: str) -> tuple[int, str, int | None]:
        process = psutil.Process(pid)
        process.terminate()
        try:
            return_code = process.wait(timeout=2)
        except psutil.TimeoutExpired:
            return pid, process_name, None
        return pid, process_name, return_code

    @staticmethod
    def _force_end_process(pid: int, process_name: str) -> tuple[int, str, int]:
        process = psutil.Process(pid)
        process.kill()
        return_code = process.wait(timeout=2)
        return pid, process_name, return_code

    def _confirm(self, title: str, message: str) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes
        )
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        dialog.button(QMessageBox.StandardButton.Cancel).setText(tr("Cancel", self.language))
        dialog.button(QMessageBox.StandardButton.Yes).setText(tr("Yes", self.language))
        return dialog.exec() == QMessageBox.StandardButton.Yes


def main() -> int:
    if "--hotkey-daemon" in sys.argv:
        try:
            return run_hotkey_daemon()
        except (OSError, RuntimeError) as error:
            print(f"Global shortcut listener failed: {error}", file=sys.stderr)
            return 1

    app = QApplication(sys.argv)
    app.setApplicationName("m-task-manager")
    app.setOrganizationName("m-task-manager")
    window = MainWindow()
    app.aboutToQuit.connect(window.monitor.shutdown)
    app.aboutToQuit.connect(
        lambda: window._background_executor.shutdown(wait=False, cancel_futures=True)
    )
    if hasattr(window, "hotkey_listener"):
        app.aboutToQuit.connect(window.hotkey_listener.stop)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
