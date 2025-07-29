"""Available Textual applications."""

# Import all available applications to register them
from . import api_tester, calculator, file_browser, process_monitor
from .api_tester import APITesterApp
from .calculator import CalculatorApp

# Make applications available for import
from .file_browser import FileBrowserApp
from .process_monitor import ProcessMonitorApp

__all__ = [
    "FileBrowserApp",
    "ProcessMonitorApp",
    "APITesterApp",
    "CalculatorApp"
]
