import git
import os
import vertexai
from vertexai.generative_models import GenerativeModel
import json
import subprocess
import shutil
import uuid
import re # Import the regular expression module

# Import everything from your other files
from ..constants import DATAFLOW_TEMPLATE_GIT_URL, GIT_PATH, MODEL, TEMPLATE_MAPPING_PATH
from ..prompts import SEARCH_DATAFLOW_TEMPLATE_INSTRUCTION, CORRECT_JAVA_FILE_INSTRUCTION, FIND_STAGED_GCS_PATH_PROMPT
from ..utils import find_all_java_files_in_dir, generate_beam_sql_query_from_sttm

def get_dataflow_template_repo() -> dict:
    """
    Clones or pulls the latest version of the Google Cloud DataflowTemplates repository.

    Ensures the template source code is available locally. If the repository already
    exists, it pulls the latest changes from the 'main' branch. Otherwise, it clones
    the repository from the official URL.

    Returns:
        dict: A dictionary with the status ('success' or 'error') and, on success,
              the local path to the repository ('repo_path').
    """
    try:
        repo_path = f'./{GIT_PATH}/DataflowTemplates'
        if os.path.exists(repo_path):
            repo = git.Repo(repo_path)
            repo.remotes.origin.pull('main')
            return {'status': 'success', 'repo_path': repo_path}
        else:
            git.Repo.clone_from(DATAFLOW_TEMPLATE_GIT_URL, to_path=repo_path, branch="main")
            return {'status': 'success', 'repo_path': repo_path}
    except Exception as err:
        return {'status': f'error - {str(err)}'}

def validate_input_params(template_definition: dict, user_inputs: dict) -> dict:
    """
    Validates user-provided parameters against a template's definition.

    Checks for two conditions:
    1. If the user provided any parameters that are not defined in the template.
    2. If the user omitted any parameters that are marked as required by the template.

    Args:
        template_definition (dict): A dictionary defining the template's 'required' and 'optional' parameters.
        user_inputs (dict): A dictionary of parameters provided by the user.

    Returns:
        dict: A dictionary with the validation result ('success' or 'failed') and a descriptive comment.
    """
    try:
        # Use .get() with an empty list as a default to prevent KeyErrors
        required_params = template_definition.get('required', [])
        optional_params = template_definition.get('optional', [])

        all_defined_params = required_params + optional_params
        user_param_keys = user_inputs.keys()

        # CHECK FOR INVALID PARAMETERS (parameters the user gave that don't exist in the template)
        invalid_params = list(set(user_param_keys) - set(all_defined_params))
        if invalid_params:
            return {
                "validation_result": "failed",
                "comment": f"Invalid param(s) passed: {invalid_params}. Valid params are: {all_defined_params}"
            }

        # CHECK IF ALL REQUIRED PARAMS ARE PRESENT in the user's input
        missing_required = list(set(required_params) - set(user_param_keys))
        if missing_required:
            return {
                "validation_result": "failed",
                "comment": f"Missing required param(s): {missing_required}"
            }
      
        return {
            "validation_result": "success",
            "comment": "Validation Passed"
        }
    except Exception as err:
        return {
            "validation_result": "failed",
            "comment": f"An unexpected error occurred during validation - {str(err)}"
        }


def get_dataflow_template(user_prompt: str):
    """
    Searches for a suitable Dataflow template based on a user's natural language prompt.

    It uses a generative model to compare the user's task against a predefined
    JSON mapping of available templates to find the best match.

    Args:
        user_prompt (str): The user's description of the desired task.

    Returns:
        str: A JSON string with the recommended template details or an error message.
    """
    try:
        get_dataflow_template_repo()
        vertexai.init(project=os.getenv('GOOGLE_CLOUD_PROJECT'), location=os.getenv('GOOGLE_CLOUD_LOCATION'))
        model = GenerativeModel(MODEL)
        with open(f'./{TEMPLATE_MAPPING_PATH}', 'r') as json_file:
            template_mapping_dict = json.load(json_file)
        instruction = SEARCH_DATAFLOW_TEMPLATE_INSTRUCTION.format(
            task=user_prompt,
            template_mapping_json=json.dumps(template_mapping_dict)
        )
        response = model.generate_content(instruction)
        return response.text
    except Exception as err:
        return json.dumps({"error": f"An unexpected error occurred: {str(err)}"})

# This function remains correct.
def customize_and_build_template(
    gcp_project: str,
    bucket_name: str,
    template_name: str,
    template_path: str,
    sttm_gcs_path: str
) -> dict:
    """
    Finds, builds, and stages a custom Dataflow template from the cloned repository.

    This function locates the main Java file for a given template, builds it using Maven,
    and stages the compiled template to a specified GCS bucket.

    Args:
        gcp_project (str): The Google Cloud project ID.
        bucket_name (str): The GCS bucket name for staging the template.
        template_name (str): The name to assign to the staged template.
        template_path (str): The relative path within the DataflowTemplates repo to the template's module.
        sttm_gcs_path (str): The GCS path to the Source-to-Target-Mapping (STTM) file (currently unused).

    Returns:
        dict: A dictionary containing the status of the operation, a comment,
              and the GCS path of the staged template if successful.
    """
    try:
        # Step 1: Ensure the source code is cloned and available.
        repo_status = get_dataflow_template_repo()
        if 'error' in repo_status['status']:
            return {'status': 'failed', 'comment': f"Could not access template repo: {repo_status['status']}"}
        
        repo_root_path = repo_status['repo_path']
        search_directory = os.path.join(repo_root_path, template_path)
        
        # Step 2: Use the "Python Finds, LLM Chooses" pattern to locate the source file.
        all_java_files = find_all_java_files_in_dir(search_directory)
        if not all_java_files:
            return {'status': 'failed', 'comment': f"No .java source files found in directory: {search_directory}"}

        vertexai.init(project=os.getenv('GOOGLE_CLOUD_PROJECT'), location=os.getenv('GOOGLE_CLOUD_LOCATION'))
        model = GenerativeModel(MODEL)
        prompt = CORRECT_JAVA_FILE_INSTRUCTION.format(template_name=template_name, java_files_list='\n'.join(all_java_files))
        response = model.generate_content(prompt)
        main_java_file_path = response.text.strip()
        print(f"Found template file: {main_java_file_path}")

        if main_java_file_path == "not_found" or not os.path.exists(main_java_file_path):
            return {'status': 'failed', 'comment': f"LLM could not identify the correct source file for {template_name}."}

        # # Step 3: Generate the SQL query from the STTM file.
        # beam_sql_query = generate_beam_sql_query_from_sttm(sttm_gcs_path)
        # if not beam_sql_query:
        #     return {'status': 'failed', 'comment': 'Failed to generate Beam SQL query from the provided STTM file.'}

        # # Step 4: Inject the SQL transformation into the source code.
        # with open(main_java_file_path, 'r') as f:
        #     original_beam_code = f.read()
        
        # injection_prompt = GENERAL_BEAM_SQL_MODIFICATION_INSTRUCTIONS.format(original_beam_code=original_beam_code, beam_sql_query=beam_sql_query)
        # injection_response = model.generate_content(injection_prompt)
        # modified_beam_code = injection_response.text

        # # Overwrite the original Java file with the modified version.
        # with open(main_java_file_path, 'w') as f:
        #     f.write(modified_beam_code)
        
        # # Print the modified code to the terminal.
        # print("======================================================================================")
        # print("MODIFIED BEAM CODE:")
        # print("======================================================================================")
        # print(modified_beam_code)
        # print("======================================================================================")
            
        template_module_path = os.path.join(repo_root_path, template_path)

        default_labels = "plumber"
        mvn_cmd = f"""
        mvn clean package -PtemplatesStage -DskipTests \\
            -DprojectId="{gcp_project}" \\
            -DbucketName="{bucket_name}" \\
            -DstagePrefix="templates" \\
            -DtemplateName="{template_name}" \\
            -Dlabels={default_labels} \\
            -f "{template_module_path}" 
        """
        print(f"Executing build command...\n{mvn_cmd}")
        # Step 5: Run the build command, capturing all output.
        cmd_run_status = subprocess.run(mvn_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True, shell=True)
        
        # Step 6: Parse the output to get the GCS path using a robust regex search.
        staged_path = ""
        combined_output = cmd_run_status.stdout
        patterns = [
            r"Flex Template was staged!\s+(gs://[^\s]+)",
            r"Template staged successfully\. It is available at\s+(gs://[^\s]+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, combined_output)
            if match:
                staged_path = match.group(1)
                break 

        if not staged_path:
            return {'status': 'failed', 'comment': 'Build succeeded, but could not find the staged template GCS path in the build output.', 'stdout': combined_output}

        # Step 7: Return the successful result.
        print(f"Successfully found staged template path: {staged_path}")
        return {'status': "success", 'comment': f"Template '{template_name}' was built and staged.", 'staged_template_gcs_path': staged_path}

    except subprocess.CalledProcessError as cmd_err:
        return {'status': 'failed', 'comment': 'The maven build command failed.', 'stdout': cmd_err.stdout, 'stderr': ''}
    except Exception as err:
        return {'status': 'failed', 'comment': f'An unexpected error occurred: {str(err)}'}


# This is the flexible launcher with the corrected logic.
def submit_dataflow_template(
       job_name: str,
       input_params: str,
       template_params: str,
       gcp_project: str,
       region: str,
       gcs_staging_location: str,
       custom_gcs_path: str = ""
   ) -> dict:
    """
    Submits a job to Dataflow using either a classic or a Flex template.

    It validates user-provided parameters against the template definition unless a custom GCS path
    is provided, in which case validation is skipped. It then constructs and executes the
    appropriate `gcloud` command to launch the job.

    Args:
        job_name (str): The name to assign to the Dataflow job.
        input_params (str): A JSON string of the parameters to pass to the template.
        template_params (str): A JSON string containing the template's definition, including its GCS path and parameter requirements.
        gcp_project (str): The Google Cloud project ID where the job will run.
        region (str): The GCP region for the Dataflow job.
        gcs_staging_location (str): The GCS path for staging temporary files.
        custom_gcs_path (str, optional): A direct GCS path to a template file. If provided,
                                         parameter validation is skipped. Defaults to "".

    Returns:
        dict: A dictionary containing the submission status, stdout from the command, and a comment.
    """
    try:
        user_input_dict = json.loads(input_params)
        template_definition_dict = json.loads(template_params)

        # Handle cases where the template definition might be wrapped in a list.
        if isinstance(template_definition_dict, list) and len(template_definition_dict) > 0:
            template_definition_dict = template_definition_dict[0]
        
        template_gcs_path = custom_gcs_path if custom_gcs_path else template_definition_dict.get("template_gcs_path")
        
        if not template_gcs_path:
            return {
                'status': 'failed',
                'comment': 'Job could not be submitted because the "template_gcs_path" key was not found.'
            }
        
        # --- MODIFIED LOGIC ---
        # If a custom GCS path is NOT provided, validate parameters against the definition.
        # If a custom path IS provided, skip validation.
        if not custom_gcs_path:
            if "params" not in template_definition_dict:
                return {
                    'status': 'failed',
                    'comment': 'Job could not be submitted because the template definition is missing the "params" key.'
                }
            
            param_validation_result = validate_input_params(
                template_definition=template_definition_dict["params"],
                user_inputs=user_input_dict
            )
            if param_validation_result['validation_result'] != 'success':
                return {
                    'status': 'failed',
                    'comment': f'Job could not be submitted due to a parameter validation error: {param_validation_result["comment"]}'
                }

        delemeter = "###"
        
        parameters_str = f"{delemeter}".join([f"{key}={value}" for key, value in user_input_dict.items()])
        parameters_str = f"^{delemeter}^{parameters_str}"
        print(f"Final parameters string for gcloud command: {parameters_str}")
        is_flex = "/flex/" in template_gcs_path or template_definition_dict.get("type") == "FLEX"
        default_labels = "source=plumber"

        if is_flex:
            run_cmd = f'gcloud dataflow flex-template run {job_name} --project={gcp_project} --region={region} --template-file-gcs-location={template_gcs_path} --parameters "{parameters_str}" --additional-user-labels={default_labels}' 
        else:
            run_cmd = f'gcloud dataflow jobs run {job_name} --project={gcp_project} --region={region} --gcs-location={template_gcs_path} --parameters "{parameters_str}" --staging-location={gcs_staging_location} --additional-user-labels={default_labels}'
        
        print("Executing command:\n", run_cmd)
        cmd_run_status = subprocess.run(run_cmd, capture_output=True, text=True, check=True, shell=True)
        return {'status': "success", 'stdout': cmd_run_status.stdout, 'comment': 'Job Submitted Successfully'}
    except Exception as err:
        return {'status': 'failed', 'comment': f'An unexpected error occurred: {str(err)}'}
