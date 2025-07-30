# Textualize-MCP Server

A Model Context Protocol (MCP) server that provides a library of useful Textual terminal applications and sophisticated development environment orchestration using [textualize/textual](https://github.com/Textualize/textual) and [multiplex](https://github.com/sebastien/multiplex)

## Features

- **Pre-built Application Library**: Collection of production-ready terminal applications
- **Environment Orchestration**: Coordinated multi-service development environments with dependencies
- **Process Coordination**: Automatic timing, sequencing, and dependency management
- **MCP Interface**: Control apps and environments via AI assistants through standardized function calls
- **Live Development**: Real-time editing and hot-reload capabilities
- **Web Deployment**: Run terminal apps in browsers via textual-web
- **Visual Process Management**: Color-coded outputs and status monitoring
- **Cross-platform**: Works on Linux, macOS, and Windows

## Available Textualize MCP Tools

### 🎯 Core App Management
- **list_apps()** - List all available Textual applications with metadata
- **launch_app()** - **UNIFIED** launch method with comprehensive mode support:
  - `launch_mode="background"` - Standard background execution  
  - `launch_mode="web"` - Web browser deployment with custom port
  - `launch_mode="terminal"` - Visible terminal window (VS Code context)
  - `launch_mode="collaborative"` - Full AI-app interaction features
- **get_app_info()** - Get detailed application information and capabilities
- **terminate_app()** - Terminate specific running applications
- **get_app_status()** - Get current application status and process info
- **list_running_apps()** - List all currently running applications

### 🤝 Interactive & Collaborative Features  
- **capture_app_screen()** - Get real-time visual state and layout of running apps
- **send_input_to_app()** - Send keystrokes, text, commands, or actions to apps
- **get_app_state()** - Get detailed UI state, data, and context information
- **create_interactive_session()** - Start shared real-time collaboration sessions
- **read_app_output()** - Read recent output and logs from applications
- **capture_terminal_output()** - Capture actual terminal content and visual output

### 🏗️ Environment Orchestration (Multiplex Integration)
- **list_environment_templates()** - List predefined development environment templates
- **launch_development_environment()** - Launch coordinated multi-service environments
- **create_custom_workflow()** - Create custom workflows with process dependencies  
- **get_environment_status()** - Get comprehensive environment status and process info
- **terminate_environment()** - Gracefully shutdown entire environments
- **list_active_environments()** - List all running environments with details

### 🔧 System Management & Debugging
- **debug_running_apps()** - Debug tool for troubleshooting app tracking issues
- **terminate_all_apps()** - Emergency shutdown of all running apps and environments
- **get_all_running_processes()** - Get detailed info about all processes for debugging
- **cleanup_dead_processes()** - Clean up orphaned process references

## 🎪 What This Enables

### 🎯 Individual App Control
**👀 Visible Terminal Launch**
```
AI: "I'll launch the process monitor in a visible terminal window"
→ Opens gnome-terminal/xterm with the app running
→ You see exactly what I'm doing in real-time
→ Both AI and user can interact with the same interface
```

**🌐 Web Browser Mode**
```
AI: "Let me launch the file browser in your web browser"
→ Starts app at http://localhost:8000
→ You open the URL and see the full interface
→ Perfect for graphs, charts, visual data
→ Works on any device with a web browser
```

### 🚀 Environment Orchestration (NEW!)

**🏗️ Development Stack Coordination**
```
AI: "Launch a full development environment"
→ Starts database, API server, file browser, and monitor in sequence
→ Color-coded outputs distinguish each service (#green, #blue, #yellow)
→ Automatic dependency management and timing (+2, +API, etc.)
→ Single command shuts down entire environment gracefully
```

**🧪 Testing Pipeline Automation**
```
AI: "Run the complete testing pipeline"
→ Executes: LINT#yellow → TYPE#blue → TEST#green → COVERAGE → CLEANUP
→ Each step waits for previous to complete (+LINT, +TYPE dependencies)
→ Automatic cleanup and summary reporting (|end action)
→ Graceful failure handling and timeout management
```

**🎨 Custom Workflow Creation**
```json
AI: "Create a custom workflow with process dependencies"
→ Define complex multi-step processes:
[
  "DEMO#green=echo 'Starting custom workflow demo'",
  "STEP1#blue+1=echo 'Step 1: Processing...'",
  "STEP2#yellow+STEP1=echo 'Step 2: Finalizing...'",
  "DONE+STEP2|end=echo '✅ Custom workflow completed!'"
]
→ Built-in timing, dependencies, and coordination
→ Color-coded process identification
→ Automatic timeout and cleanup handling
```

## 📚 Environment Templates Available

### 1. `textual_dev` - Single App Development
Perfect for developing a single Textual application with live reload and debugging.

**What it includes:**
- APP#green: Textual serve with specified app and port
- CONSOLE#blue: Development console for debugging  
- DEV: Live reload development mode
- BROWSER: Automatic browser opening

**Template Commands:**
```bash
APP#green=textual serve textualize_mcp.apps.{app_name}:{app_name}App --port {port}
CONSOLE#blue+1=textual console
DEV+2=textual run --dev textualize_mcp.apps.{app_name}:{app_name}App
BROWSER+3=xdg-open http://localhost:{port}
```

**Usage:**
```python
# Launch with customizations
await launch_development_environment("textual_dev", '{"app_name": "calculator", "port": "8000"}')
```

### 2. `full_stack` - Complete Development Stack
For complex applications requiring databases, multiple services, and monitoring.

**What it includes:**
- DB#blue: MongoDB with quiet logging (background)
- REDIS#red: Redis server on custom port (background)  
- API#green: API tester service on port 8001
- MONITOR#yellow: Process monitor on port 8002
- FILE_BROWSER#cyan: File browser on port 8003
- DASHBOARD: Opens browser to main service

**Template Commands:**
```bash
DB#blue|silent=mongod --quiet --dbpath /tmp/textual_db
REDIS#red|silent=redis-server --port 6380
API#green+2=textual serve textualize_mcp.apps.api_tester:APITesterApp --port 8001
MONITOR#yellow+API=textual serve textualize_mcp.apps.process_monitor:ProcessMonitorApp --port 8002
FILE_BROWSER#cyan+API=textual serve textualize_mcp.apps.file_browser:FileBrowserApp --port 8003
DASHBOARD+5=xdg-open http://localhost:8001
```

### 3. `testing_pipeline` - Automated Testing Workflow
Comprehensive testing pipeline with proper dependency sequencing.

**What it includes:**
- LINT#yellow: Code linting with ruff
- TYPE#blue: Type checking with mypy (waits for lint)
- TEST#green: Test execution with pytest (waits for type check)  
- COVERAGE: Coverage report generation (waits for tests)
- CLEANUP: Success notification and cleanup (auto-terminates)

**Template Commands:**
```bash
LINT#yellow=ruff check textualize_mcp/
TYPE#blue+LINT=mypy textualize_mcp/
TEST#green+TYPE=pytest tests/ -v
COVERAGE+TEST=coverage report --show-missing
CLEANUP+COVERAGE|end=echo 'Testing pipeline completed successfully'
```

### 4. `development_stack` - Multi-Service Coordination
Coordinate multiple Textual services for complex application development.

**What it includes:**
- API#green: API tester service on port 8001
- FILE_MGR#cyan: File browser on port 8002
- PROC_MON#yellow: Process monitor on port 8003  
- GATEWAY: Status message when all services are ready

**Template Commands:**
```bash
API#green=textual serve textualize_mcp.apps.api_tester:APITesterApp --port 8001
FILE_MGR#cyan+1=textual serve textualize_mcp.apps.file_browser:FileBrowserApp --port 8002
PROC_MON#yellow+1=textual serve textualize_mcp.apps.process_monitor:ProcessMonitorApp --port 8003
GATEWAY+3=echo 'All services running - API:8001 Files:8002 Monitor:8003'
```

## 🎯 Real-World Usage Examples

### Example 1: Web Browser Collaboration
```python
# Launch calculator in web browser for shared collaboration
await launch_app("calculator", launch_mode="web", port=8000)
# → Calculator available at http://localhost:8000
# → Both AI and user can interact with same interface
```

### Example 2: Multi-Service Development Environment  
```python
# Launch coordinated development stack
env_id = await launch_development_environment("development_stack")
# → API tester on port 8001
# → File browser on port 8002  
# → Process monitor on port 8003
# → Color-coded coordination with timing dependencies

# Check environment status
status = await get_environment_status(env_id)
# → Shows process coordination and service health

# Graceful shutdown when complete
await terminate_environment(env_id)
```

### Example 3: Testing Pipeline Automation
```python
# Run complete automated testing workflow
await launch_development_environment("testing_pipeline")
# → LINT#yellow → TYPE#blue → TEST#green → COVERAGE → CLEANUP
# → Each step waits for previous completion
# → Automatic reporting and cleanup
```

### Example 4: Custom Workflow Creation
```python
# Create custom workflow with process dependencies
workflow = [
    "BUILD#yellow=npm run build",
    "TEST#green+BUILD=pytest tests/ -v", 
    "DOCKER#blue+TEST=docker build -t app .",
    "DEPLOY#red+DOCKER=kubectl apply -f deployment.yaml",
    "NOTIFY+DEPLOY|end=echo '🚀 Deployment complete!'"
]

await create_custom_workflow(json.dumps(workflow), timeout=300)
# → Custom deployment pipeline with color-coded stages
# → Built-in dependency management and timeout handling
```

### Example 5: Interactive App Control
```python
# Launch app in collaborative mode for AI interaction
app_id = await launch_app("api_tester", launch_mode="collaborative")

# Capture current screen state
screen_data = await capture_app_screen(app_id)

# Send input to the running app
await send_input_to_app(app_id, "key", "Enter")

# Get detailed app state
state = await get_app_state(app_id) 
```

🎪 What This Enables:

### 🎯 Individual App Control
👀 Visible Terminal Launch
AI: "I'll launch the process monitor in a visible terminal window"
→ Opens gnome-terminal/xterm with the app running
→ You see exactly what I'm doing in real-time
→ Both AI and user can interact with the same interface

🌐 Web Browser Mode
AI: "Let me launch the file browser in your web browser"
→ Starts app at http://localhost:8000
→ You open the URL and see the full interface
→ Perfect for graphs, charts, visual data
→ Works on any device with a web browser

### 🚀 Environment Orchestration (NEW!)
🏗️ Development Stack Coordination
AI: "Let me launch a full development environment"
→ Starts database, API server, file browser, and monitor in sequence
→ Color-coded outputs distinguish each service
→ Automatic dependency management and timing
→ Single command shuts down entire environment

🧪 Testing Pipeline Automation
AI: "Run the complete testing pipeline"
→ Executes linting, type checking, tests, and coverage in order
→ Each step waits for previous to complete
→ Automatic cleanup and summary reporting
→ Graceful failure handling

🎨 Custom Workflow Creation
AI: "Create a custom workflow with process dependencies"
→ Define complex multi-step processes with JSON configuration
→ Built-in timing, dependencies, and coordination
→ Color-coded process identification
→ Automatic timeout and cleanup handling

### 📸 Real-Time Monitoring

📸 Real Terminal Screenshots
AI: "Let me capture what's currently on the terminal screen"
→ Gets actual terminal output and visual state
→ Can describe what's happening visually
→ Perfect for debugging and assistance

🤝 One-Command Collaboration
AI: "Let's open a collaborative session with the API tester"
→ Launches in both terminal AND web browser
→ You choose how you want to interact
→ AI can control while you watch or vice versa


### 📊 Unified Launch Method

The `launch_app()` method is the **single, consolidated** way to launch applications in any mode:

```python
# Basic syntax
await launch_app(
    app_name: str,           # Required: "calculator", "file_browser", "api_tester", "process_monitor"
    args: str = None,        # Optional: JSON string of arguments  
    launch_mode: str = "background",  # Mode: "background", "web", "terminal", "collaborative"
    port: int = 8000,        # Port for web mode
    terminal_type: str = "gnome-terminal"  # Terminal type for terminal mode
)

# Launch modes explained:
# "background"     → Standard execution (default)
# "web"           → Browser deployment at http://localhost:PORT
# "terminal"      → Visible terminal window (VS Code context only)  
# "collaborative" → Full AI-app interaction features
```

**Previous redundant methods removed for architectural clarity:**
- ~~`launch_app_in_terminal()`~~ → Use `launch_mode="terminal"`
- ~~`launch_app_in_web_browser()`~~ → Use `launch_mode="web"`  
- ~~`open_collaborative_session()`~~ → Use `launch_mode="collaborative"`

You can say:

"Launch the file browser in a terminal window so I can see it"
"Open the process monitor in my web browser"
"Create a collaborative session with the API tester"
"Show me what's currently on the terminal screen"

🖱️ Send Keystrokes: AI can press any key in the apps (r for refresh, q to quit, etc.)
💬 Send Commands: AI can execute app-specific commands
📸 Screen Capture: AI can see the current state of running apps
🔄 Real-Time Interaction: Both you and AI can control the same app simultaneously
📊 Monitor & Automate: AI can run automated testing and monitoring

## Applications Library

### 📊 Current Available Applications

#### **Calculator** (v1.1.0)
- **Description**: Calculator with basic arithmetic and scientific functions
- **Tags**: calculator, math, utility, scientific
- **Features**: Standard mathematical operations, scientific functions
- **Launch**: `launch_app("calculator", launch_mode="web", port=8000)`

#### **File Browser** (v1.0.0)  
- **Description**: Advanced dual-pane file manager with syntax highlighting and file preview
- **Tags**: file-management, preview, utility
- **Features**: Dual-pane interface, syntax highlighting, file preview capabilities
- **Launch**: `launch_app("file_browser", launch_mode="web", port=8001)`

#### **Process Monitor** (v1.0.0)
- **Description**: Real-time system and process monitoring with management capabilities
- **Tags**: system, monitoring, processes, performance  
- **Features**: Real-time monitoring, process management, performance metrics
- **Launch**: `launch_app("process_monitor", launch_mode="web", port=8002)`

#### **API Tester** (v1.0.0)
- **Description**: REST API testing tool with request builder and response viewer
- **Tags**: api, testing, development, http
- **Features**: Request building, response viewing, HTTP testing capabilities
- **Launch**: `launch_app("api_tester", launch_mode="web", port=8003)`

## Installation

### Prerequisites
```bash
# Install multiplex (required for environment orchestration)
uv tool install multiplex-sh

# Verify multiplex is available
multiplex --help
```

### Setup
```bash
# Navigate to the project directory
cd /textualize-mcp

# Create and activate virtual environment using uv (recommended)
uv venv --python 3.12 --seed
source .venv/bin/activate

# Install dependencies (now includes multiplex-sh)
uv pip install -r pyproject.toml

# Alternatively, install directly with uv
# uv pip install -e .
```

## Usage

### As MCP Server with Claude Desktop

1. **Copy the example configuration:**
   ```bash
   cp example_mcp_config.json claude_desktop_config.json
   ```

2. **Edit paths in the configuration file to match your system:**
   ```json
   {
     "mcpServers": {
       "textualize-mcp": {
         "command": "uv",
         "args": [
           "--directory",
           "/your/path/to/textualize-mcp",
           "run",
           "server.py"
         ]
       }
     }
   }
   ```

3. **Add to your Claude Desktop configuration:**
   - Location: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
   - Or: `~/.config/claude/claude_desktop_config.json` (Linux)

4. **Restart Claude Desktop** to load the MCP server

### Standalone Applications
```bash
# Run any app directly
python -m textualize_mcp.apps.file_browser
python -m textualize_mcp.apps.process_monitor
python -m textualize_mcp.apps.api_tester
```

### Web Interface
```bash
# Serve any app in browser
textual serve textualize_mcp.apps.file_browser:FileBrowserApp
```

## 🎯 Key Multiplex Integration Features

### Process Coordination Syntax
The multiplex integration uses a powerful syntax for coordinating processes:

- **Named Processes**: `API=textual serve app.py` (creates referenceable process)
- **Colors**: `API#green=command` (color-codes output for visual distinction)
- **Time Delays**: `+5=command` (wait 5 seconds before starting)
- **Process Dependencies**: `+API=command` (wait for API process to complete)
- **Actions**:
  - `|silent` - suppress all output
  - `|end` - terminate all processes when this one ends
  - `|noout` - suppress stdout only
  - `|noerr` - suppress stderr only

### Example Multiplex Configuration
```json
[
  "DB#blue|silent=mongod --quiet --dbpath /tmp/dev_db",
  "API#green+2=textual serve api_tester.py --port 8001",
  "MONITOR#yellow+API=textual serve process_monitor.py --port 8002",
  "BROWSER+5=xdg-open http://localhost:8001"
]
```
This creates a coordinated environment where:
1. Database starts silently in background (blue output)
2. API server waits 2 seconds, then starts (green output)
3. Monitor waits for API to be ready, then starts (yellow output)
4. Browser opens after 5 seconds total

### Benefits Over Manual Process Management

| Feature | Manual Subprocess | Multiplex Integration |
|---------|------------------|----------------------|
| **Process Dependencies** | Manual coordination | Natural syntax (`+PROCESS=command`) |
| **Timing Control** | Manual delays | Built-in timing (`+5=command`) |
| **Output Management** | Complex pipe handling | Color-coded streams (`#color`) |
| **Cleanup** | Manual termination | Automatic graceful shutdown |
| **Visual Distinction** | All processes look same | Color-coded identification |
| **Error Handling** | Custom error logic | Built-in failure handling |
| **Scalability** | Complex to extend | Simple template addition |

## Architecture

```
textualize-mcp/
├── apps/           # Individual Textual applications
├── server/         # MCP server implementation
├── core/           # Shared utilities and base classes
├── templates/      # App generation templates
└── web/           # Web deployment configurations
```

## Development

```bash

# Run tests
pytest

# Start MCP server in development mode
python server.py --dev

# Create new application
python -m textualize_mcp.create_app MyNewApp
```

## License

MIT License - see LICENSE file for details.
