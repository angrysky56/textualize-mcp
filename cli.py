#!/usr/bin/env python3
"""
Textualize MCP CLI Tool

Simple command-line interface for running Textual applications individually
or starting the MCP server.
"""

import sys
from pathlib import Path

import click

from textualize_mcp.core.base import AppRegistry
from textualize_mcp.server.mcp_server import main as server_main

# Add the package to Python path
package_root = Path(__file__).parent
sys.path.insert(0, str(package_root))





@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Textualize MCP - Terminal applications with MCP interface."""
    pass


@cli.command()
def server():
    """Start the MCP server."""
    click.echo("Starting Textualize MCP Server...")
    server_main()


@cli.command()
def list_apps():
    """List all available applications."""
    apps = AppRegistry.list_apps()
    if not apps:
        click.echo("No applications available.")
        return

    click.echo("Available applications:")
    click.echo()

    for app_config in apps:
        click.echo(f"  {app_config.name}")
        click.echo(f"    Description: {app_config.description}")
        click.echo(f"    Version: {app_config.version}")
        click.echo(f"    Tags: {', '.join(app_config.tags)}")
        click.echo()


@cli.command()
@click.argument('app_name')
@click.option('--web', is_flag=True, help='Run in web browser mode')
@click.option('--port', default=8000, help='Port for web mode')
def run(app_name: str, web: bool, port: int):
    """Run a specific application."""
    app_class = AppRegistry.get_app_class(app_name)
    if not app_class:
        click.echo(f"Unknown application: {app_name}", err=True)
        click.echo("Use 'textualize-mcp list-apps' to see available applications.")
        sys.exit(1)

    if web:
        click.echo(f"Starting {app_name} in web mode on port {port}...")
        # Use textual serve to run in web mode
        import subprocess
        module_path = f"textualize_mcp.apps.{app_name}:{app_class.__name__}"
        cmd = ["textual", "serve", module_path, "--port", str(port)]
        subprocess.run(cmd)
    else:
        click.echo(f"Starting {app_name} in terminal mode...")
        app = app_class()
        app.run()


@cli.command()
@click.argument('app_name')
def info(app_name: str):
    """Get detailed information about an application."""
    app_class = AppRegistry.get_app_class(app_name)
    if not app_class:
        click.echo(f"Unknown application: {app_name}", err=True)
        sys.exit(1)

    config = app_class.get_config()

    click.echo(f"Application: {config.name}")
    click.echo(f"Description: {config.description}")
    click.echo(f"Version: {config.version}")
    click.echo(f"Author: {config.author}")
    click.echo(f"Tags: {', '.join(config.tags)}")
    click.echo(f"Requires Web: {config.requires_web}")
    click.echo(f"Requires Sudo: {config.requires_sudo}")

    # Show key bindings if available
    bindings = getattr(app_class, 'BINDINGS', [])
    if bindings:
        click.echo("\nKey Bindings:")
        for binding in bindings:
            if len(binding) >= 3:
                key, action, description = binding[:3]
                click.echo(f"  {key}: {description}")


if __name__ == "__main__":
    cli()
