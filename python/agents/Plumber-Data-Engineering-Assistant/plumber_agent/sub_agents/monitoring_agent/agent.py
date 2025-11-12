from google.adk.agents import Agent
from .tools.utils import get_cpu_utilization, get_latest_resource_based_logs
from .prompt import AGENT_INSTRUCTIONS, AGENT_DESCRIPTION
from .tools.dataproc import get_dataproc_cluster_logs_with_name, get_dataproc_job_logs_with_id
from .tools.dataflow import get_dataflow_job_logs_with_id


root_agent = Agent(
    name="monitoring_agent",
    model="gemini-2.0-flash",
    description=(f"{AGENT_DESCRIPTION}"),
    instruction=(f"{AGENT_INSTRUCTIONS}"),
    tools = [
                get_cpu_utilization, 
                get_latest_resource_based_logs, 
                get_dataflow_job_logs_with_id,
                get_dataproc_job_logs_with_id,
                get_dataproc_cluster_logs_with_name
        ],
)