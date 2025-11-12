from typing import List, Optional

from google.cloud import dataproc_v1 as dataproc
from google.cloud.dataproc_v1.types import Cluster, ClusterConfig, GceClusterConfig, InstanceGroupConfig, DiskConfig
from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.cloud.dataproc_v1 import ClusterControllerClient


def get_cluster_client(region: str) -> ClusterControllerClient:
    """
    Creates a Dataproc ClusterControllerClient for a specific region.

    Args:
        region: The GCP region for the client.

    Returns:
        A ClusterControllerClient instance.
    """
    return ClusterControllerClient(
        client_options={"api_endpoint": f"{region}-dataproc.googleapis.com:443"}
    )
def create_cluster(project_id: str,
                   region: str, 
                   cluster_name: str, 
                   num_instances_master: int, 
                   num_instances_worker: int, 
                   machine_type_master: str, 
                   machine_type_worker: str,
                   boot_disk_size_master: int,
                   boot_disk_size_worker: int,
                   pip_packages_to_install: Optional[List[str]] = None,
                   jar_files_gcs_path: Optional[str] = None, 
                   initialization_action_script_path: Optional[str] = None
                   ) -> dict:
    """
    Creates a Dataproc cluster.

    Args:
        project_id: The GCP project ID.
        region: The GCP region for the cluster.
        cluster_name: The name of the cluster.
        num_instances_master: The number of master instances.
        num_instances_worker: The number of worker instances.
        machine_type_master: The machine type for the master node.
        machine_type_worker: The machine type for the worker nodes.
        boot_disk_size_master: The boot disk size for the master node in GB.
        boot_disk_size_worker: The boot disk size for the worker nodes in GB.
        pip_packages_to_install: A list of pip packages to install.
        jar_files_gcs_path: The GCS path to JAR files.
        initialization_action_script_path: The GCS path to an initialization script.

    Returns:
        A dictionary with the status of the cluster creation.
    """
    try:
        # Create a client with the endpoint set to the desired cluster region.
        cluster_client = get_cluster_client(region)
        
        

        # Define the configuration for the master node
        master_config = InstanceGroupConfig(
            num_instances=num_instances_master,
            machine_type_uri=machine_type_master,
            disk_config=DiskConfig(
                boot_disk_size_gb= boot_disk_size_master
            )
        )

        # Define the configuration for the worker nodes
        worker_config = InstanceGroupConfig(
            num_instances=num_instances_worker,
            machine_type_uri= machine_type_worker,
            disk_config=DiskConfig(
                boot_disk_size_gb= boot_disk_size_worker
            )
        )

        # Define the GCE (Compute Engine) configuration for the cluster
        gce_cluster_config = GceClusterConfig(
            service_account_scopes=["https://www.googleapis.com/auth/cloud-platform"], 
        )
        
        
        # Define software configuration, including pip packages
        software_properties = {}
        if pip_packages_to_install:
            software_properties["dataproc:pip.packages"] = ",".join(pip_packages_to_install)

        software_config = dataproc.SoftwareConfig(
            image_version="2.1-debian11",
            properties=software_properties
        )
        
        # If a JAR GCS path is provided, add it to the initialization actions
        initialization_actions = []
        if initialization_action_script_path:
            init_action = dataproc.cluster.InitializationAction(
                executable_file=initialization_action_script_path
            )
            initialization_actions.append(init_action)

            # Pass JAR GCS path as metadata to the initialization script if provided
            if jar_files_gcs_path:
                if not gce_cluster_config.metadata:
                    gce_cluster_config.metadata = {}
                gce_cluster_config.metadata["JAR_GCS_PATH"] = jar_files_gcs_path


    # Construct the full cluster configuration using the imported types
        cluster = Cluster(
            project_id=project_id,
            cluster_name=cluster_name,
            labels={"submitted_from": "plumber"},
            config=ClusterConfig(
                gce_cluster_config=gce_cluster_config,
                master_config=master_config,
                worker_config=worker_config,
                software_config=software_config,
                initialization_actions=initialization_actions if initialization_actions else None
            ),
        )

        # Create the cluster.
        operation = cluster_client.create_cluster(
            request={"project_id": project_id, "region": region, "cluster": cluster}
        )
        # result = operation.result() 

        # Output a success message.
        return{
            "status": "success",
            "report": (
                    f"Dataproc cluster '{cluster_name}' created successfully in region '{region}' "
                    f"It might take a few more minutes for all services to be fully ready."
                )
    }

    except GoogleAPICallError as e:
        
        return {
            "status": "error",
            "error_message": f"Failed to create Dataproc cluster: {e.message}"
        }
    except Exception as e:
     
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred during cluster creation: {str(e)}"
        }
     
        
def cluster_exists_or_not(project_id: str, region: str, cluster_name: str) -> dict:
    """
    Checks if a Dataproc cluster exists.

    Args:
        project_id: The GCP project ID.
        region: The GCP region of the cluster.
        cluster_name: The name of the cluster.

    Returns:
        A dictionary indicating whether the cluster exists.
    """
    try:
        # Create a client for the ClusterController API
        cluster_client = get_cluster_client(region)

        # Attempt to fetch the cluster details
        cluster_client.get_cluster(
            project_id=project_id, region=region, cluster_name=cluster_name
        )

        # If no exception is raised, the cluster exists
        return {
            "status": "success",
            "exists": True,
            "message": f"Cluster '{cluster_name}' exists in region '{region}'."
        }

    except NotFound:
        return {
            "status": "success",
            "exists": False,
            "message": f"Cluster '{cluster_name}' does not exist in region '{region}'."
        }

    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to check cluster existence: {e.message}"
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred while checking cluster existence: {str(e)}"
        }

def list_clusters(project_id: str, region: str) -> dict:
    """
    Lists all Dataproc clusters in a region.

    Args:
        project_id: The GCP project ID.
        region: The GCP region to list clusters from.

    Returns:
        A dictionary containing a list of clusters.
    """
    try:
       
        cluster_client = get_cluster_client(region)

        
        clusters = cluster_client.list_clusters(project_id=project_id, region=region)

        # Prepare the response
        cluster_list = []
        for cluster in clusters:
            cluster_list.append({
                "name": cluster.cluster_name,
                "status": cluster.status.state.name,
                "create_time": cluster.status.detail,
            })

        return {
            "status": "success",
            "clusters": cluster_list
        }
        

    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to list Dataproc clusters: {e.message}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred while listing clusters: {str(e)}"
        } 
        
def start_stop_cluster(project_id: str, region: str, cluster_name: str, action: str) -> dict:
    """
    Starts or stops a Dataproc cluster.

    Args:
        project_id: The GCP project ID.
        region: The GCP region of the cluster.
        cluster_name: The name of the cluster.
        action: The action to perform ('start' or 'stop').

    Returns:
        A dictionary with the status of the action.
    """
    try:
        
        
        # Create a client for the ClusterController API
        cluster_client = get_cluster_client(region)
        
        

        if action.lower() == "start":
            # Start the cluster
            operation = cluster_client.start_cluster(
                request={
                    "project_id": project_id,
                    "region": region,
                    "cluster_name": cluster_name,
                }
            )
            operation.result() 
            return {
                "status": "success",
                "report": f"Cluster '{cluster_name}' started successfully in region '{region}'."
            }

        elif action.lower() == "stop":
            # Stop the cluster
        
            operation = cluster_client.stop_cluster(
                request={
                    "project_id": project_id,
                    "region": region,
                    "cluster_name": cluster_name,
                }
            )
            operation.result() 
    
            return {
                "status": "success",
                "report": f"Cluster '{cluster_name}' stopped successfully in region '{region}'."
            }

        else:
            raise ValueError("Invalid action. Use 'start' or 'stop'.")

    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to {action} cluster: {e.message}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred while trying to {action} the cluster: {str(e)}"
        }   
        
def update_cluster(
    project_id: str,
    region: str,
    cluster_name: str,
    num_workers: Optional[int] = None,
) -> dict:
    """
    Updates a Dataproc cluster.

    Args:
        project_id: The GCP project ID.
        region: The GCP region of the cluster.
        cluster_name: The name of the cluster.
        num_workers: The new number of worker instances.

    Returns:
        A dictionary with the status of the update and cluster details.
    """
    try:
        
        if( num_workers is None):
            return {
                "status": "Success",
                "report": f"No changes made to cluster '{cluster_name}' in region '{region}', as no worker configuration was provided."
            }
        # Create a client for the ClusterController API
        cluster_client = get_cluster_client(region)

        # Fetch the current cluster configuration
        cluster = cluster_client.get_cluster(
            project_id=project_id, region=region, cluster_name=cluster_name
        )
        
        
        current_num_workers = cluster.config.worker_config.num_instances
        if num_workers == current_num_workers:
                return {
                    "status": "Success",  
                    "report": f"No changes made to cluster '{cluster_name}' in region '{region}', as the number of workers is already set to {num_workers}."  
                }
        
        # Update worker configurations if specified
        update_mask_paths = []
        if num_workers is not None:
            cluster.config.worker_config.num_instances = num_workers
            update_mask_paths.append("config.worker_config.num_instances")


        # Submit the update request
        operation = cluster_client.update_cluster(
            request={
                "project_id": project_id,
                "region": region,
                "cluster_name": cluster_name,
                "cluster": cluster,
                "update_mask": {"paths": update_mask_paths},
            }
        )

        # Wait for the operation to complete
        updated_cluster = operation.result()

        # Extract relevant details from the updated cluster
        cluster_details = {
            "cluster_name": updated_cluster.cluster_name,
            "status": updated_cluster.status.state.name,
            "config": {
                "worker_config": {
                    "num_instances": updated_cluster.config.worker_config.num_instances,
                    "machine_type_uri": updated_cluster.config.worker_config.machine_type_uri,
                    "disk_config": {
                        "boot_disk_size_gb": updated_cluster.config.worker_config.disk_config.boot_disk_size_gb
                    }
                }
            }
        }

        return {
            "status": "success",
            "report": f"Cluster '{cluster_name}' updated successfully in region '{region}'.",
            "details": cluster_details
        }

    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to update cluster: {e.message}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred during cluster update: {str(e)}"
        }
def get_cluster_details(project_id: str, region: str, cluster_name: str) -> dict:
    """
    Gets the details of a Dataproc cluster.

    Args:
        project_id: The GCP project ID.
        region: The GCP region of the cluster.
        cluster_name: The name of the cluster.

    Returns:
        A dictionary with the cluster details.
    """
    try:
        
       
        # Create a client for the ClusterController API
        cluster_client = get_cluster_client(region)

        # Fetch the cluster details
        cluster = cluster_client.get_cluster(
            project_id=project_id, region=region, cluster_name=cluster_name
        )

        # Extract relevant details
        cluster_details = {
            "cluster_name": cluster.cluster_name,
            "status": cluster.status.state.name,
            "status_detail": cluster.status.detail,
            "create_time": cluster.cluster_uuid,
            "labels": dict(cluster.labels),
            "config": {
                "master_config": {
                    "machine_type_uri": cluster.config.master_config.machine_type_uri,
                    "disk_config": {
                        "boot_disk_size_gb": cluster.config.master_config.disk_config.boot_disk_size_gb
                    }
                },
                "worker_config": {
                    "num_instances": cluster.config.worker_config.num_instances,
                    "machine_type_uri": cluster.config.worker_config.machine_type_uri,
                    "disk_config": {
                        "boot_disk_size_gb": cluster.config.worker_config.disk_config.boot_disk_size_gb
                    }
                }
            }
        }

        return {
            "status": "success",
            "details": cluster_details
        }

    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to fetch cluster details: {e.message}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred while fetching cluster details: {str(e)}"
        }


def delete_cluster(project_id: str, region: str, cluster_name: str) -> dict:
    """
    Deletes a Dataproc cluster.

    Args:
        project_id: The GCP project ID.
        region: The GCP region of the cluster.
        cluster_name: The name of the cluster to delete.

    Returns:
        A dictionary with the status of the deletion.
    """
    try:
     
        # Create a client for the ClusterController API
        cluster_client = get_cluster_client(region)

        # Delete the cluster
        operation = cluster_client.delete_cluster(
            request={
                "project_id": project_id,
                "region": region,
                "cluster_name": cluster_name,
            }
        )
        operation.result() 

        return {
            "status": "success",
            "report": f"Cluster '{cluster_name}' deleted successfully in region '{region}'."
        }

    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to delete cluster: {e.message}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred while deleting the cluster: {str(e)}"
        }
