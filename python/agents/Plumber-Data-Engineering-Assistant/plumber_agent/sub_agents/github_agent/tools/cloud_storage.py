import os
import shutil
import zipfile
import tempfile
import re
import socket
from google.cloud.exceptions import NotFound, Forbidden, Conflict
from requests.exceptions import Timeout as RequestsTimeout
from google.api_core.exceptions import GoogleAPIError
from typing import Dict, Any, List, Optional
from google.cloud import storage
from ..utils import _parse_repo_path
from google.auth.exceptions import DefaultCredentialsError
from google.api_core.exceptions import RetryError
from google.api_core.exceptions import GoogleAPICallError

# Constants
GCS_BUCKET_NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9\-_]*[a-z0-9]$')
MIN_BUCKET_NAME_LENGTH = 3
MAX_BUCKET_NAME_LENGTH = 63


def _validate_bucket_name(bucket_name: str) -> Dict[str, Any]:
    """
    Validate GCS bucket naming rules.
    
    Args:
        bucket_name: The bucket name to validate
        
    Returns:
        Dict with validation result and message
    """
    if not bucket_name:
        return {"valid": False, "message": "Bucket name cannot be empty"}
    
    if len(bucket_name) < MIN_BUCKET_NAME_LENGTH or len(bucket_name) > MAX_BUCKET_NAME_LENGTH:
        return {"valid": False, "message": f"Bucket name must be between {MIN_BUCKET_NAME_LENGTH} and {MAX_BUCKET_NAME_LENGTH} characters"}
    
    if not GCS_BUCKET_NAME_PATTERN.match(bucket_name):
        return {"valid": False, "message": "Bucket name can only contain lowercase letters, numbers, hyphens, and underscores"}
    
    if 'google' in bucket_name.lower():
        return {"valid": False, "message": "Bucket name cannot contain 'google'"}
    
    # Check for IP address format
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', bucket_name):
        return {"valid": False, "message": "Bucket name cannot be formatted as an IP address"}
    
    return {"valid": True, "message": "Bucket name is valid"}


def _get_gcs_client() -> storage.Client:
    """
    Create and return a Google Cloud Storage client.
    Uses Application Default Credentials or environment variables.
    
    Returns:
        Authenticated GCS client
    """
    try:
        # Try to use environment variable for project
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if project_id:
            return storage.Client(project=project_id)
        else:
            return storage.Client()
        # Trigger a lightweight network call to validate client credentials
        _ = list(client.list_buckets(page_size=1, timeout=10))  # request with timeout
        
        return client
    except DefaultCredentialsError as e:
        raise Exception("Google Cloud credentials not found. "
                        "Set GOOGLE_APPLICATION_CREDENTIALS or run 'gcloud auth application-default login'.")
    except RetryError:
        raise Exception("Network timeout while connecting to Google Cloud. Check your internet connection or try again.")
    except Forbidden:
        raise Exception("Access denied. Your credentials do not have permission to access this project.")
    except GoogleAPICallError as e:
        raise Exception(f"GCP API error occurred: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to authenticate with Google Cloud Storage: {str(e)}")


def _sanitize_bucket_name(name: str) -> str:
    """
    Sanitize a string to make it a valid GCS bucket name.
    
    Args:
        name: The string to sanitize
        
    Returns:
        Sanitized bucket name
    """
    # Convert to lowercase
    name = name.lower()
    
    # Replace invalid characters with hyphens
    name = re.sub(r'[^a-z0-9\-_]', '-', name)
    
    # Remove consecutive hyphens/underscores
    name = re.sub(r'[-_]+', '-', name)
    
    # Ensure it starts and ends with alphanumeric
    name = re.sub(r'^[-_]+', '', name)
    name = re.sub(r'[-_]+$', '', name)
    
    # Ensure minimum length
    if len(name) < MIN_BUCKET_NAME_LENGTH:
        name = f"{name}-repo"
    
    # Ensure maximum length
    if len(name) > MAX_BUCKET_NAME_LENGTH:
        name = name[:MAX_BUCKET_NAME_LENGTH]
        name = re.sub(r'[-_]+$', '', name)
    
    return name


def create_gcs_bucket(bucket_name: str, location: str = "us-central1", 
                     storage_class: str = "STANDARD") -> Dict[str, Any]:
    """
    Create a Google Cloud Storage bucket.
    
    Args:
        bucket_name: Name of the bucket to create
        location: GCS region (default: us-central1)
        storage_class: Storage class (default: STANDARD)
        
    Returns:
        Dict with operation result
    """
    try:
        # Validate bucket name
        validation = _validate_bucket_name(bucket_name)
        if not validation["valid"]:
            return {"status": "error", "message": validation["message"]}
        
        client = _get_gcs_client()
        
        # Check if bucket already exists
        try:
            bucket = client.get_bucket(bucket_name)
            return {
                "status": "success",
                "message": f"Bucket '{bucket_name}' already exists",
                "bucket_name": bucket_name,
                "location": bucket.location,
                "created_new": False
            }
        except NotFound:
            # Bucket doesn't exist, create it
            bucket = client.create_bucket(
                bucket_name, 
                location=location
            )
            bucket.storage_class = storage_class
            bucket.patch()
            
            return {
                "status": "success",
                "message": f"Bucket '{bucket_name}' created successfully",
                "bucket_name": bucket_name,
                "location": location,
                "storage_class": storage_class,
                "created_new": True
            }
            
    except Conflict:
        return {"status": "error", "message": f"Bucket name '{bucket_name}' is already taken by another user"}
    except Exception as e:
        return {"status": "error", "message": f"Failed to create bucket: {str(e)}"}


def upload_directory_to_gcs(local_path: str, bucket_name: str, 
                           gcs_prefix: str = "", create_bucket_if_not_exists: bool = True) -> Dict[str, Any]:
    """
    Upload an entire directory to Google Cloud Storage.
    
    Args:
        local_path: Local directory path to upload
        bucket_name: GCS bucket name
        gcs_prefix: Prefix for objects in GCS (like a folder path)
        create_bucket_if_not_exists: Whether to create bucket if it doesn't exist
        
    Returns:
        Dict with operation result
    """
    try:
        if not os.path.exists(local_path):
            return {"status": "error", "message": f"Local path does not exist: {local_path}"}
        
        if not os.path.isdir(local_path):
            return {"status": "error", "message": f"Path is not a directory: {local_path}"}
        
        client = _get_gcs_client()
        
        # Get or create bucket
        try:
            bucket = client.get_bucket(bucket_name)
        except NotFound:
            if create_bucket_if_not_exists:
                bucket_result = create_gcs_bucket(bucket_name)
                if bucket_result["status"] == "error":
                    return bucket_result
                bucket = client.get_bucket(bucket_name)
            else:
                return {"status": "error", "message": f"Bucket '{bucket_name}' does not exist"}
        
        uploaded_files = []
        failed_uploads = []
        
        # Walk through all files in the directory
        for root, dirs, files in os.walk(local_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                
                # Calculate relative path from the base directory
                relative_path = os.path.relpath(local_file_path, local_path)
                
                # Create GCS object name
                if gcs_prefix:
                    gcs_object_name = f"{gcs_prefix.rstrip('/')}/{relative_path.replace(os.sep, '/')}"
                else:
                    gcs_object_name = relative_path.replace(os.sep, '/')
                
                try:
                    blob = bucket.blob(gcs_object_name)
                    blob.upload_from_filename(local_file_path, timeout=60)   # Set a timeout for upload
                    uploaded_files.append({
                        "local_path": local_file_path,
                        "gcs_path": f"gs://{bucket_name}/{gcs_object_name}"
                    })
                except (socket.timeout, RequestsTimeout):
                    failed_uploads.append({"local_path": local_file_path,"error": "Upload timed out"
                                           })
                except GoogleAPIError as gcs_error:
                    failed_uploads.append({
                        "local_path": local_file_path,"error": f"GCS API error: {str(gcs_error)}"
                        })
                except Exception as e:
                    failed_uploads.append({
                        "local_path": local_file_path,
                        "error": str(e)
                    })
        
        return {
            "status": "success",
            "message": f"Uploaded {len(uploaded_files)} files to bucket '{bucket_name}'",
            "bucket_name": bucket_name,
            "uploaded_files": uploaded_files,
            "failed_uploads": failed_uploads,
            "total_uploaded": len(uploaded_files),
            "total_failed": len(failed_uploads)
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to upload directory: {str(e)}"}


def upload_repository_to_gcs(repo_path: str, bucket_name: Optional[str] = None, 
                            repository_name: Optional[str] = None) -> Dict[str, Any]:
    """ 
    Upload a Git repository to Google Cloud Storage as a compressed archive.
    
    Args:
        repo_path: Path to the local repository
        bucket_name: GCS bucket name (auto-generated if None)
        repository_name: Name for the repository in GCS (derived from path if None)
        
    Returns:
        Dict with operation result
    """
    try:
        if not os.path.exists(repo_path):
            return {"status": "error", "message": f"Repository path does not exist: {repo_path}"}
        
        if not os.path.isdir(repo_path):
            return {"status": "error", "message": f"Path is not a directory: {repo_path}"}
        
        # Determine repository name
        if not repository_name:
            repository_name = os.path.basename(os.path.abspath(repo_path))
        
        # Determine bucket name
        if not bucket_name:
            bucket_name = _sanitize_bucket_name(f"{repository_name}-repo")
        
        # Validate bucket name
        validation = _validate_bucket_name(bucket_name)
        if not validation["valid"]:
            return {"status": "error", "message": validation["message"]}
        
        client = _get_gcs_client()
        
        # Create bucket if it doesn't exist
        bucket_result = create_gcs_bucket(bucket_name)
        if bucket_result["status"] == "error":
            return bucket_result
        
        bucket = client.get_bucket(bucket_name)
        
        # Create a temporary zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            temp_zip_path = temp_zip.name
        
        try:
            # Create zip archive of the repository
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(repo_path):
                    # Skip .git directory for cleaner uploads
                    if '.git' in dirs:
                        dirs.remove('.git')
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, repo_path)
                        zipf.write(file_path, arc_name)
            
            # Upload zip to GCS
            zip_blob_name = f"{repository_name}.zip"
            blob = bucket.blob(zip_blob_name)
            try:
                blob.upload_from_filename(temp_zip_path, timeout=120)
            except (socket.timeout, RequestsTimeout):
                return {"status": "error", "message": "Upload of zip file to GCS timed out."}
            except GoogleAPIError as gcs_err:
                return {"status": "error", "message": f"GCS API error: {str(gcs_err)}"}
            
            # Also upload the directory structure for easier access
            directory_result = upload_directory_to_gcs(
                repo_path, 
                bucket_name, 
                gcs_prefix=repository_name,
                create_bucket_if_not_exists=False
            )
            
            return {
                "status": "success",
                "message": f"Repository uploaded to bucket '{bucket_name}'",
                "bucket_name": bucket_name,
                "repository_name": repository_name,
                "zip_location": f"gs://{bucket_name}/{zip_blob_name}",
                "directory_location": f"gs://{bucket_name}/{repository_name}/",
                "zip_upload": True,
                "directory_upload": directory_result["status"] == "success",
                "files_uploaded": directory_result.get("total_uploaded", 0)
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to upload repository: {str(e)}"}


def download_from_gcs(bucket_name: str, object_name: str, local_path: str) -> Dict[str, Any]:
    """
    Download a file from Google Cloud Storage.

    Args:
        bucket_name: GCS bucket name
        object_name: Object name in the bucket
        local_path: Local path to save the file

    Returns:
        Dict with operation result
    """
    try:
        client = _get_gcs_client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(object_name)

        if not blob.exists():
            return {
                "status": "error",
                "message": f"Object '{object_name}' does not exist in bucket '{bucket_name}'."
            }

        # Ensure the local directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Attempt to download
        blob.download_to_filename(local_path)

        return {
            "status": "success",
            "message": f"Downloaded '{object_name}' to '{local_path}'",
            "bucket_name": bucket_name,
            "object_name": object_name,
            "local_path": local_path
        }

    except NotFound:
        return {
            "status": "error",
            "message": f"Bucket '{bucket_name}' or object '{object_name}' not found."
        }
    except Forbidden:
        return {
            "status": "error",
            "message": f"Access denied to bucket '{bucket_name}' or object '{object_name}'."
        }
    except (socket.timeout, RequestsTimeout):
        return {
            "status": "error",
            "message": f"Timeout occurred while downloading '{object_name}' from '{bucket_name}'."
        }
    except GoogleAPIError as e:
        return {
            "status": "error",
            "message": f"Google Cloud error occurred: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error while downloading from GCS: {str(e)}"
        }



def delete_from_gcs(bucket_name: str, object_name: Optional[str] = None,
                   prefix: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete objects from Google Cloud Storage.

    Args:
        bucket_name: GCS bucket name
        object_name: Specific object to delete (optional)
        prefix: Delete all objects with this prefix (optional)

    Returns:
        Dict with operation result
    """
    try:
        client = _get_gcs_client()
        bucket = client.get_bucket(bucket_name)
        deleted_objects = []

        if object_name:
            blob = bucket.blob(object_name)
            if not blob.exists():
                return {
                    "status": "error",
                    "message": f"Object '{object_name}' not found in bucket '{bucket_name}'"
                }
            blob.delete()
            deleted_objects.append(object_name)

        elif prefix:
            blobs = bucket.list_blobs(prefix=prefix)
            found = False
            for blob in blobs:
                found = True
                blob.delete()
                deleted_objects.append(blob.name)
            if not found:
                return {
                    "status": "error",
                    "message": f"No objects found with prefix '{prefix}' in bucket '{bucket_name}'"
                }

        else:
            return {"status": "error", "message": "Either object_name or prefix must be specified"}

        return {
            "status": "success",
            "message": f"Deleted {len(deleted_objects)} object(s) from bucket '{bucket_name}'",
            "bucket_name": bucket_name,
            "deleted_objects": deleted_objects,
            "total_deleted": len(deleted_objects)
        }

    except NotFound:
        return {
            "status": "error",
            "message": f"Bucket '{bucket_name}' or object not found"
        }
    except Forbidden:
        return {
            "status": "error",
            "message": f"Access denied to bucket '{bucket_name}'"
        }
    except (socket.timeout, RequestsTimeout):
        return {
            "status": "error",
            "message": f"Request to delete from bucket '{bucket_name}' timed out"
        }
    except GoogleAPIError as e:
        return {
            "status": "error",
            "message": f"Google API error during deletion: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}"
        }
    
def list_gcs_buckets() -> Dict[str, Any]:
    """
    List all GCS buckets in the project.
    Returns:
        Dict with operation result and bucket list
    """
    try:
        client = _get_gcs_client()

        # List buckets with a timeout safeguard (Google API handles it internally but wrapping just in case)
        buckets = client.list_buckets(timeout=30)  # Optional timeout param
        bucket_list = []
        for bucket in buckets:
            bucket_list.append({
                "name": bucket.name,
                "location": bucket.location,
                "storage_class": bucket.storage_class,
                "created": bucket.time_created.isoformat() if bucket.time_created else None
            })

        return {
            "status": "success",
            "message": f"Found {len(bucket_list)} buckets",
            "buckets": bucket_list,
            "total_buckets": len(bucket_list)
        }

    except Forbidden:
        return {
            "status": "error",
            "message": "Access denied to list buckets. Ensure the account has proper GCS permissions."
        }
    except (RequestsTimeout, socket.timeout):
        return {
            "status": "error",
            "message": "Request timed out while listing buckets."
        }
    except GoogleAPIError as e:
        return {
            "status": "error",
            "message": f"Google API error occurred: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error occurred while listing buckets: {str(e)}"
        }

def list_gcs_objects(bucket_name: str, prefix: Optional[str] = None) -> Dict[str, Any]:
    """
    List objects in a GCS bucket with proper error handling.

    Args:
        bucket_name: GCS bucket name
        prefix: Optional prefix to filter objects

    Returns:
        Dict with operation result and object list
    """
    try:
        client = _get_gcs_client()
        bucket = client.get_bucket(bucket_name)

        # Timeout safeguard (optional, added manually)
        blobs = bucket.list_blobs(prefix=prefix, timeout=30)

        object_list = []
        for blob in blobs:
            object_list.append({
                "name": blob.name,
                "size": blob.size,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "content_type": blob.content_type,
                "storage_class": blob.storage_class
            })

        return {
            "status": "success",
            "message": f"Found {len(object_list)} objects in bucket '{bucket_name}'",
            "bucket_name": bucket_name,
            "objects": object_list,
            "total_objects": len(object_list)
        }

    except NotFound:
        return {"status": "error", "message": f"Bucket '{bucket_name}' not found"}
    except Forbidden:
        return {"status": "error", "message": f"Access denied to bucket '{bucket_name}'. Check your permissions."}
    except (RequestsTimeout, socket.timeout):
        return {"status": "error", "message": "Request timed out while listing GCS objects."}
    except GoogleAPIError as e:
        return {"status": "error", "message": f"Google API error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error while listing GCS objects: {str(e)}"}


def delete_gcs_bucket(bucket_name: str, force: bool = False) -> Dict[str, Any]:
    """
    Delete a GCS bucket with optional force delete (clears contents first).
    
    Args:
        bucket_name: GCS bucket name
        force: Whether to delete all objects in the bucket first
        
    Returns:
        Dict with operation result
    """
    try:
        client = _get_gcs_client()
        bucket = client.get_bucket(bucket_name)
        
        deleted_objects = []

        if force:
            try:
                blobs = bucket.list_blobs(timeout=30)  # 30s timeout for listing
                for blob in blobs:
                    try:
                        blob.delete(timeout=30)
                        deleted_objects.append(blob.name)
                    except GoogleAPIError as e:
                        return {"status": "error", "message": f"Failed to delete object '{blob.name}': {str(e)}"}
            except Exception as e:
                return {"status": "error", "message": f"Failed to list/delete objects in bucket: {str(e)}"}
        
        # Delete the bucket
        try:
            bucket.delete(timeout=30)
        except Conflict:
            return {"status": "error", "message": f"Bucket '{bucket_name}' is not empty. Use force=True to delete all objects first."}
        
        return {
            "status": "success",
            "message": f"Bucket '{bucket_name}' deleted successfully",
            "bucket_name": bucket_name,
            "force_delete": force,
            "objects_deleted": len(deleted_objects)
        }

    except NotFound:
        return {"status": "error", "message": f"Bucket '{bucket_name}' not found"}
    except Forbidden:
        return {"status": "error", "message": f"Access denied to bucket '{bucket_name}'. Check your permissions."}
    except (RequestsTimeout, socket.timeout):
        return {"status": "error", "message": f"Request timed out while deleting bucket '{bucket_name}'"}
    except GoogleAPIError as e:
        return {"status": "error", "message": f"Google API error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error during bucket deletion: {str(e)}"}