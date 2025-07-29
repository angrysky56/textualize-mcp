# Development Guide

## Quick Start

### 1. Setup Environment

```bash
cd textualize-mcp

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .
```

### 2. Run Individual Applications

```bash
# File Browser
python -m textualize_mcp.apps.file_browser

# Process Monitor  
python -m textualize_mcp.apps.process_monitor

# API Tester
python -m textualize_mcp.apps.api_tester

# Or use the CLI tool
python cli.py run file_browser
python cli.py run process_monitor --web --port 8001
python cli.py list-apps
```

### 3. Start MCP Server

```bash
# Start the MCP server
python server.py

# Or via CLI
python cli.py server
```

### 4. Web Mode

```bash
# Run any app in browser
textual serve textualize_mcp.apps.file_browser:FileBrowserApp
textual serve textualize_mcp.apps.process_monitor:ProcessMonitorApp --port 8001
textual serve textualize_mcp.apps.api_tester:APITesterApp --port 8002
```

## Claude Desktop Integration

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "textualize-mcp": {
      "command": "python",
      "args": ["/home/ty/Repositories/ai_workspace/textualize-mcp/server.py"],
      "env": {
        "PATH": "/home/ty/Repositories/ai_workspace/textualize-mcp/.venv/bin:/usr/bin:/bin"
      }
    }
  }
}
```

## Available MCP Functions

Once running, Claude can use these functions:

- `list_apps()` - Show available applications
- `launch_app(app_name, args, web_mode)` - Start an application
- `get_app_info(app_name)` - Get app details
- `terminate_app(app_id)` - Stop a running app
- `get_app_status(app_id)` - Check app status
- `list_running_apps()` - Show all running apps
- `get_server_info()` - Server information

## Example Claude Interactions

**"Launch the file browser"**
```python
launch_app("file_browser")
```

**"Start process monitor in web mode"**
```python
launch_app("process_monitor", web_mode=True)
```

**"Show me what apps are available"**
```python
list_apps()
```

**"Get details about the API tester"**
```python
get_app_info("api_tester")
```

## Development Workflow

### Adding New Applications

1. Create new app file in `textualize_mcp/apps/`
2. Inherit from `BaseTextualApp`
3. Add `APP_CONFIG` with metadata
4. Use `@register_app` decorator
5. Import in `textualize_mcp/apps/__init__.py`

### Example App Structure

```python
from ..core.base import BaseTextualApp, AppConfig, register_app

@register_app
class MyNewApp(BaseTextualApp):
    APP_CONFIG = AppConfig(
        name="my_new_app",
        description="Description of what it does",
        tags=["category", "keywords"]
    )
    
    def compose(self) -> ComposeResult:
        # Build your UI here
        yield Header()
        yield Static("Hello World!")
        yield Footer()
```

### CSS Styling

- Create `app_name.tcss` file alongside the Python file
- Use Textual CSS for styling
- Follow responsive design patterns
- Test on different terminal sizes

### Testing

```bash
# Run individual app for testing
python -m textualize_mcp.apps.my_new_app

# Test in web mode
textual serve textualize_mcp.apps.my_new_app:MyNewApp

# Test MCP integration
python server.py
# Then use Claude to test the functions
```

## Architecture Overview

```
textualize-mcp/
├── textualize_mcp/
│   ├── core/              # Base classes and utilities
│   │   └── base.py        # BaseTextualApp, AppRegistry
│   ├── apps/              # Individual applications
│   │   ├── file_browser.py
│   │   ├── process_monitor.py
│   │   └── api_tester.py
│   └── server/            # MCP server implementation
│       └── mcp_server.py  # FastMCP server with functions
├── server.py              # Main entry point
├── cli.py                 # Command-line interface
└── pyproject.toml         # Project configuration
```

## Key Design Patterns

1. **BaseTextualApp Framework**: Consistent app structure with metadata
2. **AppRegistry Pattern**: Automatic discovery and management
3. **Three-Pane Layouts**: Navigation + Content + Details
4. **Responsive Design**: Adapts to terminal width
5. **Status Management**: Consistent user feedback
6. **MCP Integration**: Standardized server interface

## Tips

- Always use absolute paths when possible
- Handle errors gracefully with user feedback
- Implement responsive layouts for different screen sizes
- Use reactive variables for dynamic updates
- Follow the established CSS patterns for consistency
- Test both terminal and web modes
