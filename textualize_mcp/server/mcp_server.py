"""MCP Server for Textualize Applications

Main server that provides MCP interface for managing Textual applications.
"""

import asyncio
import atexit
import json
import logging
import signal
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

# Import apps module to trigger registration decorators
from textualize_mcp import apps  # noqa: F401  # Required for app auto-registration
from textualize_mcp.core.base import AppRegistry, AppStatus, BaseTextualApp

# Configure logging to stderr for MCP servers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("textualize_mcp.server")


class AppLaunchRequest(BaseModel):
    """Request model for launching an application."""
    app_name: str
    args: dict[str, Any] = {}
    web_mode: bool = False


class AppManager:
    """Manages running Textual applications."""

    def __init__(self):
        self.running_apps: dict[str, BaseTextualApp | AppStatus] = {}
        self.app_processes: dict[str, asyncio.subprocess.Process] = {}
        self.multiplex_environments: dict[str, dict[str, Any]] = {}
        self.environment_templates = self._load_environment_templates()

    def _load_environment_templates(self) -> dict[str, list[str]]:
        """Load predefined multiplex environment templates."""
        return {
            "textual_dev": [
                "APP#green=textual serve textualize_mcp.apps.{app_name}:{app_name}App --port {port}",
                "CONSOLE#blue+1=textual console",
                "DEV+2=textual run --dev textualize_mcp.apps.{app_name}:{app_name}App",
                "BROWSER+3=xdg-open http://localhost:{port}"
            ],
            "full_stack": [
                "DB#blue|silent=mongod --quiet --dbpath /tmp/textual_db",
                "REDIS#red|silent=redis-server --port 6380",
                "API#green+2=textual serve textualize_mcp.apps.api_tester:APITesterApp --port 8001",
                "MONITOR#yellow+API=textual serve textualize_mcp.apps.process_monitor:ProcessMonitorApp --port 8002",
                "FILE_BROWSER#cyan+API=textual serve textualize_mcp.apps.file_browser:FileBrowserApp --port 8003",
                "DASHBOARD+5=xdg-open http://localhost:8001"
            ],
            "testing_pipeline": [
                "LINT#yellow=ruff check textualize_mcp/",
                "TYPE#blue+LINT=mypy textualize_mcp/",
                "TEST#green+TYPE=pytest tests/ -v",
                "COVERAGE+TEST=coverage report --show-missing",
                "CLEANUP+COVERAGE|end=echo 'Testing pipeline completed successfully'"
            ],
            "development_stack": [
                "API#green=textual serve textualize_mcp.apps.api_tester:APITesterApp --port 8001",
                "FILE_MGR#cyan+1=textual serve textualize_mcp.apps.file_browser:FileBrowserApp --port 8002",
                "PROC_MON#yellow+1=textual serve textualize_mcp.apps.process_monitor:ProcessMonitorApp --port 8003",
                "GATEWAY+3=echo 'All services running - API:8001 Files:8002 Monitor:8003'"
            ]
        }

    def generate_app_id(self) -> str:
        """Generate a unique application ID."""
        return f"app_{uuid.uuid4().hex[:8]}"

    async def launch_app(self, app_name: str, args: dict[str, Any] | None = None, web_mode: bool = False, in_process: bool = False, port: int = 8000) -> str:
        """Launch a Textual application.

        Args:
            app_name: Name of the application to launch
            args: Arguments to pass to the application
            web_mode: Whether to launch in web browser mode
            in_process: Whether to launch in same process (enables collaborative features)
            port: Port for web mode
        """
        app_class = AppRegistry.get_app_class(app_name)
        if not app_class:
            raise ValueError(f"Unknown application: {app_name}")

        app_id = self.generate_app_id()

        try:
            # Create application instance
            app_args = args or {}
            app = app_class(**app_args)
            app.set_app_id(app_id)

            # Store reference
            self.running_apps[app_id] = app
            AppRegistry.add_running_app(app_id, app)

            if in_process:
                # Launch in-process for collaborative functionality
                await self._launch_in_process_app(app_id, app)
            elif web_mode:
                # Launch in web mode using textual serve
                await self._launch_web_app(app_id, app_name, app_args, port)
            else:
                # Launch in terminal mode (background process)
                await self._launch_terminal_app(app_id, app)

            return app_id

        except Exception as e:
            # Cleanup on failure
            self.running_apps.pop(app_id, None)
            AppRegistry.remove_running_app(app_id)
            raise Exception(f"Failed to launch {app_name}: {e}") from e

    async def _launch_terminal_app(self, app_id: str, app: BaseTextualApp) -> None:
        """Launch app in terminal mode as subprocess while maintaining interactive access."""
        # Create a script that runs the SAME app instance that's stored in running_apps
        # This allows interactive functionality to work with the actual running app
        script_content = f'''#!/usr/bin/env python3
import sys
import asyncio
sys.path.insert(0, r"{Path(__file__).parent.parent.parent}")
from textualize_mcp.apps.{app.APP_CONFIG.name} import {app.__class__.__name__}

if __name__ == "__main__":
    # Create app instance with same app_id for interactive functionality
    app = {app.__class__.__name__}()
    app.set_app_id("{app_id}")

    # Initialize output buffer for interactive functionality
    app.output_buffer = []
    app._log_output("App started in terminal mode")

    app.run()
'''

        # Write temporary script to temp_apps directory
        temp_apps_dir = Path(__file__).parent.parent.parent / "temp_apps"
        temp_apps_dir.mkdir(exist_ok=True)
        script_path = temp_apps_dir / f"temp_{app_id}.py"
        script_path.write_text(script_content)

        # Launch the app in terminal with better process tracking
        process = await asyncio.create_subprocess_exec(
            "gnome-terminal", "--", "python3", str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        self.app_processes[app_id] = process

        # Update the stored app instance to have the process reference
        app.process_id = process.pid if process.pid else None
        app._log_output(f"Terminal launched with PID: {process.pid}")

        # Start monitoring the process in background
        asyncio.create_task(self._monitor_terminal_process(app_id, process))

    async def _monitor_terminal_process(self, app_id: str, process: asyncio.subprocess.Process) -> None:
        """Monitor a terminal process and clean up when it exits."""
        try:
            # Wait for the process to complete
            await process.wait()

            # Process has ended, clean up
            logger.info(f"Terminal process for app {app_id} has ended (PID: {process.pid})")

            # Update app status
            if app_id in self.running_apps:
                app = self.running_apps[app_id]
                if isinstance(app, BaseTextualApp):
                    app._log_output(f"Terminal process ended, app {app_id} stopped")
                    # Create a stopped status
                    status = AppStatus(
                        app_id=app_id,
                        name=app.APP_CONFIG.name,
                        pid=None,
                        status="stopped",
                        start_time=getattr(app, '_creation_time', datetime.now().isoformat()),
                        error_message=None
                    )
                    self.running_apps[app_id] = status

            # Clean up process reference
            self.app_processes.pop(app_id, None)

            # Clean up temp files
            await self._cleanup_temp_files(app_id)

        except Exception as e:
            logger.error(f"Error monitoring terminal process for app {app_id}: {e}")

    async def _cleanup_temp_files(self, app_id: str) -> None:
        """Clean up temporary files for an app."""
        try:
            temp_apps_dir = Path(__file__).parent.parent.parent / "temp_apps"
            temp_file_patterns = [
                f"temp_{app_id}.py",
                f"temp_web_{app_id}.py"
            ]

            for pattern in temp_file_patterns:
                temp_file = temp_apps_dir / pattern
                if temp_file.exists():
                    temp_file.unlink()
                    logger.info(f"Cleaned up temp file: {temp_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp files for {app_id}: {e}")

    async def _launch_in_process_app(self, app_id: str, app: BaseTextualApp) -> None:
        """Launch app in-process for collaborative functionality.

        This runs the app in the same process as the MCP server, allowing
        direct method calls for screen capture, input sending, etc.
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        # Create a thread pool executor for running the app
        if not hasattr(self, '_app_executor'):
            self._app_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="textual_app")

        def run_app_in_thread():
            """Run the Textual app in a separate thread."""
            try:
                app._log_output(f"Starting app {app_id} in-process (thread mode)")
                # Mark app as running
                app._is_running = True
                # Run the app (this will block until app exits)
                app.run()
                app._log_output(f"App {app_id} finished running")
            except Exception as e:
                app._log_output(f"Error running app {app_id}: {e}")
                # Mark app status in case of error by updating the AppStatus
                status = app.get_status()
                status.error_message = str(e)
                self.running_apps[app_id] = status
            finally:
                app._is_running = False

        # Submit the app to run in thread pool
        future = self._app_executor.submit(run_app_in_thread)

        # Store the future so we can check status or cancel if needed
        if not hasattr(self, '_app_futures'):
            self._app_futures = {}
        self._app_futures[app_id] = future

        # Give the app a moment to start up
        await asyncio.sleep(0.1)
        app._log_output(f"In-process app {app_id} launched successfully")

    async def _launch_web_app(self, app_id: str, app_name: str, args: dict[str, Any], port: int = 8000) -> None:
        """Launch app in web mode using textual serve."""
        # Get app class from registry
        app_class = AppRegistry.get_app_class(app_name)
        if not app_class:
            raise ValueError(f"Unknown application: {app_name}")

        # Create a script that runs the app directly
        script_content = f'''#!/usr/bin/env python3
import sys
sys.path.insert(0, r"{Path(__file__).parent.parent.parent}")
from textualize_mcp.apps.{app_name} import {app_class.__name__}

if __name__ == "__main__":
    app = {app_class.__name__}()
    app.run()
'''

        # Write temporary script to temp_apps directory
        temp_apps_dir = Path(__file__).parent.parent.parent / "temp_apps"
        temp_apps_dir.mkdir(exist_ok=True)
        script_path = temp_apps_dir / f"temp_web_{app_id}.py"
        script_path.write_text(script_content)

        # Use textual serve with the script and dynamic port
        cmd = ["textual", "serve", str(script_path), "--port", str(port)]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=Path(__file__).parent.parent.parent
        )

        self.app_processes[app_id] = process

    async def terminate_app(self, app_id: str) -> bool:
        """Terminate a running application and clean up temp files."""
        cleanup_successful = True

        # Check if app exists in registry
        if app_id not in self.running_apps:
            logger.warning(f"App {app_id} not found in running_apps")
            return False

        # Terminate in-process app if exists
        if hasattr(self, '_app_futures') and app_id in self._app_futures:
            future = self._app_futures[app_id]
            if not future.done():
                # Try to exit the app gracefully first
                if app_id in self.running_apps:
                    app = self.running_apps[app_id]
                    if isinstance(app, BaseTextualApp):
                        try:
                            app.exit()
                            app._log_output(f"App {app_id} exit requested")
                        except Exception as e:
                            logger.warning(f"Failed to gracefully exit app {app_id}: {e}")

                # Cancel the future if still running
                future.cancel()

            # Clean up future reference
            del self._app_futures[app_id]

        # Terminate subprocess if exists - handle dead processes gracefully
        if app_id in self.app_processes:
            process = self.app_processes[app_id]
            try:
                # Check if process is still alive
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except TimeoutError:
                        # Force kill if it doesn't terminate gracefully
                        process.kill()
                        await process.wait()
                logger.info(f"Process for app {app_id} terminated successfully")
            except Exception as e:
                logger.warning(f"Error terminating process for app {app_id}: {e}")
                cleanup_successful = False
            finally:
                # Always clean up the process reference
                del self.app_processes[app_id]

        # Clean up temporary files
        try:
            temp_apps_dir = Path(__file__).parent.parent.parent / "temp_apps"
            temp_file_patterns = [
                f"temp_{app_id}.py",
                f"temp_web_app_{app_id}.py"
            ]

            for pattern in temp_file_patterns:
                temp_file = temp_apps_dir / pattern
                if temp_file.exists():
                    temp_file.unlink()
                    logger.info(f"Cleaned up temp file: {temp_file}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp files for {app_id}: {e}")
            cleanup_successful = False

        # Clean up app registry - handle both BaseTextualApp and AppStatus objects
        if app_id in self.running_apps:
            app = self.running_apps[app_id]
            if isinstance(app, BaseTextualApp):
                try:
                    app.exit()
                    logger.info(f"Gracefully exited BaseTextualApp {app_id}")
                except Exception as e:
                    logger.warning(f"Failed to exit BaseTextualApp {app_id}: {e}")
            elif isinstance(app, AppStatus):
                logger.info(f"Removing AppStatus for {app_id}")

            # Always remove from registry
            del self.running_apps[app_id]
            AppRegistry.remove_running_app(app_id)
            logger.info(f"Successfully terminated and cleaned up app {app_id}")
            return cleanup_successful

        logger.warning(f"App {app_id} was not found in running_apps during cleanup")
        return False

    def get_app_status(self, app_id: str) -> AppStatus | None:
        """Get status of a running application."""
        app_or_status = self.running_apps.get(app_id)
        if isinstance(app_or_status, AppStatus):
            return app_or_status
        elif isinstance(app_or_status, BaseTextualApp):
            return app_or_status.get_status()
        return None

    def list_running_apps(self) -> list[AppStatus]:
        """List all running applications."""
        statuses = []
        for app_or_status in self.running_apps.values():
            if isinstance(app_or_status, AppStatus):
                statuses.append(app_or_status)
            elif isinstance(app_or_status, BaseTextualApp):
                statuses.append(app_or_status.get_status())
        return statuses

    async def launch_environment(
        self,
        template_name: str,
        customizations: dict[str, Any] | None = None
    ) -> str:
        """Launch a complete development environment using multiplex."""
        if template_name not in self.environment_templates:
            raise ValueError(f"Unknown template: {template_name}")

        env_id = f"env_{uuid.uuid4().hex[:8]}"
        config = self.environment_templates[template_name].copy()

        # Apply customizations
        if customizations:
            config = [cmd.format(**customizations) for cmd in config]

        try:
            # Launch multiplex with the configuration
            multiplex_cmd = ["multiplex"] + config

            process = await asyncio.create_subprocess_exec(
                *multiplex_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(__file__).parent.parent.parent
            )

            # Store environment info
            self.multiplex_environments[env_id] = {
                "template": template_name,
                "config": config,
                "process": process,
                "started_at": datetime.now().isoformat(),
                "customizations": customizations or {}
            }

            return env_id

        except Exception as exc:
            # Cleanup on failure
            if env_id in self.multiplex_environments:
                del self.multiplex_environments[env_id]
            raise Exception(f"Failed to launch environment {template_name}: {exc}") from exc

    async def create_custom_environment(self, config: list[str]) -> str:
        """Create custom environment from multiplex config."""
        env_id = f"custom_{uuid.uuid4().hex[:8]}"

        try:
            multiplex_cmd = ["multiplex"] + config

            process = await asyncio.create_subprocess_exec(
                *multiplex_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(__file__).parent.parent.parent
            )

            # Store environment info
            self.multiplex_environments[env_id] = {
                "template": "custom",
                "config": config,
                "process": process,
                "started_at": datetime.now().isoformat(),
                "customizations": {}
            }

            return env_id

        except Exception as e:
            raise Exception(f"Failed to create custom environment: {e}") from e

    def get_environment_status(self, env_id: str) -> dict[str, Any]:
        """Get comprehensive status of environment."""
        if env_id not in self.multiplex_environments:
            return {"status": "error", "error": "Environment not found"}

        env = self.multiplex_environments[env_id]
        process_status = "running" if env["process"].returncode is None else "stopped"

        return {
            "status": "success",
            "env_id": env_id,
            "template": env["template"],
            "process_status": process_status,
            "started_at": env["started_at"],
            "config": env["config"],
            "process_count": len(env["config"]),
            "customizations": env["customizations"]
        }

    async def terminate_environment(self, env_id: str) -> bool:
        """Terminate entire environment gracefully."""
        if env_id not in self.multiplex_environments:
            return False

        env = self.multiplex_environments[env_id]

        if env["process"]:
            env["process"].terminate()
            await env["process"].wait()

        del self.multiplex_environments[env_id]
        return True

    def list_environments(self) -> list[dict[str, Any]]:
        """List all active environments with status."""
        environments = []

        for env_id, env in self.multiplex_environments.items():
            process_status = "running" if env["process"].returncode is None else "stopped"

            environments.append({
                "env_id": env_id,
                "template": env["template"],
                "status": process_status,
                "started_at": env["started_at"],
                "process_count": len(env["config"])
            })

        return environments

    async def terminate_all_apps(self) -> dict[str, Any]:
        """Terminate all running applications and environments."""
        terminated_apps = []
        terminated_envs = []

        # Terminate all running apps
        for app_id in list(self.running_apps.keys()):
            try:
                success = await self.terminate_app(app_id)
                terminated_apps.append({"app_id": app_id, "success": success})
            except Exception as e:
                terminated_apps.append({"app_id": app_id, "success": False, "error": str(e)})

        # Terminate all environments
        for env_id in list(self.multiplex_environments.keys()):
            try:
                success = await self.terminate_environment(env_id)
                terminated_envs.append({"env_id": env_id, "success": success})
            except Exception as e:
                terminated_envs.append({"env_id": env_id, "success": False, "error": str(e)})

        return {
            "status": "success",
            "terminated_apps": terminated_apps,
            "terminated_environments": terminated_envs,
            "total_apps": len(terminated_apps),
            "total_envs": len(terminated_envs)
        }

    def get_all_running_processes(self) -> dict[str, Any]:
        """Get detailed info about all running processes for debugging."""
        running_info = {
            "apps": [],
            "environments": [],
            "processes": []
        }

        # Get app info
        for app_id, app_or_status in self.running_apps.items():
            app_info = {
                "app_id": app_id,
                "type": type(app_or_status).__name__,
                "has_process": app_id in self.app_processes
            }
            if isinstance(app_or_status, BaseTextualApp):
                app_info.update({
                    "name": app_or_status.APP_CONFIG.name,
                    "process_id": app_or_status.process_id,
                    "is_running": app_or_status._is_running,
                    "start_time": app_or_status._creation_time
                })
            elif isinstance(app_or_status, AppStatus):
                app_info.update({
                    "name": app_or_status.name,
                    "pid": app_or_status.pid,
                    "status": app_or_status.status,
                    "start_time": app_or_status.start_time
                })
            running_info["apps"].append(app_info)

        # Get environment info
        for env_id, env in self.multiplex_environments.items():
            env_info = {
                "env_id": env_id,
                "template": env["template"],
                "process_running": env["process"].returncode is None,
                "started_at": env["started_at"]
            }
            running_info["environments"].append(env_info)

        # Get process info
        for app_id, process in self.app_processes.items():
            process_info = {
                "app_id": app_id,
                "pid": process.pid,
                "returncode": process.returncode
            }
            running_info["processes"].append(process_info)

        return running_info

    async def cleanup_dead_processes(self) -> dict[str, Any]:
        """Clean up processes that are no longer running."""
        cleaned_apps = []

        # Check each app to see if its process is still alive
        for app_id in list(self.running_apps.keys()):
            app_or_status = self.running_apps[app_id]

            # Check if it's an AppStatus with a PID
            if isinstance(app_or_status, AppStatus) and app_or_status.pid:
                try:
                    # Check if process exists using os.kill with signal 0
                    import os
                    os.kill(app_or_status.pid, 0)
                    # Process exists, continue
                    continue
                except (OSError, ProcessLookupError):
                    # Process is dead, clean it up
                    logger.info(f"Found dead process for app {app_id} (PID: {app_or_status.pid})")

                    # Update status to stopped
                    app_or_status.status = "stopped"
                    app_or_status.pid = None

                    # Clean up process reference if it exists
                    self.app_processes.pop(app_id, None)

                    # Clean up temp files
                    await self._cleanup_temp_files(app_id)

                    cleaned_apps.append({
                        "app_id": app_id,
                        "name": app_or_status.name,
                        "was_pid": app_or_status.pid,
                        "status": "cleaned_dead_process"
                    })

        return {
            "status": "success",
            "cleaned_apps": cleaned_apps,
            "count": len(cleaned_apps),
            "timestamp": datetime.now().isoformat()
        }


# Initialize MCP server and app manager
mcp = FastMCP("Textualize MCP Server")
app_manager = AppManager()


@mcp.tool()
def list_apps() -> list[dict[str, Any]]:
    """List all available Textual applications.

    Returns:
        List of application configurations with metadata.
    """
    app_configs = []
    for config in AppRegistry.list_apps():
        app_configs.append({
            "name": config.name,
            "description": config.description,
            "version": config.version,
            "tags": config.tags,
            "requires_web": config.requires_web,
            "requires_sudo": config.requires_sudo
        })
    return app_configs


@mcp.tool()
async def launch_app(
    app_name: str,
    args: str | None = None,
    launch_mode: str = "background",
    port: int = 8000,
    terminal_type: str = "gnome-terminal"
) -> dict[str, Any]:
    """Launch a Textual application with comprehensive launch mode support.

    Args:
        app_name: Name of the application to launch
        args: JSON string of arguments to pass to the application
        launch_mode: Launch mode - 'background', 'web', 'terminal', 'collaborative'
        port: Port number for web mode
        terminal_type: Terminal type for terminal mode ('gnome-terminal', 'xterm', 'konsole', 'alacritty')

    Returns:
        Application launch result with app_id and mode-specific details.
    """
    try:
        parsed_args = {}
        if args:
            parsed_args = json.loads(args)

        # Determine launch parameters based on mode
        web_mode = launch_mode == "web"
        in_process = launch_mode == "collaborative"

        # Launch the app using the unified AppManager method
        if launch_mode == "terminal":
            # For terminal mode, use the terminal-specific implementation
            app_id = app_manager.generate_app_id()

            # Create app status for tracking
            app_status = AppStatus(
                app_id=app_id,
                name=app_name,
                pid=None,
                status="starting",
                start_time=datetime.now().isoformat(),
                error_message=None
            )

            # Build terminal command
            app_module = f"textualize_mcp.apps.{app_name}"
            base_dir = Path(__file__).parent.parent.parent

            terminal_commands = {
                "gnome-terminal": [
                    "gnome-terminal", "--", "bash", "-c",
                    f"cd {base_dir} && uv run python -m {app_module}; read -p 'Press Enter to close...'"
                ],
                "xterm": [
                    "xterm", "-e", "bash", "-c",
                    f"cd {base_dir} && uv run python -m {app_module}; read -p 'Press Enter to close...'"
                ],
                "konsole": [
                    "konsole", "-e", "bash", "-c",
                    f"cd {base_dir} && uv run python -m {app_module}; read -p 'Press Enter to close...'"
                ],
                "alacritty": [
                    "alacritty", "-e", "bash", "-c",
                    f"cd {base_dir} && uv run python -m {app_module}; read -p 'Press Enter to close...'"
                ]
            }

            if terminal_type not in terminal_commands:
                terminal_type = "gnome-terminal"

            cmd = terminal_commands[terminal_type]

            # Launch terminal process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Update status and store references
            app_status.pid = process.pid
            app_status.status = "running"
            app_manager.running_apps[app_id] = app_status
            app_manager.app_processes[app_id] = process

            return {
                "status": "success",
                "app_id": app_id,
                "app_name": app_name,
                "launch_mode": launch_mode,
                "terminal_type": terminal_type,
                "process_id": process.pid,
                "message": f"Launched {app_name} in visible {terminal_type} window",
                "launched_at": datetime.now().isoformat()
            }
        else:
            # Use standard AppManager launch for other modes
            app_id = await app_manager.launch_app(app_name, parsed_args, web_mode, in_process, port)

            result: dict[str, Any] = {
                "status": "success",
                "app_id": app_id,
                "app_name": app_name,
                "launch_mode": launch_mode,
                "launched_at": datetime.now().isoformat()
            }

            # Add mode-specific details
            if launch_mode == "web":
                result.update({
                    "web_url": f"http://localhost:{port}",
                    "port": port,
                    "message": f"Launched {app_name} in web browser at http://localhost:{port}",
                    "instructions": f"Open http://localhost:{port} in your browser to interact with the app"
                })
            elif launch_mode == "collaborative":
                result["message"] = f"Launched {app_name} in collaborative mode with full interactive features"
                result["collaborative_features"] = [
                    "Screen capture (capture_app_screen)",
                    "Input sending (send_input_to_app)",
                    "State monitoring (get_app_state)",
                    "Real-time interaction"
                ]
            else:  # background mode
                result["message"] = f"Launched {app_name} in background mode"

            return result

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "app_name": app_name,
            "launch_mode": launch_mode
        }


@mcp.tool()
def get_app_info(app_name: str) -> dict[str, Any]:
    """Get detailed information about an application.

    Args:
        app_name: Name of the application

    Returns:
        Detailed application information.
    """
    app_class = AppRegistry.get_app_class(app_name)
    if not app_class:
        return {
            "status": "error",
            "error": f"Unknown application: {app_name}"
        }

    config = app_class.get_config()
    return {
        "status": "success",
        "name": config.name,
        "description": config.description,
        "version": config.version,
        "author": config.author,
        "tags": config.tags,
        "requires_web": config.requires_web,
        "requires_sudo": config.requires_sudo,
        "bindings": getattr(app_class, 'BINDINGS', [])
    }


@mcp.tool()
async def terminate_app(app_id: str) -> dict[str, Any]:
    """Terminate a running application.

    Args:
        app_id: ID of the application to terminate

    Returns:
        Termination result.
    """
    success = await app_manager.terminate_app(app_id)

    if success:
        return {
            "status": "success",
            "app_id": app_id,
            "terminated_at": datetime.now().isoformat()
        }
    else:
        return {
            "status": "error",
            "error": f"Application {app_id} not found or already terminated",
            "app_id": app_id
        }


@mcp.tool()
def get_app_status(app_id: str) -> dict[str, Any]:
    """Get status of a running application.

    Args:
        app_id: ID of the application

    Returns:
        Application status information.
    """
    status = app_manager.get_app_status(app_id)

    if status:
        return {
            "status": "success",
            "app_status": status.model_dump()
        }
    else:
        return {
            "status": "error",
            "error": f"Application {app_id} not found",
            "app_id": app_id
        }


@mcp.tool()
def list_running_apps() -> dict[str, Any]:
    """List all currently running applications.

    Returns:
        List of running application statuses.
    """
    running_apps = app_manager.list_running_apps()

    return {
        "status": "success",
        "running_apps": [app.model_dump() for app in running_apps],
        "count": len(running_apps),
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
async def capture_app_screen(app_id: str) -> dict[str, Any]:
    """Capture the current screen/output of a running application.

    Args:
        app_id: ID of the application to capture

    Returns:
        Screen capture data including text content and layout
    """
    app = app_manager.running_apps.get(app_id)
    if not app:
        return {
            "status": "error",
            "error": f"Application {app_id} not found or not running"
        }

    try:
        # Ensure app is BaseTextualApp instance with screen capture capability
        if isinstance(app, BaseTextualApp) and hasattr(app, 'get_screen_state'):
            # Check if app is running in-process (required for collaborative features)
            if not (hasattr(app_manager, '_app_futures') and app_id in app_manager._app_futures):
                return {
                    "status": "error",
                    "error": f"Application {app_id} must be running in-process for screen capture. Please launch with in_process=True or use open_collaborative_session."
                }

            screen_data = await app.get_screen_state()
            return {
                "status": "success",
                "app_id": app_id,
                "screen_data": screen_data,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "Screen capture not supported for this application"
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to capture screen: {e}"
        }


@mcp.tool()
async def send_input_to_app(app_id: str, input_type: str, input_data: str) -> dict[str, Any]:
    """Send input (keystrokes, commands) to a running application.

    Args:
        app_id: ID of the application
        input_type: Type of input ('key', 'text', 'command')
        input_data: The actual input data to send

    Returns:
        Result of sending the input
    """
    app = app_manager.running_apps.get(app_id)
    if not app:
        return {
            "status": "error",
            "error": f"Application {app_id} not found or not running"
        }

    try:
        if isinstance(app, BaseTextualApp) and hasattr(app, 'receive_input'):
            # Check if app is running in-process (required for collaborative features)
            if not (hasattr(app_manager, '_app_futures') and app_id in app_manager._app_futures):
                return {
                    "status": "error",
                    "error": f"Application {app_id} must be running in-process for input sending. Please launch with in_process=True or use open_collaborative_session."
                }

            result = await app.receive_input(input_type, input_data)
            return {
                "status": "success",
                "app_id": app_id,
                "input_sent": f"{input_type}: {input_data}",
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "Input sending not supported for this application"
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to send input: {e}"
        }


@mcp.tool()
async def get_app_state(app_id: str) -> dict[str, Any]:
    """Get detailed state information from a running application.

    Args:
        app_id: ID of the application

    Returns:
        Detailed application state including UI state, data, and context
    """
    app = app_manager.running_apps.get(app_id)
    if not app:
        return {
            "status": "error",
            "error": f"Application {app_id} not found or not running"
        }

    try:
        if isinstance(app, BaseTextualApp) and hasattr(app, 'get_detailed_state'):
            state_data = await app.get_detailed_state()
            return {
                "status": "success",
                "app_id": app_id,
                "state": state_data,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Fallback to basic status
            if isinstance(app, BaseTextualApp):
                basic_status = app.get_status().model_dump()
            elif isinstance(app, AppStatus):
                basic_status = app.model_dump()
            else:
                return {
                    "status": "error",
                    "error": "Basic status not available for this object",
                    "app_id": app_id
                }
            return {
                "status": "success",
                "app_id": app_id,
                "state": {
                    "basic_status": basic_status,
                    "note": "Detailed state not available - using basic status"
                },
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get state: {e}"
        }


@mcp.tool()
async def create_interactive_session(app_id: str, session_type: str = "shared") -> dict[str, Any]:
    """Create an interactive session for real-time collaboration with an app.

    Args:
        app_id: ID of the application
        session_type: Type of session ('shared', 'readonly', 'control')

    Returns:
        Session information and connection details
    """
    app = app_manager.running_apps.get(app_id)
    if not app:
        return {
            "status": "error",
            "error": f"Application {app_id} not found or not running"
        }

    try:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        from textualize_mcp.core.base import BaseTextualApp

        if isinstance(app, BaseTextualApp) and hasattr(app, 'create_session'):
            session_data = await app.create_session(session_id, session_type)
            return {
                "status": "success",
                "app_id": app_id,
                "session_id": session_id,
                "session_type": session_type,
                "session_data": session_data,
                "message": f"Interactive session created! Both AI and user can now interact with {app.APP_CONFIG.name}",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "Interactive sessions not supported for this application"
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to create session: {e}"
        }


@mcp.tool()
async def read_app_output(app_id: str, lines: int = 50) -> dict[str, Any]:
    """Read recent output/logs from a running application.

    Args:
        app_id: ID of the application
        lines: Number of recent lines to read

    Returns:
        Recent application output and logs
    """
    app = app_manager.running_apps.get(app_id)
    if not app:
        return {
            "status": "error",
            "error": f"Application {app_id} not found or not running"
        }

    try:
        if isinstance(app, BaseTextualApp) and hasattr(app, 'get_recent_output'):
            output_data = await app.get_recent_output(lines)
            return {
                "status": "success",
                "app_id": app_id,
                "output": output_data,
                "lines_requested": lines,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "Output reading not supported for this application yet"
            }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to read output: {e}"
        }


# REMOVED: launch_app_in_terminal - functionality now integrated into main launch_app method
# Use launch_app(app_name, launch_mode="terminal", terminal_type="gnome-terminal") instead


# REMOVED: launch_app_in_web_browser - functionality now integrated into main launch_app method
# Use launch_app(app_name, launch_mode="web", port=8000) instead


@mcp.tool()
async def capture_terminal_output(app_id: str, lines: int = 50) -> dict[str, Any]:
    """Capture actual terminal output from a running application process.

    Args:
        app_id: ID of the application
        lines: Number of lines to capture from terminal

    Returns:
        Terminal output content and visual state
    """
    if app_id not in app_manager.app_processes:
        return {
            "status": "error",
            "error": f"No terminal process found for app {app_id}"
        }

    try:
        process = app_manager.app_processes[app_id]

        if process.stdout:
            # Try to read available output
            try:
                stdout_data = b""
                while True:
                    try:
                        chunk = await process.stdout.read(1024)
                        if not chunk:
                            break
                        stdout_data += chunk
                    except Exception:
                        break

                terminal_output = stdout_data.decode('utf-8', errors='ignore')
                output_lines = terminal_output.split('\n')[-lines:] if terminal_output else []

                return {
                    "status": "success",
                    "app_id": app_id,
                    "terminal_output": output_lines,
                    "lines_captured": len(output_lines),
                    "process_status": "running" if process.returncode is None else "stopped",
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as read_error:
                return {
                    "status": "partial_success",
                    "app_id": app_id,
                    "message": "Process running but output not accessible in this mode",
                    "process_status": "running" if process.returncode is None else "stopped",
                    "suggestion": "Use visible terminal or web browser mode for better output capture",
                    "error": str(read_error),
                    "timestamp": datetime.now().isoformat()
                }
        else:
            return {
                "status": "error",
                "error": "Process has no stdout stream available"
            }

    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to capture terminal output: {e}"
        }


# REMOVED: open_collaborative_session - functionality now integrated into main launch_app method
# Use launch_app(app_name, launch_mode="collaborative") instead
    """Get information about the MCP server.

    Returns:
        Server information and statistics.
    """
    available_apps = AppRegistry.list_apps()
    running_apps = app_manager.list_running_apps()

    return {
        "status": "success",
        "server_name": "Textualize MCP Server",
        "version": "1.0.0",
        "available_apps": len(available_apps),
        "running_apps": len(running_apps),
        "supported_features": [
            "app_management",
            "web_deployment",
            "terminal_mode",
            "process_monitoring",
            "file_management",
            "interactive_sessions",
            "screen_capture",
            "input_injection",
            "real_time_collaboration",
            "ai_app_interaction",
            "visible_terminal_launch",
            "web_browser_launch",
            "collaborative_sessions",
            "terminal_output_capture"
        ],
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
def debug_running_apps() -> dict[str, Any]:
    """Debug tool to see what's actually stored in running_apps.

    Returns:
        Raw content of running_apps dictionary for debugging.
    """
    try:
        debug_info = {
            "running_apps_count": len(app_manager.running_apps),
            "app_processes_count": len(app_manager.app_processes),
            "running_apps_keys": list(app_manager.running_apps.keys()),
            "app_processes_keys": list(app_manager.app_processes.keys()),
            "running_apps_types": {
                app_id: type(obj).__name__
                for app_id, obj in app_manager.running_apps.items()
            }
        }
        return {
            "status": "success",
            "debug_info": debug_info,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def list_environment_templates() -> dict[str, Any]:
    """List all available environment templates.

    Returns:
        Dictionary of available templates with descriptions.
    """
    templates = {}

    for name, config in app_manager.environment_templates.items():
        templates[name] = {
            "name": name,
            "processes": len(config),
            "config_preview": config[:3],  # Show first 3 commands
            "description": _get_template_description(name)
        }

    return {
        "status": "success",
        "templates": templates,
        "count": len(templates)
    }


def _get_template_description(template_name: str) -> str:
    """Get human-readable description of template."""
    descriptions = {
        "textual_dev": "Single Textual app development with live reload and console",
        "full_stack": "Complete stack with database, multiple services, and monitoring",
        "testing_pipeline": "Automated testing workflow with linting, typing, and coverage",
        "development_stack": "Multi-service development environment with coordination"
    }
    return descriptions.get(template_name, "Custom template")


@mcp.tool()
async def launch_development_environment(
    template: str,
    customizations: str | None = None
) -> dict[str, Any]:
    """Launch a complete development environment with service coordination.

    Args:
        template: Pre-configured environment template name
        customizations: JSON string of template customizations (e.g., ports, paths)

    Returns:
        Environment launch result with coordination info.
    """
    try:
        custom_params = {}
        if customizations:
            custom_params = json.loads(customizations)

        env_id = await app_manager.launch_environment(template, custom_params)

        return {
            "status": "success",
            "environment_id": env_id,
            "template": template,
            "customizations": custom_params,
            "message": f"Launched {template} environment with coordinated services",
            "launched_at": datetime.now().isoformat(),
            "next_steps": _get_environment_instructions(template)
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "template": template
        }


def _get_environment_instructions(template: str) -> list[str]:
    """Get user instructions for environment template."""
    instructions = {
        "textual_dev": [
            "Your Textual app is starting with live reload",
            "Console output will show in separate pane",
            "Browser will open automatically to app URL"
        ],
        "full_stack": [
            "Database and Redis starting in background",
            "Multiple Textual services launching on different ports",
            "Dashboard will open showing all available services"
        ],
        "testing_pipeline": [
            "Automated testing pipeline executing",
            "Will run linting, type checking, tests, and coverage",
            "Pipeline completes automatically with summary"
        ],
        "development_stack": [
            "Multiple Textual services coordinating startup",
            "File manager, API tester, and process monitor launching",
            "Gateway message will show when all services are ready"
        ]
    }
    return instructions.get(template, ["Environment launching with custom configuration"])


@mcp.tool()
async def create_custom_workflow(
    workflow_config: str,
    timeout: int = 300
) -> dict[str, Any]:
    """Create custom workflow with process dependencies.

    Args:
        workflow_config: JSON array of multiplex command configurations
        timeout: Maximum runtime for the entire workflow

    Returns:
        Workflow execution results and process coordination status.
    """
    try:
        config = json.loads(workflow_config)

        if not isinstance(config, list):
            raise ValueError("workflow_config must be JSON array of command strings")

        # Add timeout to the workflow if specified
        if timeout > 0:
            config.append(f"+{timeout}|end=echo 'Workflow timeout reached'")

        env_id = await app_manager.create_custom_environment(config)

        return {
            "status": "success",
            "workflow_id": env_id,
            "config": config,
            "timeout": timeout,
            "message": "Custom workflow created with process coordination",
            "created_at": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "workflow_config": workflow_config
        }


@mcp.tool()
def get_environment_status(env_id: str) -> dict[str, Any]:
    """Get comprehensive status of a running environment.

    Args:
        env_id: Environment ID to check

    Returns:
        Detailed environment status and process information.
    """
    return app_manager.get_environment_status(env_id)


@mcp.tool()
async def terminate_environment(env_id: str) -> dict[str, Any]:
    """Terminate an entire environment gracefully.

    Args:
        env_id: Environment ID to terminate

    Returns:
        Termination result and cleanup status.
    """
    success = await app_manager.terminate_environment(env_id)

    if success:
        return {
            "status": "success",
            "env_id": env_id,
            "message": "Environment terminated gracefully",
            "terminated_at": datetime.now().isoformat()
        }
    else:
        return {
            "status": "error",
            "error": f"Environment {env_id} not found",
            "env_id": env_id
        }


@mcp.tool()
async def terminate_all_apps() -> dict[str, Any]:
    """Terminate all running applications and environments.

    Returns:
        Summary of termination results for all apps and environments.
    """
    try:
        result = await app_manager.terminate_all_apps()
        return result
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to terminate all apps: {e}",
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def get_all_running_processes() -> dict[str, Any]:
    """Get detailed information about all running processes for debugging.

    Returns:
        Comprehensive information about apps, environments, and processes.
    """
    try:
        process_info = app_manager.get_all_running_processes()
        process_info["status"] = "success"
        process_info["timestamp"] = datetime.now().isoformat()
        return process_info
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to get process info: {e}",
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
async def cleanup_dead_processes() -> dict[str, Any]:
    """Clean up apps with dead processes that are still tracked as running.

    Returns:
        Summary of cleaned up dead processes.
    """
    try:
        result = await app_manager.cleanup_dead_processes()
        return result
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to cleanup dead processes: {e}",
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def list_active_environments() -> dict[str, Any]:
    """List all active environments with their status.

    Returns:
        List of all running environments and their details.
    """
    environments = app_manager.list_environments()

    return {
        "status": "success",
        "environments": environments,
        "count": len(environments),
        "timestamp": datetime.now().isoformat()
    }


def cleanup_processes():
    """Clean up all running processes and background tasks."""
    logger.info("Cleaning up Textualize MCP Server...")

    # Terminate all running apps
    for app_id in list(app_manager.running_apps.keys()):
        try:
            asyncio.run(app_manager.terminate_app(app_id))
        except Exception as e:
            logger.error(f"Error terminating app {app_id}: {e}")

    # Terminate all multiplex environments
    for env_id in list(app_manager.multiplex_environments.keys()):
        try:
            asyncio.run(app_manager.terminate_environment(env_id))
        except Exception as e:
            logger.error(f"Error terminating environment {env_id}: {e}")

    # Clean up any remaining processes
    for app_id, process in list(app_manager.app_processes.items()):
        try:
            if process and process.returncode is None:
                process.terminate()
        except Exception as e:
            logger.error(f"Error terminating process for app {app_id}: {e}")

    app_manager.running_apps.clear()
    app_manager.app_processes.clear()
    app_manager.multiplex_environments.clear()
    logger.info("Cleanup completed")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down gracefully")
    cleanup_processes()
    sys.exit(0)


# Register cleanup handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
atexit.register(cleanup_processes)


def main():
    """Main entry point for the MCP server."""
    try:
        logger.info(f"Starting Textualize MCP Server with {len(AppRegistry.list_apps())} applications")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        cleanup_processes()


if __name__ == "__main__":
    main()
