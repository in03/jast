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
        script_path = Path(path) / remote_script.name
        if script_path.exists() and not force:
            overwrite = Confirm.ask(
                "[yellow]  - Script file already exists. Overwrite?", default=True
            )
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
    dir: Path = typer.Argument(
        settings.scripts.path,
        help="Directory of target scripts to push to JSS. Auto match metadata files.",
    ),
    name: str = typer.Option(
        None,
        help="Whitelist. Only push scripts with filenames matching this comma separated list.",
    ),
    id: str = typer.Option(
        None,
        help="Whitelist. Only push scripts with IDs matching this comma separated list.",
    ),
):
    """
    Create or update remote Jamf scripts from local scripts and metadata files.

    By default, all scripts in the configured 'scripts_path' are pushed. Override this by specifying a directory.

    - Single filename    --name   "provisioning_script"

    - Single ID          --id     "160"

    - Filename list      --name   "script1.sh, script with spaces.sh, script_no_ext"

    - ID list            --id     "160, 109, 21"

    You may also specify dir and a list of both names and IDs within that directory.
    """

    #! Warning! Overrides the script and metadata paths!
    # Why? Dependency injection nightmare to add params to nested functions across modules.
    # To prevent side-effects, ensure the program ends soon after the push or reset it.

    # Override script path
    settings.scripts.path = dir
    if not settings.scripts.metadata_dir.exists():
        print(
            f"[yellow]Metadata directory '{settings.scripts.metadata_dir}' does not exist."
        )
        return

    # Re-derive metadata path
    if not settings.scripts.metadata_in_subfolder:
        settings.scripts.metadata_dir = dir
    else:
        settings.scripts.metadata_dir = dir / "metadata"
    if not settings.scripts.metadata_dir.exists():
        print(
            f"[yellow]Metadata directory '{settings.scripts.metadata_dir}' does not exist."
        )
        return

    ###############################################################

    jamf = JamfClient(settings.jamf.url, settings.jamf.user, settings.jamf.password)

    # Push all
    if not name and not id:
        push_all(jamf)
        print("\n[green]--- Push complete ---\n")
        return

    # Whitelisted
    if name:
        push_from_file_list(jamf, name)

    if id:
        push_from_id_list(jamf, id)

    print("\n[green]--- Push complete ---\n")
    return


def push_from_file_list(jamf: JamfClient, file_list: str):
    """
    Push scripts by filename from the local directory to Jamf Pro.

    Args:
        jamf (JamfClient): An instance of the JamfClient used to interact with Jamf Pro.
        file_list (str): A comma-separated list of filenames to push.

    Returns:
        None

    Note:
        - Skips files without corresponding metadata.
        - Prints status messages for each script processed.
    """
    filenames = [f.strip() for f in file_list.split(",")]
    print(f"[magenta]\nPushing {len(filenames)} scripts by filename...\n")

    for filename in filenames:
        print(f"[cyan]'{filename}':", end=" ")

        filepath = settings.scripts.path / filename
        metadata_path = settings.scripts.metadata_dir / f"{Path(filename)}.toml"

        if not filepath.resolve().exists():
            print(f"   [yellow]Script at path {filepath} not found. Skipping...")
            continue

        if not metadata_path.resolve().exists():
            print(f"[yellow]Metadata file {metadata_path} does not exist.")
            continue

        local_script = local.get_script_by_path(filepath)

        # Hint pushing new
        print("✨") if local_script.id is None else print(f"'{local_script.id}'")

        # Push it
        remote_script = jamf.create_or_update_script(local_script)
        print("        [green]Pushed ✅")

        # Update ID in metadata file
        if not local_script.id:
            new_local = remote_script.convert_to_local()
            new_local.save_metadata_file()
            print(f"        [green]ID {new_local.id}\n")


def push_from_id_list(jamf: JamfClient, id_list: str):
    """
    Push scripts by ID from TOML files to Jamf Pro.

    Args:
        jamf (JamfClient): An instance of the JamfClient used to interact with Jamf Pro.
        id_list (str): A comma-separated list of script IDs to push.

    Returns:
        None

    Note:
        - Supports multiple IDs, comma separated.
        - Scripts are presumed to already be registered in JSS.
        - If the name of the script has changed locally, you will be prompted to update the script name.
        - Prints status messages for each script processed.
    """
    ids = [f.strip() for f in id_list.split(",")]
    print(f"[magenta]\nPushing {len(ids)} scripts by ID...\n")

    for id in ids:
        print(f"[cyan]'{id}':", end=" ")

        id = int(id)

        remote_script = jamf.get_script_by_id(id)
        local_script = local.get_script_by_id(id)

        print(f"'{remote_script.name}'")

        if not local_script:
            print(f"   [yellow]Script with ID {id} not found. Skipping...")
            continue

        local_script = local.prompt_name_mismatch(local_script, remote_script)

        local_script.categoryId = jamf.get_category_id_by_name(
            local_script.categoryName
        )

        jamf.create_or_update_script(local_script)
        print("        [green]Pushed ✅\n")

    return


def push_all(jamf: JamfClient):
    """
    Push all scripts from the local directory to Jamf Pro.

    Args:
        jamf (JamfClient): An instance of the JamfClient used to interact with Jamf Pro.

    Returns:
        None

    Note:
        - Iterates through all files in the scripts directory specified in the settings.
        - Attempts to create or update each script in Jamf Pro.
        - Skips files without corresponding metadata.
        - Assumes that script files exist if metadata is present.
        - Prints status messages for each script processed.
    """
    for file in settings.scripts.path.glob("*"):
        print(f"[cyan]'{file}':", end=" ")

        local_script = local.get_script_by_path(file)

        assert local_script.script_file.exists()

        if not local_script.metadata_file.exists():
            print(f"   [yellow]Metadata file not found for '{file}'. Skipping...")
            continue

        jamf.create_or_update_script(local_script)
        print("        [green]Pushed ✅\n")

        return


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


# region Delete
@scripts_app.command()
def delete(
    id: int = typer.Argument(
        help="The ID of the script to delete.",
    ),
    force: bool = typer.Option(
        False,
        help="Don't prompt for confirmation.",
    ),
    soft: bool = typer.Option(
        False,
        help="Soft delete. Append '(DELETE ME)' to script name.",
    ),
):
    """
    Delete a script from Jamf.

    This does not deal with the deletion of local scripts, only remote scripts in JSS.

    Use with caution! Deletions are hard by default. Pass --soft to soft delete.

    This command is also used internally by the pre-push hook.
    """

    jamf = JamfClient(settings.jamf.url, settings.jamf.user, settings.jamf.password)

    if not force:
        if not Confirm.ask(
            "[yellow]Are you sure you want to delete this script?", default=False
        ):
            print("Aborting...")
            return

    remote_script = jamf.get_script_by_id(id)
    remote_script_name = remote_script.name

    if soft:
        delete_name = remote_script_name + " (DELETE ME)"
        print(f"[yellow]Soft deleting script: ID {id}: '{delete_name}'")
        jamf.rename_script(script_id=id, new_name=delete_name)
        return

    print(f"[yellow]Deleting script: ID {id}: '{remote_script_name}'")
    jamf.delete_script(script_id=id)
    
    # Remove ID attribute from corresponding TOML file
    local_script = remote_script.convert_to_local()
    local_script.id = None
    local_script.save_metadata_file()
    
    print("[green]Deleted ✅")


# endregion
