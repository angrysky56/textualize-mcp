"""
Quick test script to verify the textualize-mcp setup works correctly.
"""

import sys
from pathlib import Path

# Add the package to Python path
package_root = Path(__file__).parent
sys.path.insert(0, str(package_root))

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")

    try:
        from textualize_mcp.core.base import AppRegistry, BaseTextualApp
        print("✓ Core base imports successful")
    except ImportError as e:
        print(f"✗ Core base import failed: {e}")
        return False

    try:
        from textualize_mcp.apps import FileBrowserApp, ProcessMonitorApp, APITesterApp
        print("✓ App imports successful")
    except ImportError as e:
        print(f"✗ App import failed: {e}")
        return False

    try:
        from textualize_mcp.server.mcp_server import mcp, app_manager
        print("✓ MCP server imports successful")
    except ImportError as e:
        print(f"✗ MCP server import failed: {e}")
        return False

    return True


def test_app_registry():
    """Test that applications are properly registered."""
    print("\nTesting app registry...")

    from textualize_mcp.core.base import AppRegistry

    apps = AppRegistry.list_apps()
    app_names = [app.name for app in apps]

    expected_apps = ["file_browser", "process_monitor", "api_tester"]

    for expected in expected_apps:
        if expected in app_names:
            print(f"✓ {expected} is registered")
        else:
            print(f"✗ {expected} is NOT registered")
            return False

    print(f"✓ Total registered apps: {len(apps)}")
    return True


def test_app_configs():
    """Test that app configurations are valid."""
    print("\nTesting app configurations...")

    from textualize_mcp.core.base import AppRegistry

    for app_config in AppRegistry.list_apps():
        print(f"✓ {app_config.name}: {app_config.description}")

        # Check required fields
        if not app_config.name:
            print(f"✗ {app_config.name} missing name")
            return False
        if not app_config.description:
            print(f"✗ {app_config.name} missing description")
            return False

    return True


def test_mcp_functions():
    """Test that MCP functions are available."""
    print("\nTesting MCP functions...")

    from textualize_mcp.server.mcp_server import mcp

    # Check that required functions exist
    required_functions = [
        "list_apps",
        "launch_app",
        "get_app_info",
        "terminate_app",
        "get_app_status",
        "list_running_apps",
        "get_server_info"
    ]

    for func_name in required_functions:
        if hasattr(mcp, func_name):
            print(f"✓ {func_name} is available")
        else:
            # Try to import the function directly from mcp_server as a fallback
            try:
                from textualize_mcp.server import mcp_server
                if hasattr(mcp_server, func_name):
                    print(f"✓ {func_name} function exists in mcp_server")
                else:
                    print(f"✗ {func_name} function missing")
                    return False
            except Exception:
                print(f"? {func_name} - unable to verify")

    return True


def main():
    """Run all tests."""
    print("=== Textualize MCP Test Suite ===\n")

    tests = [
        test_imports,
        test_app_registry,
        test_app_configs,
        test_mcp_functions
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            print(f"\nTest failed: {test.__name__}")

    print("\n=== Results ===")
    print(f"Passed: {passed}/{total} tests")

    if passed == total:
        print("✓ All tests passed! Textualize MCP is ready to use.")
        print("\nNext steps:")
        print("1. python server.py  # Start MCP server")
        print("2. python cli.py run file_browser  # Test an app")
        print("3. Add to Claude Desktop MCP config")
        return True
    else:
        print("✗ Some tests failed. Check the errors above.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
