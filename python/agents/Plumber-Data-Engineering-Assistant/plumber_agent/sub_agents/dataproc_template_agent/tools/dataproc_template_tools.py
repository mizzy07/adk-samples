import os
import subprocess
import shutil
import uuid
import io
import vertexai
from vertexai.generative_models import GenerativeModel
from PIL import Image
from dotenv import load_dotenv
from google.cloud import storage

from ..constants import *
from ..prompts import STTM_PARSING_INSTRUCTIONS
from ..utils import *

# IMPORTING ENVIRONMENT VARIABLES FROM .env FILE
load_dotenv()

# ENABLING VERTEX AI
vertexai.init(project=os.getenv('GOOGLE_CLOUD_PROJECT'), location=os.getenv('GOOGLE_CLOUD_LOCATION'))

def get_transformation_sql(gcs_url: str):
    try:
        # CHECK FOR A VALID GCS PATH
        if not gcs_url.startswith('gs://'):
            return {
                'status': 'failure - Invalid GCS Path',
                'sql': ''
            }
        
        bucket_name, file_path = gcs_url[5:].split('/', 1)
        file_type = file_path.split('/')[-1].split('.')[1]
        
        storage_client = storage.Client() # GCS STORAGE CLIENT

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)

        model = GenerativeModel(MODEL)

        if not blob.exists():
            return {
                'status': 'failure - Object not available at input path',
                'sql': ''
            }
        
        bytes = blob.download_as_bytes()
        
        if file_type == 'csv':
            file_content = bytes.decode('utf-8')
            response = model.generate_content([STTM_PARSING_INSTRUCTIONS, file_content])
        else:
            image = Image.open(io.BytesIO(bytes))
            response = model.generate_content([STTM_PARSING_INSTRUCTIONS, image])

        output_sql = response.text.replace('```sql', '').replace('```', '')

        return {
            'status': 'success',
            'sql': output_sql
        }
    except Exception as err:
        return {
            'status': f'failure - {str(err)}',
            'sql': ''
        }
    
# TOOL TO FETCH THE RELEAVANT DATAPROC TEMPLATE BASED ON USER INPUT
def get_dataproc_template(user_prompt: str, language: LANGUAGE_OPTIONS):
    try:
        # GETTING THE DATAPROC TEMPLATE REPO FROM GITHUB
        status = get_dataproc_template_repo()

        # IF REPO IS CLONED
        if status.get('repo_path'):
            # FIND ALL THE README FILES FROM THE TEMPLATE REPO
            if language == 'Python':
                readme_files = find_files(dir = f"{status['repo_path']}/python/dataproc_templates/", regex = 'README.md')
            elif language == 'Java':
                readme_files = find_files(dir = f"{status['repo_path']}/java/src/main/java/com/google/cloud/dataproc/templates", regex = 'README.md')
            
            # GET THE CORRECT TEMPLATE BASED ON THE USER PROMPT
            matched_template = get_dataproc_template_mapping(readme_files, user_prompt, language)
            return matched_template
        
    except Exception as err:
        return str(err)
    
# TOOL TO SUBMIT DATAPROC TEMPLATE BASED ON USER INPUT
def run_dataproc_template(
        language: LANGUAGE_OPTIONS,
        template_name: str,
        input_params: str,
        template_params: str,
        template_path: str,
        REGION: str, 
        GCS_STAGING_LOCATION: str, 
        JARS: str = '', 
        SUBNET: str = '',
        SPARK_PROPERTIES: str = '',
        TRANSFORMATION_SQL: str = ''
    ) -> dict:
    try:        
        temp_template_repo_path = ''
        run_id = str(uuid.uuid4()) # UNIQUE ID FOR A GIVEN JOB

        template_bin_path = eval(f'{language.upper()}_TEMPLATE_START_SCRIPT_BIN_PATH') # FOLDER LOCATION WHERE THE BIN FOLDER IS PRESENT TO RUN start.sh

        # FETCHING THE INPUT PARAMS
        input_params = eval(input_params)
        template_params = eval(template_params)

        # VALIDATING THE USER INPUT PARAMS AGAINST THE TEMPLATE PARAMS
        param_validation_result = validate_input_params(template_params, input_params)

        # IF VALIDATION FAILS - RETURN THE FAILURE JSON
        if param_validation_result['validation_result'] != 'success':
            return {
                'status': 'failed',
                'comment': f"Job could not be submitted due to error while parameters validations: {param_validation_result['comment']}"
            }

        # IF NEED TO INTEGRATE TRANSFORMATION LOGIC            
        if TRANSFORMATION_SQL:
            template_file_name = template_path.split('/')[-1] 
            template_dir = os.path.dirname(template_path)

            # CREATE THE TEMP TEMPLATE REPO WITH INTEGRATED TRANSFORMATION LOGIC
            temp_template_repo_path = update_dataproc_template(run_id, template_file_name, template_dir, TRANSFORMATION_SQL)

            # UPDATE THE TEMPLATE BIN PATH TO TEMP DIRECTORY BIN PATH
            template_bin_path = template_bin_path.replace(TEMPLATE_REPO_PATH, temp_template_repo_path)

        my_env = os.environ.copy() # FETCH ALL THE ENVIRONMENT VARIABLES

        # SETTING UP THE ENVIRONMENT VARIABLES
        my_env['GCP_PROJECT'] = os.getenv('GCP_PROJECT')
        my_env['REGION'] = REGION
        my_env['GCS_STAGING_LOCATION'] = GCS_STAGING_LOCATION
        if JARS:
            my_env['JARS'] = JARS
        if SUBNET:
            my_env['SUBNET'] = SUBNET
        if SPARK_PROPERTIES:
            my_env['SPARK_PROPERTIES'] = SPARK_PROPERTIES
        if os.getenv('PLUMBER_TARGET_SERVICE_ACCOUNT_ID'):
            my_env['OPT_SERVICE_ACCOUNT_NAME'] = (
                f" --impersonate-service-account={os.getenv('PLUMBER_TARGET_SERVICE_ACCOUNT_ID')} --labels=submitted_from=plumber"
            )
        else:
            my_env['OPT_SERVICE_ACCOUNT_NAME'] = "--labels=submitted_from=plumber"

        # DEFINING THE RUN COMMANDS FOR DATAPROC_TEMPLATE
        run_cmd = f'''./bin/start.sh -- --template={template_name}'''

        if language == 'Python':
            for param, value in input_params.items():
                run_cmd += f' --{param}="{value}"'
        elif language == 'Java':
            for param, value in input_params.items():
                run_cmd += f' --templateProperty {param}="{value}"'

        # TRIGGERING THE DATAPROC TEMPLATE
        output = subprocess.run(
            run_cmd, 
            capture_output = True, 
            text = True, 
            check = True, 
            shell = True, 
            env = my_env, 
            cwd = f'./{template_bin_path}'
        )

        # DELETE THE TEMP TEMPLATE DIR IF EXISTING
        if temp_template_repo_path:
            shutil.rmtree(f'./{TEMP_DIR_PATH}/{run_id}')
            
        return {
            'status': "success",
            'comment': f'Job Run Completed Successfully - {output.stdout}'
        }
    except subprocess.CalledProcessError as cmd_err:
        # DELETE THE TEMP TEMPLATE DIR IF EXISTING
        if temp_template_repo_path:
            shutil.rmtree(f'./{TEMP_DIR_PATH}/{run_id}')

        return {
            'status': 'failed',
            'comment': f'Job Failed - 1 {str(cmd_err.stderr)}',
        }
    except Exception as err:
        # DELETE THE TEMP TEMPLATE DIR IF EXISTING
        if temp_template_repo_path:
            shutil.rmtree(f'./{TEMP_DIR_PATH}/{run_id}')

        return {
            'status': 'failed',
            'comment': f'Job Failed - 2 {str(err)}',
            'run_cmd': run_cmd
        }