from datetime import datetime, timedelta
from google.cloud import logging_v2

import logging

logger = logging.getLogger("plumber-agent")


def get_dataflow_job_logs_with_id(project_id: str, job_id: str, _limit: int = 10) -> dict:

    """ 
    Fetches log entries for a specific Dataflow job using its ID from Google Cloud Logging.

    This function retrieves log entries from Google Cloud Logging that are associated
    with a particular Google Cloud Dataflow job, identified by its unique `job_id`.
    It aims to provide insights into the job's execution, status, and any potential issues.
    By default, it fetches up to 10 of the most recent log entries.

    Args:
        project_id (str, required): The Google Cloud project ID. from which logs are to be fetched.
        job_id (str, required): The unique identifier of the Dataflow job for which logs are to be fetched.
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
            - example job_id : 2025-07-11_02_51_43-12657112666808971216
     """

    print("datetime.now() - timedelta(days=90)", (datetime.now() - timedelta(days=90)).isoformat())

    collected_logs = []
    filter_string = (
        f'resource.type="dataflow_step" AND '
        f'resource.labels.job_id="{job_id}" AND ' 
        f'timestamp >= "{(datetime.now() - timedelta(days=90)).isoformat()}Z"' # there is some lookback time for filter you not able to fetch logs before that to get those you have to use timestamp
    )

    try:
        client = logging_v2.Client(project=project_id)
        project_path = f"projects/{project_id}"
        iterator = client.list_entries(
            resource_names=[project_path],
            filter_=filter_string,
            max_results=_limit 
        )

        print("iterator =====> ", iterator)

        log_count = 0
        for entry in iterator:
            log_count += 1
            print(f"Entry - {log_count} \n", entry)
            collected_logs.append(f"Entry {log_count}: {str(entry)}")
            

        return {"status": "success", "report": f"Fetched log entries of Job ID: {job_id}:\n" + "\n".join(collected_logs)}

    except StopIteration:
        return {"status": "success", "report": "No job log entry found with given ID."}
    except Exception as e:
        print(f"An error occurred: {e}")
        logger.error(f"An error occurred: {e}")
        return {"status": "error", "message": f"Failed to get job with given id and error: {e}"}