import git
import os
import json
import subprocess
import shutil
import vertexai
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv

from .prompts import *
from .constants import DATAPROC_TEMPLATE_GIT_URL, GIT_PATH, TEMP_DIR_PATH, TEMPLATE_REPO_PATH, LANGUAGE_OPTIONS

# IMPORTING ENVIRONMENT VARIABLES FROM .env FILE
load_dotenv()

# ENABLING VERTEX AI
vertexai.init(project=os.getenv('GOOGLE_CLOUD_PROJECT'), location=os.getenv('GOOGLE_CLOUD_LOCATION'))

# UTIL FUNCTION TO LIST THE FILES IN THE DIRECTORY BASED ON THE INPUT REGEX
def find_files(dir: str, regex: str) -> list:
    try:
        readmd_run_cmd = f'find {dir} -iname "{regex}" -not -iname "*Config*"'

        result = subprocess.run(readmd_run_cmd, capture_output = True, shell = True, text = True, check = True)
        files = result.stdout.splitlines()

        return files
    except Exception as err:
        return []

# UTIL FUNCTION TO LIST THE FILES IN THE DIRECTORY BASED ON THE INPUT REGEX
def get_dataproc_template_mapping(readme_files_list: list, user_prompt: str, language: LANGUAGE_OPTIONS) -> json:
    try:
        model = GenerativeModel('gemini-2.0-flash')

        # FIND THE CORRECT README FILE BASED ON THE USER INPUT
        response = model.generate_content(CORRECT_README_FILE_INSTRUCTION.format(
            user_prompt = user_prompt, 
            readme_files_list = readme_files_list
        ))
        correct_readme_file = response.text.replace('\n', '')
        readme_path = os.path.dirname(correct_readme_file)

        # IF NO TEMPLATES FOUND FOR A GIVEN SOURCE - RETURN {}
        if correct_readme_file == 'not found':
            return json.dumps({})

        if language == 'Python':
            # FETCH ALL THE TEMPLATES FROM THE README PATH
            template_files_list = find_files(dir = readme_path, regex = '*_to_*.py')        
        elif language == 'Java':
            # FETCH ALL THE TEMPLATES FROM THE README PATH
            template_files_list = find_files(dir = readme_path, regex = '*To*.java')

        # FIND THE CORRECT TEMPLATE FILE BASED ON THE USER INPUT
        response = model.generate_content(eval(f'CORRECT_{language.upper()}_TEMPLATE_FILE_INSTRUCTION').format(
            user_prompt = user_prompt, 
            template_files_list = template_files_list
        ))
        
        correct_template = response.text.replace('\n', '')
        
        # IF NO TEMPLATES FOUND FOR A GIVEN SOURCE TO TARGET - RETURN {}
        if correct_template == 'not found':
            return json.dumps({})
        
        # READING THE CONTENT OF README FILE
        with open(correct_readme_file, 'r') as readme_file:
            readme_content = readme_file.read()
        
        # FETCHING THE CORRECT DATAPROC TEMPLATE FROM THE README FILE
        instruction = SEARCH_DATAPROC_TEMPLATE_INSTRUCTION.format(
            user_prompt = user_prompt,
            readme_content = readme_content
        )
        response = model.generate_content(instruction)
        
        # CLEANING THE API RESPONSE
        response = response.text.replace('```json', '').replace('```', '')
        response = eval(response)
        response['template_path'] = correct_template
        
        return json.dumps(response)
    
    except Exception as err:
        return {}
    
# UTILITY FUNCTION TO CLONE DATAPROC TEMPLATE GIT REPO
def get_dataproc_template_repo() -> dict:
    try:
        # IF THE TEMPLATE ALREADY EXISTS, JUST PULL THE LATEST CHANGES TO REPO
        if os.path.exists(f'./{GIT_PATH}/dataproc_template'):
            repo = git.Repo(f'./{GIT_PATH}/dataproc_template' )
            origin = repo.remotes.origin
            origin.pull('main')
            return {
                'status': 'success - repo already exists, updated with latest changes',
                'repo_path': f'./{GIT_PATH}/dataproc_template'
            }
        # CLONE THE DATAPROC TEMPLATE REPO
        else:
            repo = git.Repo.clone_from(DATAPROC_TEMPLATE_GIT_URL, to_path = f'./{GIT_PATH}/dataproc_template' ,branch="main")
            return {
                'status': 'success - repo created',
                'repo_path': f'./{GIT_PATH}/dataproc_template'
            }
    except Exception as err:
        return {
            'status': f'error - {str(err)}'     
        }

# UTILITY FUNCTION TO VALIDATE THE USER INPUT PARAMS FOR A GIVEN TEMPLATE
def validate_input_params(template_params: dict, input_params: dict):
    try:
        required_template_params = template_params.get('required', [])
        optional_template_params = template_params.get('optional', [])
        
        all_params = required_template_params + optional_template_params
        input_params_name = input_params.keys()

        # CHECK FOR ANY INVALID PARAMETER
        invalid_input_params = list(set(input_params_name) - set(all_params))

        if invalid_input_params:
            return {
                "validation_result": "failed",
                "comment": "Invalid param passed"
            }

        # CHECK WHETHER ALL REQUIRED PARAMS ARE PASSED OR NOT
        all_required_params = set(required_template_params).issubset(set(input_params_name))

        if not all_required_params:
            return {
                "validation_result": "failed",
                "comment": "Missing required params"
            }
        
        return {
                "validation_result": "success",
                "comment": "Validation Passed"
            }
    except Exception as err:
        return {
                "validation_result": "failed",
                "comment": f"Error while running validation - {str(err)}"
            }

# UTILITY FUNCTION TO REPLICATE THE DATAPROC TEMPLATE DIRECTORY TO THE TEMP DIRECTORY WITH THE UPDATED TEMPLATE CODE
def update_dataproc_template(run_id: str, template_file_name: str, template_dir: str, transformation_sql: str) -> str:
    template_path = f'{template_dir}/{template_file_name}' # PATH OF THE TEMPLATE TO BE RUN

    temp_template_repo_path = f'./{TEMP_DIR_PATH}/{run_id}/dataproc_template' # PATH OF THE TEMP FOLDER FOR THE GIVEN JOB RUN WITH TRANSFORMATION
    temp_template_path = template_path.replace(f'./{TEMPLATE_REPO_PATH}', temp_template_repo_path)  # PATH OF THE TEMPLATE TO BE RUN IN THE TEMP FOLDER

    # COPY THE ORIGINAL TEMPLATE TO THE TEMP FOLDER
    shutil.copytree(f'./{TEMPLATE_REPO_PATH}', temp_template_repo_path, dirs_exist_ok=True)

    # READ THE ORIGINAL TEMPLATE
    with open(template_path, 'r') as f:
        original_template_code = f.read()

    prompt = TRANSFORMATION_CODE_GENERATION_PROMPT.format(
        original_template_code = original_template_code,
        transformation_sql = transformation_sql
    )

    model = GenerativeModel('gemini-2.0-flash')
    response = model.generate_content(prompt)
    new_template_code = response.text

    new_template_code = new_template_code.strip().replace("```python", "").replace("```java", "").replace("```", "").strip()  # CODE WITH THE ADDED LOGIC FOR TRANSFORMATION
    
    # WRITING THE UPDATED TEMPLATE CODE TO THE TEMP DIRECTORY
    with open(temp_template_path, 'w') as f:
        f.write(new_template_code)

    return temp_template_repo_path