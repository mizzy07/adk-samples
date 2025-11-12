import requests
import os
import shutil
import zipfile
import tempfile
from typing import Dict, Any, Optional
from .cloud_storage import upload_repository_to_gcs
from ..utils import _create_github_headers, _get_auth_token, _parse_repo_path

API_BASE_URL = "https://api.github.com"

# Define the default download directory relative to this file's location
DEFAULT_DOWNLOAD_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'github_downloads'))

def authenticate_github(token: str = "") -> Dict[str, Any]:
    """Authenticate with GitHub using a Personal Access Token."""
    token = _get_auth_token(token)
    if not token:
        return {"status": "error", "message": "Authentication failed: No token provided."}
    headers = _create_github_headers(token)
    try:
        response = requests.get(f'{API_BASE_URL}/user', headers=headers, timeout=60)  # add timeout to avoid hanging
        response.raise_for_status()
        user_data = response.json()
        return {
            "status": "success",
            "message": f"Authenticated as {user_data.get('login')}",
            "user": user_data.get('login')
        }
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out. GitHub did not respond within the expected time."}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return {"status": "error", "message": "Authentication failed (401): Bad credentials. Please check your token."}
        return {"status": "error", "message": f"Authentication failed ({e.response.status_code}): {e.response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected authentication error occurred: {str(e)}"}

def search_repositories(repo_name: str, token: str = "") -> Dict[str, Any]:
    """Search for repositories on GitHub using a query string."""
    token = _get_auth_token(token)
    headers = _create_github_headers(token)
    try:
        response = requests.get(f"{API_BASE_URL}/search/repositories", headers=headers, params={'q': repo_name},timeout=10)        #add timeout to avoid hanging else use line 43
        response.raise_for_status()
        items = [item['full_name'] for item in response.json().get('items', [])]
        return {"status": "success", "count": len(items), "results": items}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out. GitHub did not respond within the expected time."}
    except requests.exceptions.HTTPError as e:
        return {"status": "error", "message": f"Search failed ({e.response.status_code}): {e.response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"An error occurred during search: {str(e)}"}

def list_branches(repository: str, token: str = "") -> Dict[str, Any]:
    """List all branches for a given repository."""
    owner, repo = _parse_repo_path(repository)
    if not owner:
        return {"status": "error", "message": "Invalid repository format. Use 'owner/repo'."}
    token = _get_auth_token(token)
    headers = _create_github_headers(token)
    try:
        response = requests.get(f"{API_BASE_URL}/repos/{owner}/{repo}/branches", headers=headers, timeout=10)   #add timeout to avoid hanging 
        response.raise_for_status()
        branches = [branch['name'] for branch in response.json()]
        return {"status": "success", "repository": f"{owner}/{repo}", "branches": branches}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out. GitHub did not respond in time."}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {"status": "error", "message": f"Could not list branches (404): Repository not found."}
        return {"status": "error", "message": f"Failed to list branches ({e.response.status_code}): {e.response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"An error occurred while listing branches: {str(e)}"}

def download_repository(repository: str, branch: str = "main", download_path: Optional[str] = None,
                       token: str = "", init_git: bool = True, upload_to_gcs: bool = False,
                       gcs_bucket_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Download a GitHub repository and optionally upload to Google Cloud Storage.

    Args:
        repository: Repository URL or 'owner/repo' format
        branch: Branch to download (default: main)
        download_path: Local path to download to. Defaults to 'agent/agents/github_agent/github_downloads/'.
        token: GitHub Personal Access Token
        init_git: Whether to initialize Git repository (default: True)
        upload_to_gcs: Whether to upload to Google Cloud Storage (default: False)
        gcs_bucket_name: GCS bucket name (auto-generated if None and upload_to_gcs=True)
        
    Returns:
        Dict with operation result
    """
    owner, repo = _parse_repo_path(repository)
    if not owner:
        return {"status": "error", "message": "Invalid repository format. Use 'owner/repo'."}

    # Set the default download path if not provided
    if download_path is None:
        download_path = DEFAULT_DOWNLOAD_PATH

    token = _get_auth_token(token)
    headers = _create_github_headers(token)
    zip_url = f'{API_BASE_URL}/repos/{owner}/{repo}/zipball/{branch}'

    try:
        response = requests.get(zip_url, headers=headers, stream=True, timeout=10) # add timeout to avoid hanging
        response.raise_for_status()

        # Ensure the base download directory exists
        os.makedirs(download_path, exist_ok=True)
        zip_path = os.path.join(download_path, f"{repo}-{branch}.zip")

        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        temp_extract_path = os.path.join(download_path, f"_temp_{repo}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            root_folder_in_zip = zip_ref.namelist()[0]
            zip_ref.extractall(temp_extract_path)

        extracted_root = os.path.join(temp_extract_path, root_folder_in_zip)
        final_path = os.path.join(download_path, f"{repo}-{branch}")

        if os.path.exists(final_path):
            shutil.rmtree(final_path)
        shutil.move(extracted_root, final_path)
        shutil.rmtree(temp_extract_path)
        os.remove(zip_path)

        result = {
            "status": "success",
            "message": "Repository downloaded and extracted successfully.",
            "repository": f"{owner}/{repo}",
            "branch": branch,
            "path": final_path
        }

        # Initialize Git repository if requested
        if init_git:
            from .git_ops import initialize_git_repo
            git_result = initialize_git_repo(final_path)
            result["git_initialized"] = git_result["status"] == "success"
            result["git_message"] = git_result["message"]

        # Upload to Google Cloud Storage if requested
        if upload_to_gcs:
            from .cloud_storage import upload_repository_to_gcs

            # Use repository name as bucket name if not provided
            if not gcs_bucket_name:
                gcs_bucket_name = f"{repo.lower().replace('_', '-')}-github"

            gcs_result = upload_repository_to_gcs(
                repo_path=final_path,
                bucket_name=gcs_bucket_name,
                repository_name=f"{repo}-{branch}"
            )

            result["gcs_upload"] = gcs_result["status"] == "success"
            result["gcs_message"] = gcs_result["message"]
            if gcs_result["status"] == "success":
                result["gcs_bucket"] = gcs_result["bucket_name"]
                result["gcs_zip_location"] = gcs_result["zip_location"]
                result["gcs_directory_location"] = gcs_result["directory_location"]

        return result
    except requests.exceptions.Timeout:
        return {
        "status": "error",
        "message": "Download request timed out. GitHub did not respond within the expected time."
        }
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {"status": "error", "message": f"Download failed (404): Repository or branch not found."}
        return {"status": "error", "message": f"Download failed ({e.response.status_code}): {e.response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"An error occurred during download: {str(e)}"}


def download_repository_to_gcs(repository: str, branch: str = "main",
                              gcs_bucket_name: Optional[str] = None, token: str = "") -> Dict[str, Any]:
    """
    Download a GitHub repository directly to Google Cloud Storage without local storage.

    Args:
        repository: Repository URL or 'owner/repo' format
        branch: Branch to download (default: main)
        gcs_bucket_name: GCS bucket name (auto-generated if None)
        token: GitHub Personal Access Token

    Returns:
        Dict with operation result
    """
    owner, repo = _parse_repo_path(repository)
    if not owner:
        return {"status": "error", "message": "Invalid repository format. Use 'owner/repo'."}

    token = _get_auth_token(token)
    headers = _create_github_headers(token)
    zip_url = f'{API_BASE_URL}/repos/{owner}/{repo}/zipball/{branch}'

    try:
        # Download repository to temporary location

        with tempfile.TemporaryDirectory() as temp_dir:
            # Download and extract repository
            response = requests.get(zip_url, headers=headers, stream=True, timeout=10)   # add timeout to avoid hanging
            response.raise_for_status()

            zip_path = os.path.join(temp_dir, f"{repo}-{branch}.zip")
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract repository
            extract_path = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_path)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
                # Get the actual repository folder (GitHub adds a prefix)
                repo_folder = os.path.join(extract_path, os.listdir(extract_path)[0])

            # Use repository name as bucket name if not provided
            if not gcs_bucket_name:
                gcs_bucket_name = f"{repo.lower().replace('_', '-')}-github"

            gcs_result = upload_repository_to_gcs(
                repo_path=repo_folder,
                bucket_name=gcs_bucket_name,
                repository_name=f"{repo}-{branch}"
            )

            if gcs_result["status"] == "success":
                return {
                    "status": "success",
                    "message": f"Repository '{owner}/{repo}' downloaded directly to GCS bucket '{gcs_bucket_name}'",
                    "repository": f"{owner}/{repo}",
                    "branch": branch,
                    "gcs_bucket": gcs_result["bucket_name"],
                    "gcs_zip_location": gcs_result["zip_location"],
                    "gcs_directory_location": gcs_result["directory_location"],
                    "files_uploaded": gcs_result["files_uploaded"]
                }
            else:
                return gcs_result
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out. GitHub server did not respond in time."}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {"status": "error", "message": f"Download failed (404): Repository or branch not found."}
        return {"status": "error", "message": f"Download failed ({e.response.status_code}): {e.response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"An error occurred during download: {str(e)}"}