from pathlib import Path
from typing import Optional

import tomlkit
from pydantic import BaseModel, Field

from jast.config import settings


class JamfCategory(BaseModel):
    id: int = Field(..., description="The unique identifier for the Jamf category")
    name: str = Field(..., description="The name of the Jamf category")
    priority: int = Field(..., description="The priority of the Jamf category")


# region JamfScript
class JamfScript(BaseModel):
    """
    Base model for Jamf scripts and their metadata.

    This is how Jamf's API represents a scripts metadata and contents.

    ---

    All fields are optional with some defaults.
    Of course an object with no fields cannot be mapped and is not useful.

    Instead, we use the subclasses `LocalJamfScript` and `RemoteJamfScript`:
    - `LocalJamfScript` is used to represent a script that exists on the local filesystem.
        - It is not guaranteed to have an ID if it has not yet been pushed to the server.
        - It is guaranteed to have an "expected" filename and path on the filesystem.
    - `RemoteJamfScript` is used to represent a script that exists on the Jamf server.
    """

    id: Optional[int] = Field(
        None, description="The unique identifier for the Jamf script"
    )
    name: Optional[str] = Field("", description="The name of the Jamf script")
    info: Optional[str] = Field(
        "", description="Additional information about the Jamf script"
    )
    notes: Optional[str] = Field("", description="Notes related to the Jamf script")
    priority: Optional[str] = Field(
        "AFTER",
        description="The execution priority of the script",
        pattern=r"BEFORE|AFTER|AFTER REBOOT",
    )
    parameter4: Optional[str] = Field(
        "", description="Optional parameter 4 for the script"
    )
    parameter5: Optional[str] = Field(
        "", description="Optional parameter 5 for the script"
    )
    parameter6: Optional[str] = Field(
        "", description="Optional parameter 6 for the script"
    )
    parameter7: Optional[str] = Field(
        "", description="Optional parameter 7 for the script"
    )
    parameter8: Optional[str] = Field(
        "", description="Optional parameter 8 for the script"
    )
    parameter9: Optional[str] = Field(
        "", description="Optional parameter 9 for the script"
    )
    parameter10: Optional[str] = Field(
        "", description="Optional parameter 10 for the script"
    )
    parameter11: Optional[str] = Field(
        "", description="Optional parameter 11 for the script"
    )
    osRequirements: Optional[str] = Field(
        "", description="Operating system requirements for the script"
    )
    scriptContents: Optional[str] = Field("", description="The contents of the script")
    categoryId: Optional[int] = Field(
        -1, description="The ID of the category the script belongs to"
    )
    categoryName: Optional[str] = Field(
        "NONE", description="The name of the category the script belongs to"
    )

    @property
    def toml_metadata(self):
        """
        Return a dictionary representation excluding non-editable or non-serialisable fields:

        This is used to generate the TOML metadata files:

        - Do not track `name`, since it is derived from the filename
        - Do not track `categoryID`, since it is derived from the `categoryName`
        - Do not track `scriptContents`, since it is derived from the script file
        - Do not track `scriptPath`, since it is derived from the settings and filename.
        - Do not track `metadataPath`, since it is derived from the settings and filename.

        """
        return self.model_dump(
            exclude=(
                "name",
                "categoryId",
                "scriptContents",
                "scriptPath",
                "metadataPath",
            )
        )

    @property
    def payload_data(self):
        "Return a dictionary representation of the object for use in the API excluding 'metadataPath' and 'scriptPath'"
        return self.model_dump(
            exclude=(
                "metadataPath",
                "scriptPath",
            )
        )

    def load_script_contents(self):
        """Load the script contents into the `JamfScript` instance."""
        with open(self.script_file, "r") as script_file:
            self.scriptContents = script_file.read()


# endregion


# region RemoteJamfScript
class RemoteJamfScript(JamfScript):
    id: int = Field(..., description="The unique identifier for the remote Jamf script")
    name: str = Field(..., description="The name of the remote Jamf script")

    def convert_to_local(self):
        """
        Convert `RemoteJamfScript` to `LocalJamfScript`

        This adds required fields and dynamic properties:
        - `scriptPath`
        - `script_file`
        - `metadataPath`
        - `metadata_file`
        """
        return LocalJamfScript(**self.model_dump())


# endregion


# region LocalJamfScript
class LocalJamfScript(JamfScript):
    name: str = Field(..., description="The name of the local Jamf script")
    metadataPath: Path = Field(
        settings.scripts.metadata_dir, description="The path to the metadata folder"
    )
    scriptPath: Path = Field(
        settings.scripts.path, description="The path to the script folder"
    )

    def convert_to_remote(self):
        """
        Converts `LocalJamfScript` to `RemoteJamfScript`

        This strips the unnecessary local metadata (filepaths, etc) and enforces ID is not None
        """
        return RemoteJamfScript(**self.model_dump())

    @property
    def script_file(self):
        """Path to the script file, e.g. `my_script.sh`"""
        return self.scriptPath / f"{self.name}.sh"

    @property
    def metadata_file(self):
        """Path to the toml metadata file, e.g. `my_script.toml`"""
        return self.metadataPath / f"{self.name}.toml"

    def save_metadata_file(self):
        """
        Write the relevant `JamfScript` fields to the corresponding TOML metadata file.

        Irrelevant fields are excluded:
        - `name` (derived from filename on push)
        - `categoryId` (derived from `categoryName` on push)
        - `scriptContents` (derived from script file on push)
        """

        # Create the output directory if it doesn't exist
        self.metadataPath.mkdir(exist_ok=True)

        # Write the data to a TOML file
        with open(self.metadata_file, "w") as metadata_file:
            metadata_file.write(tomlkit.dumps(self.toml_metadata))
