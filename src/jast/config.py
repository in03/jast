import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import tomlkit
import typer
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console
from rich.table import Table

# Set config path
config_filename = "config.toml"
application_dir = Path(typer.get_app_dir("Jamf Script Tool", roaming=True))
config_filepath = Path(application_dir) / config_filename

# Initialise the config app
config_app = typer.Typer()


# region Settings
class JamfSettings(BaseSettings):
    url: str = Field("http://your-jamf-url.com:8443")
    user: str = Field("your-jamf-username")
    password: str = Field("your-jamf-password")


class ScriptSettings(BaseSettings):
    path: Path = Field(".")
    metadata_in_subfolder: bool = Field(True)
    metadata_dir: Path = Field("")


class SSLSettings(BaseSettings):
    verify: bool = Field(True)
    warn: bool = Field(True)


class Settings(BaseSettings):
    jamf: JamfSettings
    scripts: ScriptSettings
    ssl: SSLSettings

    model_config = SettingsConfigDict(
        env_prefix="JAST_",
        env_nested_delimiter="__",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
    )


# Initialize settings
settings = Settings(**tomlkit.parse(config_filepath.read_text()))

# Dynamic configuration
settings.scripts.metadata_dir = Path(settings.scripts.path)
if settings.scripts.metadata_in_subfolder:
    settings.scripts.metadata_dir = Path(settings.scripts.path) / "metadata"

# endregion

# region Commands


@config_app.command()
def show():
    """
    Shows JAST's current configuration in a table.
    """
    table = Table(title="Current Configuration")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    for key, value in settings.model_dump().items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                table.add_row(f"{key}.{sub_key}", str(sub_value))
        else:
            table.add_row(key, str(value))

    console = Console()
    console.print(table)


@config_app.command()
def edit():
    """
    Edit the configuration file.
    """
    if application_dir.exists():
        if config_filepath.exists():
            typer.echo("Opening configuration file for editing...")
            typer.launch(str(config_filepath))
        else:
            typer.echo("Configuration file not found.")


@config_app.command()
def browse():
    """
    Navigate to the configuration file in file browser.
    """
    typer.echo("Opening configuration directory in file browser...")
    typer.launch(str(application_dir))


@config_app.command()
def reset():
    """
    Set the configuration file to default values.
    """
    if typer.confirm(
        "Are you sure you want to reset the configuration file to default values?",
        abort=True,
    ):
        if application_dir.exists():
            for file in application_dir.iterdir():
                file.unlink()
            typer.echo("Configuration file reset.")
        else:
            typer.echo("Configuration file not found.")


@config_app.command()
def backup(
    backup_path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Optional backup path"
    ),
):
    """
    Backup the configuration file.
    """
    if application_dir.exists():
        if config_filepath.exists():
            if backup_path:
                backup_file = (
                    backup_path / f"config_{datetime.now().strftime('%Y-%m-%d')}.toml"
                )
            else:
                backup_file = (
                    application_dir
                    / f"config_{datetime.now().strftime('%Y-%m-%d')}.toml"
                )

            backup_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(config_filepath, backup_file)
            typer.echo(f"Configuration file backed up to {backup_file}")
        else:
            typer.echo("Configuration file not found.")
    else:
        typer.echo("Configuration file not found.")


# endregion
