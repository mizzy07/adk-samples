from google.cloud import logging_v2
from datetime import datetime, timedelta, timezone
import subprocess
import logging

logger = logging.getLogger("plumber-agent")


def get_dataproc_cluster_logs_with_name(project_id: str, dataproc_cluster_name: str = "", _limit: int = 10) -> dict:
    
    """ 
    Fetches Google Cloud Logging log entries specifically for Dataproc clusters. 

    This function retrieves log entries from Google Cloud Logging for a specified
    Dataproc cluster with it's name, with an option to limit the number of results. 
    It is designed to provide an overview of recent cluster activities and potential issues.

    Args:
        project_id (str, required): The Google Cloud project ID. from which logs are to be fetched.
        dataproc_cluster_name (str, required): The name of the Dataproc cluster
            to filter logs for. If not provided don't call this tool.
        _limit (int, optional): The maximum number of log entries to retrieve.
            The function will fetch up to this many entries, Defaults to 10.

    Returns:
        dict: A dictionary containing the status of the operation and the retrieved logs.
            The dictionary will have the following structure:
                - "status" (str): "success" if logs were fetched successfully, or "error"
                    if an error occurred.
                - "report" (str): A human-readable message detailing the outcome.
                    If successful, it includes a summary and a list of the fetched log entries.
                    If no logs are found, it indicates that.
                - "message" (str, optional): Only present if "status" is "error", providing
                    details about the error that occurred.

    Note: [IMPORTANT]
        - Call this tool only when user want's logs of a cluster with the name 
    """

    try:
        collected_logs = get_dataproc_logs(project_id=project_id, resource_name="cloud_dataproc_cluster", query_str=dataproc_cluster_name, filter="cluster_name",_limit=_limit)
        log_count = len(collected_logs)
        if log_count == 0:
            print("No log entries found matching the criteria.")
            return {"status": "success", "report": "No log entries found matching the criteria."}
        
        print(f"\nSuccessfully fetched {log_count} log entries.")
        return {"status": "success", "report": "Fetched log entries:\n" + "\n".join(collected_logs)}

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        print(f"An error occurred: {e}")
        return {"status": "success", "report": f"An error occurred: {e}"}
    
def get_dataproc_cluster_logs_with_id(project_id:str, dataproc_cluster_id: str, _limit: int = 10) -> dict:
    
    """ 
    Fetches Google Cloud Logging log entries for a specific Dataproc cluster using its UUID or ID.

    This function retrieves log entries from Google Cloud Logging that are associated
    with a particular Dataproc cluster, identified by its unique ID (UUID). It allows
    for limiting the number of log entries returned, ordered by the most recent first.

    Args:
        project_id (str, required): The Google Cloud project ID. from which logs are to be fetched.
        cluster_id (str, required): The **UUID** of the Dataproc cluster to filter logs for.
            This uniquely identifies a Dataproc cluster across its lifecycle. If not
            provided don't call this tool.
            - format of UUID : 0278aa3c-085a-4ccc-b79d-78b82fbb2ba3
        _limit (int, optional): The maximum number of log entries to fetch. The function
            will retrieve up to this many entries, Defaults to 10.

    Returns:
        dict: A dictionary containing the status of the operation and the retrieved logs.
            The dictionary will have the following keys:
            - "status" (str): "success" if the logs were fetched successfully, or "error"
                if an issue occurred.
            - "report" (str): A descriptive message about the outcome. If successful,
                it includes a summary and a list of the fetched log entries. If no
                matching logs are found, it indicates that.
            - "message" (str, optional): Present only if "status" is "error", providing
                details about the specific error.

    Note: [IMPORTANT]
            - Call this tool only when user want's logs of a cluster with it's UUID or ID 
    """

    try:
        collected_logs = get_dataproc_logs(project_id=project_id, resource_name="cloud_dataproc_cluster", query_str=dataproc_cluster_id, filter="cluster_uuid",_limit=_limit)
        log_count = len(collected_logs)
        if log_count == 0:
            print("No log entries found matching the criteria.")
            return {"status": "success", "report": "No log entries found matching the criteria."}
        
        print(f"\nSuccessfully fetched {log_count} log entries.")
        return {"status": "success", "report": "Fetched log entries:\n" + "\n".join(collected_logs)}

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        print(f"An error occurred: {e}")
        return {"status": "success", "report": f"An error occurred: {e}"}

def get_dataproc_logs(project_id: str, resource_name: str = "", query_str: str = "", filter:str = "", _limit: int = 10):
    """
    Fetches raw log entries from Google Cloud Logging for Dataproc resources.

    This is a common helper function that constructs a filter string to query
    Google Cloud Logging, primarily targeting Dataproc resources. It is used
    to retrieve logs based on a specific resource label (e.g., cluster UUID or name).

    Logs are filtered to include entries from the last 90 days, ordered by the
    most recent first, and limited by a maximum result count.

    Args:
        project_id (str, required): The Google Cloud project ID from which logs are to be fetched.
        resource_name (str, optional): The `resource.type` to filter logs by (e.g., "cloud_dataproc_cluster").
                                       Defaults to an empty string, but typically set to "cloud_dataproc_cluster"
                                       by the calling function.
        query_str (str, optional): The specific value to match in the log filter (e.g., a cluster UUID).
                                   Defaults to an empty string.
        filter (str, optional): The `resource.labels` key to apply the filter to (e.g., "cluster_uuid" or "cluster_name").
                                Defaults to an empty string.
        _limit (int, optional): The maximum number of log entries to fetch. Defaults to 10.

    Returns:
        list[str]: A list of formatted strings, where each string represents a retrieved log entry.
                   Returns an empty list if an exception occurs during the fetch.

    Raises:
        Exception: Catches and logs any errors encountered during the Google Cloud Logging API call.
                   The error is printed and an empty list is returned.
    """
    full_filter = (
        f'resource.type="{resource_name}" AND '
        f'resource.labels.{filter}="{query_str.strip()}" AND '
        f'timestamp >= "{(datetime.now() - timedelta(days=90)).isoformat()}Z"' # there is some lookback time for filter you not able to fetch logs before that to get those you have to use timestamp
    )

    collected_logs = []

    try:
        client = logging_v2.Client(project=project_id)
        project_path = f"projects/{project_id}"
        iterator = client.list_entries(
            resource_names=[project_path],
            order_by='timestamp desc',
            filter_=full_filter,
            max_results=_limit,
        )

        log_count = 0
        for entry in iterator:
            log_count += 1
            print(f"Entry - {log_count} \n", entry)
            collected_logs.append(f"Entry {log_count}: {str(entry)}")
            if log_count >= 10:
                break

        return collected_logs

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        print(f"An error occurred: {e}")
        return []

def get_dataproc_normal_job_logs_with_id(project_id: str, region: str, job_id: str, filter: str):
    """
    Executes a gcloud command to fetch and wait for (or stream) logs for a traditional
    Dataproc Job or Batch, returning the raw command result.

    This function constructs and executes a `gcloud dataproc {filter} wait {job_id}` 
    command to either stream the job's logs and wait for completion (for 'jobs') or 
    to simply run the command specified in `filter`. It is typically used for older-style
    Dataproc jobs or as a fallback/alternative to Cloud Logging API calls.

    Args:
        project_id (str, required): The Google Cloud project ID.
        region (str, required): The GCP region where the Dataproc job resides (e.g., 'us-central1').
        job_id (str, required): The unique ID of the Dataproc job (e.g., 'pyspark_job-xyz').
        filter (str, required): The `gcloud dataproc` subcommand part that follows 
                                the main command, typically 'jobs' or 'batches'. 
                                E.g., setting 'jobs' results in `gcloud dataproc jobs wait ...`.

    Returns:
        subprocess.CompletedProcess | list: 
            - If successful, returns the raw `subprocess.CompletedProcess` object containing
              the command's `stdout`, `stderr`, and `returncode`.
            - If `gcloud` is not found, returns an empty list and logs a warning.
            - If another exception occurs, returns an empty list and logs the error.

    Note:
        This function uses `shell=True`, making the command execution less secure but
        necessary for simple command execution without extensive argument formatting.
        The logs and final status are contained within the returned object's stdout/stderr.
    """

    try:
        command = [
            'gcloud', 'dataproc', filter, 'wait', job_id,
            '--project', project_id,
            '--region', region
        ]
        command = ' '.join(command)

        # Execute the command and capture the output.
        result = subprocess.run(
            command,
            capture_output = True,
            text=True,
            check = False,
            shell = True
        )
        return result
    except FileNotFoundError:
        logger.warning("gcloud command not found. Please ensure it is installed and in your system's PATH.")
        print("gcloud command not found. Please ensure it is installed and in your system's PATH.")
        return []
    except Exception as e:
        logger.error(f"An error occurred while calling comand: {str(e)}")
        print(f"An error occurred: {e}")
        return []


def get_dataproc_job_logs_with_id(project_id: str, region: str, job_id: str, _limit: int = 10) -> dict:

    """ 
    Fetches log entries for a specific Dataproc job using its ID from Google Cloud Logging.

    This function retrieves log entries from Google Cloud Logging that are associated
    with a particular Google Cloud Dataproc job, identified by its unique `job_id`.
    It aims to provide insights into the job's execution, status, and any potential issues.
    By default, it fetches up to 10 of the most recent log entries.

    Args:
        project_id (str, required): The Google Cloud project ID. from which logs are to be fetched.
        region (str): The GCP region where the Dataproc job was executed (e.g., 'us-central1').
        job_id (str, required): The unique identifier of the Dataproc job for which logs are to be fetched.
            This argument is required to filter the logs specifically for a given job.
        _limit (int, optional): The maximum number of log entries to fetch. The function
            will retrieve up to this many entries, Defaults to 10.

    Returns:
        dict: A dictionary containing the status of the operation and the retrieved logs.
            The dictionary will have the following structure:
            - "status" (str): "success" if logs were fetched successfully, or "error"
                if an error occurred.
            - "report" (str): A human-readable message detailing the outcome.
                If successful, it includes a summary and a list of the fetched log entries.
                If no logs are found for the given job ID, it indicates that.
            - "message" (str, optional): Only present if "status" is "error", providing
                details about the error that occurred.

    Note: [IMPORTANT]
        - Don't call this tool till u have job_id 
            - example job_id : pyspark_job-xvqzft55adfra, dd9121f1-7925-4f18-b49a-0edc5d9b004f  
    """

    try:
        collected_logs = get_dataproc_logs(project_id=project_id, resource_name="cloud_dataproc_batch", query_str=job_id, filter="batch_id",_limit=_limit)
        if len(collected_logs) == 0:
            collected_logs = get_dataproc_normal_job_logs_with_id(project_id, region, job_id, "jobs")
            if collected_logs.returncode != 0:
                print("No log entries found matching the criteria.")
                return {"status": "success", "report": "No log entries found matching the criteria."}
            return {"status": "success", "report": "Fetched log entries:\n" + str(collected_logs.stderr) + '\n' + str(collected_logs.stdout)}
        else:
            return {"status": "success", "report": "Fetched log entries:\n" + "\n".join(collected_logs)}

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        print(f"An error occurred: {e}")
        return {"status": "error", "message": f"Failed to get logs: {e}"}