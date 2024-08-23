"""
This module provides a client for interacting with the Jamf Pro API.

It includes functionality for authentication, managing categories, and handling scripts.
"""

from typing import Any, Dict, List

import requests
from rich import print

from jast.config import settings
from jast.schema import JamfCategory, LocalJamfScript, RemoteJamfScript

# Warn ONCE if SSL verification is disabled
if not settings.ssl.verify:
    requests.packages.urllib3.disable_warnings()
    if settings.ssl.warn:
        print("[red]WARNING: SSL verification is disabled.")


class JamfClient:
    """
    A client for interacting with the Jamf Pro API.

    This class provides methods for authenticating with the Jamf Pro server
    and performing various operations such as managing categories and scripts.
    """

    def __init__(self, url: str, user: str, password: str):
        """
        Initialize the JamfClient.

        Args:
            url (str): The URL of the Jamf Pro server.
            user (str): The username for authentication.
            password (str): The password for authentication.
        """
        self.url: str = url
        self.token: str = self._get_token(user, password)

    def _get_token(self, user: str, password: str) -> str:
        """
        Obtain an authentication token from the Jamf Pro server.

        Args:
            user (str): The username for authentication.
            password (str): The password for authentication.

        Returns:
            str: The authentication token.

        Raises:
            requests.exceptions.HTTPError: If the authentication request fails.
        """
        auth = requests.auth.HTTPBasicAuth(user, password)
        response = requests.post(
            f"{self.url}/uapi/auth/tokens", auth=auth, verify=settings.ssl.verify
        )
        response.raise_for_status()

        # #! DEBUG: REMOVE LATER
        # print(response.json()["token"])
        return response.json()["token"]

    def get_all_categories(self) -> List[JamfCategory]:
        """
        Retrieve all categories from the Jamf Pro server.

        Returns:
            List[JamfCategory]: A list of all categories.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.
        """
        response = requests.get(
            f"{self.url}/uapi/v1/categories",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=settings.ssl.verify,
        )
        response.raise_for_status()

        categories = response.json()["results"]
        return [JamfCategory(**category) for category in categories]

    def get_category_id_by_name(self, category_name: str) -> int:
        """
        Get the category ID from Jamf Pro by its name.

        Args:
            category_name (str): The name of the category to search for.

        Returns:
            int: The ID of the category if found, -1 for "NONE" category.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.
            ValueError: If multiple matching categories are found or if no matching category is found.
        """

        # NONE is not defined in the API, but handled with -1
        if category_name == "NONE":
            return -1

        matching_categories = [
            x for x in self.get_all_categories() if x.name == category_name
        ]

        # At least one pls
        if not matching_categories:
            raise ValueError(
                f"Category '{category_name}' not found! Please check the category name and try again."
            )

        # Just one pls
        if len(matching_categories) > 1:
            print(matching_categories)
            raise ValueError(
                f"Multiple categories found for '{category_name}'! Either the category name is incomplete or there are duplicate categories."
            )

        return matching_categories[0].id

    def get_all_scripts(self) -> List[RemoteJamfScript]:
        """
        Get all scripts from the Jamf Pro server.

        Returns:
            List[RemoteJamfScript]: A list of all scripts.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.
        """
        response = requests.get(
            f"{self.url}/uapi/v1/scripts",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=settings.ssl.verify,
        )
        response.raise_for_status()
        return [RemoteJamfScript(**script) for script in response.json()["results"]]

    def get_script_by_id(self, script_id: int) -> RemoteJamfScript:
        """
        Get a script from the Jamf Pro server by its ID.

        Args:
            script_id (int): The ID of the script to retrieve.

        Returns:
            RemoteJamfScript: The retrieved script.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.
        """
        response = requests.get(
            f"{self.url}/uapi/v1/scripts/{script_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=settings.ssl.verify,
        )
        response.raise_for_status()
        return RemoteJamfScript(**response.json())

    def create_or_update_script(self, local_script: LocalJamfScript) -> Dict[str, Any]:
        """
        Create or update an existing Jamf Pro script.

        Uses ID in metadata to match, or if no metadata, uploads a new script.

        Args:
            local_script (LocalJamfScript): The local script to create or update.

        Returns:
            Dict[str, Any]: The response from the Jamf Pro server.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.
        """

        # Payload: Add metadata
        local_script.load_script_contents()
        payload_data = local_script.payload_data

        #! DEBUG: REMOVE LATER
        # with open(Path("./jamf_test.json"), "w") as meta_file:
        #     meta_file.write(json.dumps(payload_data, indent=4))
        # exit()

        # If ID, assume existing script update
        id = local_script.id if local_script.id else ""

        request = dict(
            url=f"{self.url}/uapi/v1/scripts/{id}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload_data,
            verify=settings.ssl.verify,
        )

        if not id:
            response = requests.put(**request)
        else:
            response = requests.put(**request)

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                error_message = f"HTTP error occurred: {e}"
                try:
                    error_details = response.json()
                    error_message += f"\nResponse details: {error_details}"
                except ValueError:
                    error_message += f"\nResponse text: {response.text}"
                raise requests.exceptions.HTTPError(error_message) from e

        return response.json()

    def delete_script(self, script_id: int) -> Dict[str, Any]:
        """
        Delete a script from the Jamf Pro server by its ID.

        Args:
            script_id (int): The ID of the script to delete.

        Returns:
            Dict[str, Any]: The response from the Jamf Pro server.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.
        """
        
        response = requests.delete(
            f"{self.url}/uapi/v1/scripts/{script_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            verify=settings.ssl.verify,
        )
        response.raise_for_status()
        return response.json()
    
    def rename_script(self, script_id: int, new_name: str) -> Dict[str, Any]:
        """
        Rename a script in the Jamf Pro server by its ID.

        Args:
            script_id (int): The ID of the script to rename.
            new_name (str): The new name for the script.

        Returns:
            Dict[str, Any]: The response from the Jamf Pro server containing the updated script information.

        Raises:
            requests.exceptions.HTTPError: If the API request fails.
        """
        response = requests.put(
            f"{self.url}/uapi/v1/scripts/{script_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"name": new_name},
            verify=settings.ssl.verify,
        )
        response.raise_for_status()
        return response.json()