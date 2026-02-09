"""aegish CLI entry point.

Provides the Typer CLI interface for launching aegish.
"""

import sys
from typing import Optional

import typer

from aegish import __version__
from aegish.config import validate_credentials
from aegish.shell import run_shell

app = typer.Typer(
    name="aegish",
    help="LLM-powered shell with security validation"
)


def version_callback(value: bool) -> None:
    """Display version and basic info, then exit."""
    if value:
        from aegish.config import get_available_providers
        print(f"aegish version {__version__}")
        providers = get_available_providers()
        if providers:
            print(f"Configured providers: {', '.join(providers)}")
        else:
            print("Configured providers: none (set API key to enable)")
        raise typer.Exit()


@app.command()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Launch aegish interactive shell."""
    # Validate credentials before starting
    is_valid, message = validate_credentials()

    if not is_valid:
        print(f"\nError: {message}\n", file=sys.stderr)
        raise typer.Exit(1)

    exit_code = run_shell()
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
