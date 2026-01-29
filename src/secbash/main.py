"""SecBASH CLI entry point.

Provides the Typer CLI interface for launching SecBASH.
"""

import typer

from secbash.shell import run_shell

app = typer.Typer(
    name="secbash",
    help="LLM-powered shell with security validation"
)


@app.command()
def main():
    """Launch SecBASH interactive shell."""
    exit_code = run_shell()
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
