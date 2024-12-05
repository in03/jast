"""
This module provides a client for interacting with the Jamf Pro API.

It includes functionality for authentication, managing categories, and handling scripts.
"""

from typing import Any, Dict, List

import httpx
from rich import print

from jast.config import settings
from jast.schema import JamfCategory, LocalJamfScript, RemoteJamfScript

# Warn ONCE if SSL verification is disabled
if not settings.ssl.verify:
    httpx.disable_warnings()
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
        Obtain an authentication token from the Jamf Pro server using the new API endpoint.
        """
        auth = (user, password)
        response = httpx.post(
            f"{self.url}/api/v1/auth/token",
            auth=auth,
            verify=settings.ssl.verify
        )
        response.raise_for_status()
        return response.json()["token"]

    def _make_request(self, method: str, endpoint: str, **kwargs):
        """
        Helper method to make API requests with proper headers.
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        if method.lower() in ['post', 'put']:
            headers["Content-Type"] = "application/json"
        
        response = httpx.request(
            method,
            f"{self.url}{endpoint}",
            headers=headers,
            verify=settings.ssl.verify,
            **kwargs
        )
        response.raise_for_status()
        return response

    def get_all_categories(self) -> List[JamfCategory]:
        """
        Retrieve all categories from the Jamf Pro server.

        Returns:
            List[JamfCategory]: A list of all categories.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        response = self._make_request("GET", "/api/v1/categories")
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
            httpx.HTTPStatusError: If the API request fails.
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
            httpx.HTTPStatusError: If the API request fails.
        """
        response = self._make_request("GET", "/api/v1/scripts")
        return [RemoteJamfScript(**script) for script in response.json()["results"]]

    def get_script_by_id(self, script_id: int) -> RemoteJamfScript:
        """
        Get a script from the Jamf Pro server by its ID.

        Args:
            script_id (int): The ID of the script to retrieve.

        Returns:
            RemoteJamfScript: The retrieved script.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        response = self._make_request("GET", f"/api/v1/scripts/{script_id}")
        return RemoteJamfScript(**response.json())

    def create_or_update_script(
        self, local_script: LocalJamfScript
    ) -> RemoteJamfScript:
        """
        Create or update an existing Jamf Pro script.

        Uses ID in metadata to match, or if no metadata, uploads a new script.

        Args:
            local_script (LocalJamfScript): The local script to create or update.

        Returns:
            RemoteJamfScript: The newly registered or updated script.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """

        # Payload: Add metadata
        local_script.load_script_contents()
        payload_data = local_script.payload_data

        # If ID, assume existing script update
        id = local_script.id if local_script.id else ""

        request = dict(
            url=f"{self.url}/api/v1/scripts/{id}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload_data,
            verify=settings.ssl.verify,
        )

        if not id:
            response = httpx.post(**request)
        else:
            response = httpx.put(**request)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error occurred: {e}"
            try:
                error_details = response.json()
                error_message += f"\nResponse details: {error_details}"
            except ValueError:
                error_message += f"\nResponse text: {response.text}"
            raise httpx.HTTPStatusError(error_message) from e

        # Fetch the newly registered or updated script
        script_id = response.json().get("id")
        return self.get_script_by_id(script_id)

    def delete_script(self, script_id: int) -> Dict[str, Any]:
        """
        Delete a script from the Jamf Pro server by its ID.

        Args:
            script_id (int): The ID of the script to delete.

        Returns:
            Dict[str, Any]: The response from the Jamf Pro server.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """

        response = httpx.delete(
            f"{self.url}/api/v1/scripts/{script_id}",
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
            httpx.HTTPStatusError: If the API request fails.
        """
        response = httpx.put(
            f"{self.url}/api/v1/scripts/{script_id}",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"name": new_name},
            verify=settings.ssl.verify,
        )
        response.raise_for_status()
        return response.json()
