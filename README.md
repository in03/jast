# Jast (JaST) 📜 🔁

[![PyPI - Version](https://img.shields.io/pypi/v/jamf-script-tool.svg)](https://pypi.org/project/jamf-script-tool)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/jamf-script-tool.svg)](https://pypi.org/project/jamf-script-tool)

-----

Jast is a tool for managing Jamf Pro scripts locally.
It allows you to download, create and update scripts through the Jamf Pro API.
This opens the door for a few things:
- **local development**: BYO IDE, linters, extensions, formatters, etc.
- **version control**: git, GitHub, etc.
- **workflow automation**: CI/CD pipelines.

## Table of Contents

- [Installation](#installation)
- [License](#license)
- [Usage](#usage)

## Installation

```console
pip install jamf-script-tool
```

## License

`jamf-script-tool` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.

## Usage

### Configuration
Provide environment variables to configure the tool. These can be set in a `.env` file or as environment variables.
If environment variables are not provided, the tool will prompt for them at runtime.

> **NOTE:**
>
> To prevent usage of existing Jamf environment variables and undesired modification of scripts, the `JAST__` prefix is used. 

- `JAST__JAMF_URL`: The URL of the Jamf Pro instance.
- `JAST__JAMF_USER`: The username of the Jamf Pro API user.
- `JAST__JAMF_PASS`: The password of the Jamf Pro API user.
- `JAST__SCRIPT_DIR`: Absolute path to local scripts directory. 
    - Created if it doesn't exist.

#### Optional
- `JAST_SSL_NO_VERIFY`: Allow self-signed certs. USE WITH CAUTION.


## Usage

**Jast** uses Typer for a convenient CLI.

Run `jast help` to see all available commands.

```console
 Usage: jast [OPTIONS] COMMAND [ARGS]...                                                   
                                                                                             
╭─ Options ─────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                   │
│ --show-completion             Show completion for the current shell, to copy it or        │
│                               customize the installation.                                 │
│ --help                        Show this message and exit.                                 │
╰───────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────╮
│ pull   Download Jamf scripts and generate TOML files for each script's Jamf metadata.     │
│ push   Create or update Jamf scripts based on TOML files in the specified directory.      │
╰───────────────────────────────────────────────────────────────────────────────────────────╯

```
