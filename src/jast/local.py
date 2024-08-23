from pathlib import Path
from typing import Any, Dict, List, Tuple

import tomlkit
from rich import print
from rich.prompt import Confirm

from jast.config import settings
from jast.jamf_client import JamfClient
from jast.schema import LocalJamfScript, RemoteJamfScript


def get_all_scripts() -> List[LocalJamfScript]:
    """
    Get all local scripts from the metadata directory.

    Returns:
        List[LocalJamfScript]: A list of LocalJamfScript objects representing all local scripts.

    Raises:
        ValueError: If no scripts are found in the metadata directory.
    """
    local_scripts = []
    for metadata_file in settings.scripts.metadata_dir.glob("*.toml"):
        
        with open(metadata_file, "r") as f:
            metadata = tomlkit.load(f)
        
        # Inject name from filename
        metadata.update(dict(
            name = metadata_file.stem
        ))
        
        local_script = LocalJamfScript(**metadata)
        local_scripts.append(local_script)
        
    if not local_scripts:
        raise ValueError("No scripts found!")
        
    return local_scripts


def get_script_by_id(script_id: int) -> LocalJamfScript:
    """
    Get a script by ID from a local directory of scripts.

    Args:
        script_id (int): The ID of the script to retrieve.

    Returns:
        LocalJamfScript: The LocalJamfScript object with the matching ID.

    Raises:
        FileNotFoundError: If no script with the given ID is found.
        ValueError: If multiple scripts with the same ID are found.
    """
    # New scripts will not have an ID, so we can ignore them.
    local_script = [x for x in get_all_scripts() if x.id is not None and int(x.id) == script_id]
    
    if not local_script:
        raise FileNotFoundError(f"Script with ID {script_id} not found.")
    
    if len(local_script) > 1:
        raise ValueError(f"Multiple scripts found with ID {script_id}!\n")
    
    return local_script[0]


def get_script_by_path(script_path: Path) -> LocalJamfScript:
    """
    Get a script by path from a local directory of scripts.

    Args:
        script_path (Path): The path of the script file to retrieve.

    Returns:
        LocalJamfScript: The LocalJamfScript object with the matching script file path.

    Raises:
        FileNotFoundError: If no script with the given path is found.
    """
    local_script = [x for x in get_all_scripts() if x.script_file == script_path]
    if not local_script:
        raise FileNotFoundError(f"Script with path {script_path} not found.")
    
    return local_script[0]


def prompt_name_mismatch(local_script: LocalJamfScript, remote_script: RemoteJamfScript) -> LocalJamfScript:
    """
    If the remote name differs from the local name, prompt the user for which name to use.

    Args:
        local_script (LocalJamfScript): The local script object.
        remote_script (RemoteJamfScript): The remote script object.

    Returns:
        LocalJamfScript: The updated local_script object.
    """
    
    # Change nothing, all good.
    if local_script.name == remote_script.name:
        return local_script
    
    # Conflict! Prompt for user action.
    use_local_name = Confirm.ask(f"[yellow]  - Script name mismatch![/]\n    Local: [green]'{local_script.name}'[/].\n    Remote: [green]'{remote_script.name}'[/].\n    Update remote?", default=True)
    if use_local_name:
        
        # Prefer local
        remote_script.name = local_script.name
        print(f"    [green]Renaming remote script: '{local_script.name}'\n")
        return local_script
        
    else:
        
        # Prefer remote
        print(f"    [magenta]Renaming local script: '{remote_script.name}'\n")
        local_script.metadata_file.rename(settings.scripts.metadata_dir / f"{remote_script.name}.toml")
        local_script.script_file.rename(settings.scripts.path / f"{remote_script.name}.sh")
        return local_script


def push_from_metadata(jamf: JamfClient, local_script: LocalJamfScript):
    """
    Find the script that matches the metadata file and push to JSS.

    Args:
        jamf (JamfClient): The Jamf client object.
        local_script (LocalJamfScript): The local script object to push.
    """
    
    # Push if it exists
    if not (local_script.script_file.exists()):
        print(f"[yellow]Script file {local_script.script_file} not found for {local_script.metadata_file}")
        return
    
    jamf.create_or_update_script(local_script)


def diff_lists(
    list1: List[Dict[str, Any]],
    list2: List[Dict[str, Any]],
    key_fields: Tuple[str, str] = ("id", "name")
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Compare two lists of dictionaries and return the differences.

    Args:
        list1 (List[Dict[str, Any]]): The first list of dictionaries to compare.
        list2 (List[Dict[str, Any]]): The second list of dictionaries to compare.
        key_fields (Tuple[str, str], optional): The fields to use as keys for comparison. Defaults to ("id", "name").

    Returns:
        Dict[str, List[Dict[str, Any]]]: A dictionary containing the differences:
            - "matched_diffs": Items that match but differ in other fields.
            - "in_list1_only": Items only in list1.
            - "in_list2_only": Items only in list2.
    """
    
    # Create lookup dictionaries based on "id" and "name"
    lookup1 = {d[key]: d for d in list1 for key in key_fields if key in d}
    lookup2 = {d[key]: d for d in list2 for key in key_fields if key in d}
    
    diffs = {
        "matched_diffs": [],  # Items that match but differ in other fields
        "in_list1_only": [],  # Items only in list1
        "in_list2_only": []   # Items only in list2
    }
    
    # Compare items from list1
    for item in list1:
        match = None
        for key in key_fields:
            if key in item and item[key] in lookup2:
                match = lookup2[item[key]]
                break
        
        if match:
            # If the items are different, add to diffs
            if item != match:
                diffs["matched_diffs"].append((item, match))
        else:
            diffs["in_list1_only"].append(item)
    
    # Compare items from list2 that weren't matched
    for item in list2:
        match = None
        for key in key_fields:
            if key in item and item[key] in lookup1:
                match = lookup1[item[key]]
                break
        
        if not match:
            diffs["in_list2_only"].append(item)
    
    return diffs