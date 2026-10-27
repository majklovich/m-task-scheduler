from __future__ import annotations

import plistlib
import os
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from xml.parsers.expat import ExpatError

import psutil
from PySide6.QtCore import QLocale, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
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
    ("App history", "◷"),
    ("Startup apps", "↗"),
    ("Users", "◉"),
    ("Details", "☷"),
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
        "Live system overview\nProcesses refresh every 5 seconds": "Živý přehled systému\nProcesy se obnovují každých 5 sekund",
        "Search by name or PID": "Hledat podle názvu nebo PID",
        "End task": "Ukončit úlohu",
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
        "PID": "PID",
        "User": "Uživatel",
        "Threads": "Vlákna",
        "Path": "Cesta",
        "App / process": "Aplikace / proces",
        "CPU time observed": "Zaznamenaný čas CPU",
        "Type": "Typ",
        "Location": "Umístění",
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
        "Could not read launchd services: {error}": "Nelze načíst služby launchd: {error}",
        "Select a process first.": "Nejprve vyberte proces.",
        "Process is still running.": "Proces stále běží.",
        "End process?": "Ukončit proces?",
        "End “{name}” (PID {pid})?": "Ukončit „{name}“ (PID {pid})?",
        "Process did not exit": "Proces se neukončil",
        "“{name}” is still running. Force quit it?": "Proces „{name}“ stále běží. Vynutit jeho ukončení?",
        "Could not force quit process: {error}": "Proces nelze vynuceně ukončit: {error}",
        "Could not end process: {error}": "Proces nelze ukončit: {error}",
        "Sent a quit signal to {name} (PID {pid}).": "Procesu {name} (PID {pid}) byl odeslán signál k ukončení.",
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
    return "cs" if QLocale.system().name().lower().startswith("cs") else "en"


def tr(text: str, language: str) -> str:
    return TRANSLATIONS.get(language, {}).get(text, text)


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


@dataclass(frozen=True)
class StartupItem:
    name: str
    kind: str
    path: str
    domain: str
    disabled: bool | None


class SystemMonitor:
    def __init__(self) -> None:
        self.processes: list[ProcessInfo] = []
        self.history: dict[str, float] = defaultdict(float)
        self._previous_cpu: dict[tuple[int, float], float] = {}
        self._previous_disk = psutil.disk_io_counters()
        self._previous_network = psutil.net_io_counters()
        self._previous_sample = time.monotonic()
        self.process_refresh_interval = 5.0
        self._previous_process_sample = time.monotonic() - self.process_refresh_interval
        self._process_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="process-scan")
        self._process_future: Future[list[ProcessInfo]] | None = None
        psutil.cpu_percent(interval=None)

    def shutdown(self) -> None:
        self._process_executor.shutdown(wait=False, cancel_futures=True)

    def sample(self, refresh_processes: bool = False) -> dict[str, float | int | str]:
        now = time.monotonic()
        elapsed = max(now - self._previous_sample, 0.001)
        self._previous_sample = now

        processes_refreshed = self._collect_process_refresh()
        if (
            refresh_processes
            and self._process_future is None
            and now - self._previous_process_sample >= self.process_refresh_interval
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
        for process in psutil.process_iter(
            ["pid", "name", "username", "status", "memory_info", "cpu_percent", "create_time", "cpu_times"]
        ):
            try:
                info = process.info
                cpu_times = info["cpu_times"]
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
        painter.setPen(QPen(self.grid_color, 1, Qt.PenStyle.DashLine))
        for fraction in (0.25, 0.5, 0.75):
            y = rect.top() + rect.height() * fraction
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))

        values = list(self.samples)
        if len(values) < 2:
            return
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


def make_table(headers: list[str], language: str, stretch_last: bool = True) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels([tr(header, language) for header in headers])
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(29)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch_last:
        table.horizontalHeader().setStretchLastSection(True)
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("m-task-manager")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumSize(740, 480)
        self.resize(980, 620)
        self.language = system_language()
        self.dark_mode = self._system_prefers_dark()
        self.metric_cards: dict[str, MetricCard] = {}
        self.monitor = SystemMonitor()
        self.section = "Processes"
        self.latest_stats: dict[str, float | int | str] = {}
        self.search_text = ""
        self.process_table_signatures: dict[str, tuple[str, frozenset[tuple[int, float]]]] = {}
        self.process_details: dict[tuple[int, float], tuple[int, str]] = {}
        self.startup_items: list[StartupItem] = []
        self._startup_loaded = False
        self.service_entries: list[tuple[str, str, str]] = []
        self._services_loaded = False
        self.pages: dict[str, QWidget] = {}
        self._build_shell()
        self._apply_style()
        QApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.show_section("Processes")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)

    def _build_shell(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(178)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(10, 12, 10, 10)
        side_layout.setSpacing(3)
        brand = QLabel("m-task-manager")
        brand.setObjectName("brand")
        side_layout.addWidget(brand)
        side_layout.addSpacing(8)

        self.nav_buttons: dict[str, QPushButton] = {}
        for name, icon in SECTIONS:
            button = QPushButton(f"  {icon}    {tr(name, self.language)}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, section=name: self.show_section(section))
            self.nav_buttons[name] = button
            side_layout.addWidget(button)
        side_layout.addStretch()
        side_note = QLabel(
            tr("Live system overview\nProcesses refresh every 5 seconds", self.language)
        )
        side_note.setObjectName("muted")
        side_layout.addWidget(side_note)
        main.addWidget(sidebar)

        content = QWidget()
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 16, 18, 14)
        content_layout.setSpacing(10)

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
        self.end_task_button = QPushButton(tr("End task", self.language))
        self.end_task_button.setObjectName("primaryButton")
        self.end_task_button.clicked.connect(self.end_selected_process)
        top.addWidget(self.end_task_button)
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
            QWidget#sidebar {{ background: {colors["sidebar"]}; border-right: 1px solid {colors["border"]}; }}
            QLabel#brand {{ font-size: 13px; font-weight: 700; padding: 4px 6px; }}
            QLabel#pageTitle {{ font-size: 21px; font-weight: 700; }}
            QLabel#muted {{ color: {colors["muted"]}; font-size: 11px; }}
            QPushButton#navButton {{
                text-align: left; border: 0; border-radius: 6px; padding: 7px 6px;
                color: {colors["nav_text"]}; font-size: 12px;
            }}
            QPushButton#navButton:hover {{ background: {colors["nav_hover"]}; }}
            QPushButton#navButton:checked {{ background: {colors["nav_selected"]}; color: {colors["nav_selected_text"]}; font-weight: 600; }}
            QPushButton#primaryButton {{
                background: #1677e8; color: white; border: 0; border-radius: 6px;
                padding: 7px 12px; font-weight: 600;
            }}
            QPushButton#primaryButton:hover {{ background: #0968d5; }}
            QPushButton#primaryButton:disabled {{ background: #636a74; color: #d7dbe0; }}
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
        self.search.setVisible(section in ("Processes", "Details"))
        self.end_task_button.setVisible(section in ("Processes", "Details"))
        self.end_task_button.setEnabled(section in ("Processes", "Details"))
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
            else ["Name", "Status", "CPU", "Memory", "Disk", "Network", "PID"]
        )
        table = make_table(headers, self.language)
        if not details:
            table.horizontalHeaderItem(4).setToolTip(
                tr("Per-process disk activity is not exposed by macOS.", self.language)
            )
            table.horizontalHeaderItem(5).setToolTip(
                tr("Per-process network activity is not exposed by macOS.", self.language)
            )
        table.setObjectName("processTable")
        if details:
            table.itemSelectionChanged.connect(self._process_selection_changed)
        table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        layout.addWidget(table)
        frame.table = table
        return frame

    def _performance_page(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        summary = QFrame()
        summary.setObjectName("surface")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(18, 14, 18, 14)
        self.performance_summary = QLabel(tr("Collecting system information…", self.language))
        self.performance_summary.setObjectName("muted")
        summary_layout.addWidget(self.performance_summary)
        outer.addWidget(summary)

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
        return container

    def _history_page(self) -> QWidget:
        frame, layout = self._surface()
        table = make_table(["App / process", "CPU time observed"], self.language)
        table.setObjectName("historyTable")
        layout.addWidget(table)
        frame.table = table
        return frame

    def _startup_page(self) -> QWidget:
        frame, layout = self._surface()
        table = make_table(["Name", "Type", "Status", "Location"], self.language)
        table.setObjectName("startupTable")
        table.itemSelectionChanged.connect(self._startup_selection_changed)
        layout.addWidget(table)
        frame.table = table
        return frame

    def _users_page(self) -> QWidget:
        frame, layout = self._surface()
        table = make_table(["User", "Processes", "CPU", "Memory"], self.language)
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
            self._update_process_table(details=False)
        elif self.section == "Details":
            self._update_process_table(details=True)

    def refresh_current_section(self) -> None:
        if self.section == "Services":
            self._services_loaded = False
        self.refresh(refresh_section=True)

    def refresh(self, refresh_section: bool = False) -> None:
        wants_processes = self.section in ("Processes", "Details", "App history", "Users")
        try:
            self.latest_stats = self.monitor.sample(refresh_processes=wants_processes)
        except (OSError, psutil.Error) as error:
            self.statusBar().showMessage(
                tr("Could not refresh system data: {error}", self.language).format(error=error)
            )
            return
        processes_refreshed = bool(self.latest_stats["processes_refreshed"])
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
            if refresh_section or not self._startup_loaded:
                self._update_startup()
        elif self.section == "Users":
            if processes_refreshed or refresh_section:
                self._update_users()
        elif self.section == "Services":
            if refresh_section or not self._services_loaded:
                self._update_services()

    def _table(self, object_name: str) -> QTableWidget | None:
        current_page = self.page_stack.currentWidget()
        return current_page.findChild(QTableWidget, object_name) if current_page else None

    @staticmethod
    def _set_cell(table: QTableWidget, row: int, column: int, text: str, sort_value=None) -> None:
        item = SortableItem(text, sort_value if sort_value is not None else text.casefold())
        table.setItem(row, column, item)

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
        signature = (
            self.search_text,
            frozenset((process.pid, process.create_time) for process in filtered_processes),
        )
        rebuild = self.process_table_signatures.get(self.section) != signature
        selected_rows = table.selectionModel().selectedRows()
        selected_pid = (
            table.item(selected_rows[0].row(), pid_column).text()
            if selected_rows and table.item(selected_rows[0].row(), pid_column)
            else None
        )
        if rebuild:
            table.setSortingEnabled(False)
            table.setRowCount(len(filtered_processes))
            for row, process in enumerate(filtered_processes):
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
                        self._localized_status(process.status),
                        f"{process.cpu:.1f}%",
                        format_bytes(process.memory),
                        "—",
                        "—",
                        str(process.pid),
                    ]
                    sort_values = [
                        process.name.casefold(), process.status, process.cpu,
                        process.memory, 0, 0, process.pid,
                    ]
                for column, (value, sort_value) in enumerate(zip(values, sort_values)):
                    self._set_cell(table, row, column, value, sort_value)
            self.process_table_signatures[self.section] = signature
            table.setSortingEnabled(True)
        else:
            rows_by_pid = {
                int(table.item(row, pid_column).text()): row
                for row in range(table.rowCount())
                if table.item(row, pid_column) is not None
            }
            pending_updates: list[tuple[int, int, str, object, QTableWidgetItem]] = []
            sort_section = table.horizontalHeader().sortIndicatorSection()
            for process in filtered_processes:
                row = rows_by_pid.get(process.pid)
                if row is None:
                    continue
                if details:
                    updates = (
                        (0, process.name, process.name.casefold()),
                        (2, process.username, process.username.casefold()),
                        (3, self._localized_status(process.status), process.status),
                        (4, f"{process.cpu:.1f}%", process.cpu),
                        (5, format_bytes(process.memory), process.memory),
                    )
                else:
                    updates = (
                        (0, process.name, process.name.casefold()),
                        (1, self._localized_status(process.status), process.status),
                        (2, f"{process.cpu:.1f}%", process.cpu),
                        (3, format_bytes(process.memory), process.memory),
                    )
                for column, text, sort_value in updates:
                    item = table.item(row, column)
                    if item is not None and (
                        item.text() != text or item.sort_value != sort_value
                    ):
                        pending_updates.append((row, column, text, sort_value, item))
            resort = any(column == sort_section for _, column, _, _, _ in pending_updates)
            if resort:
                table.setSortingEnabled(False)
            for _, _, text, sort_value, item in pending_updates:
                item.sort_value = sort_value
                if item.text() != text:
                    item.setText(text)
            if resort:
                table.setSortingEnabled(True)
        if selected_pid is not None and (rebuild or (not rebuild and resort)):
            for row in range(table.rowCount()):
                item = table.item(row, pid_column)
                if item is not None and item.text() == selected_pid:
                    table.selectRow(row)
                    break
        self.end_task_button.setEnabled(table.rowCount() > 0)

    def _process_selection_changed(self) -> None:
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
            try:
                process = psutil.Process(pid)
                details = (process.num_threads(), process.exe() or "—")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                details = (0, "—")
            self.process_details[key] = details
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
        table = self._table("startupTable")
        if table is None:
            return
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
                    name = path.stem
                disabled_labels = disabled_by_domain[domain]
                disabled = None if disabled_labels is None else str(name) in disabled_labels
                entries.append(StartupItem(str(name), kind, str(path), domain, disabled))
        self.startup_items = entries
        table.setSortingEnabled(False)
        table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            status_key = "Unknown" if entry.disabled is None else "Disabled" if entry.disabled else "Enabled"
            values = (
                entry.name,
                entry.kind,
                tr(status_key, self.language),
                entry.path,
            )
            for column, value in enumerate(values):
                self._set_cell(table, row, column, value)
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
        path = table.item(row, 3).text()
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
            tr(prompt, self.language).format(name=item.name),
        ):
            return
        target = f"{item.domain}/{item.name}"
        try:
            self._run_launchctl_action(action, target, item.domain == "system")
        except (OSError, subprocess.SubprocessError) as error:
            self.statusBar().showMessage(
                tr("Could not update startup item: {error}", self.language).format(error=error)
            )
            return
        self.statusBar().showMessage(
            tr("Updated startup item “{name}”.", self.language).format(name=item.name)
        )
        self._update_startup()

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
        logged_in = {user.name for user in psutil.users()}
        users = sorted(set(totals) | logged_in)
        table.setSortingEnabled(False)
        table.setRowCount(len(users))
        for row, username in enumerate(users):
            count, cpu, memory = totals[username]
            values = [username, str(count), f"{cpu:.1f}%", format_bytes(memory)]
            sort_values = [username.casefold(), count, cpu, memory]
            for column, (value, sort_value) in enumerate(zip(values, sort_values)):
                self._set_cell(table, row, column, value, sort_value)
        table.setSortingEnabled(True)

    def _update_services(self) -> None:
        table = self._table("servicesTable")
        if table is None:
            return
        if not self._services_loaded:
            try:
                result = subprocess.run(
                    ["launchctl", "list"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except (OSError, subprocess.SubprocessError) as error:
                self.statusBar().showMessage(
                    tr("Could not read launchd services: {error}", self.language).format(error=error)
                )
                return
            entries: list[tuple[str, str, str]] = []
            for line in result.stdout.splitlines()[1:]:
                parts = line.split("\t", 2)
                if len(parts) == 3:
                    pid, status, label = parts
                    entries.append((pid if pid != "-" else "—", status, label))
            self.service_entries = entries
            self._services_loaded = True
        table.setSortingEnabled(False)
        table.setRowCount(len(self.service_entries))
        for row, entry in enumerate(self.service_entries):
            for column, value in enumerate(entry):
                self._set_cell(table, row, column, value)
        table.setSortingEnabled(True)

    def end_selected_process(self) -> None:
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
        answer = self._confirm(
            tr("End process?", self.language),
            tr("End “{name}” (PID {pid})?", self.language).format(name=process_name, pid=pid),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            process = psutil.Process(pid)
            process.terminate()
            process.wait(timeout=2)
        except psutil.TimeoutExpired:
            force = self._confirm(
                tr("Process did not exit", self.language),
                tr("“{name}” is still running. Force quit it?", self.language).format(name=process_name),
            )
            if force:
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as error:
                    self.statusBar().showMessage(
                        tr("Could not force quit process: {error}", self.language).format(error=error)
                    )
                    return
            else:
                self.statusBar().showMessage(tr("Process is still running.", self.language))
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
            self.statusBar().showMessage(
                tr("Could not end process: {error}", self.language).format(error=error)
            )
            return
        self.statusBar().showMessage(
            tr("Sent a quit signal to {name} (PID {pid}).", self.language).format(
                name=process_name, pid=pid
            )
        )
        self.refresh()

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
    app = QApplication(sys.argv)
    app.setApplicationName("m-task-manager")
    app.setOrganizationName("m-task-manager")
    window = MainWindow()
    app.aboutToQuit.connect(window.monitor.shutdown)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
