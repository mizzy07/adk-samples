from typing import Optional, List, Dict, Union

from google.cloud import dataproc_v1 as dataproc
from google.cloud.dataproc_v1.types import (
    Batch,
    GceClusterConfig,
    EnvironmentConfig,
    ExecutionConfig,
    RuntimeConfig,
    PySparkBatch,
    SparkBatch,
    PeripheralsConfig,
    SparkHistoryServerConfig,
    CreateBatchRequest
    
)
from google.cloud.dataproc_v1 import BatchControllerClient
from google.api_core.exceptions import GoogleAPICallError


def get_batch_client(region: str) -> BatchControllerClient:
    """
    Creates a Dataproc BatchControllerClient for a specific region.

    Args:
        region: The GCP region for the client.

    Returns:
        A BatchControllerClient instance.
    """
    return BatchControllerClient(
        client_options={"api_endpoint": f"{region}-dataproc.googleapis.com:443"}
    )


def create_dataproc_serverless_batch(project_id: str,
                                     region: str,
                                     batch_id: str,
                                     job_type: str, 
                                     main_python_file_uri: Optional[str] = None, 
                                     jar_file_uris: Optional[List[str]] = None, 
                                     main_class: Optional[str] = None,
                                     args: Optional[List[str]] = None,
                                     properties: Optional[Dict[str, str]] = None,
                                     service_account: Optional[str] = None,
                                     subnet_uri: Optional[str] = None,
                                     runtime_version: Optional[str] = None,
                                     labels: Optional[Dict[str, str]] = None,
                                     spark_history_staging_dir: Optional[str] = None,
                                     ) -> dict:
    """
    Creates a Dataproc Serverless batch job.

    Args:
        project_id: The GCP project ID.
        region: The GCP region for the batch job.
        batch_id: The ID for the batch job.
        job_type: The type of job ('pyspark' or 'spark').
        main_python_file_uri: The URI of the main Python file for PySpark jobs.
        jar_file_uris: A list of URIs for JAR files for Spark jobs.
        main_class: The main class for Spark jobs.
        args: A list of arguments for the job.
        properties: A dictionary of properties for the job.
        service_account: The service account for the job.
        subnet_uri: The URI of the subnet for the job.
        runtime_version: The runtime version for the job.
        labels: A dictionary of labels for the job.
        spark_history_staging_dir: The staging directory for Spark history.

    Returns:
        A dictionary with the status of the batch creation.
    """
    try:
        
        batch_client = get_batch_client(region)
        
        pyspark_batch_config = None
        spark_batch_config = None
        
        if job_type == 'pyspark':
            
            pyspark_batch_config = PySparkBatch(
                main_python_file_uri=main_python_file_uri,
                args=args or [],
            )
            
        elif job_type == 'spark':
            
            spark_batch_config = SparkBatch(
                jar_file_uris = jar_file_uris,
                main_class = main_class,
                args=args or [],
            )
        
        
        runtime_config = RuntimeConfig( 
            version=runtime_version or "1.1",
            properties=properties or {}
            
        )

        # Create GCE Cluster config (can be top-level Ba
        gce_cluster_config_obj = None # Renamed to avoid conflict with field name later
        if service_account or subnet_uri:
            gce_cluster_config_obj = GceClusterConfig(
                service_account=service_account,
                subnetwork_uri=subnet_uri,
            )

        # Create the Environment config (top-level Batch field)
        
        execution_config = None
        if gce_cluster_config_obj: # Only create if there's a GCE config
            execution_config = ExecutionConfig(
                service_account=gce_cluster_config_obj.service_account,
                subnetwork_uri=gce_cluster_config_obj.subnetwork_uri,
                # Other execution-related fields can go here
            )

        environment_config = EnvironmentConfig() 
        
        if execution_config:
            environment_config.execution_config = execution_config
        
        if spark_history_staging_dir:
            environment_config.peripherals_config = PeripheralsConfig(
                spark_history_server_config=SparkHistoryServerConfig(
                    dataproc_staging_dir=spark_history_staging_dir
                )
            )
            
        
        batch_labels = {"submitted_from": "plumber"}
        if labels:
            batch_labels.update(labels)
        
        batch = Batch(
            pyspark_batch = pyspark_batch_config,
            spark_batch = spark_batch_config,
            labels=batch_labels,
            environment_config=environment_config,
            runtime_config=runtime_config,
            
           
        )

        parent = f"projects/{project_id}/locations/{region}"
        request = CreateBatchRequest(
            parent=parent,
            batch_id=batch_id,
            batch=batch
            
        )
        
        batch_client.create_batch(request=request)
        
        return {
            "status": "success",
            "message": f"Batch {batch_id} created successfully.",
            "batch_id": batch_id,
        }
        
        
    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to create Dataproc batch: {e.message}"
        }
        
    except Exception as e:
        
         return {
            "status": "error",
            "error_message": f"An unexpected error occurred during batch creation: {str(e)}"
        }
        

def check_dataproc_serverless_status(project_id: str, region: str, batch_id: str) -> dict:
    """
    Checks the status of a Dataproc Serverless batch job.

    Args:
        project_id: The GCP project ID.
        region: The GCP region of the batch job.
        batch_id: The ID of the batch job.

    Returns:
        A dictionary with the batch ID and its current state.
    """
    try:
        batch_client = get_batch_client(region)
        batch = batch_client.get_batch(name=f"projects/{project_id}/locations/{region}/batches/{batch_id}")
        
        batch_state = batch.state
        return {
            
            "batch_id": batch_id,
            "state": dataproc.Batch.State(batch_state).name,
            # "state": batch.state
        }
        
    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to check Dataproc Serverless batch status: {e.message}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred while checking batch status: {str(e)}"
        }

        
def list_dataproc_serverless_batches(project_id: str, region: str) -> List[dict]:
    """
    Lists all Dataproc Serverless batch jobs in a region.

    Args:
        project_id: The GCP project ID.
        region: The GCP region to list batches from.

    Returns:
        A list of dictionaries, each representing a batch job.
    """
    try:
        batch_client = get_batch_client(region)
        batches = batch_client.list_batches(parent=f"projects/{project_id}/locations/{region}")
        
        return [
            {
                "batch_id": batch.name.split("/")[-1],
                "state": dataproc.Batch.State(batch.state).name,
                "create_time": batch.create_time
            }
            
            for batch in batches
        ]
        
    except GoogleAPICallError as e:
        raise GoogleAPICallError(f"Failed to list Dataproc Serverless batches: {e.message}") from e
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {str(e)}") from e

def list_dataproc_serverless_batches_by_state(project_id: str, region: str, state: str) -> List[dict]:
    """
    Lists Dataproc Serverless batch jobs in a region filtered by state.

    Args:
        project_id: The GCP project ID.
        region: The GCP region to list batches from.
        state: The state to filter batches by (e.g., 'RUNNING', 'SUCCEEDED').

    Returns:
        A list of dictionaries, each representing a batch job in the specified state.
    """
    try:
        batch_client = get_batch_client(region)
        batches = batch_client.list_batches(parent=f"projects/{project_id}/locations/{region}")
        
        filtered_batches = [
            {
                "batch_id": batch.name.split("/")[-1],
                "state": dataproc.Batch.State(batch.state).name,
                "create_time": batch.create_time
            }
            for batch in batches if dataproc.Batch.State(batch.state).name == state
        ]
        
        return filtered_batches
        
    except GoogleAPICallError as e:
        raise GoogleAPICallError(f"Failed to list Dataproc Serverless batches by state: {e.message}") from e
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {str(e)}") from e   


def delete_dataproc_serverless_batch(project_id: str, region: str, batch_id: str) -> dict:
    """
    Deletes a Dataproc Serverless batch job.

    Args:
        project_id: The GCP project ID.
        region: The GCP region of the batch job.
        batch_id: The ID of the batch job to delete.

    Returns:
        A dictionary with the status of the deletion.
    """
    try:
        batch_client = get_batch_client(region)
        batch_client.delete_batch(name=f"projects/{project_id}/locations/{region}/batches/{batch_id}")
        
        return {
            "status": "success",
            "message": f"Batch {batch_id} deleted successfully."
        }
        
    except GoogleAPICallError as e:
        return {
            "status": "error",
            "error_message": f"Failed to delete Dataproc Serverless batch: {e.message}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"An unexpected error occurred while deleting the batch: {str(e)}"
        }
