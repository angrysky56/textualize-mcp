"""Main entry point for Textualize MCP Server."""

import sys
from pathlib import Path

from textualize_mcp.server.mcp_server import mcp

# Add the package to Python path
package_root = Path(__file__).parent
sys.path.insert(0, str(package_root))


if __name__ == "__main__":
    mcp.run()
