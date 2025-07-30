"""Available Textual applications."""

import importlib
import inspect
from pathlib import Path

from ..core.base import AppRegistry, BaseTextualApp


def discover_and_register_apps():
    """Automatically discover and register all apps in the apps directory."""
    apps_dir = Path(__file__).parent

    # Find all Python files in the apps directory (excluding __init__.py)
    for py_file in apps_dir.glob("*.py"):
        if py_file.name.startswith("__"):
            continue

        module_name = py_file.stem
        try:
            # Import the module
            module = importlib.import_module(f".{module_name}", package=__name__)

            # Find all classes that inherit from BaseTextualApp
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, BaseTextualApp) and
                    obj is not BaseTextualApp and
                    hasattr(obj, 'APP_CONFIG')):

                    # Register the app
                    AppRegistry.register(obj)

        except Exception:
            # Silently skip modules that can't be imported
            pass


# Automatically discover and register all apps
discover_and_register_apps()


def list_apps():
    """List all registered applications."""
    return AppRegistry.get_apps_dict()


def get_app_configs():
    """Get all registered application configurations."""
    return AppRegistry.list_apps()


# For backward compatibility, we can still provide explicit exports
# but they're no longer required for registration
__all__ = ["list_apps", "get_app_configs"]
