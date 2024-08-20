from pathlib import Path

import typer
from rich import print
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from jast import local
from jast.config import settings
from jast.jamf_client import JamfClient
from jast.schema import LocalJamfScript

# Initialise the config app
scripts_app = typer.Typer()


# region Show
@scripts_app.command()
def show():
    """
    Show all current JSS scripts in a table.
    """

    console = Console()
    with console.status("[cyan]Fetching scripts..."):
        jamf = JamfClient(settings.jamf.url, settings.jamf.user, settings.jamf.password)

        scripts = jamf.get_all_scripts()

    table = Table(title="JSS Scripts")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")

    for script in scripts:
        table.add_row(str(script.id), script.name)

    console = Console()
    print(table)


# endregion


# region Pull
@scripts_app.command()
def pull(
    path: str = typer.Option(
        settings.scripts.path,
        help="Path to save scripts and metadata files. Optional. Defaults to the configured 'scripts_path'.",
    ),
    force: bool = typer.Option(
        False,
        help="Force overwrite of existing local scripts and metadata files. Defaults to False.",
    ),
):
    """
    Download Jamf scripts and generate script metadata files.
    """

    console = Console()
    with console.status("[cyan]Fetching scripts..."):
        jamf = JamfClient(settings.jamf.url, settings.jamf.user, settings.jamf.password)
        remote_scripts = jamf.get_all_scripts()

    print(f"[magenta]Pulling {len(remote_scripts)} scripts...\n")
    for remote_script in remote_scripts:
        print(f"[cyan]'{remote_script.name}':")

        local_jamf_script = remote_script.convert_to_local()

        # Handle metadata (TOML file)
        metadata_file = local_jamf_script.metadata_file
        if metadata_file.exists() and not force:
            overwrite = Confirm.ask(
                "[yellow]  - Metadata file already exists. Overwrite?", default=False
            )
            if not overwrite:
                print("    [magenta]Skipped metadata")
            else:
                local_jamf_script.save_metadata_file()
                print("    [green]Saved metadata")
        else:
            local_jamf_script.save_metadata_file()

        # Handle script file
        script_content = remote_script.scriptContents
        script_path = Path(path) / f"{remote_script.name}.sh"
        if script_path.exists() and not force:
            overwrite = typer.confirm("  - Script file already exists. Overwrite?")
            if not overwrite:
                print("    [magenta]Skipped script")
            else:
                with open(script_path, "w") as script_file:
                    script_file.write(script_content)
                print("    [green]Saved script")
        else:
            with open(script_path, "w") as script_file:
                script_file.write(script_content)

    print(f'\n[green]Pull complete. Check "{settings.scripts.path}"\n')


# endregion


# region Push
@scripts_app.command()
def push(
    dir: Path = typer.Option(
        settings.scripts.path,
        help="Directory of scripts to push to JSS. Auto match metadata files.",
    ),
    file: str = typer.Option(
        None,
        help="List of filepaths to push to JSS. Relative. Comma separated. Auto match metadata files.",
    ),
    id: str = typer.Option(
        None,
        help="List of files to push to JSS. Use IDs from TOML files. Comma separated. Auto match script by name.",
    ),
):
    """Create or update Jamf scripts from local scripts and metadata files."""

    # Handle parameters as mutually exclusive
    if sum(bool(arg) for arg in [file, id, (dir != settings.scripts.path)]) > 1:
        raise typer.BadParameter(
            "Please provide only one of --scripts-path, --file, or --id."
        )

    jamf = JamfClient(settings.jamf.url, settings.jamf.user, settings.jamf.password)

    if file:
        push_from_file_list(jamf, file)
        return

    if id:
        push_from_id_list(jamf, id)
        return

    push_from_directory(jamf, dir)


def push_from_file_list(jamf: JamfClient, file: str):
    script_files = [f.strip() for f in file.split(",")]
    for script_file in script_files:
        script_name = Path(script_file).stem
        metadata_file = Path(settings.scripts.metadata_dir) / f"{script_name}.toml"

        if not Path(script_file).resolve().exists():
            print(f"[yellow]Script file {script_file} does not exist.")
            continue

        if not metadata_file.resolve().exists():
            print(f"[yellow]Metadata file {metadata_file} does not exist.")
            continue

        local.push_from_metadata(jamf, metadata_file, Path(script_file).parent)


def push_from_id_list(jamf: JamfClient, ids: str):
    """
    Push scripts by ID from TOML files

    Supports multiple IDs, comma separated.

    Since an ID is provided, scripts are presumed to already be registered in JSS.
    If the name of the script has changed locally, you will be prompted to update the script name.

    """
    script_ids = [f.strip() for f in ids.split(",")]
    print(f"[magenta]Pushing {len(script_ids)} scripts...\n")

    for script_id in script_ids:
        print(f"[cyan]'{script_id}':", end=" ")

        remote_script = jamf.get_script_by_id(script_id)
        local_script = local.get_script_by_id(script_id)

        print(f"'{remote_script.name}'")

        # No script matching ID, check next in lsit
        if not local_script:
            print(f"   [yellow]Script with ID {script_id} not found. Skipping...")
            continue

        # IDs match, script names don't... How handle??
        local_script = local.prompt_name_mismatch(local_script, remote_script)

        # Add category ID
        local_script.categoryId = jamf.get_category_id_by_name(
            local_script.categoryName
        )

        local.push_from_metadata(jamf, local_script)
        print("        [green]Pushed ✅\n")

    print("\n[green]--- Push complete ---\n")


def push_from_directory(jamf: JamfClient, scripts_path: Path):
    if not scripts_path.exists():
        raise typer.BadParameter(
            f"{scripts_path} does not exist. Please provide a valid directory."
        )

    for script_file in scripts_path.glob("*.sh"):
        script_name = script_file.stem
        metadata_file = Path(settings.scripts.metadata_dir) / f"{script_name}.toml"
        if metadata_file.exists():
            local.push_from_metadata(jamf, metadata_file, scripts_path)


# endregion


# region New
@scripts_app.command()
def new():
    """
    Create a new template script and metadata file.
    """
    # Prompt for data
    local_script = LocalJamfScript(
        name=typer.prompt("Enter script name", "New Script"),
        info=typer.prompt("Enter script information", ""),
        notes=typer.prompt("Enter script notes", ""),
    )

    if local_script.metadata_file.exists():
        print(f"[yellow]'{local_script.metadata_file}' already exists! Please check...")
        return

    if local_script.script_file.exists():
        print(f"[yellow]'{local_script.script_file}' already exists! Please check...")
        return

    # Create the toml metadata file
    local_script.save_metadata_file()
    print("[green]Created metadata file.")

    # Create a new empty script file
    with open(local_script.script_file, "x") as script_file:
        script_file.write(r"#!/bin/bash")
        script_file.write("\n\n")

    print(f"[green]Created new script: {local_script.script_file}")


# endregion


# region Verify
@scripts_app.command()
def verify():
    """
    Verify local store and JSS DB are in sync.
    """

    jamf = JamfClient(settings.jamf.url, settings.jamf.user, settings.jamf.password)

    local_scripts = local.get_all_scripts()
    remote_scripts = jamf.get_all_scripts()

    print(local_scripts)


# endregion
