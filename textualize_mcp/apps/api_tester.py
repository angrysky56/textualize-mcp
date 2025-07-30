"""API Tester - REST API testing and development tool."""

import asyncio
import json
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from rich.json import JSON
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive, var
from textual.widgets import Button, Collapsible, DataTable, Footer, Header, Input, Label, ProgressBar, Select, Static, TabbedContent, TabPane, TextArea

from ..core.base import AppConfig, AppStatus, BaseTextualApp, StatusWidget


class RequestHistory(Static):
    """Widget to display request history."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_class("request-history")
        self.history: list[dict[str, Any]] = []

    def add_request(self, request: dict[str, Any]) -> None:
        """Add a request to history."""
        self.history.insert(0, request)  # Most recent first
        if len(self.history) > 50:  # Limit to 50 items
            self.history = self.history[:50]
        self.update_display()

    def update_display(self) -> None:
        """Update the history display."""
        if not self.history:
            self.update("No requests yet")
            return

        history_text = []
        for _i, req in enumerate(self.history[:10]):  # Show last 10
            timestamp = req.get('timestamp', 'Unknown')
            method = req.get('method', 'GET')
            url = req.get('url', '')
            status = req.get('status_code', '?')

            # Color code status
            if isinstance(status, int):
                if 200 <= status < 300:
                    status_color = "green"
                elif 400 <= status < 500:
                    status_color = "yellow"
                elif status >= 500:
                    status_color = "red"
                else:
                    status_color = "blue"
            else:
                status_color = "white"

            history_text.append(
                f"[dim]{timestamp}[/dim] [{status_color}]{status}[/{status_color}] "
                f"[bold]{method}[/bold] {url[:50]}{'...' if len(url) > 50 else ''}"
            )

        self.update("\n".join(history_text))

    def get_request(self, index: int) -> dict[str, Any] | None:
        """Get a request from history by index."""
        if 0 <= index < len(self.history):
            return self.history[index]
        return None


class ResponseViewer(VerticalScroll):
    """Widget to display API response data."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_class("response-viewer")
        self.current_response: dict[str, Any] | None = None

    def display_response(self, response_data: dict[str, Any]) -> None:
        """Display API response data."""
        self.current_response = response_data
        self.remove_children()

        if not response_data:
            self.mount(Static("No response data"))
            return

        # Status and headers summary
        status_code = response_data.get('status_code', 'Unknown')
        elapsed_time = response_data.get('elapsed_ms', 0)
        content_type = response_data.get('headers', {}).get('content-type', 'Unknown')

        summary = f"""[bold]Response Summary[/bold]
Status: {status_code}
Time: {elapsed_time}ms
Content-Type: {content_type}
Size: {len(str(response_data.get('body', '')))} characters"""

        self.mount(Static(summary))

        # Response body
        body = response_data.get('body', '')
        headers = response_data.get('headers', {})

        # Try to format JSON responses
        if 'application/json' in content_type and body:
            try:
                if isinstance(body, str):
                    parsed_json = json.loads(body)
                else:
                    parsed_json = body

                json_widget = Static(JSON.from_data(parsed_json))
                json_widget.add_class("json-response")
                self.mount(json_widget)
            except json.JSONDecodeError:
                self.mount(Static(f"Invalid JSON response:\n{body}"))
        elif body:
            # Plain text or other content
            if len(body) > 5000:  # Truncate very large responses
                body = body[:5000] + "\n\n... (response truncated)"
            self.mount(Static(body))

        # Headers section
        if headers:
            headers_text = "\n".join([f"{k}: {v}" for k, v in headers.items()])
            self.mount(Collapsible(Static(headers_text), title="Response Headers"))


class APITesterApp(BaseTextualApp):
    """REST API testing and development tool."""

    APP_CONFIG = AppConfig(
        name="api_tester",
        description="REST API testing tool with request builder and response viewer",
        version="1.0.0",
        tags=["api", "testing", "development", "http"]
    )

    CSS_PATH = "api_tester.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("f5", "send_request", "Send Request"),
        ("ctrl+s", "save_request", "Save Request"),
        ("ctrl+l", "load_request", "Load Request"),
        ("ctrl+h", "toggle_history", "Toggle History"),
    ]

    # Reactive variables
    current_method = reactive("GET")
    current_url = reactive("")
    request_in_progress = var(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history: list[dict[str, Any]] = []
        self.saved_requests: dict[str, dict[str, Any]] = {}

    def compose(self) -> ComposeResult:
        """Compose the API tester interface."""
        yield Header()

        with Container(id="main-container"):
            with TabbedContent(id="main-tabs"):
                with TabPane("Request", id="request-tab"):
                    with Vertical(id="request-pane"):
                        # Request builder
                        with Horizontal(id="request-url-bar"):
                            yield Select([
                                ("GET", "GET"),
                                ("POST", "POST"),
                                ("PUT", "PUT"),
                                ("DELETE", "DELETE"),
                                ("PATCH", "PATCH"),
                                ("HEAD", "HEAD"),
                                ("OPTIONS", "OPTIONS"),
                            ], value="GET", id="method-select")
                            yield Input(placeholder="https://api.example.com/endpoint", id="url-input")
                            yield Button("Send", id="send-btn", variant="primary")

                        # Request body and headers
                        with Horizontal(id="request-body-section"):
                            with Vertical(id="headers-section"):
                                yield Label("Headers")
                                yield TextArea(
                                    text='{\n  "Content-Type": "application/json",\n  "Authorization": "Bearer token"\n}',
                                    language="json",
                                    id="headers-input"
                                )

                            with Vertical(id="body-section"):
                                yield Label("Request Body")
                                yield TextArea(
                                    text='{\n  "key": "value"\n}',
                                    language="json",
                                    id="body-input"
                                )

                with TabPane("Response", id="response-tab"):
                    with Vertical(id="response-pane"):
                        yield ResponseViewer(id="response-viewer")

                with TabPane("History", id="history-tab"):
                    with Vertical(id="history-pane"):
                        yield Label("Request History")
                        yield RequestHistory(id="request-history")
                        with Horizontal(id="history-controls"):
                            yield Button("Clear History", id="clear-history-btn")
                            yield Button("Export History", id="export-history-btn")

        with Container(id="status-container"):
            yield StatusWidget("Ready to test APIs", id="status")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application."""
        url_input = self.query_one("#url-input", Input)
        url_input.focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle method selection change."""
        if event.select.id == "method-select":
            self.current_method = event.value

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle URL input change."""
        if event.input.id == "url-input":
            self.current_url = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "send-btn":
            self.action_send_request()
        elif event.button.id == "clear-history-btn":
            self.clear_history()
        elif event.button.id == "export-history-btn":
            self.export_history()

    def action_send_request(self) -> None:
        """Send the current HTTP request."""
        if self.request_in_progress:
            self.update_status("Request already in progress", "warning")
            return

        if not self.current_url:
            self.update_status("Please enter a URL", "error")
            return

        self.run_worker(self.send_http_request, exclusive=True)

    async def send_http_request(self) -> None:
        """Worker to send HTTP request."""
        self.request_in_progress = True
        self.update_status("Sending request...", "info")

        try:
            # Get request data
            method = str(self.current_method)
            url = self.current_url

            # Parse headers
            headers_text = self.query_one("#headers-input", TextArea).text
            try:
                headers = json.loads(headers_text) if headers_text.strip() else {}
            except json.JSONDecodeError:
                headers = {}
                self.call_from_thread(self.update_status, "Invalid headers JSON, using empty headers", "warning")

            # Parse body
            body_text = self.query_one("#body-input", TextArea).text
            body = None
            if method in ["POST", "PUT", "PATCH"] and body_text.strip():
                try:
                    body = json.loads(body_text)
                except json.JSONDecodeError:
                    body = body_text  # Use as plain text

            # Make request
            start_time = datetime.now()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    content=body if isinstance(body, str) else None
                )

            elapsed_time = (datetime.now() - start_time).total_seconds() * 1000

            # Parse response
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text

            response_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response_body,
                "elapsed_ms": round(elapsed_time, 2),
                "url": url,
                "method": method,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }

            # Store in history
            self.history.append(response_data)

            # Update UI
            self.call_from_thread(self.display_response, response_data)
            self.call_from_thread(self.update_history_display)
            self.call_from_thread(self.switch_to_response_tab)

            # Status message
            status_msg = f"Request completed: {response.status_code} in {elapsed_time:.0f}ms"
            status_type = "success" if 200 <= response.status_code < 300 else "warning"
            self.call_from_thread(self.update_status, status_msg, status_type)

        except httpx.TimeoutException:
            self.call_from_thread(self.update_status, "Request timed out", "error")
        except httpx.RequestError as e:
            self.call_from_thread(self.update_status, f"Request error: {e}", "error")
        except Exception as e:
            self.call_from_thread(self.update_status, f"Unexpected error: {e}", "error")
        finally:
            self.request_in_progress = False

    def display_response(self, response_data: dict[str, Any]) -> None:
        """Display response in the response viewer."""
        response_viewer = self.query_one("#response-viewer", ResponseViewer)
        response_viewer.display_response(response_data)

    def update_history_display(self) -> None:
        """Update the history display."""
        history_widget = self.query_one("#request-history", RequestHistory)
        if self.history:
            history_widget.add_request(self.history[-1])

    def switch_to_response_tab(self) -> None:
        """Switch to the response tab."""
        tabs = self.query_one("#main-tabs", TabbedContent)
        tabs.active = "response-tab"

    def clear_history(self) -> None:
        """Clear request history."""
        self.history.clear()
        history_widget = self.query_one("#request-history", RequestHistory)
        history_widget.history.clear()
        history_widget.update_display()
        self.update_status("History cleared", "success")

    def export_history(self) -> None:
        """Export history to JSON (simplified implementation)."""
        if not self.history:
            self.update_status("No history to export", "warning")
            return

        # In a real implementation, this would save to a file
        # For now, just show the count
        self.update_status(f"Would export {len(self.history)} requests", "info")

    def update_status(self, message: str, status_type: str = "info") -> None:
        """Update the status bar."""
        status = self.query_one("#status", StatusWidget)
        status.update_status(message, status_type)

    def get_status(self) -> AppStatus:
        """Get current application status."""
        return AppStatus(
            app_id=self.app_id or "api_tester",
            name="API Tester",
            status="running" if self.is_running else "stopped",
            start_time=datetime.now().isoformat() if self.is_running else None
        )


if __name__ == "__main__":
    app = APITesterApp()
    app.run()
