
import typer

from jast.config import config_app
from jast.scripts import scripts_app

# Initialise the CLI app
app = typer.Typer(
    name="jamf-script-tool",
    no_args_is_help=True,
)
app.add_typer(
    config_app,
    name="config",
    help="Manage JAST configuration settings.",
    no_args_is_help=True,
)
app.add_typer(
    scripts_app,
    name="scripts",
    help="Manage JSS scripts.",
    no_args_is_help=True,
)

if __name__ == "__main__":
    app()
