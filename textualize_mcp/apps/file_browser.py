"""File Browser Pro - Advanced dual-pane file manager with preview capabilities."""

import mimetypes
import os
from datetime import datetime
from pathlib import Path

import psutil
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive, var
from textual.widgets import Button, Collapsible, DataTable, DirectoryTree, Footer, Header, Input, Label, ProgressBar, Static

from ..core.base import AppConfig, AppStatus, BaseTextualApp, StatusWidget


class FileInfo(Static):
    """Widget to display detailed file information."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_class("file-info")

    def update_file_info(self, file_path: Path) -> None:
        """Update the file information display."""
        if not file_path.exists():
            self.update("File not found")
            return

        try:
            stat = file_path.stat()
            size = self._format_size(stat.st_size)
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            mime_type, _ = mimetypes.guess_type(str(file_path))

            info_text = f"""[bold]File:[/bold] {file_path.name}
[bold]Path:[/bold] {file_path}
[bold]Size:[/bold] {size}
[bold]Modified:[/bold] {modified}
[bold]Type:[/bold] {mime_type or 'Unknown'}
[bold]Permissions:[/bold] {oct(stat.st_mode)[-3:]}"""

            if file_path.is_dir():
                try:
                    contents = list(file_path.iterdir())
                    dir_count = sum(1 for item in contents if item.is_dir())
                    file_count = len(contents) - dir_count
                    info_text += f"\n[bold]Contents:[/bold] {dir_count} folders, {file_count} files"
                except PermissionError:
                    info_text += "\n[bold]Contents:[/bold] Permission denied"

            self.update(info_text)

        except Exception as e:
            self.update(f"Error reading file info: {e}")

    def _format_size(self, size: float) -> str:
        """Format file size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class FilePreview(VerticalScroll):
    """Widget to preview file contents."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_class("file-preview")
        self.current_file: Path | None = None

    def preview_file(self, file_path: Path) -> None:
        """Preview the contents of a file."""
        self.current_file = file_path

        if not file_path.exists() or file_path.is_dir():
            self.mount(Static("Cannot preview this item"))
            return

        # Clear current content
        self.remove_children()

        try:
            # Check file size - don't preview large files
            if file_path.stat().st_size > 1024 * 1024:  # 1MB limit
                self.mount(Static("File too large to preview (>1MB)"))
                return

            # Try to detect file type and preview accordingly
            mime_type, _ = mimetypes.guess_type(str(file_path))

            if mime_type and mime_type.startswith('text/'):
                self._preview_text_file(file_path)
            elif file_path.suffix.lower() in ['.py', '.js', '.ts', '.html', '.css', '.json', '.xml', '.yaml', '.yml']:
                self._preview_code_file(file_path)
            elif file_path.suffix.lower() in ['.md', '.txt', '.log']:
                self._preview_text_file(file_path)
            else:
                self.mount(Static(f"Binary file - {self._format_size(file_path.stat().st_size)}"))

        except Exception as e:
            self.mount(Static(f"Error previewing file: {e}"))

    def _preview_text_file(self, file_path: Path) -> None:
        """Preview a plain text file."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            # Limit preview to first 1000 lines
            lines = content.splitlines()
            if len(lines) > 1000:
                content = '\n'.join(lines[:1000]) + '\n\n... (file truncated)'

            self.mount(Static(content))
        except Exception as e:
            self.mount(Static(f"Error reading text file: {e}"))

    def _preview_code_file(self, file_path: Path) -> None:
        """Preview a code file with syntax highlighting."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            # Limit preview to first 1000 lines
            lines = content.splitlines()
            if len(lines) > 1000:
                content = '\n'.join(lines[:1000])
                truncated = True
            else:
                truncated = False

            # Try to create syntax highlighted version
            try:
                lexer = Syntax.guess_lexer(str(file_path), content)
                syntax = Syntax(content, lexer, theme="monokai", line_numbers=True)
                self.mount(Static(syntax))
                if truncated:
                    self.mount(Static("\n... (file truncated)"))
            except Exception:
                # Fallback to plain text
                self.mount(Static(content))
                if truncated:
                    self.mount(Static("\n... (file truncated)"))

        except Exception as e:
            self.mount(Static(f"Error reading code file: {e}"))

    def _format_size(self, size: float) -> str:
        """Format file size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


class FileBrowserApp(BaseTextualApp):
    """Advanced dual-pane file manager with preview capabilities."""

    APP_CONFIG = AppConfig(
        name="file_browser",
        description="Advanced dual-pane file manager with syntax highlighting and file preview",
        version="1.0.0",
        tags=["file-management", "preview", "utility"]
    )

    CSS_PATH = "file_browser.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("f", "toggle_preview", "Toggle Preview"),
        ("h", "show_hidden", "Show Hidden"),
        ("r", "refresh", "Refresh"),
        ("ctrl+n", "new_folder", "New Folder"),
        ("delete", "delete_item", "Delete"),
        ("f2", "rename_item", "Rename"),
    ]

    show_preview = var(True)
    show_hidden = var(False)
    current_path: reactive[str] = reactive("")

    def __init__(self, start_path: str = ".", **kwargs):
        super().__init__(**kwargs)
        self.start_path = Path(start_path).resolve()
        self.current_path = str(self.start_path)

    def compose(self) -> ComposeResult:
        """Compose the file browser interface."""
        yield Header()

        with Container(id="main-container"):
            with Horizontal(id="browser-panes"):
                # Left pane - Directory tree
                with Vertical(id="tree-pane"):
                    yield Label("Directory Tree", id="tree-label")
                    yield DirectoryTree(str(self.start_path), id="directory-tree")

                # Right pane - File list and preview
                with Vertical(id="content-pane"):
                    with Horizontal(id="toolbar"):
                        yield Input(placeholder="Search files...", id="search-input")
                        yield Button("Refresh", id="refresh-btn")
                        yield Button("New Folder", id="new-folder-btn")

                    with Horizontal(id="main-content"):
                        # File list
                        with Vertical(id="file-list-container"):
                            yield Label("Files", id="file-list-label")
                            yield DataTable(id="file-list")

                        # Preview pane (conditionally shown)
                        if self.show_preview:
                            with Vertical(id="preview-pane"):
                                yield Label("Preview", id="preview-label")
                                yield FilePreview(id="file-preview")
                                with Collapsible(title="File Info", id="file-info-collapsible"):
                                    yield FileInfo(id="file-info")

        with Container(id="status-container"):
            yield StatusWidget("Ready", id="status")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application."""
        self.setup_file_list()
        self.refresh_file_list()
        tree = self.query_one("#directory-tree", DirectoryTree)
        tree.focus()

    def setup_file_list(self) -> None:
        """Setup the file list table."""
        table = self.query_one("#file-list", DataTable)
        table.add_columns("Name", "Size", "Modified", "Type")
        table.cursor_type = "row"

    def refresh_file_list(self) -> None:
        """Refresh the file list for the current directory."""
        table = self.query_one("#file-list", DataTable)
        table.clear()

        try:
            current_dir = Path(self.current_path)
            if not current_dir.exists():
                self.update_status("Directory not found", "error")
                return

            items = []
            for item in current_dir.iterdir():
                if not self.show_hidden and item.name.startswith('.'):
                    continue

                try:
                    stat = item.stat()
                    size = self._format_size(stat.st_size) if item.is_file() else "-"
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    item_type = "Folder" if item.is_dir() else (item.suffix.upper()[1:] or "File")

                    items.append((item.name, size, modified, item_type, item))
                except (PermissionError, OSError):
                    items.append((item.name, "-", "-", "Unknown", item))

            # Sort: directories first, then files, both alphabetically
            items.sort(key=lambda x: (not x[4].is_dir(), x[0].lower()))

            for name, size, modified, item_type, _path in items:
                table.add_row(name, size, modified, item_type)

            self.update_status(f"Showing {len(items)} items in {current_dir}")

        except Exception as e:
            self.update_status(f"Error refreshing: {e}", "error")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle directory selection in tree."""
        self.current_path = str(event.path)
        self.refresh_file_list()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle file selection in list."""
        if event.row_key is None:
            return

        table = self.query_one("#file-list", DataTable)
        row = table.get_row(event.row_key)
        if not row:
            return

        file_name = row[0]
        file_path = Path(self.current_path) / file_name

        # Update file info
        if self.show_preview:
            file_info = self.query_one("#file-info", FileInfo)
            file_info.update_file_info(file_path)

            # Update preview
            preview = self.query_one("#file-preview", FilePreview)
            preview.preview_file(file_path)

    def action_toggle_preview(self) -> None:
        """Toggle the preview pane."""
        self.show_preview = not self.show_preview
        # Would need to re-compose to actually toggle visibility
        self.update_status(f"Preview {'enabled' if self.show_preview else 'disabled'}")

    def action_show_hidden(self) -> None:
        """Toggle showing hidden files."""
        self.show_hidden = not self.show_hidden
        self.refresh_file_list()
        self.update_status(f"Hidden files {'shown' if self.show_hidden else 'hidden'}")

    def action_refresh(self) -> None:
        """Refresh the current directory."""
        self.refresh_file_list()

    def update_status(self, message: str, status_type: str = "info") -> None:
        """Update the status bar."""
        status = self.query_one("#status", StatusWidget)
        status.update_status(message, status_type)

    def get_status(self) -> AppStatus:
        """Get current application status."""
        return AppStatus(
            app_id=self.app_id or "file_browser",
            name="File Browser Pro",
            status="running" if self.is_running else "stopped",
            start_time=datetime.now().isoformat() if self.is_running else None
        )

    def _format_size(self, size: float) -> str:
        """Format file size in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


if __name__ == "__main__":
    app = FileBrowserApp()
    app.run()
