from google.adk.agents import Agent

from .prompts import AGENT_INSTRUCTION
from .tools.dataflow_management_utils import (
    list_dataflow_jobs,
    get_dataflow_job_details,
    cancel_dataflow_job,
)
from .tools.pipeline_utils import create_pipeline_from_scratch
from .tools.dataflow_template_tools import (
    get_dataflow_template,
    submit_dataflow_template,
    customize_and_build_template,
)
from .constants import MODEL

# Create the unified agent instance with all tools
root_agent = Agent(
    name="unified_dataflow_agent",
    model=MODEL,  # A powerful model is needed to follow these detailed instructions
    description="A powerful agent that can create, deploy, and manage Google Cloud Dataflow jobs, and find, customize, and build Dataflow templates.",
    instruction=AGENT_INSTRUCTION,
    tools=[
        # Core execution tool
        create_pipeline_from_scratch,
        # Job Management tools
        list_dataflow_jobs,
        get_dataflow_job_details,
        cancel_dataflow_job,
        # Template tools
        get_dataflow_template,
        submit_dataflow_template,
        customize_and_build_template,
    ],
)
