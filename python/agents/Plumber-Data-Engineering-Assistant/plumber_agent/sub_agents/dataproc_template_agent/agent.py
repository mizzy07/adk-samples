from google.adk.agents import Agent
import warnings

from .tools.dataproc_template_tools import get_dataproc_template, run_dataproc_template, get_transformation_sql
from .constants import MODEL
from .prompts import AGENT_INSTRUCTION

warnings.filterwarnings('ignore')

root_agent = Agent(
    name="dataproc_template_agent",
    model = MODEL,
    description = (
        "Agent to look for relevant dataproc template based on user query and submit dataproc template job"
    ),
    instruction = (
        AGENT_INSTRUCTION
    ),
    tools=[get_dataproc_template, run_dataproc_template, get_transformation_sql]
)