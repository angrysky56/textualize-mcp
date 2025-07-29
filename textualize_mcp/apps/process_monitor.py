"""Process Monitor Dashboard - Real-time system monitoring with process management."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive, var
from textual.widgets import Button, Collapsible, DataTable, Footer, Header, Input, Label, ProgressBar, Select, Static
from textual.worker import Worker

from ..core.base import AppConfig, AppStatus, BaseTextualApp, StatusWidget, register_app


class SystemInfo(Static):
    """Widget to display system information."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_class("system-info")

    async def update_system_info(self) -> None:
        """Update system information display."""
        try:
            # Get basic system info
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time

            # Memory info
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)

            # Disk info
            disk = psutil.disk_usage('/')

            info_text = f"""[bold]System Information[/bold]
[bold]Uptime:[/bold] {self._format_timedelta(uptime)}
[bold]Boot Time:[/bold] {boot_time.strftime('%Y-%m-%d %H:%M:%S')}

[bold]CPU:[/bold] {cpu_percent:.1f}% ({cpu_count} cores)
[bold]Load Average:[/bold] {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}

[bold]Memory:[/bold] {self._format_bytes(memory.used)} / {self._format_bytes(memory.total)} ({memory.percent:.1f}%)
[bold]Swap:[/bold] {self._format_bytes(swap.used)} / {self._format_bytes(swap.total)} ({swap.percent:.1f}%)

[bold]Disk (/):[/bold] {self._format_bytes(disk.used)} / {self._format_bytes(disk.total)} ({disk.percent:.1f}%)"""

            self.update(info_text)

        except Exception as e:
            self.update(f"Error getting system info: {e}")

    def _format_bytes(self, bytes_value: float) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"

    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta in human readable format."""
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


class ProcessDetails(VerticalScroll):
    """Widget to display detailed process information."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_class("process-details")
        self.current_pid: int | None = None

    def update_process_details(self, pid: int) -> None:
        """Update the detailed process information."""
        self.current_pid = pid
        self.remove_children()

        try:
            process = psutil.Process(pid)
            info = process.as_dict([
                'pid', 'ppid', 'name', 'exe', 'cmdline', 'cwd', 'username',
                'create_time', 'status', 'cpu_percent', 'memory_percent',
                'memory_info', 'num_threads', 'num_fds'
            ])

            # Format create time
            create_time = datetime.fromtimestamp(info['create_time'])
            runtime = datetime.now() - create_time

            # Format command line
            cmdline = ' '.join(info['cmdline']) if info['cmdline'] else 'N/A'
            if len(cmdline) > 100:
                cmdline = cmdline[:97] + "..."

            # Memory info
            memory_mb = info['memory_info'].rss / 1024 / 1024 if info['memory_info'] else 0

            details_text = f"""[bold]Process Details - PID {pid}[/bold]

[bold]Basic Info:[/bold]
  Name: {info['name']}
  PID: {info['pid']}
  PPID: {info['ppid']}
  User: {info['username']}
  Status: {info['status']}

[bold]Executable:[/bold]
  Path: {info['exe'] or 'N/A'}
  CWD: {info['cwd'] or 'N/A'}

[bold]Command Line:[/bold]
  {cmdline}

[bold]Performance:[/bold]
  CPU: {info['cpu_percent']:.1f}%
  Memory: {memory_mb:.1f} MB ({info['memory_percent']:.1f}%)
  Threads: {info['num_threads']}
  File Descriptors: {info.get('num_fds', 'N/A')}

[bold]Timing:[/bold]
  Created: {create_time.strftime('%Y-%m-%d %H:%M:%S')}
  Runtime: {self._format_timedelta(runtime)}"""

            self.mount(Static(details_text))

            # Add action buttons
            with Horizontal():
                self.mount(Button("Terminate", id="terminate-btn", variant="error"))
                self.mount(Button("Kill", id="kill-btn", variant="error"))
                self.mount(Button("Refresh", id="refresh-details-btn", variant="primary"))

        except psutil.NoSuchProcess:
            self.mount(Static("Process no longer exists"))
        except psutil.AccessDenied:
            self.mount(Static("Access denied to process information"))
        except Exception as e:
            self.mount(Static(f"Error getting process details: {e}"))

    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta in human readable format."""
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, _ = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


@register_app
class ProcessMonitorApp(BaseTextualApp):
    """Real-time system monitoring with process management capabilities."""

    APP_CONFIG = AppConfig(
        name="process_monitor",
        description="Real-time system and process monitoring with management capabilities",
        version="1.0.0",
        tags=["system", "monitoring", "processes", "performance"]
    )

    CSS_PATH = "process_monitor.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("k", "kill_process", "Kill Process"),
        ("t", "terminate_process", "Terminate Process"),
        ("f", "toggle_filter", "Filter"),
        ("s", "toggle_sort", "Sort"),
    ]

    # Reactive variables
    process_auto_refresh = var(True)
    refresh_interval = var(2.0)  # seconds
    show_system_processes = var(True)
    current_sort_column = reactive("cpu_percent")
    sort_descending = var(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.processes: list[dict[str, Any]] = []
        self.refresh_worker: Worker | None = None

    def compose(self) -> ComposeResult:
        """Compose the process monitor interface."""
        yield Header()

        with Container(id="main-container"):
            with Horizontal(id="monitor-panes"):
                # Left pane - Process list
                with Vertical(id="process-pane"):
                    with Horizontal(id="process-toolbar"):
                        yield Input(placeholder="Filter processes...", id="process-filter")
                        yield Select([
                            ("All Processes", "all"),
                            ("User Processes", "user"),
                            ("System Processes", "system"),
                        ], value="all", id="process-type-select")
                        yield Button("Kill", id="kill-btn", variant="error")
                        yield Button("Terminate", id="terminate-btn", variant="error")

                    yield Label("Processes", id="process-label")
                    yield DataTable(id="process-list")

                # Right pane - System info and process details
                with Vertical(id="info-pane"):
                    with Collapsible(title="System Information", collapsed=False, id="system-info-collapsible"):
                        yield SystemInfo(id="system-info")

                    with Collapsible(title="Process Details", collapsed=False, id="process-details-collapsible"):
                        yield ProcessDetails(id="process-details")

        with Container(id="status-container"):
            yield StatusWidget("Initializing...", id="status")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application."""
        self.setup_process_list()
        self.start_refresh_worker()
        process_list = self.query_one("#process-list", DataTable)
        process_list.focus()

    def setup_process_list(self) -> None:
        """Setup the process list table."""
        table = self.query_one("#process-list", DataTable)
        table.add_columns("PID", "Name", "CPU%", "Memory%", "Status", "User")
        table.cursor_type = "row"

    async def refresh_process_data(self) -> None:
        """Worker to refresh process data."""
        while self.process_auto_refresh:
            try:
                # Get all processes
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'username']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                self.processes = processes
                self.call_from_thread(self.update_process_list)
                self.call_from_thread(self.update_system_info)

                await asyncio.sleep(self.refresh_interval)

            except Exception as e:
                self.call_from_thread(self.update_status, f"Error refreshing: {e}", "error")
                await asyncio.sleep(self.refresh_interval)

    def start_refresh_worker(self) -> None:
        """Start the refresh worker."""
        if self.refresh_worker:
            self.refresh_worker.cancel()
        self.refresh_worker = self.run_worker(self.refresh_process_data)

    def update_process_list(self) -> None:
        """Update the process list table."""
        table = self.query_one("#process-list", DataTable)
        table.clear()

        # Apply filters
        filter_text = self.query_one("#process-filter", Input).value.lower()
        process_type = self.query_one("#process-type-select", Select).value

        filtered_processes = []
        for proc in self.processes:
            # Apply text filter
            if filter_text and filter_text not in proc['name'].lower():
                continue

            # Apply process type filter
            if process_type == "user" and proc['username'] in ['root', 'system']:
                continue
            elif process_type == "system" and proc['username'] not in ['root', 'system']:
                continue

            filtered_processes.append(proc)

        # Sort processes
        sort_key = self.current_sort_column
        filtered_processes.sort(
            key=lambda p: p.get(sort_key, 0) or 0,
            reverse=self.sort_descending
        )

        # Add to table
        for proc in filtered_processes:
            table.add_row(
                str(proc['pid']),
                proc['name'],
                f"{proc['cpu_percent']:.1f}" if proc['cpu_percent'] else "0.0",
                f"{proc['memory_percent']:.1f}" if proc['memory_percent'] else "0.0",
                proc['status'],
                proc['username'] or "Unknown"
            )

        self.update_status(f"Showing {len(filtered_processes)} processes")

    async def update_system_info(self) -> None:
        """Update system information."""
        system_info = self.query_one("#system-info", SystemInfo)
        await system_info.update_system_info()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle process selection."""
        if event.row_key is None:
            return

        table = self.query_one("#process-list", DataTable)
        row = table.get_row(event.row_key)
        if not row:
            return

        pid = int(row[0])
        details = self.query_one("#process-details", ProcessDetails)
        details.update_process_details(pid)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "kill-btn":
            self.action_kill_process()
        elif event.button.id == "terminate-btn":
            self.action_terminate_process()
        elif event.button.id == "refresh-details-btn":
            details = self.query_one("#process-details", ProcessDetails)
            if details.current_pid:
                details.update_process_details(details.current_pid)

    def action_kill_process(self) -> None:
        """Kill the selected process."""
        pid = self.get_selected_pid()
        if pid:
            self.perform_process_action(pid, "kill")

    def action_terminate_process(self) -> None:
        """Terminate the selected process."""
        pid = self.get_selected_pid()
        if pid:
            self.perform_process_action(pid, "terminate")

    def get_selected_pid(self) -> int | None:
        """Get the PID of the currently selected process."""
        table = self.query_one("#process-list", DataTable)
        if table.cursor_row is None:
            return None

        try:
            row = table.get_row(str(table.cursor_row))
            return int(row[0]) if row else None
        except (ValueError, IndexError):
            return None

    def perform_process_action(self, pid: int, action: str) -> None:
        """Perform an action on a process."""
        try:
            process = psutil.Process(pid)
            process_name = process.name()

            if action == "kill":
                process.kill()
                self.update_status(f"Killed process {process_name} (PID: {pid})", "success")
            elif action == "terminate":
                process.terminate()
                self.update_status(f"Terminated process {process_name} (PID: {pid})", "success")

        except psutil.NoSuchProcess:
            self.update_status(f"Process {pid} no longer exists", "warning")
        except psutil.AccessDenied:
            self.update_status(f"Access denied to process {pid}", "error")
        except Exception as e:
            self.update_status(f"Error {action}ing process {pid}: {e}", "error")

    def action_refresh(self) -> None:
        """Manual refresh of data."""
        self.update_status("Refreshing...", "info")
        # Trigger immediate refresh by restarting worker
        self.start_refresh_worker()

    def update_status(self, message: str, status_type: str = "info") -> None:
        """Update the status bar."""
        status = self.query_one("#status", StatusWidget)
        status.update_status(message, status_type)

    def get_status(self) -> AppStatus:
        """Get current application status."""
        return AppStatus(
            app_id=self.app_id or "process_monitor",
            name="Process Monitor Dashboard",
            status="running" if self.is_running else "stopped",
            start_time=datetime.now().isoformat() if self.is_running else None
        )


if __name__ == "__main__":
    app = ProcessMonitorApp()
    app.run()
