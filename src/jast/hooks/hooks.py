from pathlib import Path

import yaml

from jast.config import settings


def install_hooks():
    """
    Install pre-commit hooks for JAST.

    This function creates or updates the `.pre-commit-config.yaml` file in the current directory
    to include JAST-specific hooks. 
    
    If the .pre-commit-config.yaml file already exists, the function appends the JAST hooks
    to the existing configuration. If the file doesn't exist, it creates a new configuration
    with the JAST hooks.

    The function uses the PyYAML library to handle YAML file operations.

    Returns:
        None
    """

    # Read the adjacent pre-commit-config file.
    config_path = Path(__file__).parent / ".pre-commit-config.yaml"
    with open(config_path, "r") as config_file:
        hook_config = yaml.safe_load(config_file)
        
    precommit_config_path = (
        Path(settings.scripts.path.parent) / ".pre-commit-config.yaml"
    )

    if precommit_config_path.exists():
        with precommit_config_path.open("r") as f:
            config = yaml.safe_load(f)
        config["repos"].append(hook_config)
    else:
        config = {"repos": [hook_config]}

    with precommit_config_path.open("w") as f:
        yaml.safe_dump(config, f)


# Call this function within your CLI
install_hooks()
