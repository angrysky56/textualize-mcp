"""Base classes and utilities for Textual applications."""

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from textual.app import App
from textual.widgets import Static


class AppConfig(BaseModel):
    """Configuration for a Textual application."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Textualize-MCP"
    tags: list[str] = []
    requires_web: bool = False
    requires_sudo: bool = False


class AppStatus(BaseModel):
    """Status information for a running application."""
    app_id: str
    name: str
    pid: int | None = None
    status: str = "stopped"  # stopped, starting, running, error
    start_time: str | None = None
    error_message: str | None = None


class BaseTextualApp(App):
    """Base class for all Textual applications in the MCP server."""

    # Application metadata
    APP_CONFIG: AppConfig
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]

    async def get_app_specific_detailed_state(self) -> dict[str, Any]:
        """Get app-specific detailed state. Override in subclasses if needed."""
        return {}

    async def get_app_specific_state(self) -> dict[str, Any]:
        """Get app-specific state for AI interaction. Override in subclasses if needed."""
        return {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app_id: str | None = None
        self.mcp_server = None  # Reference to MCP server if running via MCP
        self.output_buffer: list[str] = []  # Buffer for capturing output
        self.session_data: dict[str, Any] = {}  # Session-specific data
        self.interactive_sessions: dict[str, dict] = {}  # Active interactive sessions

    @classmethod
    def get_config(cls) -> AppConfig:
        """Get application configuration."""
        return cls.APP_CONFIG

    @classmethod
    def get_description(cls) -> str:
        """Get application description for MCP interface."""
        return cls.APP_CONFIG.description

    def get_status(self) -> AppStatus:
        """Get current application status."""
        raise NotImplementedError("Subclasses must implement get_status()")

    def set_app_id(self, app_id: str) -> None:
        """Set the application ID (used by MCP server)."""
        self.app_id = app_id

    def set_mcp_server(self, server) -> None:
        """Set reference to MCP server."""
        self.mcp_server = server

    def notify_mcp_server(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Send notification to MCP server."""
        if self.mcp_server and hasattr(self.mcp_server, 'handle_app_event'):
            self.mcp_server.handle_app_event(self.app_id, event, data or {})

    # Interactive capabilities
    async def get_screen_state(self) -> dict[str, Any]:
        """Get the current screen state for AI interaction.

        Returns:
            Dictionary containing screen data, layout, and interactive elements
        """
        try:
            # Get basic app state
            screen_data = {
                "app_name": self.APP_CONFIG.name,
                "title": getattr(self, 'title', 'Unknown'),
                "size": {"width": self.size.width, "height": self.size.height} if hasattr(self, 'size') else None,
                "focused_widget": str(self.focused) if hasattr(self, 'focused') and self.focused else None,
                "available_actions": [getattr(binding, "action", None) for binding in self.BINDINGS],
                "output_buffer": self.output_buffer[-20:] if self.output_buffer else [],
                "timestamp": datetime.now().isoformat()
            }

            # Try to get more specific state if available
            if hasattr(self, 'get_app_specific_state'):
                specific_state = await self.get_app_specific_state()
                screen_data.update(specific_state)

            return screen_data
        except Exception as e:
            return {
                "error": f"Failed to get screen state: {e}",
                "app_name": self.APP_CONFIG.name,
                "timestamp": datetime.now().isoformat()
            }

    async def receive_input(self, input_type: str, input_data: str) -> dict[str, Any]:
        """Receive and process input from AI or external sources.

        Args:
            input_type: Type of input ('key', 'text', 'command', 'action')
            input_data: The input data to process

        Returns:
            Result of processing the input
        """
        try:
            result = {"input_type": input_type, "input_data": input_data, "processed": True}

            if input_type == "key":
                # Handle key press
                await self._handle_key_input(input_data)
                result["action"] = f"Key pressed: {input_data}"

            elif input_type == "text":
                # Handle text input
                await self._handle_text_input(input_data)
                result["action"] = f"Text entered: {input_data}"

            elif input_type == "command":
                # Handle command execution
                command_result = await self._handle_command_input(input_data)
                result["action"] = f"Command executed: {input_data}"
                result["command_result"] = command_result

            elif input_type == "action":
                # Handle action execution (like button clicks)
                action_result = await self._handle_action_input(input_data)
                result["action"] = f"Action executed: {input_data}"
                result["action_result"] = action_result

            else:
                result["processed"] = False
                result["error"] = f"Unknown input type: {input_type}"

            # Log the interaction
            self._log_interaction(input_type, input_data, result)

            return result

        except Exception as e:
            return {
                "input_type": input_type,
                "input_data": input_data,
                "processed": False,
                "error": f"Failed to process input: {e}"
            }

    async def get_detailed_state(self) -> dict[str, Any]:
        """Get detailed application state including UI state, data, and context.

        Returns:
            Comprehensive state information
        """
        try:
            state = {
                "basic_info": {
                    "app_id": self.app_id,
                    "name": self.APP_CONFIG.name,
                    "version": self.APP_CONFIG.version,
                    "status": "running" if self.is_running else "stopped"
                },
                "ui_state": await self.get_screen_state(),
                "session_data": self.session_data,
                "active_sessions": list(self.interactive_sessions.keys()),
                "capabilities": {
                    "can_receive_input": True,
                    "can_capture_screen": True,
                    "supports_sessions": True,
                    "available_actions": [getattr(binding, "action", None) for binding in self.BINDINGS]
                },
                "recent_interactions": self.output_buffer[-10:] if self.output_buffer else [],
                "timestamp": datetime.now().isoformat()
            }

            # Add app-specific state if available
            if hasattr(self, 'get_app_specific_detailed_state'):
                specific_state = await self.get_app_specific_detailed_state()
                state["app_specific"] = specific_state

            return state

        except Exception as e:
            return {
                "error": f"Failed to get detailed state: {e}",
                "app_id": self.app_id,
                "timestamp": datetime.now().isoformat()
            }

    async def create_session(self, session_id: str, session_type: str) -> dict[str, Any]:
        """Create an interactive session for real-time collaboration.

        Args:
            session_id: Unique session identifier
            session_type: Type of session ('shared', 'readonly', 'control')

        Returns:
            Session creation result and connection info
        """
        try:
            session_data = {
                "session_id": session_id,
                "session_type": session_type,
                "created_at": datetime.now().isoformat(),
                "app_id": self.app_id,
                "app_name": self.APP_CONFIG.name,
                "permissions": self._get_session_permissions(session_type),
                "status": "active"
            }

            self.interactive_sessions[session_id] = session_data

            # Initialize session-specific data
            self.session_data[session_id] = {
                "interactions": [],
                "state_snapshots": [],
                "created_at": datetime.now().isoformat()
            }

            return {
                "session_created": True,
                "session_info": session_data,
                "connection_details": {
                    "app_id": self.app_id,
                    "session_id": session_id,
                    "message": f"Interactive session ready! You can now interact with {self.APP_CONFIG.name} in real-time."
                }
            }

        except Exception as e:
            return {
                "session_created": False,
                "error": f"Failed to create session: {e}"
            }

    async def get_recent_output(self, lines: int = 50) -> dict[str, Any]:
        """Get recent output/logs from the application.

        Args:
            lines: Number of recent lines to retrieve

        Returns:
            Recent output data
        """
        try:
            recent_output = self.output_buffer[-lines:] if self.output_buffer else []

            return {
                "output_lines": recent_output,
                "total_lines": len(self.output_buffer),
                "lines_returned": len(recent_output),
                "app_name": self.APP_CONFIG.name,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            return {
                "error": f"Failed to get recent output: {e}",
                "app_name": self.APP_CONFIG.name,
                "timestamp": datetime.now().isoformat()
            }

    # Helper methods for input handling
    async def _handle_key_input(self, key_data: str) -> None:
        """Handle key press input."""
        # This would be implemented by subclasses for specific key handling
        self._log_output(f"Key pressed: {key_data}")

    async def _handle_text_input(self, text_data: str) -> None:
        """Handle text input."""
        # This would be implemented by subclasses for specific text handling
        self._log_output(f"Text entered: {text_data}")

    async def _handle_command_input(self, command_data: str) -> str:
        """Handle command input."""
        # This would be implemented by subclasses for specific command handling
        self._log_output(f"Command executed: {command_data}")
        return f"Command '{command_data}' processed"

    async def _handle_action_input(self, action_data: str) -> str:
        """Handle action input."""
        # This would be implemented by subclasses for specific action handling
        self._log_output(f"Action executed: {action_data}")
        return f"Action '{action_data}' processed"

    def _get_session_permissions(self, session_type: str) -> dict[str, bool]:
        """Get permissions for a session type."""
        if session_type == "shared":
            return {"read": True, "write": True, "control": True}
        elif session_type == "readonly":
            return {"read": True, "write": False, "control": False}
        elif session_type == "control":
            return {"read": True, "write": True, "control": True}
        else:
            return {"read": False, "write": False, "control": False}

    def _log_interaction(self, input_type: str, input_data: str, result: dict) -> None:
        """Log an interaction for debugging and session tracking."""
        log_entry = f"[{datetime.now().isoformat()}] {input_type}: {input_data} -> {result.get('action', 'unknown')}"
        self._log_output(log_entry)

    def _log_output(self, message: str) -> None:
        """Add message to output buffer."""
        self.output_buffer.append(message)
        # Keep buffer size manageable
        if len(self.output_buffer) > 1000:
            self.output_buffer = self.output_buffer[-500:]


class StatusWidget(Static):
    """Standard status widget for applications."""

    def __init__(self, initial_status: str = "Ready", **kwargs):
        super().__init__(initial_status, **kwargs)
        self.add_class("status-widget")

    def update_status(self, status: str, status_type: str = "info") -> None:
        """Update status with styling based on type."""
        self.update(status)
        # Remove existing status classes
        self.remove_class("status-info", "status-warning", "status-error", "status-success")
        # Add new status class
        self.add_class(f"status-{status_type}")


class BaseDataProvider(ABC):
    """Base class for data providers used by applications."""

    @abstractmethod
    async def fetch_data(self, **kwargs) -> Any:
        """Fetch data from the underlying source."""
        pass

    @abstractmethod
    async def refresh(self) -> None:
        """Refresh/reload data."""
        pass


class AppRegistry:
    """Registry for managing available applications."""

    _apps: dict[str, type] = {}
    _running_apps: dict[str, BaseTextualApp] = {}

    @classmethod
    def register(cls, app_class: type) -> None:
        """Register an application class."""
        config = app_class.get_config()
        cls._apps[config.name] = app_class

    @classmethod
    def get_app_class(cls, name: str) -> type | None:
        """Get application class by name."""
        return cls._apps.get(name)

    @classmethod
    def list_apps(cls) -> list[AppConfig]:
        """List all registered applications."""
        return [app_class.get_config() for app_class in cls._apps.values()]

    @classmethod
    def get_running_app(cls, app_id: str) -> BaseTextualApp | None:
        """Get running application instance."""
        return cls._running_apps.get(app_id)

    @classmethod
    def add_running_app(cls, app_id: str, app: BaseTextualApp) -> None:
        """Add running application to registry."""
        cls._running_apps[app_id] = app

    @classmethod
    def remove_running_app(cls, app_id: str) -> None:
        """Remove running application from registry."""
        cls._running_apps.pop(app_id, None)


def register_app(app_class: type):
    """Decorator to register an application."""
    AppRegistry.register(app_class)
    return app_class
