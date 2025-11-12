## Dataflow Log Retrieval

* **`get_dataflow_job_logs_with_id`**: Retrieves log entries for a **specific Dataflow job** using its **ID**.
    * Fetches logs from the last **90 days**.
    * Returns up to a specified limit.
    * **Purpose**: Debugging and monitoring Dataflow job execution.

---

## Dataproc Log Retrieval

* **`get_dataproc_logs_with_name`**: Fetches log entries for a **Dataproc cluster** based on its **name**.
    * Retrieves logs from the last **90 days**, ordered by timestamp in **descending order**.
    * **Purpose**: Monitoring cluster health and activity by name.
    
* **`get_dataproc_logs_with_id`**: Retrieves log entries for a **Dataproc cluster** using its **unique cluster ID**.
    * Fetches logs from the last **90 days**, ordered by timestamp in **descending order**.
    * **Purpose**: Getting logs when only the cluster's unique identifier is known.

---

## General Log and Monitoring Functions

* **`get_cpu_utilization`**: Gathers **CPU utilization data** for instances within the project.
    * Queries for data from the last **5 minutes**.
    * Groups data by **instance ID** and **zone**.
    * **Purpose**: Quickly assessing current CPU performance across instances.
    
* **`get_latest_error`**: Finds and returns the **most recent log entry** with a severity of **ERROR**.
    * Scans project logs.
    * **Purpose**: Quickly identifying and addressing the most recent critical issues.

* **`get_latest_resource_based_logs`**: Fetches the **latest log entries** filtered by a specified **resource** and **optional severity**.
    * Returns up to **10 log entries**, ordered by timestamp in **descending order**.
    * **Purpose**: Targeted log analysis based on specific resources.

* **`get_latest_10_logs`**: Retrieves the **10 most recent log entries** across the project.
    * Optionally, can filter these logs by a specified **severity level**.
    * **Purpose**: Quick overview of recent system activities, optionally focused on severity.

* **`get_logs`**: Fetches log entries within a **specified time range** and **optional severity**.
    * Allows filtering logs by **start and end times**.
    * Can also apply a **severity filter**.
    * **Purpose**: Flexible querying of logs over specific periods.