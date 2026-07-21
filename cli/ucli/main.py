import pathlib
import sys

# The package is `cli.ucli` but modules use absolute `ucli.*` imports; ensure `cli/`
# is on sys.path so those resolve when the app is run from an installed console script.
_cli_parent = pathlib.Path(__file__).resolve().parent.parent
if str(_cli_parent) not in sys.path:
    sys.path.insert(0, str(_cli_parent))

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        reconf = getattr(_stream, "reconfigure", None)
        if callable(reconf):
            try:
                reconf(encoding="utf-8")
            except (OSError, ValueError, AttributeError):
                pass

import typer
from rich.console import Console

from ucli.commands.init_ops import show_banner, show_welcome_message
from ucli.commands.typer_groups import register_all_groups

app = typer.Typer(
    help=(
        "Understand-first CLI (u): lenses, traces, contracts, boundaries, "
        "tour gate, delta visualizer."
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
)

register_all_groups(app)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", is_eager=True, help="Show version and exit"
    ),
    help: bool = typer.Option(False, "--help", "-h", help="Show help and exit"),
):
    """Understand First CLI - Accelerate code understanding with intelligent analysis."""
    console = Console()

    if version:
        console.print("Understand First CLI v0.3.0", style="bold cyan")
        raise typer.Exit()

    if ctx.invoked_subcommand is None or help:
        show_banner()
        show_welcome_message()
        console.print()
        console.print(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    app()
